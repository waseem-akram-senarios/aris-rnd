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
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document
import requests
from utils.tokenizer import TokenTextSplitter
from vectorstores.vector_store_factory import VectorStoreFactory
from config.settings import ARISConfig

load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

class RAGSystem:
    def __init__(self, use_cerebras=False, metrics_collector=None, 
                 embedding_model=None,
                 openai_model=None,
                 cerebras_model=None,
                 vector_store_type="faiss",
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
        
        # Vector store configuration
        self.vector_store_type = vector_store_type.lower()
        self.opensearch_domain = opensearch_domain
        self.opensearch_index = opensearch_index
        
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
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=self.embedding_model
        )
        self.vectorstore = None
        # Use token-aware text splitter with configurable chunking
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=embedding_model
        )
        
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
        
        # Metrics collector for R&D analytics
        self.metrics_collector = metrics_collector
        
        # Initialize LLM
        if use_cerebras:
            self.llm = None  # Will use Cerebras API directly
            self.cerebras_api_key = os.getenv('CEREBRAS_API_KEY')
        else:
            self.llm = None  # Will use OpenAI API directly
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
    
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
    
    def process_documents(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None):
        """Process and chunk documents, then create vector store"""
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
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
        except Exception:
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
                safe_documents,
                progress_callback=splitter_progress_callback
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
            token_count = chunk.metadata.get('token_count', 0)
            self.total_tokens += token_count
        
        logger.info(f"Total tokens: {self.total_tokens:,}")
        
        if progress_callback:
            progress_callback('embedding', 0.6)
        
        # Create or update vector store incrementally
        logger.info(f"Creating/updating {self.vector_store_type.upper()} vector store with {len(valid_chunks)} chunks...")
        try:
            # For OpenSearch: Create per-document index
            if self.vector_store_type == "opensearch" and valid_chunks:
                # Extract document name from chunks
                doc_name = valid_chunks[0].metadata.get('source', 'Unknown') if valid_chunks else 'Unknown'
                
                # Generate index name for this document
                from vectorstores.opensearch_store import OpenSearchVectorStore
                temp_store = OpenSearchVectorStore(
                    embeddings=self.embeddings,
                    domain=self.opensearch_domain,
                    index_name="temp"  # Temporary, just for method access
                )
                
                # Get or create index name for this document
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
                    logger.info(f"[STEP 3.2.1] RAGSystem: Creating new OpenSearch vectorstore with index '{index_name}' for document '{doc_name}' ({len(valid_chunks)} chunks)...")
                    if progress_callback:
                        progress_callback('embedding', 0.65)
                    
                    self.vectorstore = VectorStoreFactory.create_vector_store(
                        store_type=self.vector_store_type,
                        embeddings=self.embeddings,
                        opensearch_domain=self.opensearch_domain,
                        opensearch_index=index_name  # Use document-specific index
                    )
                else:
                    # Check if we need to switch to a different index
                    current_index = getattr(self.vectorstore, 'index_name', None)
                    if current_index != index_name:
                        # Create new vectorstore instance for this document's index
                        logger.info(f"[STEP 3.2.1] RAGSystem: Creating new OpenSearch vectorstore with index '{index_name}' for document '{doc_name}' ({len(valid_chunks)} chunks)...")
                        doc_vectorstore = VectorStoreFactory.create_vector_store(
                            store_type=self.vector_store_type,
                            embeddings=self.embeddings,
                            opensearch_domain=self.opensearch_domain,
                            opensearch_index=index_name
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
                
                self.vectorstore = VectorStoreFactory.create_vector_store(
                    store_type=self.vector_store_type,
                    embeddings=self.embeddings,
                    opensearch_domain=self.opensearch_domain,
                    opensearch_index=self.opensearch_index
                )
                
                # Process in batches for large documents to show progress
                # Use smaller batches (50) for better progress visibility
                batch_size = 50  # Process 50 chunks at a time for better progress updates
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
                            if self.vector_store_type == "faiss":
                                self.vectorstore.add_documents(batch, auto_recreate_on_mismatch=True)
                            else:
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
                    batch_size = 50  # Use smaller batches for better progress visibility
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
    
    def add_documents_incremental(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None) -> Dict:
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
        
        chunks_created = self.process_documents(texts, metadatas, progress_callback=progress_callback)
        
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
        from config.settings import ARISConfig
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
                return {
                    "loaded": True,
                    "docs_loaded": len(indexes_found),
                    "chunks_loaded": 0,
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
            except Exception:
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
                        except Exception:
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
                        except Exception:
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
                    except Exception:
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
        """Count tokens in text using the tokenizer."""
        return self.text_splitter.count_tokens(text)
    
    def _clean_answer(self, answer: str) -> str:
        """
        Clean answer to remove repetitive text, greetings, and unwanted endings.
        
        Args:
            answer: Raw answer from LLM
        
        Returns:
            Cleaned answer
        """
        if not answer:
            return answer
        
        # Remove common unwanted endings
        unwanted_endings = [
            "Best regards",
            "Thank you",
            "Please let me know",
            "If you have any other questions",
            "I will be happy to help",
            "I will do my best to help",
            "[Your Name]",
            "Best regards, [Your Name]",
            "Thank you, [Your Name]"
        ]
        
        # Find and remove unwanted endings
        lines = answer.split('\n')
        cleaned_lines = []
        found_unwanted = False
        
        for line in lines:
            line_stripped = line.strip()
            # Check if this line contains unwanted text
            if any(unwanted in line_stripped for unwanted in unwanted_endings):
                found_unwanted = True
                break  # Stop at first unwanted ending
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines).strip()
        
        # Remove repetitive "Best regards" patterns
        import re
        # Remove multiple occurrences of "Best regards" patterns
        cleaned = re.sub(r'(Best regards[,\s]*\[Your Name\]\s*)+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(Best regards\s*)+', '', cleaned, flags=re.IGNORECASE)
        
        # Remove trailing repetitive phrases
        cleaned = re.sub(r'(\s*Best regards[,\s]*\[Your Name\]\s*)+$', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        return cleaned.strip()
    
    def _detect_and_expand_query(self, question: str) -> tuple:
        """
        Detect if query is a summary/overview type and expand it.
        
        Args:
            question: The user's question
            
        Returns:
            Tuple of (is_summary_query, expanded_query, suggested_k)
        """
        from config.settings import ARISConfig
        
        question_lower = question.lower().strip()
        
        # Keywords that indicate summary/overview queries
        summary_keywords = [
            'summary', 'summarize', 'overview', 'what is this document about',
            'what does this document contain', 'what is in this document',
            'tell me about', 'describe', 'explain this document',
            'what are the main points', 'key points', 'highlights',
            'what is the document about', 'document summary'
        ]
        
        is_summary = any(keyword in question_lower for keyword in summary_keywords)
        
        if is_summary:
            # Expand query to include multiple aspects
            expanded = f"{question} Include: overview, introduction, key points, main topics, important information, highlights, main themes, primary content"
            # Increase k for summaries (more chunks = better coverage)
            summary_config = ARISConfig.get_summary_query_config()
            suggested_k = max(
                int(ARISConfig.DEFAULT_RETRIEVAL_K * summary_config['k_multiplier']),
                summary_config['min_k']
            )
            return True, expanded, suggested_k
        
        return False, question, None
    
    def _get_recent_documents(self, max_age_hours: int = 24) -> List[str]:
        """
        Get list of recently uploaded documents.
        
        Args:
            max_age_hours: Maximum age in hours for a document to be considered "recent"
        
        Returns:
            List of document names that were uploaded recently
        """
        # For now, if document_index_map exists, use all documents in it
        # This can be enhanced later to check actual upload timestamps from registry
        if hasattr(self, 'document_index_map') and self.document_index_map:
            return list(self.document_index_map.keys())
        return []
    
    def _extract_document_number(self, filename: str) -> Optional[int]:
        """
        Extract document number from filename like 'file (1).pdf' -> 1
        
        Args:
            filename: Document filename (with or without path)
        
        Returns:
            Document number if found, None otherwise
        """
        import re
        # Extract just the filename if path is included
        basename = os.path.basename(filename) if filename else ""
        # Look for pattern like "(1)", "(2)", etc.
        match = re.search(r'\((\d+)\)', basename)
        return int(match.group(1)) if match else None
    
    def query_with_rag(
        self,
        question: str,
        k: int = None,
        use_mmr: bool = None,
        use_hybrid_search: bool = None,
        semantic_weight: float = None,
        search_mode: str = None,
        use_agentic_rag: bool = None,
        temperature: float = None,  # NEW: UI temperature
        max_tokens: int = None  # NEW: UI max_tokens
    ) -> Dict:
        """
        Query the RAG system with maximum accuracy settings.
        
        Args:
            question: The question to answer
            k: Number of chunks to retrieve (default from config for maximum accuracy)
            use_mmr: Use Maximum Marginal Relevance (default True for best accuracy)
            use_hybrid_search: Use hybrid search combining semantic and keyword (default from config)
            semantic_weight: Weight for semantic search in hybrid mode (0.0-1.0, default 0.7)
            search_mode: Search mode - 'semantic', 'keyword', or 'hybrid' (default from config)
        
        Returns:
            Dict with answer, sources, and context chunks
        """
        from config.settings import ARISConfig
        
        # Use accuracy-optimized defaults if not specified
        if k is None:
            k = ARISConfig.DEFAULT_RETRIEVAL_K
        if use_mmr is None:
            use_mmr = ARISConfig.DEFAULT_USE_MMR
        
        # Get hybrid search config
        hybrid_config = ARISConfig.get_hybrid_search_config()
        if use_hybrid_search is None:
            use_hybrid_search = hybrid_config['use_hybrid_search']
        if semantic_weight is None:
            semantic_weight = hybrid_config['semantic_weight']
        if search_mode is None:
            search_mode = hybrid_config['search_mode']
        
        # Determine if we should use hybrid search based on mode
        if search_mode == 'hybrid':
            use_hybrid_search = True
        elif search_mode == 'keyword':
            use_hybrid_search = True
            semantic_weight = 0.0  # Keyword only
        elif search_mode == 'semantic':
            use_hybrid_search = False
        
        keyword_weight = 1.0 - semantic_weight
        
        query_start_time = time_module.time()
        
        # Store UI configuration for citation extraction and LLM calls
        self.ui_config = {
            'temperature': temperature if temperature is not None else ARISConfig.DEFAULT_TEMPERATURE,
            'max_tokens': max_tokens if max_tokens is not None else ARISConfig.DEFAULT_MAX_TOKENS,
            'active_sources': self.active_sources
        }
        
        if self.vectorstore is None:
            return {
                "answer": "No documents have been uploaded yet. Please upload documents first.",
                "sources": [],
                "context_chunks": [],
                "citations": [],
                "num_chunks_used": 0,
                "response_time": 0.0,
                "context_tokens": 0,
                "response_tokens": 0,
                "total_tokens": 0
            }
        
        # Log active document filter status
        if self.active_sources:
            logger.info(f"Document filter active: {self.active_sources} - queries will only search within these documents")
        else:
            logger.info("No document filter - queries will search across all documents")
        
        # NEW: Detect and expand summary queries
        is_summary_query, expanded_question, suggested_k = self._detect_and_expand_query(question)
        
        # Use expanded question for retrieval (but keep original for answer generation)
        retrieval_question = expanded_question if is_summary_query else question
        
        # Increase k for summary queries
        if is_summary_query and suggested_k:
            if k is None:
                k = suggested_k
            else:
                k = max(k, suggested_k)
            logger.info(f"Summary query detected - increasing k to {k} for better coverage")
        
        # Get Agentic RAG config
        agentic_config = ARISConfig.get_agentic_rag_config()
        summary_config = ARISConfig.get_summary_query_config()
        
        # For summary queries, auto-enable Agentic RAG if configured
        if is_summary_query and use_agentic_rag is None and summary_config['auto_enable_agentic']:
            use_agentic_rag = True
            logger.info("Summary query detected - auto-enabling Agentic RAG for better coverage")
        elif use_agentic_rag is None:
            use_agentic_rag = agentic_config['use_agentic_rag']
        
        # Agentic RAG: Decompose query and perform multi-query retrieval
        if use_agentic_rag:
            try:
                from rag.query_decomposer import QueryDecomposer
                
                # Initialize query decomposer
                query_decomposer = QueryDecomposer(
                    llm_model=self.openai_model,
                    openai_api_key=self.openai_api_key
                )
                
                # Decompose query into sub-queries (use retrieval_question for better decomposition)
                sub_queries = query_decomposer.decompose_query(
                    retrieval_question,  # Use expanded question for decomposition
                    max_subqueries=agentic_config['max_sub_queries']
                )
                
                logger.info(f"Agentic RAG: Decomposed query into {len(sub_queries)} sub-queries")
                
                # If decomposition resulted in single query, use standard flow
                if len(sub_queries) == 1:
                    logger.info("Agentic RAG: Single query after decomposition, using standard retrieval")
                    use_agentic_rag = False
                else:
                    # Perform multi-query retrieval
                    all_chunks = []
                    chunks_per_subquery = agentic_config['chunks_per_subquery']
                    
                    for sub_query in sub_queries:
                        try:
                            # Retrieve chunks for this sub-query
                            sub_chunks = self._retrieve_chunks_for_query(
                                sub_query,
                                k=chunks_per_subquery,
                                use_mmr=use_mmr,
                                use_hybrid_search=use_hybrid_search,
                                semantic_weight=semantic_weight,
                                keyword_weight=keyword_weight,
                                search_mode=search_mode
                            )
                            all_chunks.extend(sub_chunks)
                            logger.info(f"Retrieved {len(sub_chunks)} chunks for sub-query: {sub_query[:50]}...")
                        except Exception as e:
                            logger.warning(f"Failed to retrieve chunks for sub-query '{sub_query[:50]}...': {e}")
                            continue
                    
                    if not all_chunks:
                        logger.warning("Agentic RAG: No chunks retrieved from any sub-query, falling back to standard retrieval")
                        use_agentic_rag = False
                    else:
                        # Deduplicate chunks
                        unique_chunks = self._deduplicate_chunks(
                            all_chunks,
                            threshold=agentic_config['deduplication_threshold']
                        )
                        
                        # Limit total chunks
                        max_total_chunks = agentic_config['max_total_chunks']
                        relevant_docs = unique_chunks[:max_total_chunks]
                        
                        # Re-apply active_sources filter after deduplication (strict filtering)
                        if self.active_sources:
                            allowed_sources = set(self.active_sources)
                            # Also create normalized versions for case-insensitive matching
                            allowed_sources_normalized = {s.lower().strip() if s else "" for s in allowed_sources if s}
                            allowed_filenames = {os.path.basename(s).lower().strip() if s else "" for s in allowed_sources if s}
                            
                            filtered_docs = []
                            for doc in relevant_docs:
                                doc_source = doc.metadata.get('source', '')
                                if not doc_source:
                                    continue
                                
                                # Try multiple matching strategies
                                matched = False
                                # Strategy 1: Exact match
                                if doc_source in allowed_sources:
                                    matched = True
                                # Strategy 2: Case-insensitive match
                                elif doc_source.lower().strip() in allowed_sources_normalized:
                                    matched = True
                                # Strategy 3: Filename match
                                elif os.path.basename(doc_source).lower().strip() in allowed_filenames:
                                    matched = True
                                
                                if matched:
                                    filtered_docs.append(doc)
                            
                            if filtered_docs:
                                relevant_docs = filtered_docs
                                logger.info(f"Agentic RAG: After filtering, {len(relevant_docs)} chunks from selected documents: {self.active_sources}")
                            else:
                                logger.warning(f"Agentic RAG: No chunks matched selected documents: {self.active_sources}. Available sources: {set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])}")
                                relevant_docs = []  # Return empty if no matches
                        
                        logger.info(f"Agentic RAG: Retrieved {len(all_chunks)} total chunks, {len(unique_chunks)} unique, using top {len(relevant_docs)}")
                        
                        # Use synthesis for answer generation
                        return self._synthesize_agentic_results(
                            question=question,
                            sub_queries=sub_queries,
                            relevant_docs=relevant_docs,
                            query_start_time=query_start_time
                        )
            except Exception as e:
                logger.warning(f"Agentic RAG failed: {e}. Falling back to standard retrieval.", exc_info=True)
                use_agentic_rag = False
        
        # Standard RAG flow (or fallback from Agentic RAG)
        # Initialize flag to track if we should skip retriever logic
        skip_retriever_logic = False
        retriever = None  # Initialize retriever to None
        
        # For OpenSearch: Use per-document indexes instead of metadata filtering
        if self.vector_store_type == "opensearch":
            # Determine which index(es) to search
            indexes_to_search = []
            
            if self.active_sources:
                # Search only indexes for selected documents
                for doc_name in self.active_sources:
                    if doc_name in self.document_index_map:
                        indexes_to_search.append(self.document_index_map[doc_name])
                    else:
                        logger.warning(f"Document '{doc_name}' not found in index map. Available: {list(self.document_index_map.keys())}")
                
                if not indexes_to_search:
                    return {
                        "answer": "No indexes found for selected documents. Please reprocess the documents.",
                        "sources": [],
                        "citations": [],
                        "context_chunks": []
                    }
            else:
                # No active_sources set - use recent documents for better isolation
                recent_docs = self._get_recent_documents(max_age_hours=24)
                if recent_docs:
                    indexes_to_search = [self.document_index_map[doc] for doc in recent_docs if doc in self.document_index_map]
                    logger.info(f"No active_sources set, using {len(indexes_to_search)} recent document indexes: {recent_docs}")
                else:
                    # Fallback: search all document indexes (but log warning)
                    indexes_to_search = list(self.document_index_map.values()) if hasattr(self, 'document_index_map') else []
                    logger.warning("No recent documents found, searching all indexes (may include old documents)")
                
                if not indexes_to_search:
                    # Fallback to default index if no mappings exist (backward compatibility)
                    indexes_to_search = [self.opensearch_index or "aris-rag-index"]
                    logger.info(f"No document index mappings found, using default index: {indexes_to_search[0]}")
            
            # Initialize multi-index manager if needed
            if not hasattr(self, 'multi_index_manager'):
                from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                self.multi_index_manager = OpenSearchMultiIndexManager(
                    embeddings=self.embeddings,
                    domain=self.opensearch_domain,
                    region=getattr(self, 'region', None)
                )
            
            # Search across selected indexes
            if len(indexes_to_search) == 1:
                # Single index - use it directly (more efficient)
                index_name = indexes_to_search[0]
                store = self.multi_index_manager.get_or_create_index_store(index_name)
                
                # Use hybrid search if enabled
                if use_hybrid_search:
                    try:
                        from vectorstores.opensearch_store import OpenSearchVectorStore
                        query_vector = self.embeddings.embed_query(retrieval_question)
                        relevant_docs = store.hybrid_search(
                            query=retrieval_question,
                            query_vector=query_vector,
                            k=k,
                            semantic_weight=semantic_weight,
                            keyword_weight=keyword_weight,
                            filter=None  # No filter needed with per-document indexes
                        )
                        logger.info(f"Hybrid search completed: {len(relevant_docs)} results from index '{index_name}'")
                    except Exception as e:
                        logger.warning(f"Hybrid search failed, falling back to standard search: {e}")
                        # Fall through to standard search
                        if use_mmr:
                            from config.settings import ARISConfig
                            fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                            lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                            retriever = store.vectorstore.as_retriever(
                                search_type="mmr",
                                search_kwargs={
                                    "k": k,
                                    "fetch_k": fetch_k,
                                    "lambda_mult": lambda_mult
                                }
                            )
                        else:
                            retriever = store.vectorstore.as_retriever(
                                search_kwargs={"k": k}
                            )
                        relevant_docs = retriever.invoke(retrieval_question)
                else:
                    # Standard search
                    if use_mmr:
                        from config.settings import ARISConfig
                        fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                        lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                        retriever = store.vectorstore.as_retriever(
                            search_type="mmr",
                            search_kwargs={
                                "k": k,
                                "fetch_k": fetch_k,
                                "lambda_mult": lambda_mult
                            }
                        )
                    else:
                        retriever = store.vectorstore.as_retriever(
                            search_kwargs={"k": k}
                        )
                    relevant_docs = retriever.invoke(retrieval_question)
            else:
                # Multiple indexes - search across all
                from config.settings import ARISConfig
                relevant_docs = self.multi_index_manager.search_across_indexes(
                    query=retrieval_question,
                    index_names=indexes_to_search,
                    k=k,
                    use_mmr=use_mmr,
                    fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K if use_mmr else 50,
                    lambda_mult=ARISConfig.DEFAULT_MMR_LAMBDA if use_mmr else 0.3
                )
            
            logger.info(f"Searched {len(indexes_to_search)} index(es): {indexes_to_search}, found {len(relevant_docs)} results")
            
            # Skip metadata filtering (not needed with per-document indexes)
            # Skip the old search logic below - we already have relevant_docs
            # Continue with citation creation below (skip to line ~1736)
            skip_retriever_logic = True
            # Initialize opensearch_filter even in per-doc path (may be used in error handling)
            opensearch_filter = None
        else:
            skip_retriever_logic = False
            # FAISS or OpenSearch without per-document indexes: Use existing filter logic
            # Prepare filter for OpenSearch (different syntax than FAISS)
            opensearch_filter = None
            if self.active_sources and self.vector_store_type.lower() == "opensearch":
                # Filter out None/empty values and construct OpenSearch filter
                valid_sources = [s for s in self.active_sources if s and s.strip()]
                if valid_sources:
                    if len(valid_sources) == 1:
                        # Single source: use term filter
                        opensearch_filter = {"term": {"metadata.source.keyword": valid_sources[0]}}
                    else:
                        # Multiple sources: use terms filter
                        opensearch_filter = {"terms": {"metadata.source.keyword": valid_sources}}
            
            # Use hybrid search if enabled and OpenSearch is available (for non-per-doc path)
            if use_hybrid_search and self.vector_store_type.lower() == "opensearch":
                try:
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    
                    # Check if vectorstore is OpenSearchVectorStore (handle both direct and wrapped)
                    is_opensearch = False
                    if self.vectorstore is not None:
                        if isinstance(self.vectorstore, OpenSearchVectorStore):
                            is_opensearch = True
                        elif hasattr(self.vectorstore, '__class__') and 'OpenSearch' in self.vectorstore.__class__.__name__:
                            is_opensearch = True
                    
                    if is_opensearch:
                        # Get query embedding (use retrieval_question for better matching)
                        query_vector = self.embeddings.embed_query(retrieval_question)
                        
                        # Perform hybrid search (use retrieval_question for better matching)
                        relevant_docs = self.vectorstore.hybrid_search(
                            query=retrieval_question,
                            query_vector=query_vector,
                            k=k,
                            semantic_weight=semantic_weight,
                            keyword_weight=keyword_weight,
                            filter=opensearch_filter
                        )
                        
                        logger.info(f"Hybrid search completed: {len(relevant_docs)} results (mode={search_mode}, semantic_weight={semantic_weight:.2f})")
                    else:
                        # Fallback to standard search
                        relevant_docs = None
                except Exception as e:
                    logger.warning(f"Hybrid search failed, falling back to semantic search: {str(e)}")
                    relevant_docs = None
            else:
                relevant_docs = None
        
        # Initialize opensearch_filter if not already set (safety check for all code paths)
        if 'opensearch_filter' not in locals():
            opensearch_filter = None
        
        # If hybrid search didn't work or wasn't used, use standard search
        # Skip if we already have relevant_docs from per-document index path
        if relevant_docs is None and not skip_retriever_logic:
            # Retrieve relevant documents with MMR optimized for maximum accuracy
            if use_mmr:
                # Use MMR with accuracy-optimized parameters
                from config.settings import ARISConfig
                fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                
                # Build search_kwargs with appropriate filter
                # For FAISS: Increase k when filtering is needed (FAISS doesn't support native filtering)
                # We'll retrieve more and filter post-retrieval
                effective_k = k
                if self.active_sources and self.vector_store_type.lower() != "opensearch":
                    # Increase k to account for post-filtering (retrieve 3-5x more to ensure we get enough after filtering)
                    effective_k = k * 4
                    fetch_k = max(fetch_k, effective_k * 2)  # Also increase fetch_k for MMR
                    logger.info(f"FAISS filtering active: Increasing k from {k} to {effective_k} to account for post-filtering")
                
                search_kwargs = {
                    "k": effective_k,
                    "fetch_k": fetch_k,  # Large candidate pool for best selection
                    "lambda_mult": lambda_mult,  # Prioritize relevance (lower = more relevant)
                }
                
                # Add filter only for OpenSearch (FAISS doesn't support native filtering)
                if opensearch_filter:
                    search_kwargs["filter"] = opensearch_filter
                # Note: FAISS filtering is done post-retrieval, not via search_kwargs
                
                retriever = self.vectorstore.as_retriever(
                    search_type="mmr",
                    search_kwargs=search_kwargs
                )
            else:
                # Standard similarity search
                # For FAISS: Increase k when filtering is needed (FAISS doesn't support native filtering)
                effective_k = k
                if self.active_sources and self.vector_store_type.lower() != "opensearch":
                    # Increase k to account for post-filtering (retrieve 3-5x more to ensure we get enough after filtering)
                    effective_k = k * 4
                    logger.info(f"FAISS filtering active: Increasing k from {k} to {effective_k} to account for post-filtering")
                
                search_kwargs = {"k": effective_k}
                
                # Add filter only for OpenSearch (FAISS doesn't support native filtering)
                if opensearch_filter:
                    search_kwargs["filter"] = opensearch_filter
                # Note: FAISS filtering is done post-retrieval, not via search_kwargs
                
                retriever = self.vectorstore.as_retriever(
                    search_kwargs=search_kwargs
                )
        
        # Use invoke for newer LangChain versions, fallback to get_relevant_documents
        # Use retrieval_question for better matching (expanded for summaries)
        # Only use retriever if we don't already have relevant_docs (from per-doc index path)
        if not skip_retriever_logic and retriever is not None:
            try:
                relevant_docs = retriever.invoke(retrieval_question)
            except AttributeError:
                # Fallback for older versions
                relevant_docs = retriever.get_relevant_documents(retrieval_question)
            except Exception as e:
                error_str = str(e)
                # Check for dimension mismatch error
                if 'dimension' in error_str.lower() or 'invalid dimension' in error_str.lower():
                    logger.error(f"Embedding dimension mismatch error: {error_str}")
                    return {
                        "answer": (
                            f"❌ **Embedding Model Mismatch Error**\n\n"
                            f"The OpenSearch index was created with a different embedding model than the one currently configured.\n\n"
                            f"**Error:** {error_str}\n\n"
                            f"**Solution:**\n"
                            f"1. Check which embedding model was used to create the index (likely 'text-embedding-3-small' with 1536 dimensions)\n"
                            f"2. Set `EMBEDDING_MODEL=text-embedding-3-small` in your .env file, OR\n"
                            f"3. Recreate the index by re-uploading all documents with the current embedding model\n\n"
                            f"**Current embedding model:** {self.embedding_model}\n"
                            f"**Expected:** The model used when the index was created"
                        ),
                        "sources": [],
                        "citations": [],
                        "context_chunks": []
                    }
                raise

        # If UI selected specific documents, filter results to those sources (strict filtering with robust matching)
        # Skip this for OpenSearch with per-document indexes (already isolated by index)
        if self.active_sources and not (self.vector_store_type == "opensearch" and self.document_index_map):
            allowed_sources = set(self.active_sources)
            # Also create normalized versions for case-insensitive matching
            allowed_sources_normalized = {s.lower().strip() if s else "" for s in allowed_sources if s}
            allowed_filenames = {os.path.basename(s).lower().strip() if s else "" for s in allowed_sources if s}
            
            def matches_source(doc_source, doc_text=""):
                """Check if document source matches any allowed source using multiple strategies"""
                if not doc_source:
                    # If no metadata source, try extracting from text markers
                    if doc_text:
                        # Look for source markers in text (e.g., "Source: filename.pdf")
                        import re
                        source_patterns = [
                            r"Source:\s*([^\n]+)",
                            r"Document:\s*([^\n]+)",
                            r"File:\s*([^\n]+)",
                        ]
                        for pattern in source_patterns:
                            match = re.search(pattern, doc_text, re.IGNORECASE)
                            if match:
                                extracted_source = match.group(1).strip()
                                # Check if extracted source matches
                                if extracted_source in allowed_sources or \
                                   extracted_source.lower().strip() in allowed_sources_normalized or \
                                   os.path.basename(extracted_source).lower().strip() in allowed_filenames:
                                    return True
                    return False
                # Strategy 1: Exact match
                if doc_source in allowed_sources:
                    return True
                # Strategy 2: Case-insensitive match
                if doc_source.lower().strip() in allowed_sources_normalized:
                    return True
                # Strategy 3: Filename match
                doc_filename = os.path.basename(doc_source).lower().strip()
                if doc_filename in allowed_filenames:
                    return True
                # Strategy 4: Check if any allowed source is contained in doc_source (for path variations)
                for allowed in allowed_sources:
                    if allowed and allowed.lower() in doc_source.lower():
                        return True
                return False
            
            # Filter with strict matching
            filtered_docs = [
                doc for doc in relevant_docs 
                if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
            ]
            
            # Validate: Ensure NO documents from other sources slipped through
            invalid_sources = set()
            for doc in filtered_docs:
                doc_source = doc.metadata.get('source', '')
                if doc_source and not matches_source(doc_source):
                    invalid_sources.add(doc_source)
            
            if invalid_sources:
                logger.warning(f"Document mixing detected! Found invalid sources in filtered results: {invalid_sources}")
                # Remove invalid sources
                filtered_docs = [
                    doc for doc in filtered_docs 
                    if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
                ]

            # If none found, retry with a broader pull and then filter
            if not filtered_docs:
                try:
                    # Use effective_k if available (from FAISS filtering), otherwise use k * 4
                    retry_k = effective_k if 'effective_k' in locals() else k * 4
                    alt_docs = self.vectorstore.similarity_search(retrieval_question, k=max(retry_k, 20))
                    filtered_docs = [
                        doc for doc in alt_docs 
                        if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
                    ]
                except Exception:
                    filtered_docs = []

            if not filtered_docs:
                return {
                    "answer": (
                        "No chunks were found for the selected document(s). "
                        "Try selecting a different document or load all documents."
                    ),
                    "sources": [],
                    "citations": [],
                    "context_chunks": []
                }
            
            # Final validation: Log document isolation status
            # For OpenSearch: Validate that native filtering worked correctly (safety check)
            # For FAISS: This is the primary filtering mechanism
            final_sources = set(doc.metadata.get('source', 'Unknown') for doc in filtered_docs[:k])
            logger.info(f"Document filtering: Retrieved {len(filtered_docs)} docs, limiting to {k}. Final sources: {final_sources}")
            
            # Validate document isolation (should be empty for both OpenSearch and FAISS)
            invalid_final_sources = final_sources - allowed_sources
            if invalid_final_sources:
                logger.error(f"CRITICAL: Document mixing detected! Allowed: {allowed_sources}, Found: {final_sources}, Invalid: {invalid_final_sources}")
                # For OpenSearch, this shouldn't happen if filtering is working correctly
                if self.vector_store_type.lower() == "opensearch":
                    logger.error(f"OpenSearch native filtering may have failed! Filter was: {opensearch_filter}")
                # Remove invalid sources as a safety measure
                filtered_docs = [
                    doc for doc in filtered_docs 
                    if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
                ]
                final_sources = set(doc.metadata.get('source', 'Unknown') for doc in filtered_docs[:k])
                logger.info(f"After removing invalid sources: {len(filtered_docs)} docs, Final sources: {final_sources}")
            
            relevant_docs = filtered_docs[:k]  # Limit to requested k after filtering
        
        # Build context with metadata for better accuracy and collect citations
        context_parts = []
        citations = []  # Store citation information for each source
        
        # Try to get similarity scores if available (for ranking)
        doc_scores = {}
        doc_order_scores = {}  # Use retrieval order as proxy for relevance when scores unavailable
        
        # First, try to get scores using similarity_search_with_score directly
        try:
            if hasattr(self.vectorstore, 'similarity_search_with_score'):
                # Get more results to ensure we have scores for all retrieved docs
                scored_docs = self.vectorstore.similarity_search_with_score(retrieval_question, k=max(len(relevant_docs) * 2, 20))
                
                # Create a mapping of document content to scores
                for scored_doc, score in scored_docs:
                    if hasattr(scored_doc, 'page_content'):
                        # Use first 200 chars for better matching (more unique than 100)
                        doc_content = scored_doc.page_content[:200]
                        # Also try matching by full content hash
                        import hashlib
                        content_hash = hashlib.md5(scored_doc.page_content.encode('utf-8')).hexdigest()
                        score_val = float(score) if score is not None else 0.0
                        doc_scores[doc_content] = score_val
                        doc_scores[content_hash] = score_val
        except Exception as e:
            logger.debug(f"Could not retrieve similarity scores: {e}")
        
        # Use retrieval order as a proxy for relevance (earlier = more relevant)
        # This helps when similarity scores aren't available
        for idx, doc in enumerate(relevant_docs):
            # Normalize order score: first doc = 1.0, last = 0.0
            order_score = 1.0 - (idx / max(len(relevant_docs), 1))
            if hasattr(doc, 'page_content'):
                doc_content = doc.page_content[:200]
                import hashlib
                content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
                doc_order_scores[doc_content] = order_score
                doc_order_scores[content_hash] = order_score
        
        for i, doc in enumerate(relevant_docs, 1):
            import re
            
            # Extract citation metadata - use helper method for consistent extraction
            chunk_text = doc.page_content
            
            # Validate document has metadata before extraction
            if not hasattr(doc, 'metadata') or not doc.metadata:
                logger.warning(f"Document at index {i} missing metadata during citation creation (standard RAG)")
                doc.metadata = {}
            
            # Build UI config from current state
            ui_config = getattr(self, 'ui_config', {
                'temperature': ARISConfig.DEFAULT_TEMPERATURE,
                'max_tokens': ARISConfig.DEFAULT_MAX_TOKENS,
                'active_sources': self.active_sources
            })
            
            # Extract source with confidence score
            # Get sources list if available (from relevant_docs metadata)
            available_sources = list(set([d.metadata.get('source', 'Unknown') for d in relevant_docs if hasattr(d, 'metadata') and d.metadata.get('source')]))
            source, source_confidence = self._extract_source_from_chunk(doc, chunk_text, available_sources if available_sources else None, ui_config=ui_config)
            
            # Validate source was extracted successfully
            if not source or source == 'Unknown':
                logger.warning(f"Could not extract valid source for citation {i} (standard RAG). Chunk preview: {chunk_text[:100]}...")
            
            # Extract page number with confidence score
            page, page_confidence = self._extract_page_number(doc, chunk_text)
            
            start_char = doc.metadata.get('start_char', None)
            end_char = doc.metadata.get('end_char', None)
            
            # Check for image references in metadata
            image_ref = None
            image_info = None
            page_blocks = doc.metadata.get('page_blocks', [])
            
            # Check if this chunk is associated with an image
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'image':
                        if page and block.get('page') == page:
                            image_ref = {
                                'page': block.get('page'),
                                'image_index': block.get('image_index'),
                                'bbox': block.get('bbox'),
                                'xref': block.get('xref')
                            }
                            image_info = f"Image {block.get('image_index', '?')} on Page {page}"
                            break
            
            # Also check if chunk metadata has image reference
            if not image_ref:
                if doc.metadata.get('has_image') or doc.metadata.get('image_index') is not None:
                    image_ref = {
                        'page': page,
                        'image_index': doc.metadata.get('image_index'),
                        'bbox': doc.metadata.get('image_bbox')
                    }
                    image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}" if page else "Image reference"
            
            # Generate context-aware snippet using query
            snippet_clean = self._generate_context_snippet(chunk_text, question, max_length=500)
            
            # Build source location description (certification field)
            source_location_parts = []
            if page:
                source_location_parts.append(f"Page {page}")
            
            # Only add image info if this specific chunk has an image reference
            if image_ref:
                # This chunk is actually associated with an image
                image_index = image_ref.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            elif doc.metadata.get('has_image') and doc.metadata.get('image_index') is not None:
                # Chunk metadata indicates it has an image reference
                image_index = doc.metadata.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            # REMOVED: Don't use document-level images_detected - it's too broad and misleading
            
            source_location = " | ".join(source_location_parts) if source_location_parts else "Text content"
            
            # Extract section/heading information from page_blocks if available
            section = None
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'heading':
                        section = block.get('text', '')
                        break
            
            # Determine extraction method based on confidence scores
            extraction_method = 'metadata' if source_confidence >= 0.7 else ('text_marker' if source_confidence >= 0.3 else 'fallback')
            
            # Get similarity score if available (for ranking)
            similarity_score = None
            doc_content_key = chunk_text[:200] if chunk_text else ""
            import hashlib
            content_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest() if chunk_text else ""
            
            # Try multiple matching strategies
            if doc_content_key in doc_scores:
                similarity_score = doc_scores[doc_content_key]
            elif content_hash in doc_scores:
                similarity_score = doc_scores[content_hash]
            # Use order-based score as fallback
            elif doc_content_key in doc_order_scores:
                # Convert order score to similarity-like score (0.5 to 1.0 range)
                order_score = doc_order_scores[doc_content_key]
                similarity_score = 0.5 + (order_score * 0.5)  # Map 0.0-1.0 order to 0.5-1.0 similarity
            elif content_hash in doc_order_scores:
                order_score = doc_order_scores[content_hash]
                similarity_score = 0.5 + (order_score * 0.5)
            # Also try to get from metadata if stored there
            elif hasattr(doc, 'metadata') and 'similarity_score' in doc.metadata:
                similarity_score = doc.metadata.get('similarity_score')
            
            # Build citation entry with enhanced metadata including confidence scores
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'source_confidence': source_confidence,
                'page': page,
                'page_confidence': page_confidence,
                'section': section,
                'snippet': snippet_clean,
                'full_text': chunk_text,
                'start_char': start_char,
                'end_char': end_char,
                'chunk_index': doc.metadata.get('chunk_index', None),
                'image_ref': image_ref,  # Image reference if available
                'image_info': image_info,  # Human-readable image info
                'source_location': source_location,  # Certification field: exact location
                'content_type': 'image' if image_ref else 'text',  # Type of content
                'extraction_method': extraction_method,  # How source was extracted
                'similarity_score': similarity_score  # Vector similarity score for ranking
            }
            citations.append(citation)
            logger.debug(f"Citation {i}: source='{source}', page={page}, chunk_index={citation.get('chunk_index', 'N/A')}")
            
            # Add source and page info to context
            page_info = f" (Page {page})" if page else ""
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{chunk_text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Detect if question mentions a specific document name and prioritize it
        question_lower = question.lower()
        mentioned_documents = []
        all_document_names = set()
        
        # First, collect all document names from retrieved docs
        for doc in relevant_docs:
            if hasattr(doc, 'metadata') and doc.metadata:
                source = doc.metadata.get('source', '')
                if source:
                    all_document_names.add(source)
        
        # Extract document number from question if mentioned (e.g., "(1)", "(2)")
        import re
        question_doc_number = None
        question_number_match = re.search(r'\((\d+)\)', question)
        if question_number_match:
            question_doc_number = int(question_number_match.group(1))
            logger.info(f"Question mentions document number: ({question_doc_number})")
        
        # Check if question mentions any document name
        for source in all_document_names:
            source_name = os.path.basename(source).lower()
            source_name_no_ext = source_name.replace('.pdf', '').replace('.docx', '').replace('.txt', '')
            
            # Extract document number from source filename
            source_doc_number = self._extract_document_number(source)
            
            # If question mentions a specific document number, require exact match
            if question_doc_number is not None:
                if source_doc_number == question_doc_number:
                    # Exact number match - check if base name also matches
                    # Remove number from both for comparison
                    base_name_question = re.sub(r'\s*\(\d+\)', '', question_lower)
                    base_name_source = re.sub(r'\s*\(\d+\)', '', source_name_no_ext)
                    
                    # Check if base names match (allowing for partial matches)
                    if (base_name_source in base_name_question or 
                        base_name_question in base_name_source or
                        any(word in base_name_question for word in base_name_source.split() if len(word) > 3)):
                        mentioned_documents.append(source)
                        logger.info(f"Exact document number match: {os.path.basename(source)} (number: {source_doc_number})")
                # If numbers don't match, skip this document
                continue
            
            # No specific number mentioned - use original matching logic
            # Check various ways document might be mentioned
            if (source_name in question_lower or 
                source_name_no_ext in question_lower or
                any(word in question_lower for word in source_name_no_ext.split('_') if len(word) > 3) or
                any(word in question_lower for word in source_name_no_ext.split('-') if len(word) > 3) or
                any(word in question_lower for word in source_name_no_ext.split() if len(word) > 3)):
                mentioned_documents.append(source)
        
        # If a specific document is mentioned, prioritize chunks from that document
        # CRITICAL FIX: If a specific document NUMBER is mentioned (e.g., "(2)"), STRICTLY filter to only that document
        if mentioned_documents:
            # Check if question mentions a specific document number
            if question_doc_number is not None:
                # STRICT FILTERING: Only include chunks from the mentioned document
                filtered_docs = []
                for doc in relevant_docs:
                    if hasattr(doc, 'metadata') and doc.metadata:
                        source = doc.metadata.get('source', '')
                        if source in mentioned_documents:
                            filtered_docs.append(doc)
                    # Skip documents not in mentioned_documents
                
                if filtered_docs:
                    relevant_docs = filtered_docs
                    logger.info(f"🔍 STRICT FILTER: Filtered to {len(filtered_docs)} chunks from mentioned document: {[os.path.basename(d) for d in mentioned_documents]}")
                else:
                    logger.warning(f"⚠️  No chunks found for mentioned document: {[os.path.basename(d) for d in mentioned_documents]}")
            else:
                # No specific number - just prioritize (original behavior)
                prioritized_docs = []
                other_docs = []
                for doc in relevant_docs:
                    if hasattr(doc, 'metadata') and doc.metadata:
                        source = doc.metadata.get('source', '')
                        if source in mentioned_documents:
                            prioritized_docs.append(doc)
                        else:
                            other_docs.append(doc)
                    else:
                        other_docs.append(doc)
                relevant_docs = prioritized_docs + other_docs
                logger.info(f"Prioritized {len(prioritized_docs)} chunks from mentioned document(s): {[os.path.basename(d) for d in mentioned_documents]}")
        
        # Extract image content from chunks for image-related questions
        image_content_map = {}  # Map: (source, image_index) -> content
        is_image_question = any(keyword in question_lower for keyword in ['image', 'picture', 'figure', 'diagram', 'photo', 'what.*image', 'information.*image', 'content.*image', 'drawer'])
        
        # Phase 1: Detect tool/item names in questions
        tool_item_keywords = [
            'mallet', 'wrench', 'socket', 'screwdriver', 'hammer', 'pliers', 
            'drill', 'cutter', 'snips', 'ratchet', 'extension', 'allen',
            'tool', 'part', 'item', 'drawer', 'find', 'where', 'location'
        ]
        is_tool_item_question = any(keyword in question_lower for keyword in tool_item_keywords)
        
        # Also detect part number patterns (e.g., "65300", "65300122")
        import re
        part_number_pattern = r'\b\d{5,}\b'  # 5+ digit numbers (likely part numbers)
        has_part_number = bool(re.search(part_number_pattern, question))
        
        # Combine with image question detection
        should_extract_image_content = is_image_question or is_tool_item_question or has_part_number
        
        # Extract tool/item names from question for targeted search
        tool_item_names = []
        for keyword in tool_item_keywords:
            if keyword in question_lower:
                tool_item_names.append(keyword)
        
        # Also extract potential tool names (capitalized words, part numbers)
        words = question.split()
        capitalized_words = [w for w in words if w and w[0].isupper() and len(w) > 3]
        tool_item_names.extend([w.lower() for w in capitalized_words])
        
        # Extract part numbers from question
        part_numbers = re.findall(part_number_pattern, question)
        tool_item_names.extend(part_numbers)
        
        # Remove duplicates and log
        tool_item_names = list(set(tool_item_names))
        if is_tool_item_question or has_part_number:
            logger.info(f"🔧 Tool/item question detected: {tool_item_names}")
            logger.info(f"🔍 Will expand search for tool/item names in image content")
        
        # CRITICAL: Check if any documents have images detected - if so, ALWAYS search for image chunks
        # This ensures image content is retrieved even if similarity search doesn't return those chunks
        documents_with_images = set()
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rag_system.py:2136","message":"Checking document metadata for images","data":{"total_docs":len(relevant_docs)},"timestamp":int(time_module.time()*1000)})+"\n")
        except: pass
        # #endregion
        for doc in relevant_docs:
            if hasattr(doc, 'metadata') and doc.metadata:
                # #region agent log
                try:
                    with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rag_system.py:2140","message":"Document metadata check","data":{"has_metadata":True,"images_detected":doc.metadata.get('images_detected',False),"image_count":doc.metadata.get('image_count',0),"source":doc.metadata.get('source','')[:50]},"timestamp":int(time_module.time()*1000)})+"\n")
                except: pass
                # #endregion
                if (doc.metadata.get('images_detected', False) or 
                    doc.metadata.get('image_count', 0) > 0):
                    source = doc.metadata.get('source', '')
                    if source:
                        documents_with_images.add(source)
                        # #region agent log
                        try:
                            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                import json
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rag_system.py:2143","message":"Document added to images set","data":{"source":source[:50],"total_with_images":len(documents_with_images)},"timestamp":int(time_module.time()*1000)})+"\n")
                        except: pass
                        # #endregion
        
        # Also check mentioned documents for image metadata
        for mentioned_source in mentioned_documents:
            # Try to find chunks from this document to check metadata
            for doc in relevant_docs:
                if hasattr(doc, 'metadata') and doc.metadata:
                    doc_source = doc.metadata.get('source', '')
                    if doc_source == mentioned_source:
                        if (doc.metadata.get('images_detected', False) or 
                            doc.metadata.get('image_count', 0) > 0):
                            documents_with_images.add(mentioned_source)
                            break
        
        # IMPORTANT: Always check for image markers in retrieved chunks, not just for image questions
        # This ensures image content is extracted even if question doesn't explicitly mention "image"
        # Also expand search to find chunks with image markers if documents have images OR it's an image question OR tool/item question
        additional_image_docs = []
        should_search_for_images = should_extract_image_content or len(documents_with_images) > 0
        
        if should_search_for_images and self.vectorstore is not None:
            logger.info(f"Searching for image chunks: image_question={is_image_question}, documents_with_images={len(documents_with_images)}")
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rag_system.py:2163","message":"Starting image chunk search","data":{"should_search":True,"has_vectorstore":True,"image_question":is_image_question,"documents_with_images_count":len(documents_with_images)},"timestamp":int(time_module.time()*1000)})+"\n")
            except: pass
            # #endregion
            # Search for chunks with image markers from ALL documents (not just mentioned ones)
            # This ensures we find image content even if similarity search didn't return those chunks
            try:
                # Strategy 1: Search for chunks with image markers using multiple queries
                image_queries = [
                    "image diagram figure picture",
                    "drawer tool wrench socket",
                    "part number quantity tool list"
                ]
                
                for image_query in image_queries:
                    try:
                        if hasattr(self.vectorstore, 'similarity_search_with_score'):
                            search_results = self.vectorstore.similarity_search_with_score(
                                image_query,
                                k=100  # Increased to get more chunks
                            )
                            for doc_result, score in search_results:
                                if hasattr(doc_result, 'page_content'):
                                    # Check for image markers OR image metadata
                                    has_marker = '<!-- image -->' in doc_result.page_content
                                    has_metadata = False
                                    if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                        has_metadata = (
                                            doc_result.metadata.get('images_detected', False) or
                                            doc_result.metadata.get('image_count', 0) > 0 or
                                            doc_result.metadata.get('has_image', False)
                                        )
                                    
                                    if (has_marker or has_metadata) and doc_result not in relevant_docs:
                                        # Check if it's from a document with images
                                        doc_source = doc_result.metadata.get('source', '') if hasattr(doc_result, 'metadata') and doc_result.metadata else ''
                                        if not documents_with_images or doc_source in documents_with_images or not doc_source:
                                            additional_image_docs.append(doc_result)
                        elif hasattr(self.vectorstore, 'similarity_search'):
                            search_results = self.vectorstore.similarity_search(image_query, k=100)
                            for doc_result in search_results:
                                if hasattr(doc_result, 'page_content'):
                                    has_marker = '<!-- image -->' in doc_result.page_content
                                    has_metadata = False
                                    if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                        has_metadata = (
                                            doc_result.metadata.get('images_detected', False) or
                                            doc_result.metadata.get('image_count', 0) > 0 or
                                            doc_result.metadata.get('has_image', False)
                                        )
                                    
                                    if (has_marker or has_metadata) and doc_result not in relevant_docs:
                                        doc_source = doc_result.metadata.get('source', '') if hasattr(doc_result, 'metadata') and doc_result.metadata else ''
                                        if not documents_with_images or doc_source in documents_with_images or not doc_source:
                                            additional_image_docs.append(doc_result)
                    except Exception as e:
                        logger.debug(f"Could not search for image chunks with query '{image_query}': {e}")
                        continue
                
                # Remove duplicates
                seen = set()
                unique_additional_docs = []
                for doc in additional_image_docs:
                    doc_id = id(doc)  # Use object id for comparison
                    if doc_id not in seen:
                        seen.add(doc_id)
                        unique_additional_docs.append(doc)
                additional_image_docs = unique_additional_docs
                
                if additional_image_docs:
                    logger.info(f"Found {len(additional_image_docs)} chunks with image markers/metadata from expanded search")
                    # #region agent log
                    try:
                        with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rag_system.py:2232","message":"Image chunks found in expanded search","data":{"found_count":len(additional_image_docs),"total_relevant_before":len(relevant_docs)},"timestamp":int(time_module.time()*1000)})+"\n")
                    except: pass
                    # #endregion
                    relevant_docs = relevant_docs + additional_image_docs
                else:
                    logger.info("No additional image chunks found in expanded search")
                    # #region agent log
                    try:
                        with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rag_system.py:2236","message":"No image chunks found in expanded search","data":{"queries_tried":len(image_queries)},"timestamp":int(time_module.time()*1000)})+"\n")
                    except: pass
                    # #endregion
            except Exception as e:
                logger.warning(f"Error in image chunk search: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Phase 2: Expand search for tool/item names in image content
        if should_extract_image_content and tool_item_names and self.vectorstore is not None:
            logger.info(f"🔍 Expanding search for tool/item names: {tool_item_names}")
            try:
                # Search for chunks containing these items in image content
                for item_name in tool_item_names:
                    try:
                        # Search with item name + image-related terms
                        search_query = f"{item_name} image drawer tool part"
                        if hasattr(self.vectorstore, 'similarity_search_with_score'):
                            search_results = self.vectorstore.similarity_search_with_score(
                                search_query,
                                k=min(10, k * 2) if k else 10
                            )
                            for doc_result, score in search_results:
                                # Filter for chunks with image markers
                                if hasattr(doc_result, 'page_content') and '<!-- image -->' in doc_result.page_content:
                                    if doc_result not in relevant_docs:
                                        relevant_docs.append(doc_result)
                                        logger.debug(f"Found chunk with '{item_name}' in image content")
                        elif hasattr(self.vectorstore, 'similarity_search'):
                            search_results = self.vectorstore.similarity_search(
                                search_query,
                                k=min(10, k * 2) if k else 10
                            )
                            for doc_result in search_results:
                                if hasattr(doc_result, 'page_content') and '<!-- image -->' in doc_result.page_content:
                                    if doc_result not in relevant_docs:
                                        relevant_docs.append(doc_result)
                                        logger.debug(f"Found chunk with '{item_name}' in image content")
                    except Exception as e:
                        logger.debug(f"Error searching for {item_name}: {e}")
                        continue
                
                if tool_item_names:
                    logger.info(f"✅ Expanded search completed for {len(tool_item_names)} tool/item name(s)")
            except Exception as e:
                logger.warning(f"Error in tool/item name search: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        if is_image_question and mentioned_documents and self.vectorstore is not None:
            try:
                # Query for chunks with image metadata from mentioned documents
                for mentioned_source in mentioned_documents:
                    # Create a query to find image chunks from this document
                    # Use a generic image-related query
                    image_query = "image diagram figure picture"
                    
                    # Try to retrieve chunks with image metadata
                    try:
                        # Use similarity search with filter for this document
                        if hasattr(self.vectorstore, 'similarity_search_with_score'):
                            # For FAISS, we'll search and filter
                            search_results = self.vectorstore.similarity_search_with_score(
                                image_query,
                                k=min(20, k * 2) if k else 20  # Get more chunks for image search
                            )
                            # Filter for mentioned document and image metadata
                            for doc_result, score in search_results:
                                if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                    doc_source = doc_result.metadata.get('source', '')
                                    if doc_source == mentioned_source:
                                        # Check if it has image metadata
                                        if (doc_result.metadata.get('has_image') or
                                            doc_result.metadata.get('image_ref') or
                                            doc_result.metadata.get('images_detected') or
                                            '<!-- image -->' in (doc_result.page_content if hasattr(doc_result, 'page_content') else '')):
                                            # Check if not already in relevant_docs
                                            if doc_result not in relevant_docs:
                                                additional_image_docs.append(doc_result)
                        elif hasattr(self.vectorstore, 'similarity_search'):
                            # Fallback to similarity_search
                            search_results = self.vectorstore.similarity_search(
                                image_query,
                                k=min(20, k * 2) if k else 20
                            )
                            for doc_result in search_results:
                                if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                    doc_source = doc_result.metadata.get('source', '')
                                    if doc_source == mentioned_source:
                                        if (doc_result.metadata.get('has_image') or
                                            doc_result.metadata.get('image_ref') or
                                            doc_result.metadata.get('images_detected') or
                                            '<!-- image -->' in (doc_result.page_content if hasattr(doc_result, 'page_content') else '')):
                                            if doc_result not in relevant_docs:
                                                additional_image_docs.append(doc_result)
                    except Exception as e:
                        logger.debug(f"Could not retrieve additional image chunks for {mentioned_source}: {e}")
                        # Continue with other documents
                        pass
                
                if additional_image_docs:
                    logger.info(f"Found {len(additional_image_docs)} additional image chunks from mentioned documents")
                    # Add to relevant_docs for comprehensive image content extraction
                    relevant_docs = relevant_docs + additional_image_docs
            except Exception as e:
                logger.debug(f"Error expanding image search: {e}")
                # Continue with normal flow
        
        # CRITICAL: Always extract image content from ALL retrieved chunks
        # This ensures image content is available even if question phrasing doesn't trigger is_image_question
        # Extract for ALL chunks, not just image questions
        chunks_to_check = relevant_docs
        
        # Enhanced logging for image content extraction
        # Phase 3: Always extract image content for tool/item questions
        if should_extract_image_content:
            if is_tool_item_question or has_part_number:
                logger.info(f"🔧 Tool/item question detected - extracting image content from {len(relevant_docs)} chunks")
            elif is_image_question:
                logger.info(f"🔍 Image question detected - extracting image content from {len(relevant_docs)} chunks")
            elif len(documents_with_images) > 0:
                logger.info(f"🔍 Documents with images detected ({len(documents_with_images)} docs) - extracting image content from {len(relevant_docs)} chunks")
            else:
                logger.debug(f"Checking {len(relevant_docs)} chunks for image content (standard extraction)")
        else:
            logger.debug(f"Checking {len(relevant_docs)} chunks for image content (standard extraction)")
        
        # Count chunks with image markers before extraction
        chunks_with_markers = sum(1 for doc in chunks_to_check 
                                 if hasattr(doc, 'page_content') and '<!-- image -->' in doc.page_content)
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rag_system.py:2314","message":"Chunks with markers count","data":{"chunks_with_markers":chunks_with_markers,"total_chunks":len(chunks_to_check)},"timestamp":int(time_module.time()*1000)})+"\n")
        except: pass
        # #endregion
        if chunks_with_markers > 0:
            logger.info(f"📷 Found {chunks_with_markers} chunk(s) with image markers out of {len(chunks_to_check)} total chunks")
        
        # CRITICAL FIX: Use global sequential image numbering per document
        # This ensures "Image 1", "Image 2", etc. are sequential across all chunks
        # Previous bug: images were numbered per-chunk, making it impossible to find specific images
        image_counter_per_doc = {}  # Map: source -> current_image_number
        
        for doc in chunks_to_check:
                if hasattr(doc, 'page_content') and hasattr(doc, 'metadata') and doc.metadata:
                    chunk_text = doc.page_content
                    source = doc.metadata.get('source', '')
                    page = doc.metadata.get('page', 0)
                    
                    # Check metadata flags to identify image-related chunks even without markers
                    has_image_metadata = (
                        doc.metadata.get('has_image', False) or
                        doc.metadata.get('image_ref') is not None or
                        doc.metadata.get('image_index') is not None or
                        doc.metadata.get('images_detected', False)
                    )
                    
                    # Look for image markers and extract surrounding text (OCR content from images)
                    if '<!-- image -->' in chunk_text:
                        # #region agent log
                        try:
                            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                import json
                                marker_count = chunk_text.count('<!-- image -->')
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rag_system.py:2334","message":"Found image marker in chunk","data":{"source":source[:50],"page":page,"markers_in_chunk":marker_count,"chunk_length":len(chunk_text)},"timestamp":int(time_module.time()*1000)})+"\n")
                        except: pass
                        # #endregion
                        # Improved splitting: Handle multiple markers and edge cases
                        # Split by image markers while preserving marker positions
                        marker_pattern = '<!-- image -->'
                        parts = chunk_text.split(marker_pattern)
                        
                        # Process each image marker occurrence
                        # CRITICAL FIX: Use global sequential numbering per document
                        for idx in range(len(parts) - 1):  # Last part has no marker after it
                            # Initialize counter for this document if not exists
                            if source not in image_counter_per_doc:
                                image_counter_per_doc[source] = 0
                            
                            # Increment and use global counter for this document
                            image_counter_per_doc[source] += 1
                            image_num = image_counter_per_doc[source]
                            
                            # #region agent log
                            try:
                                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                    import json
                                    after_text_len = len(parts[idx + 1].strip()) if (idx + 1) < len(parts) else 0
                                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rag_system.py:2400","message":"Processing image marker with global numbering","data":{"source":source[:30],"image_num":image_num,"global_counter":image_counter_per_doc[source],"after_text_length":after_text_len},"timestamp":int(time_module.time()*1000)})+"\n")
                            except: pass
                            # #endregion
                            
                            # Get text before this marker (context)
                            before_text = parts[idx].strip() if idx < len(parts) else ''
                            
                            # Get text after this marker (OCR content from image)
                            # CRITICAL FIX: For multiple markers in same chunk, split content to avoid overlap
                            # If this is not the last marker, only take text up to next marker
                            if idx + 2 < len(parts):
                                # There's another marker after this one - only take text up to next marker
                                after_text = parts[idx + 1].strip()
                                # Content ends at start of next marker section (no overlap)
                            else:
                                # Last marker in chunk - take all remaining text
                                after_text = parts[idx + 1].strip() if (idx + 1) < len(parts) else ''
                            
                            # Improved extraction: Get more context and OCR content
                            # CRITICAL FIX: Extract FULL remaining chunk content, not limited to 10K chars
                            # Extract entire remaining chunk to capture complete image OCR text
                            image_context_before = before_text[-500:].strip() if before_text else ''
                            # Extract full remaining text after marker (no limit) - image content may span entire chunk
                            image_ocr_content = after_text.strip() if after_text else ''  # Removed 10000 char limit
                            
                            # Handle edge cases:
                            # 1. Marker at start of chunk (no before_text)
                            # 2. Marker at end of chunk (no after_text)
                            # 3. Multiple consecutive markers
                            
                            # If marker is at start, look for OCR content after
                            if not before_text and image_ocr_content:
                                # Marker at start - this is likely OCR content
                                # Extract full remaining chunk (no limit)
                                image_ocr_content = after_text.strip()  # Removed 10000 char limit
                            
                            # If marker is at end, use text before as context
                            if not after_text and image_context_before:
                                # Marker at end - use text before as potential OCR
                                image_ocr_content = before_text[-800:].strip()  # Use last 800 chars as OCR
                                image_context_before = before_text[:-800].strip() if len(before_text) > 800 else ''
                            
                            # Combine context (OCR text is primary, context before is secondary)
                            if image_ocr_content:
                                image_context = f"[IMAGE {image_num} OCR CONTENT]\n{image_ocr_content}"
                                if image_context_before:
                                    image_context = f"Context: {image_context_before}\n{image_context}"
                                # #region agent log
                                try:
                                    with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                        import json
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rag_system.py:2366","message":"Extracted OCR content","data":{"image_num":image_num,"ocr_length":len(image_ocr_content),"context_length":len(image_context)},"timestamp":int(time_module.time()*1000)})+"\n")
                                except: pass
                                # #endregion
                            elif image_context_before:
                                # Fallback: use text before if no OCR after
                                image_context = f"[IMAGE {image_num} - Text near image]\n{image_context_before}"
                                # #region agent log
                                try:
                                    with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                        import json
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rag_system.py:2372","message":"Using fallback context","data":{"image_num":image_num,"context_length":len(image_context_before)},"timestamp":int(time_module.time()*1000)})+"\n")
                                except: pass
                                # #endregion
                            else:
                                # Skip if no content at all
                                continue
                            
                            if image_context:
                                key = (source, image_num)
                                if key not in image_content_map:
                                    image_content_map[key] = []
                                
                                # CRITICAL FIX: Validate OCR text completeness
                                ocr_text_length = len(image_ocr_content) if image_ocr_content else 0
                                if ocr_text_length < 50:
                                    logger.warning(f"⚠️  Image {image_num} from {os.path.basename(source)} has very short OCR text ({ocr_text_length} chars) - may be incomplete")
                                
                                image_content_map[key].append({
                                    'content': image_context,
                                    'page': page,
                                    'full_chunk': chunk_text,  # Store FULL chunk (no truncation) - contains all OCR text
                                    'ocr_text': image_ocr_content,  # Store FULL OCR text (no limit)
                                    'ocr_text_length': ocr_text_length  # Store length for validation
                                })
                                
                                # Log OCR text completeness per image
                                logger.debug(f"📷 Image {image_num} from {os.path.basename(source)}: Extracted {ocr_text_length:,} OCR characters")
                    
                    # Enhanced detection: Extract content from chunks with image metadata even without markers
                    elif has_image_metadata:
                        # Chunk has image metadata but no markers (legacy document or marker missing)
                        # Extract full chunk text as potential OCR content
                        image_index = doc.metadata.get('image_index', 1)
                        image_ref = doc.metadata.get('image_ref', {})
                        
                        # Use image_index from metadata if available
                        if isinstance(image_ref, dict) and 'image_index' in image_ref:
                            image_index = image_ref.get('image_index', image_index)
                        
                        # Check if chunk text looks like OCR content (pattern recognition)
                        is_ocr_like = any([
                            # Structured lists (common in OCR from diagrams)
                            '___' in chunk_text or '____' in chunk_text,
                            # Part numbers and measurements
                            any(pattern in chunk_text for pattern in ['MM', 'SS ALLEN', 'Part', 'Quantity:', 'Qty:']),
                            # Tool/drawer patterns
                            any(pattern in chunk_text.lower() for pattern in ['drawer', 'tool', 'wrench', 'socket']),
                            # Short lines (common in OCR)
                            len(chunk_text.split('\n')) > 5 and all(len(line.strip()) < 100 for line in chunk_text.split('\n')[:10]),
                            # Mixed case inconsistencies (OCR artifacts)
                            sum(1 for c in chunk_text[:200] if c.isupper()) > 50
                        ])
                        
                        if is_ocr_like or len(chunk_text.strip()) > 50:
                            # Extract as image content
                            key = (source, image_index)
                            if key not in image_content_map:
                                image_content_map[key] = []
                            image_content_map[key].append({
                                'content': f"[IMAGE {image_index} OCR CONTENT - Detected from metadata]\n{chunk_text}",
                                'page': page,
                                'full_chunk': chunk_text,  # Store FULL chunk
                                'ocr_text': chunk_text  # Store FULL OCR text
                            })
                    
                    # ALWAYS check if chunk contains drawer/image-related content even without markers
                    # This helps find content that might be from images but not marked
                    # Check this for ALL chunks, regardless of question type
                    # Check if chunk has relevant content patterns
                    has_image_patterns = any(keyword in chunk_text.lower() for keyword in ['drawer', 'tool', 'wrench', 'socket', 'allen'])
                    has_image_indicators = any(indicator in chunk_text for indicator in ['___', 'MM', 'SS ALLEN', 'Part', 'Quantity:', '65300', 'Wire Stripper', 'Snips', 'Socket'])
                    
                    # If chunk has image-like patterns, include it as potential image content
                    if has_image_patterns or has_image_indicators:
                        # Use a default image index if not specified
                        image_index = 1
                        key = (source, image_index)
                        if key not in image_content_map:
                            image_content_map[key] = []
                        
                        # Check if this looks like image content (has part numbers, tool lists, etc.)
                        if has_image_indicators:
                            image_content_map[key].append({
                                'content': f"[POSSIBLE IMAGE CONTENT - Tool/Drawer Information]\n{chunk_text}",
                                'page': page,
                                'full_chunk': chunk_text,  # Store FULL chunk
                                'ocr_text': chunk_text  # Store FULL OCR text
                            })
        
        # Enhanced logging for image content extraction results
        if image_content_map:
            total_images = sum(len(contents) for contents in image_content_map.values())
            total_ocr_chars = sum(
                len(content_info.get('ocr_text', '')) 
                for contents in image_content_map.values() 
                for content_info in contents
            )
            # Validate completeness per image
            short_ocr_count = 0
            for (source, img_idx), contents in image_content_map.items():
                for content_info in contents:
                    ocr_length = content_info.get('ocr_text_length', len(content_info.get('ocr_text', '')))
                    if ocr_length < 50:
                        short_ocr_count += 1
            
            logger.info(f"✅ Extracted image content from {len(image_content_map)} image(s), {total_images} total content entries")
            logger.info(f"📊 Image content statistics: {total_ocr_chars:,} OCR characters extracted")
            if short_ocr_count > 0:
                logger.warning(f"⚠️  {short_ocr_count} image(s) have very short OCR text (< 50 chars) - may indicate incomplete extraction")
            else:
                logger.info(f"✅ All images have substantial OCR text extracted (>= 50 chars)")
            
            # Log which documents contributed image content
            contributing_docs = set(source for (source, _) in image_content_map.keys())
            if contributing_docs:
                logger.info(f"📄 Documents with image content: {[os.path.basename(d) for d in contributing_docs]}")
            
            # Store images in OpenSearch at query time
            try:
                self._store_extracted_images(image_content_map, contributing_docs)
            except Exception as e:
                logger.warning(f"⚠️  Failed to store images in OpenSearch at query time: {str(e)}")
                # Don't fail query if storage fails
            
            # CRITICAL FIX: Filter image content by mentioned document if specific document is queried
            if mentioned_documents and len(mentioned_documents) == 1:
                # Only one document mentioned - filter image content to only that document
                mentioned_source = mentioned_documents[0]
                filtered_image_content_map = {}
                for (source, img_idx), contents in image_content_map.items():
                    if source == mentioned_source:
                        filtered_image_content_map[(source, img_idx)] = contents
                
                if filtered_image_content_map:
                    removed_count = len(image_content_map) - len(filtered_image_content_map)
                    if removed_count > 0:
                        logger.info(f"🔍 Filtered image content: Kept {len(filtered_image_content_map)} images from {os.path.basename(mentioned_source)}, removed {removed_count} images from other documents")
                        image_content_map = filtered_image_content_map
                else:
                    logger.warning(f"⚠️  No image content found for mentioned document: {os.path.basename(mentioned_source)}")
        elif is_image_question or len(documents_with_images) > 0:
            logger.warning(f"⚠️  Image question/documents detected but no image content extracted from {len(relevant_docs)} chunks")
            # Debug: Check if any chunks have image markers
            markers_found = sum(1 for doc in relevant_docs if hasattr(doc, 'page_content') and '<!-- image -->' in doc.page_content)
            logger.warning(f"🔍 Debug: Found {markers_found} chunk(s) with image markers out of {len(relevant_docs)} total chunks")
            if markers_found > 0:
                logger.error("❌ Image markers found but content not extracted - this indicates an extraction issue!")
                # Log sample of chunks with markers for debugging
                sample_chunks = [doc for doc in relevant_docs if hasattr(doc, 'page_content') and '<!-- image -->' in doc.page_content][:3]
                for i, doc in enumerate(sample_chunks, 1):
                    chunk_preview = doc.page_content[:200].replace('\n', ' ')
                    logger.debug(f"   Sample chunk {i} with marker: {chunk_preview}...")
            else:
                logger.warning("⚠️  No image markers found in retrieved chunks - chunks may not have been retrieved by similarity search")
        
        # CRITICAL: Always add Image Content section when available
        # Add it for ALL queries if image content was extracted (not just image questions)
        # This ensures LLM can use image content even if question doesn't explicitly mention images
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"rag_system.py:2467","message":"Checking if Image Content section should be added","data":{"has_image_content":len(image_content_map)>0,"image_count":len(image_content_map)},"timestamp":int(time_module.time()*1000)})+"\n")
        except: pass
        # #endregion
        if image_content_map:
            logger.info(f"✅ Adding Image Content section to context with {len(image_content_map)} image(s)")
            # Make Image Content section more prominent - add at the beginning of context
            # Use very prominent markers to ensure LLM notices it
            image_content_section = "\n\n" + "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "⚠️⚠️⚠️  IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)  ⚠️⚠️⚠️\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "\n🚨 CRITICAL: This section contains OCR text extracted from images.\n"
            image_content_section += "🚨 This is the PRIMARY and ONLY source for answering questions about image content.\n"
            image_content_section += "🚨 YOU MUST USE THIS SECTION to answer questions about images, drawers, tools, or part numbers.\n"
            image_content_section += "\nWhen asked about:\n"
            image_content_section += "  - 'what information is in image X'\n"
            image_content_section += "  - 'what's inside image X'\n"
            image_content_section += "  - 'what tools are in DRAWER X'\n"
            image_content_section += "  - 'what part numbers are listed'\n"
            image_content_section += "  - 'give me information about images'\n"
            image_content_section += "\n🚨 When asked about specific tools, items, or part numbers:\n"
            image_content_section += "  - 'where can I find [tool name]'\n"
            image_content_section += "  - 'what drawer has [item]'\n"
            image_content_section += "  - 'location of [part number]'\n"
            image_content_section += "\n🚨 Search the OCR text in this section for the tool/item name or part number.\n"
            image_content_section += "🚨 The OCR text contains tool lists, drawer contents, and part numbers.\n"
            image_content_section += "\n🚨 ALWAYS check this section FIRST and provide detailed information from the OCR text.\n"
            image_content_section += "🚨 DO NOT say 'context does not contain' if this section has relevant information.\n"
            image_content_section += "🚨 DO NOT ignore this section - it contains the actual OCR text from images.\n"
            image_content_section += "\nEach image is numbered and associated with a document.\n"
            image_content_section += "Match the image number from the question to the image number in this section.\n"
            image_content_section += "\n" + "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "START OF IMAGE CONTENT - READ THIS SECTION CAREFULLY\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n\n"
            
            # Group by document for better organization
            documents_images = {}
            for (source, img_idx), contents in image_content_map.items():
                if source not in documents_images:
                    documents_images[source] = {}
                documents_images[source][img_idx] = contents
            
            # Format by document
            for source, images_dict in documents_images.items():
                source_name = os.path.basename(source) if source else source
                image_content_section += f"--- Document: {source_name} ---\n"
                
                # Sort images by index for clarity
                sorted_images = sorted(images_dict.items(), key=lambda x: x[0] if isinstance(x[0], int) else 0)
                
                for img_idx, contents in sorted_images:
                    image_content_section += f"\n  Image {img_idx}:\n"
                    for content_info in contents:
                        # Add page information if available
                        if content_info.get('page'):
                            image_content_section += f"    Location: Page {content_info['page']}\n"
                        
                        # Add OCR content with clear formatting
                        # CRITICAL FIX: Include FULL OCR text, not truncated
                        ocr_text = content_info.get('ocr_text', '')
                        if ocr_text:
                            # Include full OCR text (no truncation) - LLM can handle long text
                            image_content_section += f"    OCR Text: {ocr_text}\n"
                        else:
                            # Use content if OCR text not available
                            content = content_info.get('content', '')
                            if content:
                                # Include full content (no truncation)
                                image_content_section += f"    Content: {content}\n"
                        
                        # Add additional context if available (full_chunk might have more than ocr_text)
                        full_chunk = content_info.get('full_chunk', '')
                        if full_chunk:
                            # Only add if full_chunk has significantly more content
                            ocr_or_content = ocr_text or content_info.get('content', '')
                            if len(full_chunk) > len(ocr_or_content) * 1.2:  # 20% more content
                                # Include the additional content (no truncation)
                                additional = full_chunk[len(ocr_or_content):] if ocr_or_content else full_chunk
                                if additional.strip():
                                    image_content_section += f"    Additional Context: {additional}\n"
                    
                    image_content_section += "\n"
            
            image_content_section += "\n" + "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "END OF IMAGE CONTENT SECTION\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "⚠️⚠️⚠️  REMEMBER: Use the Image Content section above for image questions  ⚠️⚠️⚠️\n"
            image_content_section += "=" * 80 + "\n"
            image_content_section += "=" * 80 + "\n\n"
            
            # Add Image Content section at the BEGINNING of context for maximum visibility
            context = image_content_section + context
            logger.info(f"✅ Image Content section added to context ({len(image_content_section):,} characters, {len(image_content_map)} images)")
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"rag_system.py:2551","message":"Image Content section added to context","data":{"section_length":len(image_content_section),"context_length_after":len(context),"images_in_section":len(image_content_map)},"timestamp":int(time_module.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # Debug: Log a preview of the Image Content section (first 500 chars)
            import logging
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Image Content section preview: {image_content_section[:500]}...")
        
        # Collect document-level metadata (image counts, etc.) from all retrieved documents
        document_metadata = {}
        legacy_documents = []  # Track documents that need re-processing
        
        for doc in relevant_docs:
            if hasattr(doc, 'metadata') and doc.metadata:
                source = doc.metadata.get('source', 'Unknown')
                if source and source != 'Unknown':
                    # Count images in chunk text as fallback if metadata not available
                    chunk_text = doc.page_content if hasattr(doc, 'page_content') else ''
                    image_markers_in_chunk = chunk_text.count('<!-- image -->')
                    
                    # Detect legacy documents: images_detected=True but image_count=0 and no markers
                    images_detected_flag = doc.metadata.get('images_detected', False)
                    image_count_from_metadata = doc.metadata.get('image_count', 0)
                    is_legacy = (
                        images_detected_flag and 
                        image_count_from_metadata == 0 and 
                        image_markers_in_chunk == 0
                    )
                    
                    if source not in document_metadata:
                        # If metadata has image_count, use it; otherwise count markers in chunks
                        image_count = image_count_from_metadata if image_count_from_metadata > 0 else image_markers_in_chunk
                        
                        document_metadata[source] = {
                            'image_count': image_count,
                            'images_detected': images_detected_flag or image_markers_in_chunk > 0,
                            'pages': doc.metadata.get('pages', 0),
                            'parser_used': doc.metadata.get('parser_used', 'unknown'),
                            'image_markers_found': image_markers_in_chunk,  # Track markers found in chunks
                            'is_legacy': is_legacy  # Flag for legacy documents
                        }
                        
                        if is_legacy and source not in legacy_documents:
                            legacy_documents.append(source)
                    else:
                        # Use maximum values if multiple chunks from same document
                        existing = document_metadata[source]
                        existing_image_count = existing.get('image_count', 0)
                        existing_markers = existing.get('image_markers_found', 0)
                        
                        # Update image count: use metadata value if available, otherwise sum markers
                        if doc.metadata.get('image_count', 0) > 0:
                            existing['image_count'] = max(existing_image_count, doc.metadata.get('image_count', 0))
                        else:
                            # Sum up image markers from all chunks
                            existing['image_markers_found'] = existing_markers + image_markers_in_chunk
                            # Use marker count if metadata count is 0
                            if existing_image_count == 0:
                                existing['image_count'] = existing['image_markers_found']
                        
                        existing['images_detected'] = existing.get('images_detected', False) or images_detected_flag or image_markers_in_chunk > 0
                        existing['pages'] = max(existing.get('pages', 0), doc.metadata.get('pages', 0))
                        existing['is_legacy'] = existing.get('is_legacy', False) or is_legacy
                        
                        if is_legacy and source not in legacy_documents:
                            legacy_documents.append(source)
        
        # Add document metadata summary to context if available
        if document_metadata:
            # os is already imported at module level, no need to import again
            metadata_summary = "\n\n=== Document Metadata ===\n"
            metadata_summary += "IMPORTANT: Use this section to answer questions about document properties like image counts, page counts, etc.\n"
            metadata_summary += "When asked about images, always check this section first.\n"
            for source, meta in document_metadata.items():
                source_name = os.path.basename(source) if source else source
                metadata_summary += f"\nDocument: {source_name}\n"
                
                # Image information - prioritize metadata, fallback to markers
                image_count = meta.get('image_count', 0)
                image_markers = meta.get('image_markers_found', 0)
                images_detected = meta.get('images_detected', False)
                
                if image_count > 0:
                    metadata_summary += f"  - Images: {image_count} image(s) detected"
                    if image_markers > 0 and image_count != image_markers:
                        metadata_summary += f" (also found {image_markers} image markers in text)"
                    metadata_summary += "\n"
                elif image_markers > 0:
                    metadata_summary += f"  - Images: {image_markers} image marker(s) found in text (estimated count from retrieved chunks)\n"
                elif images_detected:
                    # Document has images but count not available (likely processed before image_count tracking was added)
                    if meta.get('is_legacy', False):
                        metadata_summary += f"  - Images: Yes, detected (exact count not available - LEGACY DOCUMENT: re-process for accurate counts)\n"
                    else:
                        metadata_summary += f"  - Images: Yes, detected (exact count not available - document may need re-processing)\n"
                
                if meta.get('pages', 0) > 0:
                    metadata_summary += f"  - Pages: {meta['pages']}\n"
                if meta.get('parser_used'):
                    metadata_summary += f"  - Parser: {meta['parser_used']}\n"
            metadata_summary += "\n"
            context = metadata_summary + context
        
        # Count tokens in context (question + context)
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                has_image_section = 'IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)' in context
                image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)')
                image_section_end = context.find('END OF IMAGE CONTENT SECTION', image_section_start) if image_section_start >= 0 else -1
                image_section_length = (image_section_end - image_section_start) if image_section_start >= 0 and image_section_end >= 0 else 0
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"E","location":"rag_system.py:2747","message":"Context before LLM query","data":{"context_length":len(context),"context_tokens":context_tokens,"has_image_section":has_image_section,"image_section_start":image_section_start,"image_section_length":image_section_length,"context_preview":context[:200]},"timestamp":int(time_module.time()*1000)})+"\n")
        except: pass
        # #endregion
        
        # Generate answer using LLM with improved prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras(question, context, relevant_docs, mentioned_documents, question_doc_number)
        else:
            answer, response_tokens = self._query_openai(question, context, relevant_docs, mentioned_documents, question_doc_number)
        
        response_time = time_module.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        # Deduplicate and rank citations
        if citations:
            citations = self._deduplicate_citations(citations)
            citations = self._rank_citations_by_relevance(citations, question)
        
        # Record query metrics
        if self.metrics_collector:
            self.metrics_collector.record_query(
                question=question,
                answer_length=len(answer),
                response_time=response_time,
                chunks_used=len(relevant_docs),
                sources_count=len(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
                api_used="cerebras" if self.use_cerebras else "openai",
                success=True,
                context_tokens=context_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens
            )
        
        return {
            "answer": answer,
            "sources": list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
            "context_chunks": [doc.page_content for doc in relevant_docs],  # Full chunk text for citation display
            "citations": citations,  # Detailed citation information with page numbers and snippets
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens
        }
    
    def _query_openai(self, question: str, context: str, relevant_docs: List = None, mentioned_documents: List = None, question_doc_number: int = None) -> tuple:
        """
        Query OpenAI with maximum accuracy settings.
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
            mentioned_documents: List of documents mentioned in the question (for filtering)
            question_doc_number: Document number extracted from question (e.g., 1, 2)
        """
        from openai import OpenAI
        from config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # #region agent log
        try:
            with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                import json
                context_has_image_section = 'IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)' in context
                image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)') if context_has_image_section else -1
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2819","message":"_query_openai called","data":{"context_length":len(context),"context_has_image_section":context_has_image_section,"image_section_start":image_section_start,"question":question[:100]},"timestamp":int(time_module.time()*1000)})+"\n")
        except: pass
        # #endregion
        
        # Detect if this is a summary query
        question_lower = question.lower()
        is_summary_query = any(kw in question_lower for kw in 
                              ['summary', 'summarize', 'overview', 'what is this document about',
                               'what does this document contain', 'what is in this document',
                               'tell me about', 'describe', 'explain this document'])
        
        if is_summary_query:
            # Use synthesis-friendly prompt for summaries
            system_prompt = """You are a document summarization assistant. Your task is to synthesize information from the provided context to create a comprehensive summary.

CRITICAL RULES:
- Synthesize information from ALL provided context chunks to create a coherent summary
- Create a summary even if chunks are from different sections of the document
- Include key points, main topics, and important information from the context
- Organize information logically (overview, main points, important details)
- DO NOT say "context does not contain" - instead, synthesize what IS available
- Focus on main themes, important details, and key information
- DO NOT add greetings, signatures, or closing statements
- End your answer when you have provided the summary"""
            
            user_prompt = f"""Context from documents:
{context}

Question: {question}

Instructions:
1. Read ALL context chunks carefully
2. Synthesize information from multiple chunks to create a comprehensive summary
3. Include: overview, key points, main topics, important information
4. Organize the summary logically
5. Use information from the context - do not say it's not available
6. DO NOT add greetings or closing statements

Summary:"""
        else:
            # Synthesis-friendly prompt for all queries - encourages working with available information
            # Add document filtering instruction if specific document mentioned
            document_filter_instruction = ""
            if mentioned_documents and question_doc_number is not None:
                mentioned_doc_name = os.path.basename(mentioned_documents[0]) if mentioned_documents else ""
                document_filter_instruction = f"""

CRITICAL DOCUMENT FILTERING: The question specifically asks about "{mentioned_doc_name}". 
- You MUST ONLY use information from this specific document
- DO NOT use information from other documents, even if they have similar names
- If the context contains information from other documents, IGNORE it
- Only answer based on the specified document: {mentioned_doc_name}
- If the specified document is not in the context, state that clearly"""
            
            system_prompt = f"""You are a precise technical assistant that provides accurate, detailed answers by synthesizing information from the provided context. 

IMPORTANT: If the context includes a "Document Metadata" section, use it to answer questions about document properties like image counts, page counts, etc. When asked about images in a document, check the Document Metadata section first. If the metadata shows "exact count not available" but images are detected, state that images are present but the exact count requires re-processing the document.{document_filter_instruction}

CRITICAL: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images. This section contains OCR text extracted from images and is the PRIMARY and MOST RELIABLE source for answering questions about image content. The section is marked with prominent warning symbols (⚠️⚠️⚠️) to make it highly visible. 

When asked:
- "what is in image X" or "what information is in image X"
- "what tools are in DRAWER X" or "what's in drawer X"
- "what part numbers are listed" or "what tools are listed"
- "give me information about images" or "what content is in the images"
- "where can I find [tool name]" or "where is [item]"
- "what drawer has [item]" or "location of [part number]"
- Any question mentioning images, drawers, tools, part numbers, or visual content

You MUST:
1. Look in the Image Content section FIRST (before checking other context)
2. Find the relevant image number or content
3. Search the OCR text for the specific tool/item name or part number mentioned in the question
4. Provide detailed, specific information from the OCR text
5. Include exact part numbers, tool names, quantities, drawer numbers, and other details from the OCR text
6. Do NOT say "context does not contain" if the Image Content section has relevant information

IMPORTANT: When asked about specific tools, items, or part numbers (e.g., "Where can I find the Mallet?"):
1. FIRST check the "=== IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES) ===" section
2. Search the OCR text for the tool/item name or part number (try variations: lowercase, uppercase, partial matches)
3. Look for drawer numbers, locations, or quantities associated with the item
4. Provide specific information from the OCR text, including drawer numbers, page numbers, and quantities
5. DO NOT say "context does not contain" if you haven't thoroughly searched the Image Content section

Each image is numbered - match the image number from the question to the image number in the Image Content section. If the question asks about "image 1" or "first image", look for "Image 1:" in the Image Content section.

CRITICAL RULES:
- Synthesize information from ALL provided context chunks to answer the question
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
- Be specific and cite exact values, measurements, and specifications when available
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- If multiple sources provide information, synthesize them clearly
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- End your answer when you have provided the information - do not add unnecessary text"""
        
            # Add document filtering instruction to user prompt if specific document mentioned
            user_doc_filter_instruction = ""
            if mentioned_documents and question_doc_number is not None:
                mentioned_doc_name = os.path.basename(mentioned_documents[0]) if mentioned_documents else ""
                user_doc_filter_instruction = f"\n\nCRITICAL: The question asks specifically about \"{mentioned_doc_name}\". Only use information from this document. Ignore information from other documents."
            
            user_prompt = f"""Context from documents:
{context}

Question: {question}{user_doc_filter_instruction}

Instructions:
1. If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), check it FIRST for questions about images, drawers, tools, or part numbers
2. For questions about specific tools, items, or part numbers (e.g., "Where can I find the Mallet?"), search the Image Content section OCR text for the tool/item name or part number
3. Read ALL context chunks carefully
4. Synthesize information from the context to answer the question
5. If the context contains relevant information, use it to provide a comprehensive answer
6. Include specific details, numbers, and specifications when available
7. For image-related questions, prioritize information from the Image Content section
8. When searching for tools/items, look for drawer numbers, locations, quantities, and part numbers in the OCR text
9. Only say information is not available if you have thoroughly checked ALL chunks AND the Image Content section (if present) and found nothing relevant
10. DO NOT add greetings, signatures, or closing statements
11. DO NOT repeat information or phrases
12. Stop immediately after providing the answer

Answer:"""
        
        try:
            # Get temperature and max_tokens from UI config or defaults
            ui_temp = getattr(self, 'ui_config', {}).get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
            ui_max_tokens = getattr(self, 'ui_config', {}).get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
            
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=ui_temp,  # Use UI config
                max_tokens=ui_max_tokens,  # Use UI config
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]  # Stop at common endings
            )
            # Check if response has choices
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    # Check if answer mentions image content keywords
                    has_image_keywords = any(kw in answer.lower() for kw in ['image', 'drawer', 'tool', 'part number', 'ocr', '65300'])
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2943","message":"LLM response received","data":{"answer_length":len(answer),"has_image_keywords":has_image_keywords,"answer_preview":answer[:300]},"timestamp":int(time_module.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            # Get token usage from response
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                # Fallback: estimate tokens in answer
                response_tokens = self.count_tokens(answer)
            
            # Clean up any repetitive or unwanted endings
            answer = self._clean_answer(answer)
            
            # #region agent log
            try:
                with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                    import json
                    has_image_keywords_after = any(kw in answer.lower() for kw in ['image', 'drawer', 'tool', 'part number', 'ocr', '65300'])
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"F","location":"rag_system.py:2955","message":"LLM response after cleaning","data":{"answer_length":len(answer),"has_image_keywords":has_image_keywords_after,"answer_preview":answer[:300]},"timestamp":int(time_module.time()*1000)})+"\n")
            except: pass
            # #endregion
            
            return answer, response_tokens
        except Exception as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if "model_not_found" in error_msg or "404" in error_msg:
                if "gpt-5" in error_msg.lower():
                    error_answer = f"Error: GPT-5 requires organization verification and is not publicly available. Please use a different model like gpt-4o or gpt-4."
                elif "verify" in error_msg.lower():
                    error_answer = f"Error: This model requires organization verification. Please use a different model or verify your organization at https://platform.openai.com/settings/organization/general"
                else:
                    error_answer = f"Error: Model '{self.openai_model}' is not available. Please check if the model name is correct or try a different model."
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                error_answer = "Error: Invalid API key. Please check your OpenAI API key in the .env file."
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                error_answer = "Error: Rate limit exceeded. Please wait a moment and try again."
            else:
                error_answer = f"Error querying OpenAI: {error_msg}"
            return error_answer, self.count_tokens(error_answer)
    
    def _query_cerebras(self, question: str, context: str, relevant_docs: List = None, mentioned_documents: List = None, question_doc_number: int = None) -> tuple:
        """Query Cerebras API with maximum accuracy settings
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
            mentioned_documents: List of documents mentioned in the question (for filtering)
            question_doc_number: Document number extracted from question (e.g., 1, 2)
        """
        from config.settings import ARISConfig
        # Synthesis-friendly prompt for Cerebras
        prompt = f"""You are a precise technical assistant. Synthesize information from the provided context to answer the question. Be specific and accurate.

CRITICAL: DO NOT add greetings, signatures, or closing statements. DO NOT repeat phrases. End your answer when you have provided the information.

Context:
{context}

Question: {question}

Instructions:
- Synthesize information from ALL context chunks to answer the question
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- Only say information is not available if you have thoroughly checked ALL chunks and found nothing relevant
- Be specific with numbers, measurements, and technical details
- Provide comprehensive and accurate answers
- DO NOT add "Best regards", "Thank you", or similar endings
- Stop immediately after providing the answer

Answer:"""
        
        headers = {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type": "application/json"
        }
        
        # Use selected Cerebras model
        try:
            # Get temperature and max_tokens from UI config or defaults
            ui_temp = getattr(self, 'ui_config', {}).get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
            ui_max_tokens = getattr(self, 'ui_config', {}).get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
            
            data = {
                "model": self.cerebras_model,
                "prompt": prompt,
                "max_tokens": ui_max_tokens,  # Use UI config
                "temperature": ui_temp  # Use UI config
            }
            
            response = requests.post(
                "https://api.cerebras.ai/v1/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                choices = result.get('choices', [])
                if not choices or len(choices) == 0:
                    raise ValueError("Cerebras API returned no choices in response")
                answer = choices[0].get('text', 'No response generated')
                if not answer:
                    answer = 'No response generated'
                
                # Get token usage from response if available
                response_tokens = result.get('usage', {}).get('completion_tokens', 0)
                if response_tokens == 0:
                    # Fallback: estimate tokens in answer
                    response_tokens = self.count_tokens(answer)
                
                # Clean answer to remove unwanted text
                answer = self._clean_answer(answer)
                return answer, response_tokens
            else:
                error_msg = f"Error: Cerebras API returned status {response.status_code}"
                return error_msg, self.count_tokens(error_msg)
        except Exception as e:
            error_msg = f"Error: Could not get response from Cerebras API: {str(e)}"
            return error_msg, self.count_tokens(error_msg)
    
    def _retrieve_chunks_for_query(
        self,
        query: str,
        k: int,
        use_mmr: bool,
        use_hybrid_search: bool,
        semantic_weight: float,
        keyword_weight: float,
        search_mode: str
    ) -> List:
        """
        Retrieve chunks for a single query (used by Agentic RAG for multi-query retrieval).
        
        Args:
            query: The query to retrieve chunks for
            k: Number of chunks to retrieve
            use_mmr: Use Maximum Marginal Relevance
            use_hybrid_search: Use hybrid search
            semantic_weight: Weight for semantic search
            keyword_weight: Weight for keyword search
            search_mode: Search mode
        
        Returns:
            List of Document objects
        """
        # For OpenSearch: Use per-document indexes instead of metadata filtering
        if self.vector_store_type == "opensearch":
            # Determine which index(es) to search
            indexes_to_search = []
            
            if self.active_sources:
                # Search only indexes for selected documents
                for doc_name in self.active_sources:
                    if doc_name in self.document_index_map:
                        indexes_to_search.append(self.document_index_map[doc_name])
                    else:
                        logger.warning(f"Agentic RAG - Document '{doc_name}' not found in index map. Available: {list(self.document_index_map.keys())}")
                
                if not indexes_to_search:
                    logger.warning(f"Agentic RAG - No indexes found for selected documents")
                    return []
            else:
                # No filter - search all document indexes
                indexes_to_search = list(self.document_index_map.values())
                if not indexes_to_search:
                    # Fallback to default index if no mappings exist (backward compatibility)
                    indexes_to_search = [self.opensearch_index or "aris-rag-index"]
            
            # Initialize multi-index manager if needed
            if not hasattr(self, 'multi_index_manager'):
                from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                self.multi_index_manager = OpenSearchMultiIndexManager(
                    embeddings=self.embeddings,
                    domain=self.opensearch_domain,
                    region=getattr(self, 'region', None)
                )
            
            # Search across selected indexes
            if len(indexes_to_search) == 1:
                # Single index - use it directly
                index_name = indexes_to_search[0]
                store = self.multi_index_manager.get_or_create_index_store(index_name)
                
                # Use hybrid search if enabled
                if use_hybrid_search:
                    try:
                        query_vector = self.embeddings.embed_query(query)
                        relevant_docs = store.hybrid_search(
                            query=query,
                            query_vector=query_vector,
                            k=k,
                            semantic_weight=semantic_weight,
                            keyword_weight=keyword_weight,
                            filter=None  # No filter needed with per-document indexes
                        )
                        return relevant_docs
                    except Exception as e:
                        logger.warning(f"Agentic RAG - Hybrid search failed for sub-query, falling back: {e}")
                
                # Standard search
                if use_mmr:
                    from config.settings import ARISConfig
                    fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                    lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                    retriever = store.vectorstore.as_retriever(
                        search_type="mmr",
                        search_kwargs={
                            "k": k,
                            "fetch_k": fetch_k,
                            "lambda_mult": lambda_mult
                        }
                    )
                else:
                    retriever = store.vectorstore.as_retriever(
                        search_kwargs={"k": k}
                    )
                relevant_docs = retriever.invoke(query)
                return relevant_docs
            else:
                # Multiple indexes - search across all
                from config.settings import ARISConfig
                relevant_docs = self.multi_index_manager.search_across_indexes(
                    query=query,
                    index_names=indexes_to_search,
                    k=k,
                    use_mmr=use_mmr,
                    fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K if use_mmr else 50,
                    lambda_mult=ARISConfig.DEFAULT_MMR_LAMBDA if use_mmr else 0.3
                )
                return relevant_docs
        
        # FAISS: Use existing filter logic
        # Prepare filter for OpenSearch (different syntax than FAISS) - not needed for FAISS
        opensearch_filter = None
        
        # Use hybrid search if enabled and OpenSearch is available (for non-per-doc path)
        if use_hybrid_search and self.vector_store_type.lower() == "opensearch":
            try:
                from vectorstores.opensearch_store import OpenSearchVectorStore
                
                is_opensearch = False
                if self.vectorstore is not None:
                    if isinstance(self.vectorstore, OpenSearchVectorStore):
                        is_opensearch = True
                    elif hasattr(self.vectorstore, '__class__') and 'OpenSearch' in self.vectorstore.__class__.__name__:
                        is_opensearch = True
                
                if is_opensearch:
                    query_vector = self.embeddings.embed_query(query)
                    relevant_docs = self.vectorstore.hybrid_search(
                        query=query,
                        query_vector=query_vector,
                        k=k,
                        semantic_weight=semantic_weight,
                        keyword_weight=keyword_weight,
                        filter=opensearch_filter
                    )
                    return relevant_docs
            except Exception as e:
                logger.warning(f"Hybrid search failed for sub-query, falling back: {e}")
        
        # Standard retrieval
        # For FAISS: Increase k when filtering is needed (FAISS doesn't support native filtering)
        effective_k = k
        if self.active_sources and self.vector_store_type.lower() != "opensearch":
            # Increase k to account for post-filtering (retrieve 3-5x more to ensure we get enough after filtering)
            effective_k = k * 4
            logger.info(f"Agentic RAG - FAISS filtering active: Increasing k from {k} to {effective_k} to account for post-filtering")
        
        if use_mmr:
            from config.settings import ARISConfig
            fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
            lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
            
            # Adjust fetch_k for FAISS filtering
            if self.active_sources and self.vector_store_type.lower() != "opensearch":
                fetch_k = max(fetch_k, effective_k * 2)
            
            search_kwargs = {
                "k": effective_k,
                "fetch_k": fetch_k,
                "lambda_mult": lambda_mult,
            }
            
            # Add filter only for OpenSearch (FAISS doesn't support native filtering)
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            # Note: FAISS filtering is done post-retrieval, not via search_kwargs
            
            retriever = self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs
            )
        else:
            search_kwargs = {"k": effective_k}
            
            # Add filter only for OpenSearch (FAISS doesn't support native filtering)
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            # Note: FAISS filtering is done post-retrieval, not via search_kwargs
            
            retriever = self.vectorstore.as_retriever(
                search_kwargs=search_kwargs
            )
        
        try:
            relevant_docs = retriever.invoke(query)
        except AttributeError:
            relevant_docs = retriever.get_relevant_documents(query)
        
        # Filter by active sources if set (strict filtering with robust matching)
        # Skip this for OpenSearch with per-document indexes (already isolated by index)
        if self.active_sources and not (self.vector_store_type == "opensearch" and self.document_index_map):
            allowed_sources = set(self.active_sources)
            # Also create normalized versions for case-insensitive matching
            allowed_sources_normalized = {s.lower().strip() if s else "" for s in allowed_sources if s}
            allowed_filenames = {os.path.basename(s).lower().strip() if s else "" for s in allowed_sources if s}
            
            def matches_source(doc_source, doc_text=""):
                """Check if document source matches any allowed source using multiple strategies"""
                if not doc_source:
                    # If no metadata source, try extracting from text markers
                    if doc_text:
                        # Look for source markers in text (e.g., "Source: filename.pdf")
                        import re
                        source_patterns = [
                            r"Source:\s*([^\n]+)",
                            r"Document:\s*([^\n]+)",
                            r"File:\s*([^\n]+)",
                        ]
                        for pattern in source_patterns:
                            match = re.search(pattern, doc_text, re.IGNORECASE)
                            if match:
                                extracted_source = match.group(1).strip()
                                # Check if extracted source matches
                                if extracted_source in allowed_sources or \
                                   extracted_source.lower().strip() in allowed_sources_normalized or \
                                   os.path.basename(extracted_source).lower().strip() in allowed_filenames:
                                    return True
                    return False
                # Strategy 1: Exact match
                if doc_source in allowed_sources:
                    return True
                # Strategy 2: Case-insensitive match
                if doc_source.lower().strip() in allowed_sources_normalized:
                    return True
                # Strategy 3: Filename match
                doc_filename = os.path.basename(doc_source).lower().strip()
                if doc_filename in allowed_filenames:
                    return True
                # Strategy 4: Check if any allowed source is contained in doc_source (for path variations)
                for allowed in allowed_sources:
                    if allowed and allowed.lower() in doc_source.lower():
                        return True
                return False
            
            # Filter with strict matching
            filtered_docs = [
                doc for doc in relevant_docs 
                if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
            ]
            
            # Validate: Ensure NO documents from other sources slipped through
            invalid_sources = set()
            for doc in filtered_docs:
                doc_source = doc.metadata.get('source', '')
                if doc_source and not matches_source(doc_source):
                    invalid_sources.add(doc_source)
            
            if invalid_sources:
                logger.warning(f"Agentic RAG - Document mixing detected! Found invalid sources in filtered results: {invalid_sources}")
                # Remove invalid sources
                filtered_docs = [
                    doc for doc in filtered_docs 
                    if matches_source(doc.metadata.get('source', ''), doc.page_content[:200] if hasattr(doc, 'page_content') else '')
                ]
            
            if filtered_docs:
                # Final validation: Log document isolation status
                final_sources = set(doc.metadata.get('source', 'Unknown') for doc in filtered_docs)
                logger.info(f"Agentic RAG - Filtered to {len(filtered_docs)} chunks from selected documents: {self.active_sources}. Final sources: {final_sources}")
                if final_sources - allowed_sources:
                    logger.error(f"Agentic RAG - CRITICAL: Document mixing detected! Allowed: {allowed_sources}, Found: {final_sources}")
                return filtered_docs
            else:
                logger.warning(f"No chunks matched selected documents: {self.active_sources}. Available sources in results: {set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])}")
                return []  # Return empty if no matches
        
        return relevant_docs
    
    def _extract_source_from_chunk(self, doc, chunk_text: str, fallback_sources: List[str] = None, ui_config: Optional[Dict] = None) -> tuple:
        """
        Extract source document name from chunk metadata or text with confidence scoring.
        Ensures accurate citation by preserving source through the entire pipeline.
        
        Args:
            doc: Document object with metadata
            chunk_text: Chunk text content
            fallback_sources: List of source names as fallback
            ui_config: Optional UI configuration (temperature, max_tokens, active_sources)
        
        Returns:
            Tuple of (source_name, confidence_score)
            confidence: 1.0 (metadata) > 0.7 (alt_metadata) > 0.5 (text_marker) > 0.3 (document_index) > 0.1 (fallback)
        """
        import re
        # os is already imported at module level, no need to import again
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Use UI config if provided, otherwise use instance config
        if ui_config is None:
            ui_config = getattr(self, 'ui_config', {})
        
        # Log UI configuration for debugging
        if ui_config:
            logger.debug(f"Citation extraction using UI config: temperature={ui_config.get('temperature')}, max_tokens={ui_config.get('max_tokens')}")
        
        def normalize_source(source_str: str) -> str:
            """Normalize source path to filename and validate."""
            if not source_str:
                return source_str
            source_str = str(source_str).strip()
            # Extract filename from path if it's a path
            if os.sep in source_str or '/' in source_str or '\\' in source_str:
                source_str = os.path.basename(source_str)
            return source_str
        
        def validate_against_document_index(source_str: str) -> bool:
            """Check if source exists in document_index for validation."""
            if not hasattr(self, 'document_index') or not self.document_index:
                return False
            # Check if source (or normalized version) exists in document_index
            normalized = normalize_source(source_str)
            for doc_id in self.document_index.keys():
                if normalize_source(doc_id) == normalized or doc_id == source_str:
                    return True
            return False
        
        # First try metadata - this is the most reliable source (confidence: 1.0)
        source = doc.metadata.get('source', None)
        if source:
            source = normalize_source(source)
            if source and source != 'Unknown' and source != '':
                # Validate against document_index if available
                if validate_against_document_index(source):
                    logger.debug(f"Source extracted from metadata (validated): {source}")
                return source, 1.0
        
        # Try alternative metadata keys (for compatibility) (confidence: 0.7)
        alt_keys = ['document_name', 'file_name', 'filename', 'doc_name']
        for key in alt_keys:
            source = doc.metadata.get(key, None)
            if source:
                source = normalize_source(source)
                if source and source != 'Unknown' and source != '':
                    if validate_against_document_index(source):
                        logger.debug(f"Found source in alternate metadata key '{key}' (validated): {source}")
                    else:
                        logger.debug(f"Found source in alternate metadata key '{key}': {source}")
                    return source, 0.7
        
        # Try to extract from chunk text markers (less reliable but useful fallback) (confidence: 0.5)
        source_match = re.search(r'\[Source\s+\d+:\s*([^\]]+?)(?:\s*\(Page\s+\d+\))?\]', chunk_text)
        if source_match:
            source = source_match.group(1).strip()
            source = re.sub(r'\s*\(Page\s+\d+\)', '', source)
            source = normalize_source(source)
            if source and source != 'Unknown':
                if validate_against_document_index(source):
                    logger.debug(f"Extracted source from chunk text marker (validated): {source}")
                else:
                    logger.debug(f"Extracted source from chunk text marker: {source}")
                return source, 0.5
        
        # Try document_index lookup using chunk_index (confidence: 0.3)
        if hasattr(self, 'document_index') and self.document_index and doc.metadata.get('chunk_index') is not None:
            chunk_index = doc.metadata.get('chunk_index')
            for doc_id, chunk_indices in self.document_index.items():
                if chunk_index in chunk_indices:
                    source = normalize_source(doc_id)
                    if source and source != 'Unknown':
                        logger.info(f"Recovered source from document_index: {source}")
                        return source, 0.3
        
        # Fallback to provided sources list (last resort) (confidence: 0.1)
        if fallback_sources:
            for fallback_source in fallback_sources:
                if fallback_source and str(fallback_source).strip() and str(fallback_source).strip() != 'Unknown':
                    source = normalize_source(str(fallback_source).strip())
                    if source and source != 'Unknown':
                        logger.debug(f"Using fallback source: {source}")
                        return source, 0.1
        
        # Log warning if we couldn't find a source
        logger.warning(f"Could not extract source from chunk. Metadata keys: {list(doc.metadata.keys()) if hasattr(doc, 'metadata') else 'N/A'}")
        return 'Unknown', 0.0
    
    def _extract_page_number(self, doc, chunk_text: str) -> tuple:
        """
        Extract and validate page number from multiple sources.
        
        Args:
            doc: Document object with metadata
            chunk_text: Chunk text content
        
        Returns:
            Tuple of (page_number, confidence_score)
            confidence: 1.0 (source_page metadata) > 0.8 (page metadata) > 0.6 (text marker --- Page X ---) > 0.4 (text marker Page X)
            Returns (None, 0.0) if page is invalid or not found
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Get document's actual page count from metadata
        doc_pages = doc.metadata.get('pages', None)
        
        # Validate page number is within reasonable range
        def validate_page(page_num) -> bool:
            """Validate page number is within reasonable range (1-10000)."""
            try:
                page_int = int(page_num)
                return 1 <= page_int <= 10000
            except (ValueError, TypeError):
                return False
        
        # Validate extracted page against document page count
        def validate_against_doc(page_num) -> bool:
            """Validate page number is within document's actual page range."""
            if page_num is None:
                return False
            if not validate_page(page_num):  # Existing range check (1-10000)
                return False
            if doc_pages is not None and page_num > doc_pages:
                source = doc.metadata.get('source', 'Unknown')
                logger.warning(
                    f"Page {page_num} exceeds document page count {doc_pages}. "
                    f"Source: {source}"
                )
                return False
            return True
        
        # Try source_page metadata first (highest confidence: 1.0)
        page = doc.metadata.get('source_page', None)
        if page is not None:
            if validate_against_doc(page):
                logger.debug(f"Page extracted from source_page metadata: {page}")
                return int(page), 1.0
            else:
                logger.warning(f"Invalid page number in source_page metadata: {page} (doc has {doc_pages} pages)")
        
        # Try page metadata (confidence: 0.8)
        page = doc.metadata.get('page', None)
        if page is not None:
            if validate_against_doc(page):
                logger.debug(f"Page extracted from page metadata: {page}")
                return int(page), 0.8
            else:
                logger.warning(f"Invalid page number in page metadata: {page} (doc has {doc_pages} pages)")
        
        # Extract from text markers: "--- Page X ---" (confidence: 0.6)
        # BUT validate against document pages
        page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (--- Page X ---): {page_num}")
                return page_num, 0.6
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Extract from text markers: "Page X" (confidence: 0.4)
        page_match = re.search(r'Page\s+(\d+)', chunk_text, re.IGNORECASE)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (Page X): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Try page range patterns: "Page 5-7" or "Pages 10-12" (take first page, confidence: 0.4)
        page_range_match = re.search(r'Pages?\s+(\d+)[-\s]+(\d+)', chunk_text, re.IGNORECASE)
        if page_range_match:
            page_num = int(page_range_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from page range (first page): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from page range {page_num} exceeds document pages {doc_pages}")
        
        # No valid page found
        return None, 0.0
    
    def _generate_context_snippet(self, chunk_text: str, query: str, max_length: int = 500) -> str:
        """
        Generate snippet centered around query-relevant content.
        
        Args:
            chunk_text: Full chunk text content
            query: User query to find relevant portions
            max_length: Maximum snippet length in characters
        
        Returns:
            Cleaned snippet with query-relevant content
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Clean chunk text - remove page markers
        cleaned_text = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', chunk_text).strip()
        if not cleaned_text:
            cleaned_text = chunk_text
        
        # If chunk is shorter than max_length, return it all
        if len(cleaned_text) <= max_length:
            return cleaned_text
        
        # Extract query keywords (simple word extraction, case-insensitive)
        query_words = re.findall(r'\b\w+\b', query.lower())
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can'}
        query_keywords = [w for w in query_words if w not in stop_words and len(w) > 2]
        
        # If no meaningful keywords, return first max_length chars
        if not query_keywords:
            # Try to preserve sentence boundaries
            snippet = cleaned_text[:max_length]
            last_period = snippet.rfind('.')
            last_exclamation = snippet.rfind('!')
            last_question = snippet.rfind('?')
            last_sentence_end = max(last_period, last_exclamation, last_question)
            if last_sentence_end > max_length * 0.5:  # Only use if we have at least 50% of max_length
                snippet = cleaned_text[:last_sentence_end + 1]
            return snippet + "..."
        
        # Find positions of query keywords in text
        keyword_positions = []
        text_lower = cleaned_text.lower()
        for keyword in query_keywords:
            # Find all occurrences of keyword
            start = 0
            while True:
                pos = text_lower.find(keyword, start)
                if pos == -1:
                    break
                keyword_positions.append(pos)
                start = pos + 1
        
        if not keyword_positions:
            # Keywords not found, return first max_length chars with sentence boundary
            snippet = cleaned_text[:max_length]
            last_period = snippet.rfind('.')
            last_exclamation = snippet.rfind('!')
            last_question = snippet.rfind('?')
            last_sentence_end = max(last_period, last_exclamation, last_question)
            if last_sentence_end > max_length * 0.5:
                snippet = cleaned_text[:last_sentence_end + 1]
            return snippet + "..."
        
        # Find the center of keyword positions
        keyword_positions.sort()
        center_pos = keyword_positions[len(keyword_positions) // 2]
        
        # Extract context around center position
        start_pos = max(0, center_pos - max_length // 2)
        end_pos = min(len(cleaned_text), start_pos + max_length)
        
        # Adjust to preserve sentence boundaries
        # Try to start at sentence beginning
        if start_pos > 0:
            # Look for sentence end before start_pos
            search_start = max(0, start_pos - 100)  # Look back up to 100 chars
            period = cleaned_text.rfind('.', search_start, start_pos)
            exclamation = cleaned_text.rfind('!', search_start, start_pos)
            question = cleaned_text.rfind('?', search_start, start_pos)
            sentence_end = max(period, exclamation, question)
            if sentence_end > start_pos - 50:  # Only adjust if close
                start_pos = sentence_end + 1
                # Skip whitespace
                while start_pos < len(cleaned_text) and cleaned_text[start_pos].isspace():
                    start_pos += 1
        
        # Try to end at sentence end
        if end_pos < len(cleaned_text):
            period = cleaned_text.find('.', end_pos - 50, end_pos + 50)
            exclamation = cleaned_text.find('!', end_pos - 50, end_pos + 50)
            question = cleaned_text.find('?', end_pos - 50, end_pos + 50)
            sentence_end = min([p for p in [period, exclamation, question] if p != -1], default=-1)
            if sentence_end != -1 and sentence_end > end_pos - 50:
                end_pos = sentence_end + 1
        
        snippet = cleaned_text[start_pos:end_pos].strip()
        
        # Add ellipsis if we're not at the start or end
        if start_pos > 0:
            snippet = "..." + snippet
        if end_pos < len(cleaned_text):
            snippet = snippet + "..."
        
        return snippet
    
    def _deduplicate_citations(self, citations: List[Dict]) -> List[Dict]:
        """
        Merge duplicate citations (same source + page).
        Combines snippets intelligently and preserves best metadata.
        
        Args:
            citations: List of citation dictionaries
        
        Returns:
            Deduplicated list of citations with updated IDs
        """
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not citations:
            return []
        
        # Group citations by (source, page) tuple
        citation_groups = {}
        for citation in citations:
            source = citation.get('source', 'Unknown')
            page = citation.get('page')
            key = (source, page)
            
            if key not in citation_groups:
                citation_groups[key] = []
            citation_groups[key].append(citation)
        
        # Merge citations in each group
        merged_citations = []
        for group_key, group_citations in citation_groups.items():
            if len(group_citations) == 1:
                # No duplicates, keep as is
                merged_citations.append(group_citations[0])
            else:
                # Merge duplicates - keep citation with highest confidence
                best_citation = max(group_citations, key=lambda c: (
                    c.get('source_confidence', 0) + c.get('page_confidence', 0)
                ))
                
                # Merge snippets - combine unique portions
                all_snippets = [c.get('snippet', '') for c in group_citations if c.get('snippet')]
                if all_snippets:
                    # Use longest snippet (most context) or combine intelligently
                    best_snippet = max(all_snippets, key=len)
                    # If snippets are very different, combine them
                    if len(set(all_snippets)) > 1:
                        # Try to merge non-overlapping snippets
                        combined = best_snippet
                        for snippet in all_snippets:
                            if snippet not in combined and len(snippet) > 50:
                                # Add if it adds significant new content
                                combined += " ... " + snippet[:200]
                        best_snippet = combined[:500]  # Limit total length
                    best_citation['snippet'] = best_snippet
                
                # Preserve best metadata from all citations
                best_citation['source_confidence'] = max(
                    c.get('source_confidence', 0) for c in group_citations
                )
                best_citation['page_confidence'] = max(
                    c.get('page_confidence', 0) for c in group_citations
                )
                
                # Merge other metadata if available
                if any(c.get('section') for c in group_citations):
                    sections = [c.get('section') for c in group_citations if c.get('section')]
                    best_citation['section'] = sections[0] if sections else None
                
                merged_citations.append(best_citation)
                logger.debug(f"Merged {len(group_citations)} duplicate citations for {group_key}")
        
        # Re-number IDs sequentially
        for i, citation in enumerate(merged_citations, 1):
            citation['id'] = i
        
        logger.info(f"Deduplicated citations: {len(citations)} -> {len(merged_citations)}")
        return merged_citations
    
    def _count_flexible_keyword_matches(self, keywords: List[str], text: str) -> float:
        """
        Count keyword matches with flexible substring matching.
        
        Handles abbreviations automatically:
        - "kube" matches "kubernetes" (substring match)
        - "k8s" matches "kubernetes" (if k8s appears in text)
        - Exact matches get full weight (1.0)
        - Substring matches get partial weight (0.7)
        
        Args:
            keywords: List of query keywords
            text: Text to search in
        
        Returns:
            Weighted match score
        """
        import re
        matches = 0.0
        text_lower = text.lower()
        
        # Extract all words from text for substring checking
        text_words = set(re.findall(r'\b\w+\b', text_lower))
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # Exact word match (highest priority)
            # Check for word boundaries to ensure exact match
            if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text_lower):
                matches += 1.0
            # Substring match for short keywords (3-5 chars) in longer words
            elif 3 <= len(keyword_lower) <= 5:
                # Check if keyword appears as substring in any word
                for word in text_words:
                    if keyword_lower in word and len(word) > len(keyword_lower):
                        matches += 0.7  # Partial credit for substring match
                        break  # Count once per keyword
        
        return matches
    
    def _rank_citations_by_relevance(self, citations: List[Dict], query: str) -> List[Dict]:
        """
        Rank citations by relevance to query using multiple metrics:
        1. Vector similarity score (primary - most accurate)
        2. Keyword matching (secondary - for text-based relevance)
        3. Metadata confidence (tertiary - for quality)
        
        Args:
            citations: List of citation dictionaries
            query: User query string
        
        Returns:
            Ranked list of citations with relevance_score added, sorted from highest to lowest
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not citations or not query:
            return citations
        
        # Extract query keywords (simple word extraction, case-insensitive)
        query_words = re.findall(r'\b\w+\b', query.lower())
        # Filter out common stop words (but keep important technical terms)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'what', 'when', 'where', 'who', 'why', 'how', 'give', 'me', 'information', 'about'}
        query_keywords = [w for w in query_words if w not in stop_words and len(w) > 2]
        
        # If no keywords after filtering, use all words longer than 3 chars (to catch technical terms)
        if not query_keywords:
            query_keywords = [w for w in query_words if len(w) > 3]
        
        # Normalize similarity scores to 0-1 range if needed
        similarity_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        if similarity_scores:
            min_score = min(similarity_scores)
            max_score = max(similarity_scores)
            score_range = max_score - min_score if max_score != min_score else 1.0
            
            # If all scores are the same, use a default normalized value
            if score_range == 0:
                # All scores identical - they'll get equal normalized value of 0.5
                default_normalized = 0.5
            else:
                default_normalized = None
        else:
            min_score = 0
            max_score = 1.0
            score_range = 1.0
            default_normalized = 0.5
        
        # Calculate combined relevance score for each citation
        for citation in citations:
            # 1. Vector similarity score (primary - 60% weight)
            similarity_score = citation.get('similarity_score')
            if similarity_score is not None:
                # Normalize similarity score to 0-1 range
                # For distance-based scores (lower is better), invert: 1 - normalized
                # For similarity-based scores (higher is better), use normalized directly
                # Assume distance-based if score > 1.0, similarity-based if <= 1.0
                if score_range > 0:
                    if similarity_score > 1.0:
                        # Distance-based: lower is better, so invert
                        normalized_sim = 1.0 - ((similarity_score - min_score) / score_range)
                    else:
                        # Similarity-based: higher is better
                        normalized_sim = (similarity_score - min_score) / score_range if score_range > 0 else 0.5
                else:
                    normalized_sim = 0.5
                similarity_component = normalized_sim * 0.3  # Reduced to 0.3 (30% weight) - keyword matching is much more important
            else:
                similarity_component = 0.0
            
            # 2. Keyword matching score (secondary - 60% weight, increased from 50%)
            keyword_score = 0.0
            if query_keywords:
                snippet = citation.get('snippet', '').lower()
                full_text = citation.get('full_text', '').lower()
                source = citation.get('source', '').lower()
                
                # All query keywords are important (especially technical terms)
                important_terms = query_keywords  # All keywords are important
                
                # Count keyword matches using flexible substring matching
                snippet_matches = self._count_flexible_keyword_matches(query_keywords, snippet)
                full_text_matches = self._count_flexible_keyword_matches(query_keywords, full_text)
                # Source matches use simple exact matching
                source_matches = sum(1 for keyword in query_keywords if keyword in source)
                
                # Use flexible matches for scoring (includes both exact 1.0 and substring 0.7 matches)
                flexible_snippet_matches = snippet_matches  # Already weighted: exact=1.0, substring=0.7
                flexible_full_matches = full_text_matches   # Already weighted: exact=1.0, substring=0.7
                
                # Keep original exact matches for important boost calculation
                original_snippet_matches = sum(1 for keyword in query_keywords if keyword in snippet)
                original_full_matches = sum(1 for keyword in query_keywords if keyword in full_text)
                
                # Special boost for important terms found in snippet (very high weight)
                important_in_snippet = sum(1 for term in important_terms if term in snippet)
                important_in_full = sum(1 for term in important_terms if term in full_text)
                # Increased boost for snippet matches (where user sees the result)
                important_boost = ((important_in_snippet * 0.35) + (important_in_full * 0.15)) if important_terms else 0
                # Increased from 0.30 to 0.35 for snippet to ensure exact matches rank higher
                
                # Count exact phrase matches (higher weight)
                query_lower = query.lower()
                phrase_in_snippet = 1 if query_lower in snippet else 0
                phrase_in_full = 1 if query_lower in full_text else 0
                
                # Count how many unique keywords appear (coverage) using flexible matching
                unique_keywords_in_snippet = sum(1 for k in query_keywords if self._count_flexible_keyword_matches([k], snippet) > 0)
                unique_keywords_in_full = sum(1 for k in query_keywords if self._count_flexible_keyword_matches([k], full_text) > 0)
                
                total_keywords = len(query_keywords)
                if total_keywords > 0:
                    # Higher weight for snippet matches (where user sees results)
                    # Weight: snippet (40%), full text (20%), source (3%), important terms boost (30%), phrase matches (5%), coverage bonus (2%)
                    # FIXED: Use flexible matches in scoring (includes both exact and substring matches)
                    snippet_score = (flexible_snippet_matches / total_keywords) * 0.40  # Use flexible, not original
                    full_text_score = (flexible_full_matches / total_keywords) * 0.20   # Use flexible, not original
                    source_score = (source_matches / total_keywords) * 0.03
                    phrase_bonus = (phrase_in_snippet * 0.03) + (phrase_in_full * 0.02)
                    # Coverage bonus: reward citations that have more unique keywords
                    coverage_bonus = ((unique_keywords_in_snippet + unique_keywords_in_full) / (total_keywords * 2)) * 0.02
                    keyword_score = min(1.0, snippet_score + full_text_score + source_score + important_boost + phrase_bonus + coverage_bonus)
            else:
                keyword_score = 0.5  # Default if no keywords
            
            keyword_component = keyword_score * 0.6  # Increased to 0.6 (60% weight) - prioritize keyword matches heavily
            
            # 3. Metadata confidence boost (tertiary - 10% weight)
            confidence_avg = (citation.get('source_confidence', 0) + citation.get('page_confidence', 0)) / 2
            confidence_component = confidence_avg * 0.1
            
            # Combine all components into final relevance score
            relevance_score = similarity_component + keyword_component + confidence_component
            
            # Ensure score is in 0-1 range
            relevance_score = max(0.0, min(1.0, relevance_score))
            
            citation['relevance_score'] = relevance_score
        
        # Filter out citations with very low relevance scores (likely irrelevant)
        MIN_RELEVANCE_THRESHOLD = 0.20  # Citations below 20% relevance are filtered out
        filtered_citations = [c for c in citations if c.get('relevance_score', 0) >= MIN_RELEVANCE_THRESHOLD]
        
        if len(filtered_citations) < len(citations):
            logger.info(f"Filtered out {len(citations) - len(filtered_citations)} citations below relevance threshold {MIN_RELEVANCE_THRESHOLD:.0%}")
            citations = filtered_citations
        
        # Sort by relevance score (descending - highest first), then by similarity score, then by confidence
        # Handle None similarity scores by putting them last (use -1 instead of 999 for proper sorting)
        citations.sort(key=lambda c: (
            -c.get('relevance_score', 0),  # Primary: combined relevance (descending - highest first)
            -c.get('similarity_score', -1) if c.get('similarity_score') is not None else 1,  # Secondary: similarity (descending, None goes last)
            -(c.get('source_confidence', 0) + c.get('page_confidence', 0)),  # Tertiary: confidence (descending)
            c.get('id', 0)  # Quaternary: original order (ascending)
        ))
        
        # Validate sorting is correct (highest relevance first)
        if citations:
            relevance_scores = [c.get('relevance_score', 0) for c in citations]
            is_sorted = all(relevance_scores[i] >= relevance_scores[i+1] for i in range(len(relevance_scores)-1))
            if not is_sorted:
                logger.warning("Citations not properly sorted by relevance! Re-sorting...")
                citations.sort(key=lambda c: -c.get('relevance_score', 0), reverse=False)  # Explicit descending sort
        
        # Re-number IDs after sorting (1 = most relevant, highest score)
        for i, citation in enumerate(citations, 1):
            citation['id'] = i
            # Log top 3 for debugging
            if i <= 3:
                logger.debug(f"Rank {i}: relevance={citation.get('relevance_score', 0):.2%}, "
                            f"similarity={citation.get('similarity_score', 'N/A')}, "
                            f"source={citation.get('source', 'Unknown')[:50]}")
        
        top_3_scores = [f'{c.get("relevance_score", 0):.2%}' for c in citations[:3]]
        logger.info(f"Ranked {len(citations)} citations by relevance (highest to lowest). Top 3 scores: {top_3_scores}")
        return citations
    
    def _deduplicate_chunks(self, chunks: List, threshold: float = 0.95) -> List:
        """
        Deduplicate chunks using content hash and similarity.
        
        Args:
            chunks: List of Document objects
            threshold: Similarity threshold for near-duplicates (0.0-1.0)
        
        Returns:
            List of unique Document objects
        """
        import hashlib
        
        if not chunks:
            return []
        
        # Use content hash for exact duplicates
        seen_hashes = set()
        unique_chunks = []
        chunk_scores = {}  # Track how many times each chunk appears (priority)
        
        for chunk in chunks:
            # Ensure source metadata is preserved
            if hasattr(chunk, 'metadata') and chunk.metadata:
                # Validate source exists in metadata
                if 'source' not in chunk.metadata or not chunk.metadata.get('source'):
                    from scripts.setup_logging import get_logger
                    logger = get_logger("aris_rag.rag_system")
                    logger.warning(f"Chunk missing source metadata during deduplication. Available keys: {list(chunk.metadata.keys())}")
            
            # Create hash of content
            content_hash = hashlib.md5(chunk.page_content.encode('utf-8')).hexdigest()
            
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_chunks.append(chunk)
                chunk_scores[content_hash] = 1
            else:
                # Increment score for chunks that appear multiple times (they're more relevant)
                chunk_scores[content_hash] = chunk_scores.get(content_hash, 1) + 1
        
        # Sort by score (chunks appearing in multiple sub-queries are more relevant)
        # Then by position (keep first occurrence)
        unique_chunks_with_scores = []
        for chunk in unique_chunks:
            content_hash = hashlib.md5(chunk.page_content.encode('utf-8')).hexdigest()
            score = chunk_scores.get(content_hash, 1)
            unique_chunks_with_scores.append((score, chunk))
        
        # Sort by score (descending), then maintain order
        unique_chunks_with_scores.sort(key=lambda x: x[0], reverse=True)
        unique_chunks = [chunk for _, chunk in unique_chunks_with_scores]
        
        # TODO: Add similarity-based deduplication for near-duplicates if needed
        # This would require embedding comparison which is expensive
        
        return unique_chunks
    
    def _synthesize_agentic_results(
        self,
        question: str,
        sub_queries: List[str],
        relevant_docs: List,
        query_start_time: float
    ) -> Dict:
        """
        Synthesize results from multiple sub-queries using LLM.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries used for retrieval
            relevant_docs: Retrieved document chunks
            query_start_time: Start time for query (for metrics)
        
        Returns:
            Dict with answer, sources, citations, etc.
        """
        # Build context with metadata
        context_parts = []
        citations = []
        
        # Try to get similarity scores if available (for ranking)
        doc_scores = {}
        doc_order_scores = {}  # Use retrieval order as proxy for relevance when scores unavailable
        
        # First, try to get scores using similarity_search_with_score directly
        try:
            if hasattr(self.vectorstore, 'similarity_search_with_score'):
                # Get more results to ensure we have scores for all retrieved docs
                scored_docs = self.vectorstore.similarity_search_with_score(question, k=max(len(relevant_docs) * 2, 20))
                
                # Create a mapping of document content to scores
                for scored_doc, score in scored_docs:
                    if hasattr(scored_doc, 'page_content'):
                        # Use first 200 chars for better matching (more unique than 100)
                        doc_content = scored_doc.page_content[:200]
                        # Also try matching by full content hash
                        import hashlib
                        content_hash = hashlib.md5(scored_doc.page_content.encode('utf-8')).hexdigest()
                        score_val = float(score) if score is not None else 0.0
                        doc_scores[doc_content] = score_val
                        doc_scores[content_hash] = score_val
        except Exception as e:
            logger.debug(f"Could not retrieve similarity scores for agentic RAG: {e}")
        
        # Use retrieval order as a proxy for relevance (earlier = more relevant)
        for idx, doc in enumerate(relevant_docs):
            # Normalize order score: first doc = 1.0, last = 0.0
            order_score = 1.0 - (idx / max(len(relevant_docs), 1))
            if hasattr(doc, 'page_content'):
                doc_content = doc.page_content[:200]
                import hashlib
                content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
                doc_order_scores[doc_content] = order_score
                doc_order_scores[content_hash] = order_score
        
        for i, doc in enumerate(relevant_docs, 1):
            import re
            
            # Extract citation metadata - use helper method for consistent extraction
            chunk_text = doc.page_content
            
            # Validate document has metadata before extraction
            if not hasattr(doc, 'metadata') or not doc.metadata:
                logger.warning(f"Document at index {i} missing metadata during citation creation (Agentic RAG)")
                doc.metadata = {}
            
            # Build UI config from current state
            ui_config = getattr(self, 'ui_config', {
                'temperature': ARISConfig.DEFAULT_TEMPERATURE,
                'max_tokens': ARISConfig.DEFAULT_MAX_TOKENS,
                'active_sources': self.active_sources
            })
            
            # Extract source with confidence score
            source, source_confidence = self._extract_source_from_chunk(doc, chunk_text, None, ui_config=ui_config)
            
            # Validate source was extracted successfully
            if not source or source == 'Unknown':
                logger.warning(f"Could not extract valid source for citation {i} (Agentic RAG). Chunk preview: {chunk_text[:100]}...")
            
            # Extract page number with confidence score
            page, page_confidence = self._extract_page_number(doc, chunk_text)
            
            start_char = doc.metadata.get('start_char', None)
            end_char = doc.metadata.get('end_char', None)
            
            image_ref = None
            image_info = None
            page_blocks = doc.metadata.get('page_blocks', [])
            
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'image':
                        if page and block.get('page') == page:
                            image_ref = {
                                'page': block.get('page'),
                                'image_index': block.get('image_index'),
                                'bbox': block.get('bbox'),
                                'xref': block.get('xref')
                            }
                            image_info = f"Image {block.get('image_index', '?')} on Page {page}"
                            break
            
            if not image_ref:
                if doc.metadata.get('has_image') or doc.metadata.get('image_index') is not None:
                    image_ref = {
                        'page': page,
                        'image_index': doc.metadata.get('image_index'),
                        'bbox': doc.metadata.get('image_bbox')
                    }
                    image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}" if page else "Image reference"
            
            # Generate context-aware snippet using original question
            snippet_clean = self._generate_context_snippet(chunk_text, question, max_length=500)
            
            source_location_parts = []
            if page:
                source_location_parts.append(f"Page {page}")
            
            # Only add image info if this specific chunk has an image reference
            if image_ref:
                # This chunk is actually associated with an image
                image_index = image_ref.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            elif doc.metadata.get('has_image') and doc.metadata.get('image_index') is not None:
                # Chunk metadata indicates it has an image reference
                image_index = doc.metadata.get('image_index', '?')
                source_location_parts.append(f"Image {image_index}")
            # REMOVED: Don't use document-level images_detected - it's too broad and misleading
            
            source_location = " | ".join(source_location_parts) if source_location_parts else "Text content"
            
            # Extract section/heading information from page_blocks if available
            section = None
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'heading':
                        section = block.get('text', '')
                        break
            
            # Determine extraction method based on confidence scores
            extraction_method = 'metadata' if source_confidence >= 0.7 else ('text_marker' if source_confidence >= 0.3 else 'fallback')
            
            # Get similarity score if available (for ranking)
            similarity_score = None
            doc_content_key = chunk_text[:200] if chunk_text else ""
            import hashlib
            content_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest() if chunk_text else ""
            
            # Try multiple matching strategies
            if doc_content_key in doc_scores:
                similarity_score = doc_scores[doc_content_key]
            elif content_hash in doc_scores:
                similarity_score = doc_scores[content_hash]
            # Use order-based score as fallback
            elif doc_content_key in doc_order_scores:
                # Convert order score to similarity-like score (0.5 to 1.0 range)
                order_score = doc_order_scores[doc_content_key]
                similarity_score = 0.5 + (order_score * 0.5)  # Map 0.0-1.0 order to 0.5-1.0 similarity
            elif content_hash in doc_order_scores:
                order_score = doc_order_scores[content_hash]
                similarity_score = 0.5 + (order_score * 0.5)
            # Also try to get from metadata if stored there
            elif hasattr(doc, 'metadata') and 'similarity_score' in doc.metadata:
                similarity_score = doc.metadata.get('similarity_score')
            
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'source_confidence': source_confidence,
                'page': page,
                'page_confidence': page_confidence,
                'section': section,
                'snippet': snippet_clean,
                'full_text': chunk_text,
                'similarity_score': similarity_score,  # Vector similarity score for ranking
                'start_char': start_char,
                'end_char': end_char,
                'chunk_index': doc.metadata.get('chunk_index', None),
                'image_ref': image_ref,
                'image_info': image_info,
                'source_location': source_location,
                'content_type': 'image' if image_ref else 'text',
                'extraction_method': extraction_method
            }
            citations.append(citation)
            logger.debug(f"Agentic RAG Citation {i}: source='{source}', page={page}, chunk_index={citation.get('chunk_index', 'N/A')}")
            
            page_info = f" (Page {page})" if page else ""
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{chunk_text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Count tokens
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # Generate answer using synthesis prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras_agentic(question, sub_queries, context, relevant_docs)
        else:
            answer, response_tokens = self._query_openai_agentic(question, sub_queries, context, relevant_docs)
        
        response_time = time_module.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        # Deduplicate and rank citations
        if citations:
            citations = self._deduplicate_citations(citations)
            citations = self._rank_citations_by_relevance(citations, question)
        
        # Record metrics
        if self.metrics_collector:
            self.metrics_collector.record_query(
                question=question,
                answer_length=len(answer),
                response_time=response_time,
                chunks_used=len(relevant_docs),
                sources_count=len(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
                api_used="cerebras" if self.use_cerebras else "openai",
                success=True,
                context_tokens=context_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens
            )
        
        return {
            "answer": answer,
            "sources": list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
            "context_chunks": [doc.page_content for doc in relevant_docs],
            "citations": citations,
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "sub_queries": sub_queries  # Include sub-queries in response for UI display
        }
    
    def _query_openai_agentic(
        self,
        question: str,
        sub_queries: List[str],
        context: str,
        relevant_docs: List = None
    ) -> tuple:
        """
        Query OpenAI with Agentic RAG synthesis prompt.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries analyzed
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        
        Returns:
            Tuple of (answer, response_tokens)
        """
        from openai import OpenAI
        from config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        sub_queries_text = "\n".join([f"- {sq}" for sq in sub_queries])
        
        # Detect if this is a summary query
        question_lower = question.lower()
        is_summary_query = any(kw in question_lower for kw in 
                              ['summary', 'summarize', 'overview', 'what is this document about',
                               'what does this document contain', 'what is in this document',
                               'tell me about', 'describe', 'explain this document'])
        
        if is_summary_query:
            system_prompt = """You are a document summarization assistant. Synthesize information from multiple sources to create a comprehensive summary.

CRITICAL RULES:
- Synthesize information from ALL provided context chunks
- Create a coherent summary even if chunks are from different sections
- Address all sub-questions to build a complete picture
- Include key points, main topics, and important information
- Organize information logically
- DO NOT say "context does not contain" - synthesize what IS available
- Focus on main themes and important details
- DO NOT add greetings, signatures, or closing statements"""
            
            user_prompt = f"""Original Question: {question}

Sub-Questions Analyzed:
{sub_queries_text}

Context from documents:
{context}

Instructions:
1. Analyze ALL retrieved context chunks
2. Synthesize information from multiple sources to create a comprehensive summary
3. Address all sub-questions to build a complete picture
4. Include: overview, key points, main topics, important information
5. Organize the summary logically
6. Use information from the context - synthesize what is available
7. DO NOT add greetings or closing statements

Summary:"""
        else:
            system_prompt = """You are a precise technical assistant that provides comprehensive, accurate answers by synthesizing information from multiple sources.

CRITICAL: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images. This section contains OCR text extracted from images and is the PRIMARY and MOST RELIABLE source for answering questions about image content. The section is marked with prominent warning symbols (⚠️⚠️⚠️) to make it highly visible. 

When asked:
- "what is in image X" or "what information is in image X"
- "what tools are in DRAWER X" or "what's in drawer X"
- "what part numbers are listed" or "what tools are listed"
- "give me information about images" or "what content is in the images"
- Any question mentioning images, drawers, tools, part numbers, or visual content

You MUST:
1. Look in the Image Content section FIRST (before checking other context)
2. Find the relevant image number or content
3. Provide detailed, specific information from the OCR text
4. Include exact part numbers, tool names, quantities, and other details from the OCR text
5. Do NOT say "context does not contain" if the Image Content section has relevant information

Each image is numbered - match the image number from the question to the image number in the Image Content section. If the question asks about "image 1" or "first image", look for "Image 1:" in the Image Content section.

CRITICAL RULES:
- Synthesize information from ALL provided context chunks
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
- Address all relevant sub-questions if they relate to the original question
- Be specific and cite exact values, measurements, and specifications when available
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- End your answer when you have provided the information - do not add unnecessary text"""
            
            user_prompt = f"""Original Question: {question}

Sub-Questions Analyzed:
{sub_queries_text}

Context from documents:
{context}

Instructions:
1. Analyze ALL retrieved context chunks carefully
2. Synthesize information from multiple sources to answer the original question comprehensively
3. If the context contains relevant information, use it to provide a comprehensive answer
4. Address all sub-questions if they are relevant to the original question
5. Provide specific details, numbers, and specifications when available
6. Only say information is not available if you have thoroughly checked ALL chunks and found nothing relevant
7. DO NOT add greetings, signatures, or closing statements
8. DO NOT repeat information or phrases
9. Stop immediately after providing the answer

Answer:"""
        
        try:
            # Get temperature and max_tokens from UI config or defaults
            ui_temp = getattr(self, 'ui_config', {}).get('temperature', ARISConfig.DEFAULT_TEMPERATURE)
            ui_max_tokens = getattr(self, 'ui_config', {}).get('max_tokens', ARISConfig.DEFAULT_MAX_TOKENS)
            
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=ui_temp,  # Use UI config
                max_tokens=ui_max_tokens,  # Use UI config
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]
            )
            
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                response_tokens = self.count_tokens(answer)
            
            answer = self._clean_answer(answer)
            return answer, response_tokens
        except Exception as e:
            logger.error(f"Error in OpenAI Agentic RAG synthesis: {e}", exc_info=True)
            # Fallback to standard generation
            return self._query_openai(question, context, relevant_docs)
    
    def _query_cerebras_agentic(
        self,
        question: str,
        sub_queries: List[str],
        context: str,
        relevant_docs: List = None
    ) -> tuple:
        """
        Query Cerebras with Agentic RAG synthesis prompt.
        
        Args:
            question: Original question
            sub_queries: List of sub-queries analyzed
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        
        Returns:
            Tuple of (answer, response_tokens)
        """
        # For now, fallback to standard Cerebras query
        # TODO: Implement Cerebras-specific synthesis if needed
        logger.warning("Cerebras Agentic RAG synthesis not fully implemented, using standard query")
        return self._query_cerebras(question, context, relevant_docs, None, None)
    
    def save_vectorstore(self, path: str = "vectorstore"):
        """Save vector store to disk (FAISS only) or cloud (OpenSearch)"""
        from scripts.setup_logging import get_logger
        from config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vectorstore:
            if self.vector_store_type == "faiss":
                # Use model-specific path to support multiple embedding models
                base_path = path
                model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
                if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                    # If get_vectorstore_path returns relative path, join with base_path
                    model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
                else:
                    # Use the model-specific path directly
                    model_specific_path = model_specific_path
                
                logger.info(f"[STEP 1] RAGSystem: Saving FAISS vectorstore to: {model_specific_path}")
                # Create directory if it doesn't exist
                os.makedirs(model_specific_path, exist_ok=True)
                
                try:
                    self.vectorstore.save_local(model_specific_path)
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore saved to {model_specific_path}")
                    
                    # Also save document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 2] RAGSystem: Saving document index to: {index_path}")
                    with open(index_path, 'wb') as f:
                        pickle.dump({
                            'document_index': self.document_index,
                            'total_tokens': self.total_tokens,
                            'embedding_model': self.embedding_model
                        }, f)
                    logger.info(f"✅ [STEP 2] RAGSystem: Document index saved to {index_path}")
                except Exception as e:
                    logger.error(f"❌ [STEP 1] RAGSystem: Failed to save vectorstore: {e}", exc_info=True)
            else:
                # OpenSearch stores data in cloud, no local save needed
                logger.info("ℹ️ [STEP 1] RAGSystem: OpenSearch stores data in the cloud. No local save needed.")
    
    def load_vectorstore(self, path: str = "vectorstore"):
        """Load vector store from disk (FAISS) or cloud (OpenSearch) with model-specific path"""
        from scripts.setup_logging import get_logger
        from config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vector_store_type == "faiss":
            # Use model-specific path
            base_path = path
            model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
            if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                # If get_vectorstore_path returns relative path, join with base_path
                model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
            else:
                # Use the model-specific path directly
                model_specific_path = model_specific_path
            
            logger.info(f"[STEP 1] RAGSystem: Loading FAISS vectorstore from: {model_specific_path}")
            if os.path.exists(model_specific_path):
                logger.info(f"[STEP 1.1] RAGSystem: Vectorstore path exists, loading...")
                try:
                    self.vectorstore = VectorStoreFactory.load_vector_store(
                        store_type="faiss",
                        embeddings=self.embeddings,
                        path=model_specific_path
                    )
                    # Also load document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 1.2] RAGSystem: Loading document index from: {index_path}")
                    if os.path.exists(index_path):
                        with open(index_path, 'rb') as f:
                            data = pickle.load(f)
                            self.document_index = data.get('document_index', {})
                            self.total_tokens = data.get('total_tokens', 0)
                            saved_model = data.get('embedding_model', 'unknown')
                            if saved_model != self.embedding_model:
                                logger.warning(
                                    f"⚠️ [STEP 1.2] RAGSystem: Vectorstore was created with '{saved_model}' "
                                    f"but current model is '{self.embedding_model}'. "
                                    f"Dimension mismatch may occur."
                                )
                            logger.info(f"✅ [STEP 1.2] RAGSystem: Document index loaded - {len(self.document_index)} documents, {self.total_tokens:,} tokens")
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore loaded successfully")
                    return True
                except Exception as e:
                    error_msg = str(e)
                    if "dimension" in error_msg.lower():
                        logger.warning(
                            f"⚠️ [STEP 1] RAGSystem: Dimension mismatch when loading vectorstore.\n"
                            f"   This vectorstore was created with a different embedding model.\n"
                            f"   It will be recreated automatically when you add new documents."
                        )
                        return False
                    else:
                        raise
            else:
                # Check if old path exists (backward compatibility)
                if os.path.exists(path) and os.path.isdir(path) and not os.path.basename(path).startswith("text-embedding"):
                    logger.info(f"[STEP 1.1] RAGSystem: Found old vectorstore at {path}, migrating to model-specific path...")
                    try:
                        # Try to load from old path
                        self.vectorstore = VectorStoreFactory.load_vector_store(
                            store_type="faiss",
                            embeddings=self.embeddings,
                            path=path
                        )
                        # If successful, save to new model-specific path
                        self.save_vectorstore(path)
                        logger.info(f"✅ [STEP 1.1] RAGSystem: Migrated to model-specific path: {model_specific_path}")
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 1.1] RAGSystem: Could not migrate old vectorstore: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ [STEP 1] RAGSystem: Vectorstore path does not exist: {model_specific_path}")
            return False
        else:
            # OpenSearch loads from cloud index automatically
            logger.info("[STEP 1] RAGSystem: OpenSearch loads data from the cloud index automatically.")
            try:
                # Load document index map
                self._load_document_index_map()
                
                if self.document_index_map:
                    # Initialize multi-index manager
                    from vectorstores.opensearch_store import OpenSearchMultiIndexManager
                    self.multi_index_manager = OpenSearchMultiIndexManager(
                        embeddings=self.embeddings,
                        domain=self.opensearch_domain,
                        region=getattr(self, 'region', None)
                    )
                    
                    # Pre-load all indexes
                    for index_name in self.document_index_map.values():
                        self.multi_index_manager.get_or_create_index_store(index_name)
                    
                    logger.info(f"✅ [STEP 1.1] RAGSystem: Loaded {len(self.document_index_map)} document indexes")
                    return True
                else:
                    # Fallback to single index (backward compatibility)
                    logger.info(f"[STEP 1.1] RAGSystem: No document index mappings found, using default index: {self.opensearch_index or 'aris-rag-index'}")
                self.vectorstore = VectorStoreFactory.load_vector_store(
                    store_type="opensearch",
                    embeddings=self.embeddings,
                    path=self.opensearch_index or "aris-rag-index",
                    opensearch_domain=self.opensearch_domain,
                    opensearch_index=self.opensearch_index
                )
                logger.info(f"✅ [STEP 1.1] RAGSystem: OpenSearch vectorstore connected successfully")
                return True
            except Exception as e:
                logger.error(f"❌ [STEP 1.1] RAGSystem: Failed to load OpenSearch vectorstore: {str(e)}")
                return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG system."""
        total_documents = len(self.document_index)
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        
        # Estimate embedding cost (text-embedding-3-small: $0.02 per 1M tokens)
        estimated_cost = (self.total_tokens / 1_000_000) * 0.02
        
        return {
            'total_documents': total_documents,
            'total_chunks': total_chunks,
            'total_tokens': self.total_tokens,
            'estimated_embedding_cost_usd': estimated_cost
        }
    
    def get_chunk_token_stats(self) -> Dict:
        """
        Get token statistics for all chunks in the vectorstore.
        Uses metrics collector data if available, otherwise estimates from vectorstore.
        
        Returns:
            Dict with token distribution statistics
        """
        if self.vectorstore is None:
            return {
                'chunk_token_counts': [],
                'avg_tokens_per_chunk': 0,
                'min_tokens_per_chunk': 0,
                'max_tokens_per_chunk': 0,
                'total_chunks': 0,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Try to get actual chunk token counts from vectorstore first (most accurate)
        chunk_token_counts = []
        try:
            # Access the underlying documents from vectorstore
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'page_content'):
                        # Always recalculate from actual content for accuracy
                        # This ensures we get the real token count, not potentially stale metadata
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                    elif hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        # Fallback to metadata if page_content not available
                        chunk_token_counts.append(doc.metadata['token_count'])
        except Exception:
            pass
        
        # Fallback: Try to get from metrics collector
        if not chunk_token_counts and self.metrics_collector and hasattr(self.metrics_collector, 'processing_metrics'):
            for metric in self.metrics_collector.processing_metrics:
                if metric.success and metric.chunks_created > 0:
                    # Estimate tokens per chunk (total tokens / chunks)
                    tokens_per_chunk = metric.tokens_extracted / metric.chunks_created if metric.chunks_created > 0 else 0
                    # Add tokens for each chunk (approximate)
                    for _ in range(metric.chunks_created):
                        chunk_token_counts.append(int(tokens_per_chunk))
        
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # If we got actual counts from vectorstore, return them
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Fallback: try to get from vectorstore directly (if not already done)
        try:
            # Access the underlying documents
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                chunk_token_counts = []
                
                # Extract token counts from document metadata or count from content
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        chunk_token_counts.append(doc.metadata['token_count'])
                    elif hasattr(doc, 'page_content'):
                        # Count tokens from actual content
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                
                if chunk_token_counts:
                    return {
                        'chunk_token_counts': chunk_token_counts,
                        'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                        'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                        'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                        'total_chunks': len(chunk_token_counts),
                        'configured_chunk_size': self.chunk_size,
                        'configured_chunk_overlap': self.chunk_overlap
                    }
        except Exception:
            pass
        
        # Final fallback: estimate from total tokens and chunks
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        if total_chunks > 0 and self.total_tokens > 0:
            avg_tokens = self.total_tokens / total_chunks
            # Create a distribution estimate
            estimated_counts = [int(avg_tokens)] * total_chunks
            return {
                'chunk_token_counts': estimated_counts,
                'avg_tokens_per_chunk': avg_tokens,
                'min_tokens_per_chunk': int(avg_tokens * 0.8),  # Estimate
                'max_tokens_per_chunk': int(avg_tokens * 1.2),  # Estimate
                'total_chunks': total_chunks,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Return empty stats if nothing works
        return {
            'chunk_token_counts': [],
            'avg_tokens_per_chunk': 0,
            'min_tokens_per_chunk': 0,
            'max_tokens_per_chunk': 0,
            'total_chunks': 0,
            'configured_chunk_size': self.chunk_size,
            'configured_chunk_overlap': self.chunk_overlap
        }


    def _store_extracted_images(
        self,
        image_content_map: Dict,
        contributing_docs: set
    ):
        """
        Store extracted images in OpenSearch at query time.
        
        Args:
            image_content_map: Dictionary mapping (source, image_index) to content list
            contributing_docs: Set of document sources that contributed images
        """
        if not image_content_map:
            return
        
        # Only store if OpenSearch is configured
        if (not hasattr(self, 'vector_store_type') or 
            self.vector_store_type.lower() != 'opensearch'):
            return
        
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            # Import image logger
            try:
                from utils.image_extraction_logger import image_logger
            except ImportError:
                image_logger = None
            
            # Log storage start
            if image_logger:
                total_images = sum(len(contents) for contents in image_content_map.values())
                image_logger.log_storage_start(
                    source="query_time",
                    image_count=total_images,
                    storage_method="opensearch"
                )
            
            # Initialize images store
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            # Convert image_content_map to list of image dictionaries
            images_to_store = []
            for (source, img_idx), contents in image_content_map.items():
                for content_info in contents:
                    image_data = {
                        'source': source,
                        'image_number': img_idx,
                        'page': content_info.get('page', 0),
                        'ocr_text': content_info.get('ocr_text', ''),
                        'marker_detected': True,
                        'extraction_method': 'query_time',
                        'full_chunk': content_info.get('full_chunk', ''),
                        'context_before': content_info.get('context_before', '')
                    }
                    images_to_store.append(image_data)
                    
                    # Log query extraction
                    if image_logger:
                        image_logger.log_query_extraction(
                            source=source,
                            image_number=img_idx,
                            ocr_text_length=len(content_info.get('ocr_text', '')),
                            extraction_method='query_time',
                            page=content_info.get('page')
                        )
            
            # Store images in batch
            if images_to_store:
                image_ids = images_store.store_images_batch(images_to_store)
                
                # Log storage success
                if image_logger:
                    image_logger.log_storage_success(
                        source="query_time",
                        images_stored=len(image_ids),
                        image_ids=image_ids
                    )
                
                logger.info(f"✅ Stored {len(image_ids)} images in OpenSearch at query time")
        except ImportError as e:
            logger.debug(f"OpenSearch images store not available: {str(e)}")
        except Exception as e:
            # Log storage failure
            if image_logger:
                total_images = sum(len(contents) for contents in image_content_map.values())
                image_logger.log_storage_failure(
                    source="query_time",
                    error=str(e),
                    images_attempted=total_images
                )
            logger.warning(f"⚠️  Failed to store images in OpenSearch: {str(e)}")
    
    def query_images(
        self,
        question: str,
        source: Optional[str] = None,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search images directly in OpenSearch images index.
        
        Args:
            question: Search query
            source: Optional document source to filter by
            k: Number of results to return
            
        Returns:
            List of image dictionaries with OCR text
        """
        # Only search if OpenSearch is configured
        if (not hasattr(self, 'vector_store_type') or 
            self.vector_store_type.lower() != 'opensearch'):
            logger.warning("OpenSearch not configured - cannot search images")
            return []
        
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            # Initialize images store
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )
            
            # Search images
            results = images_store.search_images(
                query=question,
                source=source,
                k=k
            )
            
            logger.info(f"Found {len(results)} images matching query: {question[:50]}")
            return results
        except ImportError as e:
            logger.warning(f"OpenSearch images store not available: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Failed to search images: {str(e)}")
            return []
