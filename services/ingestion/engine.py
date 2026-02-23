"""
RAG System for document processing and querying
"""
import os
import time as time_module
import math
import logging
import traceback
from typing import List, Dict, Optional, Callable, Any
import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from shared.utils.local_embeddings import LocalHashEmbeddings
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document
import requests
from shared.utils.tokenizer import TokenTextSplitter
from shared.utils.s3_service import S3Service
# Accuracy Improvements: Recursive Chunking and Reranking
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter
    except ImportError:
        RecursiveCharacterTextSplitter = None

try:
    from flashrank import Ranker, RerankRequest
except ImportError:
    Ranker = None
    RerankRequest = None
from vectorstores.vector_store_factory import VectorStoreFactory
from shared.config.settings import ARISConfig

load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class IngestionEngine:
    def __init__(self, use_cerebras=False, metrics_collector=None, 
                 embedding_model=None,
                 openai_model=None,
                 cerebras_model=None,
                 vector_store_type="opensearch",
                 opensearch_domain=None,
                 opensearch_index=None,
                 chunk_size=None,
                 chunk_overlap=None):
        self.use_cerebras = use_cerebras
        
        # Store model selections - use ARISConfig defaults if not provided
        if embedding_model is None:
            embedding_model = ARISConfig.EMBEDDING_MODEL
        if openai_model is None:
            openai_model = ARISConfig.OPENAI_MODEL
        if cerebras_model is None:
            cerebras_model = ARISConfig.CEREBRAS_MODEL
        
        self.embedding_model = embedding_model
        self.openai_model = openai_model
        self.cerebras_model = cerebras_model
        
        # Vector store configuration - REQUIRE OpenSearch
        self.vector_store_type = vector_store_type.lower()
        if self.vector_store_type != 'opensearch':
            raise ValueError(
                f"Vector store type must be 'opensearch'. Got '{vector_store_type}'. "
                f"Please set VECTOR_STORE_TYPE=opensearch and configure AWS_OPENSEARCH_DOMAIN."
            )
        
        # Validate OpenSearch domain - REQUIRED, no fallback
        if not opensearch_domain or len(str(opensearch_domain).strip()) < 3:
            # Use default from ARISConfig if not provided
            opensearch_domain = ARISConfig.AWS_OPENSEARCH_DOMAIN
            if not opensearch_domain or len(str(opensearch_domain).strip()) < 3:
                raise ValueError(
                    f"OpenSearch domain is required. Please set AWS_OPENSEARCH_DOMAIN in .env file. "
                    f"Got: '{opensearch_domain}'"
                )
        
        self.opensearch_domain = str(opensearch_domain).strip()
        self.opensearch_index = opensearch_index or ARISConfig.AWS_OPENSEARCH_INDEX
        
        # Active document filter (set by UI to restrict queries to selected docs)
        self.active_sources: Optional[List[str]] = None
        
        # Chunking configuration - use defaults optimized for large documents if not provided
        if chunk_size is None:
            chunk_size = ARISConfig.DEFAULT_CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = ARISConfig.DEFAULT_CHUNK_OVERLAP
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Use selected embedding model (use instance variable after defaults applied)
        if os.getenv('OPENAI_API_KEY'):
            self.embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
        else:
            self.embeddings = LocalHashEmbeddings(model_name=self.embedding_model)
        self.vectorstore = None
        # Use token-aware text splitter with configurable chunking
        # Accuracy Upgrade: Use RecursiveCharacterTextSplitter for context preservation
        # This splits by paragraphs/headers first, then falls back to tokens
        if RecursiveCharacterTextSplitter:
            try:
                self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                    model_name=embedding_model,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=["\n\n", "\n", " ", ""],
                    disallowed_special=(),  # Allow special tokens in documents
                    add_start_index=True    # CRITICAL: Track offsets for page mapping
                )
                # Keep legacy splitter for pure token counting if needed
                self._legacy_splitter = TokenTextSplitter(
                    chunk_size=chunk_size, 
                    chunk_overlap=chunk_overlap, 
                    model_name=embedding_model
                )
            except Exception as e:
                logger.warning(f"Could not init RecursiveCharacterTextSplitter: {e}, using legacy")
                self.text_splitter = TokenTextSplitter(
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    model_name=embedding_model
                )
        else:
            # Fallback to legacy splitter if RecursiveCharacterTextSplitter not available
            logger.warning("RecursiveCharacterTextSplitter not available, using legacy TokenTextSplitter")
            self.text_splitter = TokenTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                model_name=embedding_model
            )
        
        # Metrics collector
        self.metrics_collector = metrics_collector
        if self.metrics_collector is None:
            # Create a local one if not provided
            from metrics.metrics_collector import MetricsCollector
            self.metrics_collector = MetricsCollector()
            
        # Initialize S3 Service
        self.s3_service = S3Service()
            
        # Accuracy Upgrade: Initialize FlashRank Reranker
        self.ranker = None
        if Ranker:
            try:
                # Use a high-quality but fast model
                self.ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="models/cache")
                logger.info("✅ FlashRank Reranker initialized (ms-marco-MiniLM-L-12-v2)")
            except Exception as e:
                logger.warning(f"⚠️ FlashRank init failed: {e}")
        
        # Document tracking for incremental updates
        self.document_index: Dict[str, List[int]] = {}  # {doc_id: [chunk_indices]}
        self.total_tokens = 0
        
        # Document-to-index mapping for per-document OpenSearch indexes
        self.document_index_map: Dict[str, str] = {}  # document_name -> index_name
        self.document_index_map_path = os.path.join(
            ARISConfig.VECTORSTORE_PATH,
            "document_index_map.json"
        )
        self._load_document_index_map()
        
        # Metrics collector is already initialized above (lines 142-147)
    
    def _load_document_index_map(self):
        """Load document-to-index mapping from file."""
        import json
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if os.path.exists(self.document_index_map_path):
            try:
                with open(self.document_index_map_path, 'r') as f:
                    self.document_index_map = json.load(f)
                    logger.info(f"Loaded {len(self.document_index_map)} document-index mappings")
            except Exception as e:
                logger.warning(f"Could not load document index map: {e}")
    
    def _save_document_index_map(self):
        """Save document-to-index mapping to file."""
        import json
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        os.makedirs(os.path.dirname(self.document_index_map_path), exist_ok=True)
        try:
            with open(self.document_index_map_path, 'w') as f:
                json.dump(self.document_index_map, f, indent=2)
            logger.info(f"Saved {len(self.document_index_map)} document-index mappings")
        except Exception as e:
            logger.error(f"Could not save document index map: {e}")


    ######################################################################################################################
    # CRITICAL FUNCTION: This is where we assign page numbers to chunks based on original metadata from DocumentProcessor.
    ######################################################################################################################
    def _assign_metadata_to_chunks(self, chunks: List[Document], original_metadata: Dict) -> List[Document]:
        """
        Assign accurate page numbers + citation metadata to chunks.

        UPDATED (Option 02):
        - Prefer compact page->char-range mapping: original_metadata['page_char_ranges']
        to compute page by maximum overlap using chunk global start/end chars.
        - Compute chunk-level global start_char/end_char even for "pre_assigned" page-level texts
        (page_start_char + chunk.start_index).
        - Fall back to page_blocks overlap only if page_char_ranges not available.
        - Final fallback: single-page / unknown page.
        """
        page_blocks = original_metadata.get('page_blocks', [])
        page_char_ranges = original_metadata.get('page_char_ranges', [])

        # Build image page mapping from image references if available
        image_page_map = {}  # Map image_index -> page
        image_refs = original_metadata.get('image_refs', [])
        if not image_refs:
            # Try to extract from page_blocks that have image metadata
            for block in page_blocks:
                if isinstance(block, dict) and block.get('type') == 'image':
                    img_idx = block.get('image_index')
                    img_page = block.get('page') or block.get('image_page')
                    if img_idx is not None and img_page is not None:
                        image_page_map[img_idx] = img_page

        # If we have neither blocks nor ranges, we cannot do deterministic mapping.
        if not page_blocks and not page_char_ranges:
            fallback_page = original_metadata.get('page') or original_metadata.get('source_page') or 1
            total_pages = original_metadata.get('pages', 1) or 1
            for chunk in chunks:
                if 'page' not in chunk.metadata or not chunk.metadata['page']:
                    chunk.metadata['page'] = fallback_page
                if 'source_page' not in chunk.metadata:
                    chunk.metadata['source_page'] = fallback_page
                if 'page_extraction_method' not in chunk.metadata:
                    chunk.metadata['page_extraction_method'] = 'fallback_no_blocks'
                if 'page_confidence' not in chunk.metadata:
                    chunk.metadata['page_confidence'] = 0.9 if total_pages <= 1 else 0.3
            return chunks

        # If we don't have page_char_ranges but we do have page_blocks, build a compact range map on the fly.
        # (This keeps the logic stable even if DocumentProcessor didn’t attach the ranges.)
        if not page_char_ranges and page_blocks:
            tmp = {}
            for b in page_blocks:
                if not isinstance(b, dict):
                    continue
                p = b.get('page')
                if p is None:
                    continue
                s = b.get('start_char', 0)
                e = b.get('end_char', 0)
                if p not in tmp:
                    tmp[p] = [s, e]
                else:
                    tmp[p][0] = min(tmp[p][0], s)
                    tmp[p][1] = max(tmp[p][1], e)
            page_char_ranges = [{"page": p, "start_char": se[0], "end_char": se[1]} for p, se in sorted(tmp.items())]

        # Optimize blocks search only if we actually use page_blocks
        use_blocks = bool(page_blocks) and not bool(page_char_ranges)
        if use_blocks:
            page_blocks = sorted(page_blocks, key=lambda x: x.get('start_char', 0))
            block_idx = 0
            num_blocks = len(page_blocks)

        for chunk in chunks:
            # ---------------------------
            # PRIORITY 1: image_index -> image_page_map
            # ---------------------------
            chunk_image_idx = chunk.metadata.get('image_index')
            if chunk_image_idx is not None and chunk_image_idx in image_page_map:
                img_page = image_page_map[chunk_image_idx]
                chunk.metadata['page'] = img_page
                chunk.metadata['source_page'] = img_page
                chunk.metadata['image_page'] = img_page
                chunk.metadata['has_image'] = True
                chunk.metadata['page_extraction_method'] = 'image_metadata'
                chunk.metadata['page_confidence'] = 0.95
                continue

            # ---------------------------
            # PRIORITY 2: image_ref
            # ---------------------------
            image_ref = chunk.metadata.get('image_ref')
            if image_ref and isinstance(image_ref, dict):
                img_page = image_ref.get('page') or image_ref.get('image_page')
                if img_page:
                    chunk.metadata['page'] = img_page
                    chunk.metadata['source_page'] = img_page
                    chunk.metadata['image_page'] = img_page
                    chunk.metadata['has_image'] = True
                    chunk.metadata['page_extraction_method'] = 'image_ref'
                    chunk.metadata['page_confidence'] = 0.9
                    continue

            # ---------------------------
            # Compute chunk global start/end chars (CRITICAL for correct citations)
            # ---------------------------
            start_index = chunk.metadata.get('start_index', 0)
            chunk_length = len(chunk.page_content) if hasattr(chunk, 'page_content') else 0
            local_end_index = start_index + chunk_length

            # If the chunk comes from page-level text, DocumentProcessor sets page_start_char (and often start_char=end_char as page bounds).
            # If it comes from full-doc text, these are typically absent -> base=0.
            page_base = (
                chunk.metadata.get('page_start_char')
                if chunk.metadata.get('page_start_char') is not None
                else chunk.metadata.get('start_char')  # in page-level mode this was page start in Step 4.2
                if chunk.metadata.get('start_char') is not None and chunk.metadata.get('end_char') is not None and chunk.metadata.get('end_char') >= chunk.metadata.get('start_char')
                else 0
            ) or 0

            global_start = int(page_base) + int(start_index)
            global_end = global_start + int(chunk_length)

            chunk.metadata['start_char'] = global_start
            chunk.metadata['end_char'] = global_end

            # Keep original pre-assigned page if present (we will validate/override deterministically below)
            pre_assigned_page = chunk.metadata.get('page') or chunk.metadata.get('source_page')

            # ---------------------------
            # Option 02: page_char_ranges overlap (preferred)
            # ---------------------------
            if page_char_ranges:
                best_page = pre_assigned_page or 1
                max_overlap_chars = 0

                for r in page_char_ranges:
                    rs = r.get('start_char', 0)
                    re = r.get('end_char', 0)
                    # overlap between [global_start, global_end) and [rs, re)
                    overlap = max(0, min(global_end, re) - max(global_start, rs))
                    if overlap > max_overlap_chars:
                        max_overlap_chars = overlap
                        best_page = r.get('page', best_page)

                chunk.metadata['page'] = best_page
                if 'source_page' not in chunk.metadata:
                    chunk.metadata['source_page'] = best_page

                chunk.metadata['page_extraction_method'] = 'char_range_ingestion'
                chunk.metadata['page_confidence'] = 0.98 if max_overlap_chars > 0 else 0.75
                continue

            # ---------------------------
            # Fallback: page_blocks maximum overlap (only if ranges not available)
            # ---------------------------
            if use_blocks:
                best_page = 1
                max_overlap_chars = 0
                temp_idx = block_idx

                while temp_idx < num_blocks:
                    block = page_blocks[temp_idx]
                    block_start = block.get('start_char', 0)
                    block_end = block.get('end_char', 0)

                    if block_start >= global_end:
                        break

                    overlap_start = max(global_start, block_start)
                    overlap_end = min(global_end, block_end)
                    overlap_chars = max(0, overlap_end - overlap_start)

                    if overlap_chars > max_overlap_chars:
                        max_overlap_chars = overlap_chars
                        best_page = block.get('page', 1)

                    temp_idx += 1

                if max_overlap_chars == 0:
                    min_distance = float('inf')
                    nearest_page = 1
                    for blk in page_blocks:
                        blk_start = blk.get('start_char', 0)
                        blk_end = blk.get('end_char', 0)
                        if blk_start <= global_start <= blk_end:
                            nearest_page = blk.get('page', 1)
                            min_distance = 0
                            break
                        dist = min(abs(global_start - blk_start), abs(global_start - blk_end))
                        if dist < min_distance:
                            min_distance = dist
                            nearest_page = blk.get('page', 1)
                    chunk_page = nearest_page
                else:
                    chunk_page = best_page

                while block_idx < num_blocks - 1:
                    next_block_end = page_blocks[block_idx].get('end_char', 0)
                    if next_block_end < global_start:
                        block_idx += 1
                    else:
                        break

                chunk.metadata['page'] = chunk_page
                if 'source_page' not in chunk.metadata:
                    chunk.metadata['source_page'] = chunk_page

                chunk.metadata['page_extraction_method'] = 'char_position_ingestion'
                chunk.metadata['page_confidence'] = 0.95 if max_overlap_chars > 0 else 0.7
                continue

            # ---------------------------
            # Last resort: trust pre-assigned if present, otherwise page 1
            # ---------------------------
            if pre_assigned_page:
                chunk.metadata['page'] = pre_assigned_page
                chunk.metadata.setdefault('source_page', pre_assigned_page)
                chunk.metadata.setdefault('page_extraction_method', 'pre_assigned')
                chunk.metadata.setdefault('page_confidence', 0.85)
            else:
                chunk.metadata['page'] = 1
                chunk.metadata.setdefault('source_page', 1)
                chunk.metadata.setdefault('page_extraction_method', 'fallback_no_blocks')
                chunk.metadata.setdefault('page_confidence', 0.3)

        return chunks

    ######################################################################################################################
    ######################################################################################################################

    # def _assign_metadata_to_chunks(self, chunks: List[Document], original_metadata: Dict) -> List[Document]:
    #     """
    #     Assigns accurate page numbers and other metadata to chunks.
    #     Uses page_blocks from original_metadata to find the correct page for each chunk offset.
    #     Optimized for large documents with 100,000+ blocks.
        
    #     ENHANCED: Prioritizes image metadata for image-transcribed content to ensure correct page citations.
    #     """

    #     page_char_ranges = original_metadata.get("page_char_ranges", [])
    #     page_blocks = original_metadata.get('page_blocks', [])
        
    #     # Build image page mapping from image references if available
    #     image_page_map = {}  # Map image_index -> page
    #     image_refs = original_metadata.get('image_refs', [])
    #     if not image_refs:
    #         # Try to extract from page_blocks that have image metadata
    #         for block in page_blocks:
    #             if isinstance(block, dict) and block.get('type') == 'image':
    #                 img_idx = block.get('image_index')
    #                 img_page = block.get('page') or block.get('image_page')
    #                 if img_idx is not None and img_page is not None:
    #                     image_page_map[img_idx] = img_page
        
    #     if not page_blocks and not page_char_ranges:
    #         # If no blocks, use fallback page for all chunks and set citation metadata
    #         fallback_page = original_metadata.get('page') or original_metadata.get('source_page') or 1
    #         total_pages = original_metadata.get('pages', 1) or 1
    #         for chunk in chunks:
    #             if 'page' not in chunk.metadata or not chunk.metadata['page']:
    #                 chunk.metadata['page'] = fallback_page
    #             if 'source_page' not in chunk.metadata:
    #                 chunk.metadata['source_page'] = fallback_page
    #             if 'page_extraction_method' not in chunk.metadata:
    #                 chunk.metadata['page_extraction_method'] = 'fallback_no_blocks'
    #             if 'page_confidence' not in chunk.metadata:
    #                 # Higher confidence for single-page docs (page 1 is guaranteed correct)
    #                 chunk.metadata['page_confidence'] = 0.9 if total_pages <= 1 else 0.3
    #         return chunks
            
    #     # Optimization: Sort blocks by start_char for faster lookup
    #     # Some blocks might be unsorted depending on the parser
    #     page_blocks = sorted(page_blocks, key=lambda x: x.get('start_char', 0))
        
    #     # Use a pointer to avoid O(N*M) - since both chunks and blocks are mostly sorted by offset
    #     block_idx = 0
    #     num_blocks = len(page_blocks)
        
    #     for chunk in chunks:
    #         # PRIORITY 1: Check if chunk has image metadata - use image's page number
    #         chunk_image_idx = chunk.metadata.get('image_index')
    #         if chunk_image_idx is not None and chunk_image_idx in image_page_map:
    #             # This chunk is from an image - use image's page number
    #             img_page = image_page_map[chunk_image_idx]
    #             chunk.metadata['page'] = img_page
    #             chunk.metadata['source_page'] = img_page
    #             chunk.metadata['image_page'] = img_page
    #             chunk.metadata['has_image'] = True
    #             chunk.metadata['page_extraction_method'] = 'image_metadata'
    #             chunk.metadata['page_confidence'] = 0.95
    #             continue
            
    #         # PRIORITY 2: Check for image_ref in chunk metadata
    #         image_ref = chunk.metadata.get('image_ref')
    #         if image_ref and isinstance(image_ref, dict):
    #             img_page = image_ref.get('page') or image_ref.get('image_page')
    #             if img_page:
    #                 chunk.metadata['page'] = img_page
    #                 chunk.metadata['source_page'] = img_page
    #                 chunk.metadata['image_page'] = img_page
    #                 chunk.metadata['has_image'] = True
    #                 chunk.metadata['page_extraction_method'] = 'image_ref'
    #                 chunk.metadata['page_confidence'] = 0.9
    #                 continue
            
    #         # PRIORITY 3: If chunk already has a valid page number (from DocumentProcessor's page-level processing), use it
    #         if 'page' in chunk.metadata and chunk.metadata['page']:
    #             # Ensure source_page is also set
    #             if 'source_page' not in chunk.metadata:
    #                 chunk.metadata['source_page'] = chunk.metadata['page']
    #             if 'page_extraction_method' not in chunk.metadata:
    #                 chunk.metadata['page_extraction_method'] = 'pre_assigned'
    #             if 'page_confidence' not in chunk.metadata:
    #                 chunk.metadata['page_confidence'] = 0.85
    #             continue
                
    #         # Get start_index from LangChain splitter - maps to character position
    #         start_index = chunk.metadata.get('start_index', 0)
    #         chunk_length = len(chunk.page_content) if hasattr(chunk, 'page_content') else 0
    #         end_index = start_index + chunk_length
            
    #         # IMPROVED: Also set start_char and end_char for retrieval compatibility
    #         chunk.metadata['start_char'] = start_index
    #         chunk.metadata['end_char'] = end_index
            
    #         # Accuracy Upgrade: Use Maximum Overlap for Page Assignment
    #         # Instead of just checking where the chunk starts, we calculate which page 
    #         # contains the MOST characters from this chunk.
            
    #         best_page = 1
    #         max_overlap_chars = 0
            
    #         # Check blocks starting from current position
    #         # We might need to check multiple blocks if the chunk spans pages
    #         temp_idx = block_idx
            
    #         while temp_idx < num_blocks:
    #             block = page_blocks[temp_idx]
    #             block_start = block.get('start_char', 0)
    #             block_end = block.get('end_char', 0)
                
    #             # If block starts after chunk ends, we can stop searching
    #             if block_start >= end_index:
    #                 break
                
    #             # Calculate overlap
    #             overlap_start = max(start_index, block_start)
    #             overlap_end = min(end_index, block_end)
    #             overlap_chars = max(0, overlap_end - overlap_start)
                
    #             if overlap_chars > max_overlap_chars:
    #                 max_overlap_chars = overlap_chars
    #                 best_page = block.get('page', 1)
                
    #             temp_idx += 1
            
    #         # If no overlap found (rare, e.g. gaps in blocks), find the nearest block
    #         if max_overlap_chars == 0:
    #             # Find the block whose character range is closest to this chunk's start
    #             min_distance = float('inf')
    #             nearest_page = 1
    #             for blk in page_blocks:
    #                 blk_start = blk.get('start_char', 0)
    #                 blk_end = blk.get('end_char', 0)
    #                 # Distance: 0 if chunk start is inside block, else min gap
    #                 if blk_start <= start_index <= blk_end:
    #                     nearest_page = blk.get('page', 1)
    #                     min_distance = 0
    #                     break
    #                 dist = min(abs(start_index - blk_start), abs(start_index - blk_end))
    #                 if dist < min_distance:
    #                     min_distance = dist
    #                     nearest_page = blk.get('page', 1)
    #             chunk_page = nearest_page
    #         else:
    #             chunk_page = best_page
            
    #         # Advance block_idx pointer to keep it close to current chunk position
    #         # This keeps the search window efficient for sorted chunks
    #         while block_idx < num_blocks - 1:
    #             next_block_end = page_blocks[block_idx].get('end_char', 0)
    #             if next_block_end < start_index:
    #                 block_idx += 1
    #             else:
    #                 break
            
    #         chunk.metadata['page'] = chunk_page
    #         # Also set source_page for consistency if missing
    #         if 'source_page' not in chunk.metadata:
    #             chunk.metadata['source_page'] = chunk_page
            
    #         # Store page extraction method and confidence for debugging
    #         chunk.metadata['page_extraction_method'] = 'char_position_ingestion'
    #         # High confidence if overlap was found, lower if nearest-block fallback was used
    #         chunk.metadata['page_confidence'] = 0.95 if max_overlap_chars > 0 else 0.7
                
    #     return chunks
    
    def process_documents(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None, index_name: Optional[str] = None):
        """Process and chunk documents, then create vector store"""
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Handle index override if provided (Fix #9)
        if index_name and index_name != self.opensearch_index:
            logger.info(f"IngestionEngine: Overriding OpenSearch index: {self.opensearch_index} -> {index_name}")
            self.opensearch_index = index_name
            
            # Re-initialize vectorstore for the new index if using OpenSearch
            if self.vector_store_type == "opensearch":
                from vectorstores.opensearch_store import OpenSearchVectorStore
                try:
                    self.vectorstore = OpenSearchVectorStore(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain,
                        index_name=self.opensearch_index,
                        region=getattr(self, 'region', None)
                    )
                    logger.info(f"✅ IngestionEngine: Re-initialized OpenSearchVectorStore with index: {index_name}")
                except Exception as e:
                    logger.error(f"❌ IngestionEngine: Failed to re-initialize OpenSearchVectorStore: {e}")
                    # Continue anyway as it might be a valid state or using defaults
            
            # Update mapping for each document in this batch
            if metadatas:
                processed_sources = set()
                for meta in metadatas:
                    source = meta.get('source')
                    if source and source not in processed_sources:
                        self.document_index_map[source] = index_name
                        processed_sources.add(source)
                
                # Save the mapping immediately
                if processed_sources:
                    self._save_document_index_map()
        
        # Validate inputs
        if not texts:
            return 0
        
        # Create Document objects
        # IMPORTANT: Convert all text to plain strings BEFORE threading to avoid PyMuPDF NoSessionContext errors
        documents = []
        for i, text in enumerate(texts):
            # Safely get metadata - handle case where metadatas list is shorter than texts
            if metadatas and i < len(metadatas):
                metadata = metadatas[i] if isinstance(metadatas[i], dict) else {}
            else:
                metadata = {}
            
            # Ensure text is a string and not None
            # Convert to string BEFORE threading to avoid PyMuPDF NoSessionContext errors
            if text is None:
                text = ""
            elif not isinstance(text, str):
                try:
                    # Try to convert to string - this might fail with NoSessionContext if text is a PyMuPDF object
                    text = str(text)
                except Exception as e:
                    error_str = str(e) if str(e) else type(e).__name__
                    if "NoSessionContext" in error_str or "NoSessionContext" in type(e).__name__:
                        logger.warning(f"Text conversion failed with NoSessionContext. Attempting safe extraction...")
                        # Try to get text content safely without accessing PyMuPDF internals
                        try:
                            # If it's a ParsedDocument or similar, try to get text attribute
                            if hasattr(text, 'text'):
                                text = str(text.text) if text.text else ""
                            elif hasattr(text, 'page_content'):
                                text = str(text.page_content) if text.page_content else ""
                            else:
                                # Last resort: try repr and extract if possible
                                text = repr(text)
                                # If repr contains quotes, try to extract the content
                                if text.startswith("'") and text.endswith("'"):
                                    text = text[1:-1]
                                elif text.startswith('"') and text.endswith('"'):
                                    text = text[1:-1]
                        except Exception as e2:
                            logger.error(f"Failed to safely extract text: {str(e2)}")
                            text = ""  # Fallback to empty string
                    else:
                        # Re-raise if it's not a NoSessionContext error
                        raise
            
            # Skip empty documents
            if not text.strip():
                continue
            
            documents.append(Document(page_content=text, metadata=metadata))
        
        # Validate we have documents to process
        if not documents:
            return 0
        
        # Split documents into chunks using token-aware splitter
        # IMPORTANT: Extract all text content BEFORE threading to avoid PyMuPDF NoSessionContext errors
        total_text_length = sum(len(doc.page_content) if hasattr(doc, 'page_content') and isinstance(doc.page_content, str) else 0 for doc in documents)
        logger.info(f"[STEP 3.1] RAGSystem: Starting chunking for {len(documents)} document(s), total text length: {total_text_length:,} chars")
        if progress_callback:
            progress_callback('chunking', 0.1, detailed_message="Starting chunking process...")
        
        # Ensure all document text is extracted as plain strings before chunking
        # This prevents downstream components from interacting with parser-specific objects
        safe_documents = []
        for doc in documents:
            try:
                # Extract text content as plain string
                text_content = doc.page_content if hasattr(doc, 'page_content') else ""
                if not isinstance(text_content, str):
                    text_content = str(text_content)
                
                # Create a new Document with plain string content
                safe_doc = Document(page_content=text_content, metadata=doc.metadata if hasattr(doc, 'metadata') else {})
                safe_documents.append(safe_doc)
            except Exception as e:
                error_str = str(e) if str(e) else type(e).__name__
                if "NoSessionContext" in error_str:
                    logger.warning(f"Skipping document due to NoSessionContext error during text extraction: {error_str}")
                    continue
                else:
                    # For other errors, try to continue with empty text
                    safe_doc = Document(page_content="", metadata=doc.metadata if hasattr(doc, 'metadata') else {})
                    safe_documents.append(safe_doc)
        
        if not safe_documents:
            raise ValueError("No valid documents to chunk after text extraction. This may be due to parser session context issues.")
        
        # Adaptive chunking: upscale chunk size for very large documents when user selected small chunks
        splitter_to_use = self.text_splitter
        adaptive_chunk_size = None
        adaptive_chunk_overlap = None
        estimated_tokens = 0
        try:
            estimated_tokens = sum(self.count_tokens(doc.page_content) for doc in safe_documents)
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            # Fallback estimate using character count
            estimated_tokens = total_text_length // 4
        
        estimated_chunks = math.ceil(estimated_tokens / max(self.chunk_size, 1))
        logger.info(
            f"[STEP 3.1.1] RAGSystem: Chunking configuration - requested chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, estimated tokens≈{estimated_tokens:,}, "
            f"estimated chunks≈{estimated_chunks}"
        )
        
        MAX_CHUNKS_BEFORE_ADAPT = 200
        MIN_ADAPTIVE_CHUNK_SIZE = 512
        MAX_ADAPTIVE_CHUNK_SIZE = 1536
        
        if (
            estimated_chunks > MAX_CHUNKS_BEFORE_ADAPT
            and self.chunk_size <= MIN_ADAPTIVE_CHUNK_SIZE
        ):
            target_chunk_size = math.ceil(estimated_tokens / MAX_CHUNKS_BEFORE_ADAPT)
            adaptive_chunk_size = min(
                max(target_chunk_size, MIN_ADAPTIVE_CHUNK_SIZE, self.chunk_size),
                MAX_ADAPTIVE_CHUNK_SIZE
            )
            
            if adaptive_chunk_size > self.chunk_size:
                overlap_ratio = self.chunk_overlap / max(self.chunk_size, 1)
                adaptive_chunk_overlap = int(adaptive_chunk_size * overlap_ratio)
                adaptive_chunk_overlap = min(adaptive_chunk_overlap, adaptive_chunk_size // 2)
                
                if RecursiveCharacterTextSplitter:
                    try:
                        splitter_to_use = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                            model_name=self.embedding_model,
                            chunk_size=adaptive_chunk_size,
                            chunk_overlap=adaptive_chunk_overlap,
                            separators=self._get_language_separators(metadatas),  # Language-aware separators
                            disallowed_special=(),  # Allow special tokens in documents
                            add_start_index=True    # CRITICAL: Track offsets for page mapping
                        )
                    except Exception:
                        splitter_to_use = TokenTextSplitter(
                            chunk_size=adaptive_chunk_size,
                            chunk_overlap=adaptive_chunk_overlap,
                            model_name=self.embedding_model
                        )
                else:
                    splitter_to_use = TokenTextSplitter(
                        chunk_size=adaptive_chunk_size,
                        chunk_overlap=adaptive_chunk_overlap,
                        model_name=self.embedding_model
                    )
                
                logger.info(
                    f"[STEP 3.1.2] RAGSystem: Adaptive chunking enabled for large document - "
                    f"chunk_size {self.chunk_size} -> {adaptive_chunk_size}, "
                    f"overlap {self.chunk_overlap} -> {adaptive_chunk_overlap}, "
                    f"document tokens≈{estimated_tokens:,}"
                )
                if progress_callback:
                    progress_callback(
                        'chunking',
                        0.12,
                        detailed_message=(
                            f"Large document detected (~{estimated_tokens:,} tokens). "
                            f"Auto-adjusted chunk size to {adaptive_chunk_size} tokens "
                            f"for better performance."
                        )
                    )
        
        # Perform chunking synchronously (avoids Streamlit NoSessionContext errors)
        def splitter_progress_callback(status, progress, **kwargs):
            if progress_callback:
                progress_callback(status, progress, **kwargs)
        
        # Track chunking performance
        chunking_start_time = time_module.time()
        chunking_timeout_warning = 600  # 10 minutes in seconds
        
        try:
            logger.info(f"[STEP 3.1.3] RAGSystem: Starting chunking operation (timeout warning at {chunking_timeout_warning}s)...")
            chunks = splitter_to_use.split_documents(
                safe_documents
            )
            if chunks is None:
                chunks = []
            
            # Log chunking performance
            chunking_end_time = time_module.time()
            chunking_duration = chunking_end_time - chunking_start_time
            
            if chunking_duration > chunking_timeout_warning:
                logger.warning(
                    f"⚠️ [STEP 3.1] RAGSystem: Chunking took {chunking_duration:.1f}s ({chunking_duration/60:.1f} minutes) - "
                    f"this is longer than expected. Consider using larger chunk sizes for very large documents."
                )
            else:
                logger.info(
                    f"[STEP 3.1] RAGSystem: Chunking completed in {chunking_duration:.1f}s ({chunking_duration/60:.1f} minutes)"
                )
            
            # [Fix #10] Accuracy Upgrade: Assign accurate page numbers to chunks based on character offsets
            # This ensures citations match original document pages perfectly
            processed_chunks = []
            for doc in documents:
                # Group chunks by document to look up their original metadata
                doc_source = doc.metadata.get('source')
                doc_chunks = [c for c in chunks if c.metadata.get('source') == doc_source]
                
                # Assign metadata (especially page numbers)
                mapped_chunks = self._assign_metadata_to_chunks(doc_chunks, doc.metadata)
                processed_chunks.extend(mapped_chunks)
            
            # Use the processed chunks from now on
            if processed_chunks:
                chunks = processed_chunks
            
            # Log performance metrics
            if len(chunks) > 0:
                chunks_per_sec = len(chunks) / chunking_duration if chunking_duration > 0 else 0
                logger.info(
                    f"[STEP 3.1] RAGSystem: Chunking performance - {chunks_per_sec:.2f} chunks/sec, "
                    f"{estimated_tokens/chunking_duration:.0f} tokens/sec"
                )
        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            if not error_msg or error_msg.strip() == "":
                error_msg = f"Unknown error ({type(e).__name__})"
            if "NoSessionContext" in error_msg:
                error_msg = (
                    "Streamlit session context was lost while updating progress. "
                    "This typically happens when attempting to update the UI from a background thread. "
                    "Please retry the operation."
                )
            logger.error(f"❌ [STEP 3.1] RAGSystem: Chunking failed: {error_msg}\n{error_details}")
            raise ValueError(f"Failed to split documents into chunks: {error_msg}")
        
        chunk_size_used = adaptive_chunk_size or self.chunk_size
        overlap_used = adaptive_chunk_overlap if adaptive_chunk_overlap is not None else self.chunk_overlap
        logger.info(
            f"✅ [STEP 3.1] RAGSystem: Chunking completed - {len(chunks)} chunks created "
            f"(effective chunk_size={chunk_size_used}, overlap={overlap_used})"
        )
        
        # Validate chunks
        if not chunks:
            raise ValueError("No chunks created from documents. The documents may be empty or too small.")
        
        if progress_callback:
            progress_callback(
                'chunking',
                0.3,
                detailed_message=(
                    f"Chunking completed: {len(chunks)} chunks created "
                    f"(effective chunk size ≈ {chunk_size_used} tokens)"
                )
            )
        
        # Filter out invalid chunks
        valid_chunks = []
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            if chunk is None:
                continue
            if not hasattr(chunk, 'page_content'):
                continue
            if not chunk.page_content or not chunk.page_content.strip():
                continue
            valid_chunks.append(chunk)
            
            # Update progress every 10 chunks or at the end
            if progress_callback and (idx % 10 == 0 or idx == total_chunks - 1):
                progress = 0.3 + (idx / total_chunks) * 0.2  # 0.3 to 0.5
                progress_callback('chunking', progress, detailed_message=f"Validating chunks... {idx + 1}/{total_chunks} processed")
        
        if not valid_chunks:
            raise ValueError("No valid chunks created. All chunks are empty or invalid.")
        
        logger.info(f"Valid chunks: {len(valid_chunks)}/{len(chunks)}")
        
        if progress_callback:
            progress_callback(
                'chunking',
                0.5,
                detailed_message=(
                    f"Chunking complete: {len(valid_chunks)} valid chunks ready for embedding "
                    f"(chunk size ≈ {chunk_size_used} tokens)"
                )
            )
        
        # Track tokens
        for chunk in valid_chunks:
            token_count = chunk.metadata.get('token_count')
            if token_count is None:
                # Count tokens if missing from metadata
                token_count = self.count_tokens(chunk.page_content)
                chunk.metadata['token_count'] = token_count
            self.total_tokens += token_count
        
        logger.info(f"Total tokens: {self.total_tokens:,}")
        
        if progress_callback:
            progress_callback('embedding', 0.6)
        
        # Create or update vector store incrementally
        logger.info(f"Creating/updating {self.vector_store_type.upper()} vector store with {len(valid_chunks)} chunks...")
        try:
            # For OpenSearch: Create per-document index
            if self.vector_store_type == "opensearch" and valid_chunks:
                # Best-plan: prefer strict per-document index from metadata
                first_meta = valid_chunks[0].metadata if valid_chunks and hasattr(valid_chunks[0], 'metadata') else {}
                doc_name = first_meta.get('source', 'Unknown')
                doc_id = first_meta.get('document_id')
                explicit_index_name = first_meta.get('text_index') or first_meta.get('opensearch_index')

                if explicit_index_name:
                    index_name = explicit_index_name
                    logger.info(f"Using explicit OpenSearch index '{index_name}' for document '{doc_name}'")
                    # Ensure mapping exists for query-time filtering
                    try:
                        if doc_name:
                            self.document_index_map[doc_name] = index_name
                            self._save_document_index_map()
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        pass
                elif doc_id:
                    index_name = f"aris-doc-{doc_id}"
                    logger.info(f"Using per-document OpenSearch index '{index_name}' for document '{doc_name}' (document_id={doc_id})")
                    # Ensure mapping exists for query-time filtering
                    try:
                        if doc_name:
                            self.document_index_map[doc_name] = index_name
                            self._save_document_index_map()
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        pass
                else:
                    # Backward compatibility: fall back to existing name->index mapping
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    temp_store = OpenSearchVectorStore(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain,
                        index_name="temp"  # Temporary, just for method access
                    )
                    if doc_name in self.document_index_map:
                        index_name = self.document_index_map[doc_name]
                        logger.info(f"Using existing index '{index_name}' for document '{doc_name}'")
                    else:
                        index_name = temp_store.get_index_name_for_document(doc_name, auto_increment=True)
                        self.document_index_map[doc_name] = index_name
                        logger.info(f"Created new index '{index_name}' for document '{doc_name}'")
                        self._save_document_index_map()
                
                # Create vectorstore with document-specific index
                if self.vectorstore is None:
                    # First document - create vectorstore with its index
                    logger.info(f"[STEP 3.2.1] RAGSystem: Creating new {self.vector_store_type.upper()} vectorstore with index '{index_name}' for document '{doc_name}' ({len(valid_chunks)} chunks)...")
                    if progress_callback:
                        progress_callback('embedding', 0.65)
                    
                    try:
                        self.vectorstore = VectorStoreFactory.create_vector_store(
                            store_type=self.vector_store_type,
                            embeddings=self.embeddings,
                            opensearch_domain=self.opensearch_domain,
                            opensearch_index=index_name  # Use document-specific index
                        )
                    except ValueError as e:
                        logger.error(f"OpenSearch initialization failed: {e}")
                        raise ValueError(
                            f"Failed to initialize OpenSearch. Please check your AWS_OPENSEARCH_DOMAIN configuration. Error: {e}"
                        )
                else:
                    # Check if we need to switch to a different index
                    current_index = getattr(self.vectorstore, 'index_name', None)
                    if current_index != index_name:
                        # Create new vectorstore instance for this document's index
                        logger.info(f"[STEP 3.2.1] RAGSystem: Creating new {self.vector_store_type.upper()} vectorstore with index '{index_name}' for document '{doc_name}' ({len(valid_chunks)} chunks)...")
                        try:
                            doc_vectorstore = VectorStoreFactory.create_vector_store(
                                store_type=self.vector_store_type,
                                embeddings=self.embeddings,
                                opensearch_domain=self.opensearch_domain,
                                opensearch_index=index_name
                            )
                        except ValueError as e:
                            logger.error(f"OpenSearch initialization failed: {e}")
                            raise ValueError(
                                f"Failed to initialize OpenSearch. Please check your AWS_OPENSEARCH_DOMAIN configuration. Error: {e}"
                            )
                        doc_vectorstore.from_documents(valid_chunks)
                        logger.info(f"Added document '{doc_name}' to index '{index_name}'")
                        # Don't update self.vectorstore - we'll use multi_index_manager for queries
                        return len(valid_chunks)
                    # Same index, continue with normal flow below
            
            if self.vectorstore is None:
                # Validate chunks before creating vectorstore
                if len(valid_chunks) == 0:
                    raise ValueError("Cannot create vectorstore: no valid chunks")
                
                # Create vector store using factory (for FAISS or OpenSearch without per-doc indexes)
                logger.info(f"[STEP 3.2.1] RAGSystem: Creating new {self.vector_store_type.upper()} vectorstore with {len(valid_chunks)} chunks (this may take a few minutes for large documents)...")
                if progress_callback:
                    progress_callback('embedding', 0.65)
                
                try:
                    self.vectorstore = VectorStoreFactory.create_vector_store(
                        store_type=self.vector_store_type,
                        embeddings=self.embeddings,
                        opensearch_domain=self.opensearch_domain,
                        opensearch_index=self.opensearch_index
                    )
                except ValueError as e:
                    logger.error(f"OpenSearch initialization failed: {e}")
                    raise ValueError(
                        f"Failed to initialize OpenSearch. Please check your AWS_OPENSEARCH_DOMAIN configuration. Error: {e}"
                    )
                
                # Process in batches for large documents to show progress
                # Increased batch size for better throughput on large documents
                batch_size = getattr(ARISConfig, 'EMBEDDING_BATCH_SIZE', 1000) 
                total_batches = (len(valid_chunks) + batch_size - 1) // batch_size
                
                if len(valid_chunks) > batch_size:
                    logger.info(f"[STEP 3.2.2] RAGSystem: Processing {len(valid_chunks)} chunks in {total_batches} batches of {batch_size} (this may take several minutes)...")
                    # Process first batch to create vectorstore
                    first_batch = valid_chunks[:batch_size]
                    logger.info(f"[STEP 3.2.2.1] RAGSystem: Processing batch 1/{total_batches} ({len(first_batch)} chunks) - creating embeddings...")
                    if progress_callback:
                        progress_callback('embedding', 0.65, detailed_message=f"Initializing vector store... Batch 1/{total_batches} ({len(first_batch)} chunks)")
                    
                    import time
                    batch_start = time_module.time()
                    self.vectorstore.from_documents(first_batch)
                    batch_time = time_module.time() - batch_start
                    logger.info(f"✅ [STEP 3.2.2.1] RAGSystem: Batch 1/{total_batches} completed in {batch_time:.1f}s ({len(first_batch)} chunks embedded)")
                    
                    if progress_callback:
                        progress_callback('embedding', 0.7, detailed_message=f"Batch 1/{total_batches} complete ({len(first_batch)} chunks embedded in {batch_time:.1f}s)")
                    
                    # Process remaining batches
                    embedding_start_time = time_module.time()
                    for batch_num in range(1, total_batches):
                        start_idx = batch_num * batch_size
                        end_idx = min(start_idx + batch_size, len(valid_chunks))
                        batch = valid_chunks[start_idx:end_idx]
                        
                        if batch:
                            batch_pct = int((batch_num + 1) / total_batches * 100)
                            elapsed_embedding = time_module.time() - embedding_start_time
                            
                            # Calculate speed and remaining time
                            chunks_processed_so_far = (batch_num * batch_size) + len(first_batch)
                            if elapsed_embedding > 0:
                                chunks_per_sec = chunks_processed_so_far / elapsed_embedding
                                remaining_chunks = len(valid_chunks) - chunks_processed_so_far
                                estimated_remaining = remaining_chunks / chunks_per_sec if chunks_per_sec > 0 else 0
                                remaining_minutes = int(estimated_remaining // 60)
                                remaining_seconds = int(estimated_remaining % 60)
                                remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining" if estimated_remaining > 0 else "calculating..."
                            else:
                                remaining_str = "calculating..."
                                chunks_per_sec = 0
                            
                            logger.info(f"[STEP 3.2.2.{batch_num + 1}] RAGSystem: Processing batch {batch_num + 1}/{total_batches} ({batch_pct}%) - {len(batch)} chunks | {remaining_str}")
                            if progress_callback:
                                # Update progress: 0.7 to 0.9 based on batches
                                batch_progress = 0.7 + ((batch_num + 1) / total_batches) * 0.2
                                detailed_msg = f"Batch {batch_num + 1}/{total_batches} ({batch_pct}%) | {len(batch)} chunks | {remaining_str}"
                                progress_callback('embedding', batch_progress, detailed_message=detailed_msg)
                            
                            batch_start = time_module.time()
                            # OpenSearch only - no FAISS fallback
                            self.vectorstore.add_documents(batch)
                            batch_time = time_module.time() - batch_start
                            chunks_per_sec_batch = len(batch) / batch_time if batch_time > 0 else 0
                            logger.info(f"✅ [STEP 3.2.2.{batch_num + 1}] RAGSystem: Batch {batch_num + 1}/{total_batches} completed in {batch_time:.1f}s | Speed: {chunks_per_sec_batch:.2f} chunks/sec | {len(batch)} chunks embedded")
                            
                            if progress_callback:
                                # Update progress: 0.7 to 0.9 based on batches
                                batch_progress = 0.7 + ((batch_num + 1) / total_batches) * 0.2
                                progress_callback('embedding', batch_progress, detailed_message=f"Batch {batch_num + 1}/{total_batches} complete ({len(batch)} chunks embedded in {batch_time:.1f}s, {chunks_per_sec_batch:.2f} chunks/sec)")
                else:
                    # Small document - process all at once
                    logger.info(f"[STEP 3.2.2] RAGSystem: Processing {len(valid_chunks)} chunks - creating embeddings (this may take a minute)...")
                    if progress_callback:
                        progress_callback('embedding', 0.7, detailed_message=f"Creating embeddings for {len(valid_chunks)} chunks... This may take a minute")
                    import time
                    embed_start = time_module.time()
                    self.vectorstore.from_documents(valid_chunks)
                    embed_time = time_module.time() - embed_start
                    logger.info(f"✅ [STEP 3.2.2] RAGSystem: Embedding completed in {embed_time:.1f}s ({len(valid_chunks)} chunks)")
                    if progress_callback:
                        progress_callback('embedding', 0.85, detailed_message=f"Embeddings complete! {len(valid_chunks)} chunks embedded in {embed_time:.1f}s")
                
                logger.info(f"✅ [STEP 3.2] RAGSystem: {self.vector_store_type.upper()} vectorstore created successfully")
            else:
                # Add to existing vector store (incremental update)
                if len(valid_chunks) > 0:
                    logger.info(f"[STEP 3.2.3] RAGSystem: Adding {len(valid_chunks)} chunks to existing {self.vector_store_type.upper()} vectorstore (this may take a few minutes for large documents)...")
                    
                    # Process in batches for large documents
                    batch_size = getattr(ARISConfig, 'EMBEDDING_BATCH_SIZE', 1000)
                    total_batches = (len(valid_chunks) + batch_size - 1) // batch_size
                    
                    if len(valid_chunks) > batch_size:
                        logger.info(f"[STEP 3.2.3.1] RAGSystem: Processing {len(valid_chunks)} chunks in {total_batches} batches of {batch_size} (this may take several minutes)...")
                        embedding_start_time = time_module.time()
                        for batch_num in range(total_batches):
                            start_idx = batch_num * batch_size
                            end_idx = min(start_idx + batch_size, len(valid_chunks))
                            batch = valid_chunks[start_idx:end_idx]
                            
                            if batch:
                                batch_pct = int((batch_num + 1) / total_batches * 100)
                                elapsed_embedding = time_module.time() - embedding_start_time
                                
                                # Calculate speed and remaining time
                                chunks_processed_so_far = (batch_num + 1) * batch_size if (batch_num + 1) * batch_size <= len(valid_chunks) else len(valid_chunks)
                                if elapsed_embedding > 0:
                                    chunks_per_sec = chunks_processed_so_far / elapsed_embedding
                                    remaining_chunks = len(valid_chunks) - chunks_processed_so_far
                                    estimated_remaining = remaining_chunks / chunks_per_sec if chunks_per_sec > 0 else 0
                                    remaining_minutes = int(estimated_remaining // 60)
                                    remaining_seconds = int(estimated_remaining % 60)
                                    remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining" if estimated_remaining > 0 else "calculating..."
                                else:
                                    remaining_str = "calculating..."
                                    chunks_per_sec = 0
                                
                                logger.info(f"[STEP 3.2.3.{batch_num + 1}] RAGSystem: Processing batch {batch_num + 1}/{total_batches} ({batch_pct}%) - {len(batch)} chunks | {remaining_str}")
                                batch_start = time_module.time()
                                if self.vector_store_type == "faiss":
                                    self.vectorstore.add_documents(batch, auto_recreate_on_mismatch=True)
                                else:
                                    self.vectorstore.add_documents(batch)
                                batch_time = time_module.time() - batch_start
                                chunks_per_sec_batch = len(batch) / batch_time if batch_time > 0 else 0
                                logger.info(f"✅ [STEP 3.2.3.{batch_num + 1}] RAGSystem: Batch {batch_num + 1}/{total_batches} completed in {batch_time:.1f}s | Speed: {chunks_per_sec_batch:.2f} chunks/sec | {len(batch)} chunks embedded")
                                
                                if progress_callback:
                                    # Update progress: 0.6 to 0.9 based on batches
                                    batch_progress = 0.6 + ((batch_num + 1) / total_batches) * 0.3
                                    detailed_msg = f"Batch {batch_num + 1}/{total_batches} ({batch_pct}%) | {len(batch)} chunks | {remaining_str}"
                                    progress_callback('embedding', batch_progress, detailed_message=detailed_msg)
                    else:
                        # Small update - process all at once
                        logger.info(f"[STEP 3.2.3.1] RAGSystem: Processing {len(valid_chunks)} chunks - creating embeddings (this may take a minute)...")
                        if progress_callback:
                            progress_callback('embedding', 0.7)
                        embed_start = time_module.time()
                        if self.vector_store_type == "faiss":
                            self.vectorstore.add_documents(valid_chunks, auto_recreate_on_mismatch=True)
                        else:
                            self.vectorstore.add_documents(valid_chunks)
                        embed_time = time_module.time() - embed_start
                        logger.info(f"✅ [STEP 3.2.3.1] RAGSystem: Embedding completed in {embed_time:.1f}s ({len(valid_chunks)} chunks)")
                        if progress_callback:
                            progress_callback('embedding', 0.85)
                    
                    logger.info(f"✅ [STEP 3.2.3] RAGSystem: Chunks added to {self.vector_store_type.upper()} vectorstore successfully")
        except Exception as e:
            # Capture full error details including traceback
            error_details = traceback.format_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            if not error_msg or error_msg.strip() == "":
                error_msg = f"Unknown error ({type(e).__name__})"
            
            logger.error(f"❌ [STEP 3.2] RAGSystem: Vectorstore creation/update failed: {error_msg}")
            logger.error(f"❌ [STEP 3.2] RAGSystem: Full traceback:\n{error_details}")
            
            # Check for specific error types
            if "OpenSearch" in error_msg or "opensearch" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update OpenSearch vectorstore: {error_msg}. "
                    f"Please check your OpenSearch credentials and domain configuration. "
                    f"You may want to use FAISS instead for local storage."
                )
            elif "dimension" in error_msg.lower() or "shape" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to dimension mismatch in embeddings. "
                    f"Try removing existing vectorstore and reprocessing documents."
                )
            elif "empty" in error_msg.lower() or "no documents" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to empty chunks. Please check your document content."
                )
            else:
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to empty chunks or embedding issues. "
                    f"Full error: {error_details[-500:]}"  # Last 500 chars of traceback
                )
        
        if progress_callback:
            progress_callback('embedding', 0.9)
        
        # Track document chunks
        # Calculate chunk_start based on total existing chunks
        chunk_start = sum(len(chunk_list) for chunk_list in self.document_index.values())
        for i, chunk in enumerate(valid_chunks):
            doc_id = chunk.metadata.get('source', f'doc_{len(documents)}')
            if doc_id not in self.document_index:
                self.document_index[doc_id] = []
            self.document_index[doc_id].append(chunk_start + i)
        
        logger.info(f"✅ [STEP 3.3] RAGSystem: Document indexing completed - {len(valid_chunks)} chunks indexed")
        
        return len(valid_chunks)
    
    def add_documents_incremental(self, 
        texts: List[str],
        metadatas: List[Dict] = None,
        progress_callback: Optional[Callable] = None,
        index_name: Optional[str] = None
    ) -> Dict:
        """
        Add documents incrementally to the vector store.
        Returns processing statistics.
        
        Args:
            texts: List of text content
            metadatas: List of metadata dictionaries
            progress_callback: Optional callback function(status, progress) for updates
        
        Returns:
            Dict with processing stats: chunks_created, tokens_added, documents_added
        """
        chunks_before = sum(len(chunks) for chunks in self.document_index.values())
        tokens_before = self.total_tokens
        
        chunks_created = self.process_documents(texts, metadatas, progress_callback=progress_callback, index_name=index_name)
        
        chunks_after = sum(len(chunks) for chunks in self.document_index.values())
        tokens_after = self.total_tokens
        
        return {
            'chunks_created': chunks_created,
            'tokens_added': tokens_after - tokens_before,
            'documents_added': len(texts),
            'total_chunks': chunks_after,
            'total_tokens': tokens_after
        }

    def load_selected_documents(self, document_names: List[str], path: str = "vectorstore") -> Dict:
        """
        Load only the selected documents into a fresh vectorstore (FAISS) or
        configure OpenSearch to filter by those documents.

        Args:
            document_names: List of document names (metadata 'source') to load.
            path: Base path for FAISS vectorstore storage.

        Returns:
            Dict with keys:
                loaded: bool
                docs_loaded: int
                chunks_loaded: int
                message: str
        """
        from scripts.setup_logging import get_logger
        from langchain_community.docstore.in_memory import InMemoryDocstore
        from shared.config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")

        if not document_names:
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": "No documents selected."
            }

        self.active_sources = document_names

        if self.vector_store_type == "opensearch":
            # For per-document indexes, verify indexes exist for selected documents
            indexes_found = []
            for doc_name in document_names:
                if doc_name in self.document_index_map:
                    index_name = self.document_index_map[doc_name]
                    # Verify index exists
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    temp_store = OpenSearchVectorStore(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain,
                        index_name=index_name
                    )
                    if temp_store.index_exists(index_name):
                        indexes_found.append(index_name)
                    else:
                        logger.warning(f"Index '{index_name}' for document '{doc_name}' does not exist")
                else:
                    logger.warning(f"Document '{doc_name}' not found in index map")
            
            if indexes_found:
                # Initialize multi-index manager
                if not hasattr(self, 'multi_index_manager'):
                    from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                    self.multi_index_manager = OpenSearchMultiIndexManager(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain
                    )
                
                # Verify indexes are accessible
                for index_name in indexes_found:
                    self.multi_index_manager.get_or_create_index_store(index_name)
                
                msg = f"OpenSearch indexes ready for {len(indexes_found)} document(s): {indexes_found}"
                logger.info(f"✅ {msg}")

                # Best-effort: report chunk counts by counting docs in the selected indexes
                chunks_loaded = 0
                try:
                    for index_name in indexes_found:
                        store = self.multi_index_manager.get_or_create_index_store(index_name)
                        if hasattr(store, 'count_documents'):
                            chunks_loaded += int(store.count_documents() or 0)
                except Exception as e:
                    logger.warning(f"operation: {type(e).__name__}: {e}")
                    chunks_loaded = 0
                return {
                    "loaded": True,
                    "docs_loaded": len(indexes_found),
                    "chunks_loaded": chunks_loaded,
                    "message": msg
                }
            else:
                msg = f"No indexes found for selected documents: {document_names}"
                logger.error(f"❌ {msg}")
                return {
                    "loaded": False,
                    "docs_loaded": 0,
                    "chunks_loaded": 0,
                    "message": msg
                }

        # FAISS: build a fresh in-memory index containing only selected docs
        # Load the full store once to extract vectors, then rebuild subset
        model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
        base_path = path
        if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
            model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))

        if not os.path.exists(model_specific_path):
            msg = f"Vectorstore path does not exist: {model_specific_path}. Reprocess documents first."
            logger.warning(f"⚠️ {msg}")
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }

        try:
            logger.info(f"[STEP 1] Loading full FAISS store to extract selected docs: {model_specific_path}")
            full_vs = VectorStoreFactory.load_vector_store(
                store_type="faiss",
                embeddings=self.embeddings,
                path=model_specific_path
            )
        except Exception as e:
            msg = f"Failed to load base vectorstore: {e}"
            logger.error(f"❌ {msg}", exc_info=True)
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }

        # Extract matching docs and vectors
        docs = []
        vectors = []
        
        # Try multiple ways to access docstore and mapping
        mapping = None
        ds = None
        actual_faiss = None  # The actual FAISS object we'll use
        
        # Method 1: Check if it's a wrapped FAISSVectorStore (from VectorStoreFactory)
        if hasattr(full_vs, "vectorstore"):
            actual_faiss = full_vs.vectorstore
            logger.info("Detected FAISSVectorStore wrapper, accessing inner vectorstore")
        # Method 2: Direct FAISS object
        elif hasattr(full_vs, "docstore"):
            actual_faiss = full_vs
        else:
            actual_faiss = full_vs
        
        # Now try to access docstore and mapping from the actual FAISS object
        if actual_faiss and hasattr(actual_faiss, "docstore"):
            ds = actual_faiss.docstore
            # Try to get index_to_docstore_id
            if hasattr(actual_faiss, "index_to_docstore_id"):
                mapping = actual_faiss.index_to_docstore_id
            # Some versions might store it differently
            elif hasattr(actual_faiss, "_index_to_docstore_id"):
                mapping = actual_faiss._index_to_docstore_id
        
        # Check if documents are stored as strings (metadata lost) by sampling first document
        use_fallback = False
        if mapping is not None and ds is not None:
            # Sample first document to check if it's a string
            try:
                if len(mapping) > 0:
                    first_doc_id = mapping[0]
                    if hasattr(ds, "_dict") and first_doc_id in ds._dict:
                        first_doc = ds._dict[first_doc_id]
                        if isinstance(first_doc, str):
                            logger.info("Documents in docstore are strings (metadata lost), using similarity_search fallback")
                            use_fallback = True
            except Exception as e:
                logger.warning(f"operation: {type(e).__name__}: {e}")
                pass
        
        if mapping is not None and ds is not None and not use_fallback:
            # Extract documents and vectors using mapping
            logger.info(f"Using index_to_docstore_id mapping with {len(mapping)} entries")
            all_sources_in_mapping = []
            for i, doc_id in enumerate(mapping):
                try:
                    # Try different ways to get document from docstore
                    # Prefer _dict access as it's more direct
                    doc = None
                    if hasattr(ds, "_dict") and doc_id in ds._dict:
                        doc = ds._dict[doc_id]
                    elif hasattr(ds, "search"):
                        doc = ds.search(doc_id)
                    elif hasattr(ds, "get") and callable(ds.get):
                        doc = ds.get(doc_id)
                    
                    if doc and hasattr(doc, "metadata"):
                        metadata = doc.metadata
                        source = metadata.get("source", "") if isinstance(metadata, dict) else ""
                        all_sources_in_mapping.append(source)
                        if i < 3:  # Log first 3 for debugging
                            logger.info(f"Document {i} (id={doc_id}) source: '{source}'")
                        
                        # Try multiple matching strategies
                        matched = False
                        # Strategy 1: Exact match
                        if source in document_names:
                            matched = True
                        # Strategy 2: Case-insensitive match
                        elif not matched:
                            source_lower = source.lower()
                            for doc_name in document_names:
                                if source_lower == doc_name.lower():
                                    matched = True
                                    break
                        # Strategy 3: Filename match (extract just filename from path)
                        elif not matched:
                            source_filename = os.path.basename(source) if source else ""
                            for doc_name in document_names:
                                doc_filename = os.path.basename(doc_name) if doc_name else ""
                                if source_filename and doc_filename and source_filename.lower() == doc_filename.lower():
                                    matched = True
                                    break
                        
                        if matched:
                            docs.append(doc)
                            logger.info(f"✅ Found matching document via mapping: '{source}' matches '{document_names}'")
                            try:
                                # Try to reconstruct vector from index (use actual_faiss if available)
                                index_obj = actual_faiss.index if actual_faiss and hasattr(actual_faiss, "index") else (full_vs.index if hasattr(full_vs, "index") else None)
                                if index_obj and hasattr(index_obj, "reconstruct"):
                                    vec = index_obj.reconstruct(i)
                                    vectors.append(vec)
                            except Exception as e:
                                logger.debug(f"Could not reconstruct vector for index {i}: {e}")
                                # Continue without vector - we'll re-embed if needed
                except Exception as e:
                    logger.debug(f"Error accessing document {doc_id}: {e}")
                    continue
            
            if not docs and all_sources_in_mapping:
                logger.warning(f"Looking for: {document_names}, but found sources in mapping: {set(all_sources_in_mapping)}")
        
        if use_fallback or mapping is None or not docs:
            # Fallback: Try to access docstore directly or use similarity_search
            logger.info("Using fallback method: attempting direct docstore access or similarity_search")
            try:
                # Determine which vectorstore to use for searching
                search_vs = actual_faiss if actual_faiss else full_vs
                
                # Try to access docstore directly if available
                if hasattr(search_vs, "docstore"):
                    ds = search_vs.docstore
                    # Try to iterate through all documents in docstore
                    if hasattr(ds, "_dict"):
                        logger.info(f"Accessing docstore._dict with {len(ds._dict)} entries")
                        all_sources_found = []
                        for doc_id, doc in ds._dict.items():
                            try:
                                if hasattr(doc, "metadata"):
                                    source = doc.metadata.get("source", "")
                                    all_sources_found.append(source)
                                    logger.debug(f"Document {doc_id} has source: {source}")
                                    
                                    # Try multiple matching strategies
                                    matched = False
                                    # Strategy 1: Exact match
                                    if source in document_names:
                                        matched = True
                                    # Strategy 2: Case-insensitive match
                                    elif not matched:
                                        source_lower = source.lower()
                                        for doc_name in document_names:
                                            if source_lower == doc_name.lower():
                                                matched = True
                                                break
                                    # Strategy 3: Filename match (extract just filename from path)
                                    elif not matched:
                                        source_filename = os.path.basename(source) if source else ""
                                        for doc_name in document_names:
                                            doc_filename = os.path.basename(doc_name) if doc_name else ""
                                            if source_filename and doc_filename and source_filename.lower() == doc_filename.lower():
                                                matched = True
                                                break
                                    
                                    if matched:
                                        docs.append(doc)
                                        logger.info(f"✅ Found matching document via fallback: '{source}' matches '{document_names}'")
                            except Exception as e:
                                logger.debug(f"Error checking document {doc_id}: {e}")
                                continue
                        
                        if not docs and all_sources_found:
                            logger.warning(f"Looking for: {document_names}, but found sources: {set(all_sources_found)}")
                    elif hasattr(ds, "search"):
                        # Try to search for documents - this is tricky without knowing IDs
                        # We'll use similarity_search as fallback
                        pass
                
                # If we still don't have docs, use similarity_search with multiple queries
                if not docs:
                    logger.info("Using similarity_search to extract documents...")
                    # Try multiple generic queries to get all documents
                    queries = ["document", "text", "content", "information", "data"]
                    all_docs_set = set()  # Use set to avoid duplicates
                    
                    for query in queries:
                        try:
                            found_docs = search_vs.similarity_search(query, k=1000)
                            for doc in found_docs:
                                # Use a unique identifier for each doc (content + metadata)
                                doc_key = (doc.page_content[:100] if hasattr(doc, "page_content") else str(doc),
                                          str(doc.metadata.get("source", "")) if hasattr(doc, "metadata") else "")
                                if doc_key not in all_docs_set:
                                    all_docs_set.add(doc_key)
                                    # Try multiple matching strategies
                                    if hasattr(doc, "metadata"):
                                        source = doc.metadata.get("source", "")
                                        matched = False
                                        # Strategy 1: Exact match
                                        if source in document_names:
                                            matched = True
                                        # Strategy 2: Case-insensitive match
                                        elif not matched:
                                            source_lower = source.lower()
                                            for doc_name in document_names:
                                                if source_lower == doc_name.lower():
                                                    matched = True
                                                    break
                                        # Strategy 3: Filename match
                                        elif not matched:
                                            source_filename = os.path.basename(source) if source else ""
                                            for doc_name in document_names:
                                                doc_filename = os.path.basename(doc_name) if doc_name else ""
                                                if source_filename and doc_filename and source_filename.lower() == doc_filename.lower():
                                                    matched = True
                                                    break
                                        
                                        if matched:
                                            docs.append(doc)
                        except Exception as e:
                            logger.debug(f"operation: {type(e).__name__}: {e}")
                            continue
                    
                    # If still no docs, try one more time with empty query and very large k
                    if not docs:
                        try:
                            all_docs = search_vs.similarity_search("the", k=10000)
                            seen = set()
                            for doc in all_docs:
                                doc_key = (doc.page_content[:100] if hasattr(doc, "page_content") else str(doc),
                                          str(doc.metadata.get("source", "")) if hasattr(doc, "metadata") else "")
                                if doc_key not in seen:
                                    seen.add(doc_key)
                                    # Try multiple matching strategies
                                    if hasattr(doc, "metadata"):
                                        source = doc.metadata.get("source", "")
                                        matched = False
                                        # Strategy 1: Exact match
                                        if source in document_names:
                                            matched = True
                                        # Strategy 2: Case-insensitive match
                                        elif not matched:
                                            source_lower = source.lower()
                                            for doc_name in document_names:
                                                if source_lower == doc_name.lower():
                                                    matched = True
                                                    break
                                        # Strategy 3: Filename match
                                        elif not matched:
                                            source_filename = os.path.basename(source) if source else ""
                                            for doc_name in document_names:
                                                doc_filename = os.path.basename(doc_name) if doc_name else ""
                                                if source_filename and doc_filename and source_filename.lower() == doc_filename.lower():
                                                    matched = True
                                                    break
                                        
                                        if matched:
                                            docs.append(doc)
                        except Exception as e:
                            logger.debug(f"operation: {type(e).__name__}: {e}")
                            pass
                
                if not docs:
                    # Try to list available sources for better error message
                    available_sources = set()
                    try:
                        debug_vs = actual_faiss if actual_faiss else full_vs
                        if hasattr(debug_vs, "docstore") and hasattr(debug_vs.docstore, "_dict"):
                            for doc in debug_vs.docstore._dict.values():
                                if hasattr(doc, "metadata") and "source" in doc.metadata:
                                    available_sources.add(doc.metadata["source"])
                        # Also check all_sources_found and all_sources_in_mapping
                        if all_sources_found:
                            available_sources.update(all_sources_found)
                        if all_sources_in_mapping:
                            available_sources.update(all_sources_in_mapping)
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        pass
                    
                    if available_sources:
                        available_list = sorted(list(available_sources))[:10]
                        msg = f"Selected documents ({document_names}) not found in vectorstore.\n\nAvailable sources: {', '.join(available_list)}{'...' if len(available_sources) > 10 else ''}\n\nTip: Make sure the document name matches exactly (including file extension)."
                        logger.warning(f"⚠️ {msg}")
                    else:
                        msg = f"Selected documents ({document_names}) not found in vectorstore. Available sources may differ."
                        logger.warning(f"⚠️ {msg}")
                    
                    return {
                        "loaded": False,
                        "docs_loaded": 0,
                        "chunks_loaded": 0,
                        "message": msg
                    }
                
                # Re-embed the filtered documents to get vectors
                logger.info(f"Re-embedding {len(docs)} filtered documents...")
                doc_texts = [doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in docs]
                vectors = self.embeddings.embed_documents(doc_texts)
                
            except Exception as e:
                msg = f"Failed to extract documents from vectorstore: {e}"
                logger.error(f"❌ {msg}", exc_info=True)
                return {
                    "loaded": False,
                    "docs_loaded": 0,
                    "chunks_loaded": 0,
                    "message": msg
                }

        if not docs:
            msg = "Selected documents not found in vectorstore."
            logger.warning(f"⚠️ {msg}")
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }
        
        # If we don't have vectors (fallback method), re-embed the documents
        if not vectors or len(vectors) != len(docs):
            logger.info(f"Re-embedding {len(docs)} documents to get vectors...")
            doc_texts = [doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in docs]
            vectors = self.embeddings.embed_documents(doc_texts)

        # Build a fresh FAISS index with selected vectors
        try:
            # Get dimension from vectors or existing index
            if vectors and len(vectors) > 0:
                dim = len(vectors[0])
            else:
                # Try to get dimension from the actual FAISS index
                index_obj = None
                if actual_faiss and hasattr(actual_faiss, "index"):
                    index_obj = actual_faiss.index
                elif hasattr(full_vs, "index"):
                    index_obj = full_vs.index
                elif hasattr(full_vs, "vectorstore") and hasattr(full_vs.vectorstore, "index"):
                    index_obj = full_vs.vectorstore.index
                
                if index_obj and hasattr(index_obj, "d"):
                    dim = index_obj.d
                else:
                    # Fallback: get dimension from embeddings
                    test_embedding = self.embeddings.embed_query("test")
                    dim = len(test_embedding)
            
            import faiss
            new_index = faiss.IndexFlatL2(dim)
            new_docstore = InMemoryDocstore()
            new_index_to_docstore_id = []

            for vec, doc in zip(vectors, docs):
                doc_id = str(len(new_index_to_docstore_id))
                new_docstore._dict[doc_id] = doc
                new_index_to_docstore_id.append(doc_id)
                new_index.add(np.array([vec], dtype="float32"))

            from langchain_community.vectorstores.faiss import FAISS as LCFAISS
            subset_vs = LCFAISS(
                embedding_function=self.embeddings,
                index=new_index,
                docstore=new_docstore,
                index_to_docstore_id=new_index_to_docstore_id
            )

            # Replace active vectorstore with subset
            self.vectorstore = subset_vs

            # Rebuild document_index for the subset
            self.document_index = {}
            for idx, doc in enumerate(docs):
                src = doc.metadata.get("source", f"doc_{idx}")
                if src not in self.document_index:
                    self.document_index[src] = []
                self.document_index[src].append(idx)

            msg = f"Loaded {len(docs)} document(s) into subset vectorstore ({len(vectors)} chunks)."
            logger.info(f"✅ {msg}")
            return {
                "loaded": True,
                "docs_loaded": len(docs),
                "chunks_loaded": len(vectors),
                "message": msg
            }
        except Exception as e:
            msg = f"Failed to build subset vectorstore: {e}"
            logger.error(f"❌ {msg}", exc_info=True)
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
        }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken."""
        if not text:
            return 0
        try:
            import tiktoken
            # Use cl100k_base for OpenAI models (GPT-3.5/4)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception as e:
            logger.debug(f"count_tokens: {type(e).__name__}: {e}")
            # Fallback to rough estimate if tiktoken fails
            return len(text) // 4
    
    def _truncate_text_by_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to fit within token limit, preserving structure where possible.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens allowed
        
        Returns:
            Truncated text
        """
        if not text or max_tokens <= 0:
            return text
        
        current_tokens = self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        # Estimate characters per token (rough: ~4 chars per token)
        chars_per_token = len(text) / max(current_tokens, 1)
        max_chars = int(max_tokens * chars_per_token * 0.9)  # 90% to be safe
        
        # Try to truncate at a natural boundary (sentence or chunk separator)
        if len(text) > max_chars:
            truncated = text[:max_chars]
            # Try to find a good break point
            last_separator = max(
                truncated.rfind('\n\n---\n\n'),  # Chunk separator
                truncated.rfind('\n\n'),  # Paragraph break
                truncated.rfind('. '),  # Sentence end
                truncated.rfind('\n')  # Line break
            )
            if last_separator > max_chars * 0.8:  # If we found a break point reasonably close
                truncated = text[:last_separator]
            
            # Verify token count
            while self.count_tokens(truncated) > max_tokens and len(truncated) > 100:
                truncated = truncated[:int(len(truncated) * 0.95)]  # Reduce by 5%
            
            return truncated
        
        return text

    def check_index_exists(self, index_name: str) -> bool:
        """
        Check if an OpenSearch index exists.
        
        Args:
            index_name: Name of the index to check
            
        Returns:
            True if exists, False otherwise (or if not using OpenSearch)
        """
        if self.vector_store_type != 'opensearch':
            return False
            
        try:
            # Check if vectorstore handles this
            if hasattr(self.vectorstore, 'index_exists'):
                return self.vectorstore.index_exists(index_name)
            
            # Fallback: create temp store to check
            from vectorstores.opensearch_store import OpenSearchVectorStore
            temp_store = OpenSearchVectorStore(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                index_name=index_name
            )
            return temp_store.index_exists(index_name)
        except Exception as e:
            logger.warning(f"Error checking if index {index_name} exists: {e}")
            return False

    def get_next_index_name(self, base_name: str) -> str:
        """
        Find the next available auto-incremented index name.
        
        Args:
            base_name: Base name for the index (e.g., 'my-doc')
            
        Returns:
            Next available name (e.g., 'my-doc-1')
        """
        if self.vector_store_type != 'opensearch':
            return base_name
            
        try:
            # Clean base name first
            from vectorstores.opensearch_store import OpenSearchVectorStore
            clean_base = OpenSearchVectorStore.sanitize_index_name(base_name)
            
            # Use vectorstore method if available
            if hasattr(self.vectorstore, 'find_next_available_index_name'):
                return self.vectorstore.find_next_available_index_name(clean_base)
                
            # Fallback: manual check
            if not self.check_index_exists(clean_base):
                return clean_base
                
            counter = 1
            while True:
                candidate = f"{clean_base}-{counter}"
                if not self.check_index_exists(candidate):
                    return candidate
                counter += 1
                if counter > 100:  # Safety break
                    return f"{clean_base}-{int(time_module.time())}"
        except Exception as e:
            logger.warning(f"Error finding next index name: {e}")
            return f"{base_name}-1"

    def _get_language_separators(self, metadatas: Optional[List[Dict]] = None) -> List[str]:
        """
        Get language-aware separators for text splitting.
        
        Args:
            metadatas: Optional list of metadata dictionaries to detect language
            
        Returns:
            List of separator strings optimized for the detected language
        """
        # Default separators (English/Western)
        separators = ["\n\n", "\n", " ", ""]
        
        if not metadatas:
            return separators
            
        # Detect predominant language
        languages = [m.get('language', 'eng') for m in metadatas if m]
        if not languages:
            return separators
            
        # Get most common language
        from collections import Counter
        most_common_lang = Counter(languages).most_common(1)[0][0]
        
        # Improvement 4: Language-Aware Chunking
        # Adjust separators based on language family
        
        # Asian languages (Chinese, Japanese) - no spaces between words
        if most_common_lang in ['zho', 'chi', 'jpn', 'kor']:
            separators = ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
            
        # Thai - no spaces, specialized boundaries
        elif most_common_lang in ['tha']:
            separators = ["\n\n", "\n", " ", ""]  # Thai usually needs specialized tokenizer
            
        # German - long compound words, split on hyphens if needed
        elif most_common_lang in ['deu', 'ger']:
            separators = ["\n\n", "\n", " ", "-", ""]
            
        # Arabic - specialized punctuation
        elif most_common_lang in ['ara']:
            separators = ["\n\n", "\n", "؛", "،", " ", ""]
        
        return separators
