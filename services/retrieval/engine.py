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

# ============================================================================
# Mixin imports - methods extracted from this file for maintainability
# ============================================================================
from services.retrieval.utils import UtilsMixin
from services.retrieval.search import SearchMixin
from services.retrieval.citation import PageExtractionMixin, SnippetMixin, CitationRankingMixin
from services.retrieval.answer import AnswerGeneratorMixin, AgenticRAGMixin
from services.retrieval.crud import StorageMixin

# Set up logging
logger = logging.getLogger(__name__)

class RetrievalEngine(
    UtilsMixin,
    SearchMixin,
    PageExtractionMixin,
    SnippetMixin,
    CitationRankingMixin,
    AnswerGeneratorMixin,
    AgenticRAGMixin,
    StorageMixin,
):
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
        
        # Dual-Model strategy: Track simple and deep models
        self.simple_query_model = ARISConfig.SIMPLE_QUERY_MODEL
        self.deep_query_model = ARISConfig.DEEP_QUERY_MODEL
        
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
        actual_embeddings = None
        if os.getenv('OPENAI_API_KEY'):
            actual_embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.embedding_model
            )
        else:
            actual_embeddings = LocalHashEmbeddings(model_name=self.embedding_model)
            
        # Wrap embeddings with caching to avoid redundant API calls
        from shared.utils.cached_embeddings import CachedEmbeddings
        self.embeddings = CachedEmbeddings(actual_embeddings)
        self.vectorstore = None
        
        # Try to load existing FAISS vectorstore if using FAISS
        if self.vector_store_type == 'faiss':
            try:
                # Try current model first
                vectorstore_path = ARISConfig.get_vectorstore_path(self.embedding_model)
                if os.path.exists(vectorstore_path):
                    logger.info(f"Attempting to load existing FAISS vectorstore from {vectorstore_path}")
                    self.vectorstore = VectorStoreFactory.load_vector_store(
                        store_type="faiss",
                        embeddings=self.embeddings,
                        path=vectorstore_path
                    )
                    if self.vectorstore:
                        logger.info("✅ Loaded existing FAISS vectorstore")
                else:
                    # Try alternative embedding models
                    alternative_models = ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002']
                    for alt_model in alternative_models:
                        if alt_model != self.embedding_model:
                            alt_path = ARISConfig.get_vectorstore_path(alt_model)
                            if os.path.exists(alt_path):
                                logger.info(f"Trying alternative model {alt_model} at {alt_path}")
                                try:
                                    alt_embeddings = OpenAIEmbeddings(
                                        openai_api_key=os.getenv('OPENAI_API_KEY'),
                                        model=alt_model
                                    ) if os.getenv('OPENAI_API_KEY') else LocalHashEmbeddings(model_name=alt_model)
                                    self.vectorstore = VectorStoreFactory.load_vector_store(
                                        store_type="faiss",
                                        embeddings=alt_embeddings,
                                        path=alt_path
                                    )
                                    if self.vectorstore:
                                        logger.info(f"✅ Loaded FAISS vectorstore with model {alt_model}")
                                        # Update embedding model to match loaded vectorstore
                                        self.embedding_model = alt_model
                                        self.embeddings = alt_embeddings
                                        break
                                except Exception as e:
                                    logger.debug(f"Could not load with {alt_model}: {e}")
                                    continue
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                self.vectorstore = None
        
        # Metrics collector
        self.metrics_collector = metrics_collector
        if self.metrics_collector is None:
            # Create a local one if not provided
            from metrics.metrics_collector import MetricsCollector
            self.metrics_collector = MetricsCollector()
            
        # Initialize S3 Service
        self.s3_service = S3Service()
            
        # Use token-aware text splitter with configurable chunking
        # Accuracy Upgrade: Use RecursiveCharacterTextSplitter for context preservation
        # This splits by paragraphs/headers first, then falls back to tokens
        if RecursiveCharacterTextSplitter:
            try:
                self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                    model_name=embedding_model,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    separators=["\n\n", "\n", " ", ""]
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
        
        # Accuracy Upgrade: Initialize FlashRank Reranker
        self.ranker = None
        if Ranker:
            try:
                # Get reranker config from settings
                multilingual_config = ARISConfig.get_multilingual_config()
                
                # Determine model name
                # Default to English model if not specified, but switch to multilingual if auto-translate or ingestion translation is on
                model_name = "ms-marco-MiniLM-L-12-v2"  # Default English
                
                if (multilingual_config.get('enable_auto_translate') or 
                    multilingual_config.get('translate_on_ingestion')):
                    # Use a model with better multilingual capabilities if available in FlashRank
                    # For now, we stick to the high-quality model but allow config override
                    # Ideal: "ms-marco-MultiBERT-L-12" if supported by FlashRank cache
                    pass
                
                # Allow env override
                config_model = os.getenv('RERANKER_MODEL_NAME')
                if config_model:
                    model_name = config_model
                
                self.ranker = Ranker(model_name=model_name, cache_dir="models/cache")
                logger.info(f"✅ FlashRank Reranker initialized ({model_name})")
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
        
        # Metrics collector is already initialized above (lines 153-158)
        
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
                # Store modification time to detect changes
                self._document_index_map_mtime = os.path.getmtime(self.document_index_map_path)
            except Exception as e:
                logger.warning(f"Could not load document index map: {e}")
        else:
            self._document_index_map_mtime = 0
    
    def _check_and_reload_document_index_map(self):
        """Check if document_index_map file was modified and reload if needed."""
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not hasattr(self, '_document_index_map_mtime'):
            self._document_index_map_mtime = 0
        
        if os.path.exists(self.document_index_map_path):
            try:
                current_mtime = os.path.getmtime(self.document_index_map_path)
                if current_mtime > self._document_index_map_mtime:
                    logger.info("Document index map file was modified, reloading...")
                    self._load_document_index_map()
                    return True
            except Exception as e:
                logger.warning(f"Could not check document index map modification time: {e}")
        return False
    
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
    

    # ========================================================================
    # Methods below are provided by mixin classes:
    # - UtilsMixin (utils.py): count_tokens, text truncation, answer cleaning, query analysis
    # - SearchMixin (search/retriever.py): chunk retrieval, occurrence search, dedup
    # - PageExtractionMixin (citation/page_extractor.py): page number & source extraction
    # - SnippetMixin (citation/snippet.py): snippet generation, semantic similarity
    # - CitationRankingMixin (citation/ranking.py): citation dedup & ranking
    # - AnswerGeneratorMixin (answer/generator.py): OpenAI/Cerebras answer generation
    # - AgenticRAGMixin (answer/agentic.py): agentic RAG synthesis
    # - StorageMixin (crud/storage.py): vectorstore persistence, stats, images, deletion
    # ========================================================================

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
        max_tokens: int = None,  # NEW: UI max_tokens
        active_sources: Optional[List[str]] = None,  # NEW: Document filtering
        response_language: Optional[str] = None,  # NEW: Response language
        filter_language: Optional[str] = None,  # NEW: Language filtering
        auto_translate: bool = False  # NEW: Auto-detect and translate queries
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
            response_language: Language to answer in (e.g. 'Spanish')
            filter_language: Filter retrieval by language code (e.g. 'spa')
        
        Returns:
            Dict with answer, sources, and context chunks
        """
        
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
        
        # IMPROVED: Auto-detect specific query types that benefit from higher keyword weight
        # Contact info queries often have specific words (email, phone) that need keyword matching
        question_lower = question.lower()
        specific_info_keywords = ['email', 'phone', 'contact', 'address', 'fax', 'website', 'url', 
                                  'correo', 'teléfono', 'contacto', 'dirección',  # Spanish
                                  'número', 'numero']  # Additional Spanish variants
        found_keywords = [kw for kw in specific_info_keywords if kw in question_lower]
        
        # QA FIX: Also detect safety/cleaning/maintenance queries that need comprehensive retrieval
        # These queries often have critical information scattered across multiple sections (e.g., solvents, procedures)
        safety_keywords = ['clean', 'cleaning', 'solvent', 'alcohol', 'acetone', 'isopropanol', 'ethanol',
                          'maintenance', 'procedure', 'safety', 'warning', 'caution', 'damage', 'prevent',
                          'limpieza', 'solvente', 'mantenimiento', 'procedimiento', 'seguridad',  # Spanish
                          'advertencia', 'precaución', 'daño', 'prevenir', 'surface', 'heating', 'layer']
        found_safety_keywords = [kw for kw in safety_keywords if kw in question_lower]
        
        # Log for debugging
        logger.info(f"🔍 Contact keyword check: search_mode={search_mode}, found_keywords={found_keywords}")
        logger.info(f"🔍 Safety keyword check: found_safety_keywords={found_safety_keywords}")
        
        # Auto-adjust semantic weight for contact-related queries (always adjust if keywords found)
        # QA DATA: Contact queries often fail → need VERY aggressive keyword matching
        # QA FINDING: 70-90% information retrieved → need higher k and disable reranking
        is_contact_query = False
        is_safety_query = len(found_safety_keywords) > 0
        
        if found_keywords and search_mode == 'hybrid':
            is_contact_query = True
            # For contact-related queries, use VERY LOW semantic weight (QA-driven)
            original_semantic_weight = semantic_weight if semantic_weight is not None else 0.7
            semantic_weight = 0.1  # Increased from 0.35 to 0.1 (90% keyword!) for contact queries
            logger.info(f"🔧 AUTO-ADJUSTED semantic_weight {original_semantic_weight:.2f} -> {semantic_weight:.2f} for contact keywords: {found_keywords} [QA-driven]")
            
            # Also increase k for contact queries to ensure we find scattered contact info
            # QA DATA: 70-90% info retrieved with k=40 → increase to k=50 minimum
            if k is None:
                k = ARISConfig.DEFAULT_RETRIEVAL_K
            if k < 40:  # Increased threshold from 30 to 40
                original_k = k
                k = max(50, k * 1.5)  # At least 50 chunks (increased from 40) for contact queries
                logger.info(f"🔧 AUTO-INCREASED k: {original_k} → {int(k)} for contact query [QA-driven: 70-90% issue]")
        
        # QA FIX: Increase k for safety/cleaning queries to ensure comprehensive coverage
        # QA FINDING: Missing solvent information (alcohol, acetone, isopropanol) in answers
        if is_safety_query and search_mode == 'hybrid':
            if k is None:
                k = ARISConfig.DEFAULT_RETRIEVAL_K
            if k < 30:
                original_k = k
                k = max(40, k * 1.5)  # At least 40 chunks for safety queries
                logger.info(f"🔧 AUTO-INCREASED k: {original_k} → {int(k)} for safety/cleaning query [QA-driven: missing solvent info]")
            
            # Slightly reduce semantic weight for safety queries (more keyword matching)
            if semantic_weight is None:
                semantic_weight = 0.7
            if semantic_weight > 0.3:
                original_semantic_weight = semantic_weight
                semantic_weight = 0.25  # 75% keyword for safety queries
                logger.info(f"🔧 AUTO-ADJUSTED semantic_weight {original_semantic_weight:.2f} -> {semantic_weight:.2f} for safety keywords: {found_safety_keywords} [QA-driven]")
        
        keyword_weight = 1.0 - semantic_weight
        
        # QA FIX: Increase temperature for contact queries to improve synthesis of scattered information
        if is_contact_query:
            original_temperature = temperature if temperature is not None else ARISConfig.DEFAULT_TEMPERATURE
            temperature = max(0.3, original_temperature)  # At least 0.3 for contact queries
            logger.info(f"🌡️ AUTO-INCREASED temperature: {original_temperature:.1f} → {temperature:.1f} for contact query (better synthesis) [QA-driven: 70-90% issue]")
        
        # SYNC: Check and reload document index map before querying
        self._check_and_reload_document_index_map()
        
        query_start_time = time_module.time()
        # [NEW] Track request ID on instance for sub-methods to use
        import uuid
        self.current_request_id = getattr(self, 'current_request_id', str(uuid.uuid4()))
        req_id = self.current_request_id
        
        # Determine active sources for this request
        # CRITICAL FIX: Don't use stale instance-level filter for API requests
        # Each request should be independent - None or [] means "search all documents"
        if active_sources is None or active_sources == []:
            # No filter or empty list - search ALL documents
            # Clear any stale instance-level filter to prevent stateful bugs
            self.active_sources = None
            active_sources = None  # Will trigger "search all indexes" logic below
            logger.info(f"📚 [ACTIVE_SOURCES] ALL DOCUMENTS mode - searching across all indexes")
        else:
            # Specific documents passed - set filter for this request
            self.active_sources = active_sources
            logger.info(f"📄 [ACTIVE_SOURCES] Document filter: {active_sources}")
            
        # Store UI configuration for citation extraction and LLM calls
        self.ui_config = {
            'temperature': temperature if temperature is not None else ARISConfig.DEFAULT_TEMPERATURE,
            'max_tokens': max_tokens if max_tokens is not None else ARISConfig.DEFAULT_MAX_TOKENS,
            'active_sources': active_sources,
            'response_language': response_language
        }
        
        # Auto-translation: Detect language and translate query to English for better search
        original_question = question
        detected_language = None
        needs_response_translation = False
        self.expanded_query_for_keywords = None  # Initialize for cross-language query expansion
        
        # Log the auto_translate setting for debugging
        logger.info(f"🌐 [AUTO-TRANSLATE] auto_translate={auto_translate}, question='{question[:50]}...'")
        
        if auto_translate:
            try:
                from services.language.detector import get_detector
                from services.language.translator import get_translator
                
                trans_start = time_module.time()
                detector = get_detector()
                detected_language = detector.detect(original_question)  # FIX: Detect from original, not potentially translated question
                
                # If query is not English, translate for better search matching
                if detected_language and detected_language != "en":
                    translator = get_translator()
                    translated_question = translator.translate(question, target_lang="en", source_lang=detected_language)
                    
                    trans_time = time_module.time() - trans_start
                    # Improvement 2 & 5: Dual-Language Search
                    # Combine original (for keyword match on original text) and translated (for semantic match on English embeddings)
                    # We pass the translated question as the primary for semantic search, but append original for keyword boosts
                    logger.info(f"🌐 [TRANSLATION] Detected language: {detected_language}")
                    logger.info(f"🌐 [TRANSLATION] Original: '{question}'")
                    logger.info(f"🌐 [TRANSLATION] Translated: '{translated_question}'")
                    logger.info(f"🌐 [TRANSLATION] Time: {trans_time:.2f}s")
                    
                    # Use English for retrieval but keep context
                    original_question = question
                    question = translated_question
                    
                    # FIX 1: For cross-language queries, adjust semantic/keyword weights
                    # Cross-language semantic search is less reliable, so prioritize keyword matching
                    # QA DATA: English queries on Spanish docs score only 1.71/10 → need more aggressive keyword focus
                    if search_mode == 'hybrid' and semantic_weight is not None:
                        original_semantic_weight = semantic_weight
                        # VERY LOW semantic weight (0.2) for cross-language based on QA findings
                        semantic_weight = min(0.2, semantic_weight)  # Reduced from 0.4 to 0.2 (80% keyword!)
                        keyword_weight = 1.0 - semantic_weight
                        logger.info(f"🌐 [CROSS-LANGUAGE] Adjusted weights: semantic={semantic_weight:.2f} (was {original_semantic_weight:.2f}), keyword={keyword_weight:.2f} [QA-driven]")
                    elif search_mode == 'hybrid':
                        # If semantic_weight not set, use cross-language optimized default
                        semantic_weight = 0.2  # Reduced from 0.4 to 0.2 based on QA findings
                        keyword_weight = 0.8  # Increased from 0.6 to 0.8
                        logger.info(f"🌐 [CROSS-LANGUAGE] Using QA-optimized weights: semantic=0.20, keyword=0.80 (English 1.71/10 → target 4.0+/10)")
                    
                    # FIX 3: Increase k for cross-language queries
                    # Cross-language retrieval needs more chunks because similarity scores are less accurate
                    # QA DATA: Low scores indicate insufficient context retrieval
                    if k is None:
                        k = ARISConfig.DEFAULT_RETRIEVAL_K
                    if k < 25:  # Increased threshold from 15 to 25
                        original_k = k
                        k = max(30, k * 2)  # At least 30 chunks (increased from 20), or double the original k
                        logger.info(f"🌐 [CROSS-LANGUAGE] Increased k: {original_k} → {k} for better coverage [QA-driven]")
                    
                    # FIX 2: Expand query with original language terms for better keyword matching
                    # This helps keyword search find matches in the original document language
                    # Store as instance variable for use in retrieval
                    if use_hybrid_search is None or use_hybrid_search:
                        # Store expanded query for keyword matching
                        self.expanded_query_for_keywords = f"{translated_question} {original_question}"
                        logger.info(f"🌐 [CROSS-LANGUAGE] Expanded query for keyword matching: '{self.expanded_query_for_keywords[:100]}...'")
                    else:
                        self.expanded_query_for_keywords = None
                    
                    # Set response language to original if not explicitly specified
                    if not response_language:
                        response_language = detector.get_language_name(detected_language)
                        self.ui_config['response_language'] = response_language
                        self.ui_config['query_language'] = detected_language  # Store for citation language matching
                        needs_response_translation = True
                        logger.info(f"Retrieval: Will translate response back to {response_language}")
                else:
                    logger.info(f"🌐 [AUTO-TRANSLATE] Query already in English (detected: {detected_language}), no translation needed")
                    # Even for English queries, set response_language if Auto was selected
                    if not response_language:
                        response_language = "English"
                        self.ui_config['response_language'] = response_language
                        self.ui_config['query_language'] = "en"  # Store for citation language matching
                        logger.info(f"Retrieval: Auto response language set to English (detected: {detected_language})")
            except Exception as e:
                logger.warning(f"Retrieval: Auto-translation failed, using original query: {e}")
                question = original_question
        else:
            logger.info(f"🌐 [AUTO-TRANSLATE] Disabled - searching with original query as-is")
        
        # FIX: Always detect query language for Auto response language, even when auto_translate is disabled
        # This ensures the LLM gets a specific language instruction instead of generic multilingual instructions
        if not response_language:
            try:
                from services.language.detector import get_detector
                detector = get_detector()
                detected_language = detector.detect(original_question)  # FIX: Detect from original question
                if detected_language:
                    response_language = detector.get_language_name(detected_language)
                    self.ui_config['response_language'] = response_language
                    self.ui_config['query_language'] = detected_language  # Store for citation language matching
                    logger.info(f"🌐 [AUTO-RESPONSE-LANG] Detected query language: {detected_language} → {response_language}")
                else:
                    # Fallback to English if detection fails
                    response_language = "English"
                    self.ui_config['response_language'] = response_language
                    logger.warning(f"🌐 [AUTO-RESPONSE-LANG] Language detection failed, defaulting to English")
            except Exception as e:
                logger.warning(f"🌐 [AUTO-RESPONSE-LANG] Failed to detect language for Auto response: {e}, defaulting to English")
                response_language = "English"
                self.ui_config['response_language'] = response_language
        
        if self.vectorstore is None:
            # For OpenSearch, the authoritative storage is in the cloud; initialize on demand.
            if self.vector_store_type == "opensearch":
                try:
                    target_index = getattr(self, 'opensearch_index', None) or "aris-rag-index"
                    self.vectorstore = VectorStoreFactory.create_vector_store(
                        store_type="opensearch",
                        embeddings=self.embeddings,
                        opensearch_domain=self.opensearch_domain,
                        opensearch_index=target_index
                    )
                    # Verify index has documents - BUT skip this check if we have per-document indexes
                    # Per-document indexes (aris-doc-*) are the primary storage, not the default index
                    has_per_doc_indexes = hasattr(self, 'document_index_map') and self.document_index_map and len(self.document_index_map) > 0
                    
                    if not has_per_doc_indexes and hasattr(self.vectorstore, 'count_documents'):
                        doc_count = self.vectorstore.count_documents()
                        if doc_count == 0:
                            # Check document registry to provide better error message
                            try:
                                from storage.document_registry import DocumentRegistry
                                registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                                docs = registry.list_documents()
                                if docs:
                                    processing_docs = [d for d in docs if d.get('status') == 'processing']
                                    if processing_docs:
                                        return {
                                            "answer": f"Document(s) are still processing. Please wait a few moments and try again. Processing: {', '.join([d.get('document_name', 'Unknown') for d in processing_docs[:3]])}",
                                            "sources": [],
                                            "context_chunks": [],
                                            "citations": [],
                                            "num_chunks_used": 0,
                                            "response_time": 0.0,
                                            "context_tokens": 0,
                                            "response_tokens": 0,
                                            "total_tokens": 0
                                        }
                                    else:
                                        return {
                                            "answer": f"Documents found in registry but not yet indexed. Please wait for indexing to complete or check document processing status. Found {len(docs)} document(s) in registry.",
                                            "sources": [],
                                            "context_chunks": [],
                                            "citations": [],
                                            "num_chunks_used": 0,
                                            "response_time": 0.0,
                                            "context_tokens": 0,
                                            "response_tokens": 0,
                                            "total_tokens": 0
                                        }
                            except Exception as e:
                                logger.debug(f"operation: {type(e).__name__}: {e}")
                                pass
                    elif has_per_doc_indexes:
                        logger.info(f"Skipping default index check - using per-document indexes ({len(self.document_index_map)} indexes available)")
                except Exception as e:
                    logger.warning(f"Could not initialize OpenSearch vectorstore for querying: {e}")
            else:
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

        if self.vectorstore is None:
            # For OpenSearch, check if we have per-document indexes first
            has_per_doc_indexes = hasattr(self, 'document_index_map') and self.document_index_map and len(self.document_index_map) > 0
            
            if self.vector_store_type == "opensearch" and has_per_doc_indexes:
                # Skip default vectorstore initialization - we'll use multi-index search
                logger.info(f"✅ Using per-document indexes ({len(self.document_index_map)} available) - skipping default vectorstore")
            elif self.vector_store_type == "opensearch":
                # No per-document indexes, try to initialize default
                try:
                    target_index = getattr(self, 'opensearch_index', None) or ARISConfig.AWS_OPENSEARCH_INDEX
                    self.vectorstore = VectorStoreFactory.create_vector_store(
                        store_type="opensearch",
                        embeddings=self.embeddings,
                        opensearch_domain=self.opensearch_domain,
                        opensearch_index=target_index
                    )
                    logger.info(f"✅ Initialized OpenSearch vectorstore (domain: {self.opensearch_domain}, index: {target_index})")
                except Exception as e:
                    logger.error(f"Failed to initialize OpenSearch vectorstore: {e}")
                    raise ValueError(
                        f"Could not initialize OpenSearch. Please check your AWS_OPENSEARCH_DOMAIN configuration. Error: {e}"
                    )
            
            # If still None AND no per-document indexes, check document registry for better error message
            has_per_doc_indexes = hasattr(self, 'document_index_map') and self.document_index_map and len(self.document_index_map) > 0
            
            if self.vectorstore is None and not has_per_doc_indexes:
                try:
                    from storage.document_registry import DocumentRegistry
                    registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                    docs = registry.list_documents()
                    if docs:
                        processing_docs = [d for d in docs if d.get('status') == 'processing']
                        failed_docs = [d for d in docs if d.get('status') == 'failed']
                        success_docs = [d for d in docs if d.get('status') == 'success' and d.get('chunks_created', 0) > 0]
                        
                        if success_docs:
                            # There are successfully processed documents, but vectorstore not loaded
                            return {
                                "answer": f"Documents are processed but vectorstore needs to be loaded. Please wait a moment and try again, or re-upload if the issue persists. Found {len(success_docs)} successfully processed document(s).",
                                "sources": [],
                                "context_chunks": [],
                                "citations": [],
                                "num_chunks_used": 0,
                                "response_time": 0.0,
                                "context_tokens": 0,
                                "response_tokens": 0,
                                "total_tokens": 0
                            }
                        elif processing_docs:
                            return {
                                "answer": f"Document(s) are still processing. Please wait a few moments and try again. Processing: {', '.join([d.get('document_name', 'Unknown') for d in processing_docs[:3]])}",
                                "sources": [],
                                "context_chunks": [],
                                "citations": [],
                                "num_chunks_used": 0,
                                "response_time": 0.0,
                                "context_tokens": 0,
                                "response_tokens": 0,
                                "total_tokens": 0
                            }
                        elif failed_docs:
                            return {
                                "answer": f"Document processing failed. Please re-upload the document(s). Failed: {', '.join([d.get('document_name', 'Unknown') for d in failed_docs[:3]])}",
                                "sources": [],
                                "context_chunks": [],
                                "citations": [],
                                "num_chunks_used": 0,
                                "response_time": 0.0,
                                "context_tokens": 0,
                                "response_tokens": 0,
                                "total_tokens": 0
                            }
                except Exception as e:
                    logger.debug(f"operation: {type(e).__name__}: {e}")
                    pass
                
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

        # Option A: Find all occurrences (page + snippet) within the active document
        try:
            is_occurrence_query, term = self._detect_occurrence_query(question)
            if is_occurrence_query:
                return self.find_all_occurrences(term)
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass
        
        # Log active document filter status
        if active_sources:
            logger.info(f"Document filter active: {active_sources} - queries will only search within these documents")
        else:
            logger.info("No document filter - queries will search across all documents")
            
            # AUTO-DETECT document mentions in question and filter accordingly
            # This helps when user asks "What is in VUORMAR MK?" without explicitly selecting the document
            if hasattr(self, 'document_index_map') and self.document_index_map:
                detected_docs = self._detect_document_in_question(question, list(self.document_index_map.keys()))
                if detected_docs:
                    active_sources = detected_docs
                    logger.info(f"🔍 Auto-detected document mention in question: {detected_docs} - filtering search to this document")
        
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

        if use_agentic_rag and (not self.use_cerebras) and (not self.openai_api_key):
            use_agentic_rag = False
        
        # Select target model based on search mode (Agent vs Simple)
        if use_agentic_rag:
            target_llm_model = self.deep_query_model
            logger.info(f"🧠 Agent Mode detected - switching to DEEP model: {target_llm_model}")
        else:
            target_llm_model = self.simple_query_model
            logger.info(f"⚡ Simple Mode detected - switching to FAST model: {target_llm_model}")

        # Agentic RAG: Decompose query and perform multi-query retrieval
        if use_agentic_rag:
            try:
                from services.retrieval.query_decomposer import QueryDecomposer
                
                # Initialize query decomposer with FAST model (gpt-4o-mini is 10x faster than gpt-4o)
                decomposition_model = getattr(ARISConfig, 'QUERY_DECOMPOSITION_MODEL', 'gpt-4o-mini')
                decomp_start = time_module.time()
                
                query_decomposer = QueryDecomposer(
                    llm_model=decomposition_model,
                    openai_api_key=self.openai_api_key
                )
                
                # Decompose query into sub-queries (use retrieval_question for better decomposition)
                sub_queries = query_decomposer.decompose_query(
                    retrieval_question,  # Use expanded question for decomposition
                    max_subqueries=agentic_config['max_sub_queries']
                )
                
                decomp_time = time_module.time() - decomp_start
                logger.info(f"⚡ Query decomposition: {decomp_time:.2f}s using {decomposition_model} → {len(sub_queries)} sub-queries")
                
                # If decomposition resulted in single query, use standard flow
                if len(sub_queries) == 1:
                    logger.info("Agentic RAG: Single query after decomposition, using standard retrieval")
                    use_agentic_rag = False
                    target_llm_model = self.simple_query_model
                    logger.info(f"⚡ Reverting to FAST model for single query: {target_llm_model}")
                else:
                    # Perform multi-query retrieval in parallel
                    all_chunks = []
                    chunks_per_subquery = agentic_config['chunks_per_subquery']
                    
                    retrieval_start = time_module.time()
                    
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(sub_queries), 5)) as executor:
                        future_to_query = {
                            executor.submit(
                                self._retrieve_chunks_for_query,
                                sub_query,
                                k=chunks_per_subquery,
                                use_mmr=use_mmr,
                                use_hybrid_search=use_hybrid_search,
                                semantic_weight=semantic_weight,
                                keyword_weight=keyword_weight,
                                search_mode=search_mode,
                                disable_reranking=is_contact_query,
                                active_sources=active_sources
                            ): sub_query for sub_query in sub_queries
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_query):
                            sub_query = future_to_query[future]
                            try:
                                sub_chunks = future.result()
                                all_chunks.extend(sub_chunks)
                                logger.debug(f"Retrieved {len(sub_chunks)} chunks for sub-query: {sub_query[:50]}...")
                            except Exception as e:
                                logger.warning(f"Failed to retrieve chunks for sub-query '{sub_query[:50]}...': {e}")
                    
                    retrieval_time = time_module.time() - retrieval_start
                    logger.info(f"⚡ Sub-query retrieval completed in {retrieval_time:.2f}s for {len(sub_queries)} sub-queries")
                    
                    if not all_chunks:
                        logger.warning("Agentic RAG: No chunks retrieved from any sub-query, falling back to standard retrieval")
                        use_agentic_rag = False
                        target_llm_model = self.simple_query_model
                        logger.info(f"⚡ Reverting to FAST model: {target_llm_model}")
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
                        if active_sources:
                            allowed_sources = set(active_sources)
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
                                logger.info(f"Agentic RAG: After filtering, {len(relevant_docs)} chunks from selected documents: {active_sources}")
                            else:
                                logger.warning(f"Agentic RAG: No chunks matched selected documents: {active_sources}. Available sources: {set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])}")
                                relevant_docs = []  # Return empty if no matches
                        
                        logger.info(f"Agentic RAG: Retrieved {len(all_chunks)} total chunks, {len(unique_chunks)} unique, using top {len(relevant_docs)}")
                        
                        # Use synthesis for answer generation
                        return self._synthesize_agentic_results(
                            question=question,
                            sub_queries=sub_queries,
                            relevant_docs=relevant_docs,
                            query_start_time=query_start_time,
                            model=target_llm_model  # Pass target model to synthesis
                        )
            except Exception as e:
                logger.warning(f"Agentic RAG failed: {e}. Falling back to standard retrieval.", exc_info=True)
                use_agentic_rag = False
                target_llm_model = self.simple_query_model # Update model if falling back
                logger.info(f"⚡ Reverting to FAST model after error: {target_llm_model}")
        
        # Standard RAG flow (or fallback from Agentic RAG)
        # Initialize flag to track if we should skip retriever logic
        skip_retriever_logic = False
        retriever = None  # Initialize retriever to None
        
        # Prepare filter for OpenSearch (early initialization for all paths)
        opensearch_filter = None
        if self.vector_store_type.lower() == "opensearch":
            # Construct OpenSearch filters
            filters = []
            
            # Language filtering (Global filter logic)
            if filter_language:
                 filters.append({"term": {"metadata.language.keyword": filter_language}})
            
            # Note: active_sources source filtering is handled differently per path:
            # - For per-document indexes: Handled by selecting specific indexes
            # - For standard/fallback: Handled by adding metadata filter (see below)
            
            # Combine early filters (like language)
            if filters:
                 if len(filters) == 1:
                     opensearch_filter = filters[0]
                 else:
                     opensearch_filter = {"bool": {"must": filters}}
        
        # For OpenSearch: Use per-document indexes instead of metadata filtering
        if self.vector_store_type == "opensearch":
            # Determine which index(es) to search
            indexes_to_search = []
            
            # IMPORTANT: use request-scoped active_sources (not only self.active_sources)
            if active_sources:
                # Search only indexes for selected documents
                # First, check if we have direct document_id -> index mapping
                if hasattr(self, '_document_id_to_index') and self._document_id_to_index:
                    for doc_id, index_name in self._document_id_to_index.items():
                        indexes_to_search.append(index_name)
                        logger.info(f"Using direct index mapping: {doc_id} -> {index_name}")
                
                # Also try document_name lookup
                for doc_name in active_sources:
                    if doc_name in self.document_index_map:
                        index_name = self.document_index_map[doc_name]
                        if index_name not in indexes_to_search:
                            indexes_to_search.append(index_name)
                            logger.info(f"Found index via document_name: {doc_name} -> {index_name}")
                    else:
                        # Try direct index lookup by document_id pattern (aris-doc-{document_id})
                        # If doc_name looks like a UUID, try it as document_id
                        import re
                        uuid_pattern = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
                        if uuid_pattern.match(doc_name):
                            direct_index = f"aris-doc-{doc_name}"
                            if direct_index not in indexes_to_search:
                                indexes_to_search.append(direct_index)
                                logger.info(f"Using direct index name for document_id: {direct_index}")
                        else:
                            logger.warning(f"Document '{doc_name}' not found in index map. Available: {list(self.document_index_map.keys())[:10]}")
                
                
                if not indexes_to_search:
                    # Simple fallback: use default index or all indexes
                    if self.opensearch_index:
                        indexes_to_search = [self.opensearch_index]
                    else:
                        indexes_to_search = list(self.document_index_map.values()) if self.document_index_map else []
                    logger.info(f"Document filter not available (or fallback), using {len(indexes_to_search)} index(es)")
            else:
                # No active_sources set - SEARCH ALL DOCUMENTS
                # Previously restricted to recent documents, which caused issues finding older files
                indexes_to_search = list(self.document_index_map.values()) if hasattr(self, 'document_index_map') and self.document_index_map else []
                
                if not indexes_to_search and self.opensearch_index:
                     indexes_to_search = [self.opensearch_index]
                     
                logger.info(f"No active_sources set - searching ALL {len(indexes_to_search)} available indexes")
                
                if not indexes_to_search:
                    # Fallback to default index if no mappings exist (backward compatibility)
                    indexes_to_search = [self.opensearch_index or "aris-rag-index"]
                    logger.info(f"No document index mappings found, using default index: {indexes_to_search[0]}")
            
            # Final safety check: ensure we have at least one index to search
            if not indexes_to_search:
                default_index = self.opensearch_index or "aris-rag-index"
                indexes_to_search = [default_index]
                logger.warning(f"⚠️ No indexes determined, using default index as last resort: {default_index}")
            
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
                        search_timer = time_module.time()
                        # For cross-language: use expanded query (translated + original) for better keyword matching
                        alternate_for_keywords = None
                        if original_question != retrieval_question:
                            # Cross-language query: use expanded query with both languages
                            alternate_for_keywords = f"{retrieval_question} {original_question}"
                            logger.debug(f"🌐 Using expanded alternate query for keyword matching: '{alternate_for_keywords[:100]}...'")
                        elif hasattr(self, 'expanded_query_for_keywords') and self.expanded_query_for_keywords:
                            alternate_for_keywords = self.expanded_query_for_keywords
                        
                        relevant_docs = store.hybrid_search(
                            query=retrieval_question,
                            query_vector=query_vector,
                            k=k,
                            semantic_weight=semantic_weight,
                            keyword_weight=keyword_weight,
                            filter=opensearch_filter, # Apply global filters
                            alternate_query=alternate_for_keywords or (original_question if original_question != retrieval_question else None)
                        )
                        search_duration = time_module.time() - search_timer
                        logger.info(f"Retrieval: [ReqID: {req_id}] Hybrid search completed in {search_duration:.2f}s: {len(relevant_docs)} results from index '{index_name}'")
                    except Exception as e:
                        logger.warning(f"Hybrid search failed, falling back to standard search: {e}")
                        # Fall through to standard search
                        if use_mmr:
                            fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                            lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                            
                            search_kwargs = {
                                "k": k,
                                "fetch_k": fetch_k,
                                "lambda_mult": lambda_mult
                            }
                            if opensearch_filter:
                                search_kwargs["filter"] = opensearch_filter
                                
                            retriever = store.vectorstore.as_retriever(
                                search_type="mmr",
                                search_kwargs=search_kwargs
                            )
                        else:
                            search_kwargs = {"k": k}
                            if opensearch_filter:
                                search_kwargs["filter"] = opensearch_filter
                                
                            retriever = store.vectorstore.as_retriever(
                                search_kwargs=search_kwargs
                            )
                        relevant_docs = retriever.invoke(retrieval_question)
                else:
                    # Standard search
                    if use_mmr:
                        fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                        lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                        
                        search_kwargs = {
                            "k": k,
                            "fetch_k": fetch_k,
                            "lambda_mult": lambda_mult
                        }
                        if opensearch_filter:
                            search_kwargs["filter"] = opensearch_filter
                            
                        retriever = store.vectorstore.as_retriever(
                            search_type="mmr",
                            search_kwargs=search_kwargs
                        )
                    else:
                        search_kwargs = {"k": k}
                        if opensearch_filter:
                            search_kwargs["filter"] = opensearch_filter
                            
                        retriever = store.vectorstore.as_retriever(
                            search_kwargs=search_kwargs
                        )
                    relevant_docs = retriever.invoke(retrieval_question)
            else:
                # Multiple indexes - search across all
                # For cross-language: use expanded query (translated + original) for better keyword matching
                alternate_for_keywords = None
                if original_question != retrieval_question:
                    # Cross-language query: use expanded query with both languages
                    alternate_for_keywords = f"{retrieval_question} {original_question}"
                    logger.debug(f"🌐 Using expanded alternate query for multi-index search: '{alternate_for_keywords[:100]}...'")
                elif hasattr(self, 'expanded_query_for_keywords') and self.expanded_query_for_keywords:
                    alternate_for_keywords = self.expanded_query_for_keywords
                
                relevant_docs = self.multi_index_manager.search_across_indexes(
                    query=retrieval_question,
                    index_names=indexes_to_search,
                    k=k,
                    use_mmr=use_mmr,
                    # Pass hybrid search parameters for Maximum Accuracy
                    use_hybrid_search=use_hybrid_search,
                    semantic_weight=semantic_weight,
                    keyword_weight=keyword_weight,
                    alternate_query=alternate_for_keywords or (original_question if original_question != retrieval_question else None),
                    fetch_k=ARISConfig.DEFAULT_MMR_FETCH_K if use_mmr else 50,
                    lambda_mult=ARISConfig.DEFAULT_MMR_LAMBDA if use_mmr else 0.3,
                    filter=opensearch_filter # Apply global filters (e.g. language)
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
            if self.vector_store_type.lower() == "opensearch":
                # Construct OpenSearch filters
                filters = []
                
                # Source filtering
                if active_sources:
                    valid_sources = [s for s in active_sources if s and s.strip()]
                    if valid_sources:
                        if len(valid_sources) == 1:
                            filters.append({"term": {"metadata.source.keyword": valid_sources[0]}})
                        else:
                            filters.append({"terms": {"metadata.source.keyword": valid_sources}})
                            
                # Language filtering
                if filter_language:
                     filters.append({"term": {"metadata.language.keyword": filter_language}})
                
                # Combine filters
                if filters:
                    if len(filters) == 1:
                        opensearch_filter = filters[0]
                    else:
                        opensearch_filter = {"bool": {"must": filters}}
            
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
                fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
                lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
                
                # Build search_kwargs with appropriate filter
                # For FAISS: Increase k when filtering is needed (FAISS doesn't support native filtering)
                # We'll retrieve more and filter post-retrieval
                effective_k = k
                if active_sources and self.vector_store_type.lower() != "opensearch":
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
                if active_sources and self.vector_store_type.lower() != "opensearch":
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
            except AttributeError as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
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
        # CRITICAL: Always apply post-retrieval filter to prevent document mixing (OpenSearch index isolation is not guaranteed)
        if active_sources:
            logger.info(f"🔒 [DOC_FILTER] Applying strict document filter: {active_sources}")
            # Log sources BEFORE filtering
            pre_filter_sources = set(doc.metadata.get('source', 'Unknown') for doc in relevant_docs)
            logger.info(f"🔒 [DOC_FILTER] PRE-FILTER sources ({len(relevant_docs)} docs): {pre_filter_sources}")
            
            allowed_sources = set(active_sources)
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
            
            # Log filtering results
            post_filter_sources = set(doc.metadata.get('source', 'Unknown') for doc in filtered_docs)
            logger.info(f"🔒 [DOC_FILTER] POST-FILTER sources ({len(filtered_docs)} docs): {post_filter_sources}")
            logger.info(f"🔒 [DOC_FILTER] Removed {len(relevant_docs) - len(filtered_docs)} docs from other documents")
            
            # Validate: Ensure NO documents from other sources slipped through
            invalid_sources = set()
            for doc in filtered_docs:
                doc_source = doc.metadata.get('source', '')
                if doc_source and not matches_source(doc_source):
                    invalid_sources.add(doc_source)
            
            if invalid_sources:
                logger.warning(f"Document mixing detected! Found invalid sources in filtered results: {invalid_sources}")
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
        
        # ── FlashRank Reranking (main query path) ──
        # The ranker was only called in the Agentic RAG sub-query path.
        # We must also rerank the main path so rerank_score flows into citations.
        if self.ranker and relevant_docs and len(relevant_docs) > 1:
            try:
                passages = [
                    {"id": str(i), "text": doc.page_content, "meta": doc.metadata}
                    for i, doc in enumerate(relevant_docs)
                ]
                rerank_query = original_question if original_question else question
                logger.info(f"⚡ Main-path reranking {len(passages)} chunks with FlashRank...")
                rerank_request = RerankRequest(query=rerank_query, passages=passages)
                results = self.ranker.rerank(rerank_request)
                
                reranked_docs = []
                for res in results:
                    original_idx = int(res['id'])
                    doc = relevant_docs[original_idx]
                    doc.metadata['rerank_score'] = res['score']
                    reranked_docs.append(doc)
                
                relevant_docs = reranked_docs[:k]
                logger.info(f"⚡ Main-path reranking complete: top rerank_score={results[0]['score']:.4f}" if results else "⚡ Reranking returned no results")
            except Exception as e:
                logger.warning(f"Main-path reranking failed (using original order): {e}")
        
        # Build context with metadata for better accuracy and collect citations
        context_parts = []
        citations = []  # Store citation information for each source
        
        # Try to get similarity scores if available (for ranking)
        doc_scores = {}
        doc_order_scores = {}  # Use retrieval order as proxy for relevance when scores unavailable
        
        # First, try to extract scores from retrieved documents if they have them
        # (e.g., from hybrid_search which stores scores in metadata)
        for doc in relevant_docs:
            if hasattr(doc, 'metadata') and doc.metadata:
                # Check for OpenSearch score from hybrid_search
                if '_opensearch_score' in doc.metadata:
                    score = doc.metadata.get('_opensearch_score')
                    if hasattr(doc, 'page_content') and doc.page_content:
                        import hashlib
                        doc_content_200 = doc.page_content[:200]
                        content_hash = hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()
                        doc_scores[doc_content_200] = float(score)
                        doc_scores[content_hash] = float(score)
                        logger.debug(f"Extracted OpenSearch score {score:.4f} from document metadata")
        
        # Then, try to get scores using similarity_search_with_score directly
        # Match scores to retrieved documents using multiple strategies
        try:
            if hasattr(self.vectorstore, 'similarity_search_with_score') and len(doc_scores) == 0:
                # Get more results to ensure we have scores for all retrieved docs
                # Use the same query and filters that were used for retrieval
                scored_docs = self.vectorstore.similarity_search_with_score(retrieval_question, k=max(len(relevant_docs) * 3, 50))
                
                # Create a mapping of document content to scores using multiple keys
                for scored_doc, score in scored_docs:
                    if hasattr(scored_doc, 'page_content'):
                        import hashlib
                        doc_content = scored_doc.page_content
                        # Use multiple matching strategies
                        doc_content_200 = doc_content[:200] if doc_content else ""
                        doc_content_100 = doc_content[:100] if doc_content else ""
                        content_hash = hashlib.md5(doc_content.encode('utf-8')).hexdigest() if doc_content else ""
                        content_hash_200 = hashlib.md5(doc_content_200.encode('utf-8')).hexdigest() if doc_content_200 else ""
                        
                        score_val = float(score) if score is not None else 0.0
                        
                        # Store with multiple keys for better matching
                        if doc_content_200:
                            doc_scores[doc_content_200] = score_val
                        if doc_content_100:
                            doc_scores[doc_content_100] = score_val
                        if content_hash:
                            doc_scores[content_hash] = score_val
                        if content_hash_200:
                            doc_scores[content_hash_200] = score_val
                        
                        # Also try matching by metadata source + first 50 chars
                        if hasattr(scored_doc, 'metadata') and scored_doc.metadata:
                            source = scored_doc.metadata.get('source', '')
                            if source and doc_content:
                                source_content_key = f"{source}:{doc_content[:50]}"
                                doc_scores[source_content_key] = score_val
                                
                logger.debug(f"Retrieved {len(scored_docs)} scored documents for matching")
        except Exception as e:
            logger.warning(f"Could not retrieve similarity scores: {e}")
            import traceback
            logger.debug(f"Score retrieval traceback: {traceback.format_exc()[:300]}")
        
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
            # First, check if ingestion already computed a high-confidence page assignment
            ingestion_page = doc.metadata.get('page')
            ingestion_confidence = doc.metadata.get('page_confidence')
            ingestion_metadata_method = doc.metadata.get('page_extraction_method')
            
            # Robust document_id extraction
            document_id = doc.metadata.get('document_id')
            if not document_id and hasattr(doc, 'id'):
                document_id = doc.id
            
            # If still no document_id, try to infer from index_name if possible (aris-doc-UUID format)
            if not document_id and 'index_name' in doc.metadata:
                idx = doc.metadata['index_name']
                if idx.startswith('aris-doc-'):
                    document_id = idx.replace('aris-doc-', '')
            
            if (ingestion_page is not None and ingestion_confidence is not None 
                    and float(ingestion_confidence) >= 0.7):
                # Trust the ingestion-time page assignment
                page = int(ingestion_page)
                page_confidence = float(ingestion_confidence)
            else:
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
            
            # Also check if chunk metadata has image reference (CRITICAL: This is where image content chunks are marked)
            if not image_ref:
                if doc.metadata.get('has_image') or doc.metadata.get('image_index') is not None:
                    # Use metadata image_ref if available (set during image content extraction)
                    if doc.metadata.get('image_ref'):
                        image_ref = doc.metadata.get('image_ref')
                        image_info = doc.metadata.get('image_info', f"Image {doc.metadata.get('image_index', '?')} on Page {page}")  # page is always set
                    else:
                        # Fallback to basic image reference
                        image_ref = {
                            'page': page,
                            'image_index': doc.metadata.get('image_index'),
                            'bbox': doc.metadata.get('image_bbox')
                        }
                        image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}"  # page is always set
            
            # CRITICAL: Also check if chunk text contains image markers (image content chunks)
            # These chunks should be marked as image content even if metadata doesn't have image_ref
            if not image_ref and '<!-- image -->' in chunk_text:
                # This is an image content chunk - extract image number from context if possible
                # Try to find image number in the chunk text or use a default
                import re
                image_match = re.search(r'IMAGE\s+(\d+)', chunk_text, re.IGNORECASE)
                if image_match:
                    image_num = int(image_match.group(1))
                    image_ref = {
                        'page': page,
                        'image_index': image_num,
                        'source': source
                    }
                    image_info = f"Image {image_num} on Page {page}"  # page is always set
                else:
                    # Default to image_index from metadata or 1
                    image_num = doc.metadata.get('image_index', 1)
                    image_ref = {
                        'page': page,
                        'image_index': image_num,
                        'source': source
                    }
                    image_info = f"Image {image_num} on Page {page}"  # page is always set
            
            # Generate context-aware snippet using query
            # ENHANCEMENT: Pass query language to prefer English text for English queries (fixes QA citation language mismatch)
            query_language = self.ui_config.get('query_language', None)
            snippet_clean = self._generate_context_snippet(
                chunk_text, question, max_length=500,
                query_language=query_language, doc_metadata=doc.metadata
            )
            
            # Build source location description (certification field)
            # Page is always guaranteed to be set (>= 1) at this point
            source_location_parts = [f"Page {page}"]  # Always include page
            
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
            
            source_location = " | ".join(source_location_parts)  # Always includes "Page X"
            
            # Extract section/heading information from page_blocks if available
            section = None
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'heading':
                        section = block.get('text', '')
                        break
            
            # Determine extraction method based on confidence scores
            extraction_method = 'metadata' if source_confidence >= 0.7 else ('text_marker' if source_confidence >= 0.3 else 'fallback')
            
            # Get similarity score if available (for ranking) - improved matching
            # Priority order: rerank_score > OpenSearch score > doc_scores > order_scores > position-based
            similarity_score = None
            rerank_score = None
            import hashlib
            
            # PRIORITY 0: FlashRank rerank_score (highest quality — cross-encoder relevance)
            if hasattr(doc, 'metadata') and doc.metadata and 'rerank_score' in doc.metadata:
                rerank_score = doc.metadata.get('rerank_score')
                # FlashRank scores are 0-1 (relevance probability). Use directly as similarity_score
                # to ensure the ranking pipeline sees the best available signal.
                similarity_score = rerank_score
                logger.debug(f"Citation {i}: Using FlashRank rerank_score: {rerank_score:.4f}")
            
            # PRIORITY 1: Check metadata for OpenSearch score from hybrid_search
            if similarity_score is None and hasattr(doc, 'metadata') and doc.metadata:
                if '_opensearch_score' in doc.metadata:
                    similarity_score = doc.metadata.get('_opensearch_score')
                    logger.debug(f"Citation {i}: Using OpenSearch score from metadata: {similarity_score:.4f}")
                elif 'similarity_score' in doc.metadata:
                    similarity_score = doc.metadata.get('similarity_score')
                    logger.debug(f"Citation {i}: Using similarity_score from metadata: {similarity_score:.4f}")
            
            # PRIORITY 2: Try to match from doc_scores (from similarity_search_with_score)
            if similarity_score is None and chunk_text:
                doc_content_200 = chunk_text[:200]
                doc_content_100 = chunk_text[:100]
                content_hash = hashlib.md5(chunk_text.encode('utf-8')).hexdigest()
                content_hash_200 = hashlib.md5(doc_content_200.encode('utf-8')).hexdigest()
                
                # Try multiple matching strategies (most specific first)
                if doc_content_200 in doc_scores:
                    similarity_score = doc_scores[doc_content_200]
                    logger.debug(f"Citation {i}: Using doc_scores match (200 chars): {similarity_score:.4f}")
                elif content_hash in doc_scores:
                    similarity_score = doc_scores[content_hash]
                    logger.debug(f"Citation {i}: Using doc_scores match (content hash): {similarity_score:.4f}")
                elif doc_content_100 in doc_scores:
                    similarity_score = doc_scores[doc_content_100]
                    logger.debug(f"Citation {i}: Using doc_scores match (100 chars): {similarity_score:.4f}")
                elif content_hash_200 in doc_scores:
                    similarity_score = doc_scores[content_hash_200]
                    logger.debug(f"Citation {i}: Using doc_scores match (hash 200): {similarity_score:.4f}")
                # Try source + content matching
                elif hasattr(doc, 'metadata') and doc.metadata:
                    source = doc.metadata.get('source', '')
                    if source:
                        source_content_key = f"{source}:{chunk_text[:50]}"
                        if source_content_key in doc_scores:
                            similarity_score = doc_scores[source_content_key]
                            logger.debug(f"Citation {i}: Using doc_scores match (source+content): {similarity_score:.4f}")
            
            # PRIORITY 3: Use order-based score as fallback
            if similarity_score is None and chunk_text:
                if doc_content_200 in doc_order_scores:
                    order_score = doc_order_scores[doc_content_200]
                    similarity_score = 0.5 + (order_score * 0.5)  # Map 0.0-1.0 order to 0.5-1.0 similarity
                    logger.debug(f"Citation {i}: Using order-based score: {similarity_score:.4f}")
                elif content_hash in doc_order_scores:
                    order_score = doc_order_scores[content_hash]
                    similarity_score = 0.5 + (order_score * 0.5)
                    logger.debug(f"Citation {i}: Using order-based score (hash): {similarity_score:.4f}")
            
            # PRIORITY 4: Final fallback - Use retrieval position as similarity proxy
            # Earlier documents = higher similarity (normalized to 0.5-1.0 range)
            if similarity_score is None:
                # position_factor: 1.0 for first doc, decays to 0.0 for last doc
                position_factor = 1.0 - ((i - 1) / max(len(relevant_docs), 1))
                # Map into 0.5-1.0 range: first doc = 1.0, last doc = 0.5
                similarity_score = 0.5 + (position_factor * 0.5)
                logger.warning(f"Citation {i}: Using position-based similarity score {similarity_score:.3f} (no actual score available)")
            
            # Ensure page is always set (fallback to 1 if None)
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Citation {i}: page was None, using fallback page 1. Source: {source_name}")
            
            # Get page_extraction_method from chunk metadata 
            # Use ingestion-stored method if available, otherwise infer from page_confidence
            page_extraction_method = doc.metadata.get('page_extraction_method', None)
            if not page_extraction_method or page_extraction_method == 'unknown':
                # Infer from the page_confidence level set by _extract_page_number
                if page_confidence >= 0.98:
                    page_extraction_method = 'text_marker'
                elif page_confidence >= 0.85:
                    page_extraction_method = 'metadata'
                elif page_confidence >= 0.75:
                    page_extraction_method = 'image_metadata'
                elif page_confidence >= 0.3:
                    page_extraction_method = 'heuristic'
                elif page_confidence >= 0.1:
                    page_extraction_method = 'fallback'
                else:
                    page_extraction_method = 'unknown'
            
            # Extract image_number from image_ref, metadata, OR text patterns
            image_number = None
            
            # PRIORITY 1: Check metadata sources
            if image_ref and isinstance(image_ref, dict):
                image_number = image_ref.get('image_index') or image_ref.get('image_number')
            
            if image_number is None and doc.metadata.get('image_index') is not None:
                image_number = doc.metadata.get('image_index')
            
            if image_number is None and doc.metadata.get('image_number') is not None:
                image_number = doc.metadata.get('image_number')
            
            # PRIORITY 2: Extract from text patterns (for OCR content)
            if image_number is None and chunk_text:
                import re
                # Pattern: "Image X on Page Y" or "IMAGE X"
                image_text_match = re.search(r'(?:Image|IMAGE|Imagen|Fig(?:ure)?|FIGURE)\s*[#:]?\s*(\d+)', chunk_text[:500])
                if image_text_match:
                    image_number = int(image_text_match.group(1))
                    logger.debug(f"Citation {i}: Extracted image number {image_number} from text pattern")
            
            # Check if this is image-derived content (for content_type indicator only)
            # NOTE: We don't show specific image numbers as they're misleading
            # (document-wide sequential counters, not per-page positions)
            is_image_content = (image_number is not None) or (image_ref is not None) or ('<!-- image -->' in chunk_text)
            
            # Build source_location - just show Page number
            # Content type indicates if it's from image/OCR
            source_location = f"Page {page}"
            
            # Build citation entry with enhanced metadata including confidence scores
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'document_id': document_id,  # Robust ID from metadata or inference
                'source_confidence': source_confidence,
                'page': page,  # Always guaranteed to be an integer >= 1
                'image_number': None,  # Don't show misleading sequential image numbers
                'page_confidence': page_confidence,
                'page_extraction_method': page_extraction_method,  # How page was determined
                'section': section,
                'snippet': snippet_clean,
                'full_text': chunk_text,
                'start_char': start_char,
                'end_char': end_char,
                'chunk_index': doc.metadata.get('chunk_index', None),
                'image_ref': {'page': page, 'has_image': True} if is_image_content else image_ref,
                'image_info': f"Image content on Page {page}" if is_image_content else image_info,
                'source_location': source_location,
                'content_type': 'image' if is_image_content else 'text',  # Type of content
                'extraction_method': extraction_method,  # How source was extracted
                'similarity_score': similarity_score,  # Best available score for ranking
                'rerank_score': rerank_score,  # FlashRank cross-encoder score (0-1), None if not reranked
                's3_url': doc.metadata.get('s3_url')
            }
            
            # Generate pre-signed URL if S3 is enabled and URL is present
            if self.s3_service.enabled and citation['s3_url']:
                try:
                    # Extract key from s3://bucket/key
                    s3_parts = citation['s3_url'].replace("s3://", "").split("/", 1)
                    if len(s3_parts) > 1 and s3_parts[1]:  # Ensure key is not empty
                        s3_key = s3_parts[1]
                        signed_url = self.s3_service.get_signed_url(s3_key)
                        if signed_url:
                            citation['s3_preview_url'] = signed_url
                except Exception as e:
                    logger.debug(f"Failed to generate pre-signed URL for {citation['s3_url']}: {e}")
            citations.append(citation)
            logger.debug(f"Citation {i}: source='{source}', page={page}, method={page_extraction_method}, chunk_index={citation.get('chunk_index', 'N/A')}")
            
            # Add source and page info to context
            page_info = f" (Page {page})"  # page is always set
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
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            pass
        # #endregion
        for doc in relevant_docs:
            if hasattr(doc, 'metadata') and doc.metadata:
                # #region agent log
                try:
                    with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                        import json
                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"rag_system.py:2140","message":"Document metadata check","data":{"has_metadata":True,"images_detected":doc.metadata.get('images_detected',False),"image_count":doc.metadata.get('image_count',0),"source":doc.metadata.get('source','')[:50]},"timestamp":int(time_module.time()*1000)})+"\n")
                except Exception as e:
                    logger.warning(f"operation: {type(e).__name__}: {e}")
                    pass
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
                        except Exception as e:
                            logger.warning(f"operation: {type(e).__name__}: {e}")
                            pass
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
        # This ensures image content is retrieved even if similarity search doesn't explicitly mention "image"
        # Also expand search to find chunks with image markers if documents have images OR it's an image question OR tool/item question
        additional_image_docs = []
        should_search_for_images = should_extract_image_content or len(documents_with_images) > 0
        
        if should_search_for_images:
            # For OpenSearch/multi-index, we need a search function that handles multiple indexes
            def search_images(q):
                try:
                    if self.vector_store_type == 'opensearch' and hasattr(self, 'multi_index_manager'):
                        # Use multi-index search for images
                        return self.multi_index_manager.search_across_indexes(
                            query=q,
                            index_names=indexes_to_search,
                            k=100,
                            use_hybrid_search=True
                        )
                    elif self.vectorstore is not None:
                        return self.vectorstore.similarity_search(q, k=100)
                    return []
                except Exception as e:
                    logger.debug(f"Image search failed for query '{q}': {e}")
                    return []

            logger.info(f"Searching for image chunks: image_question={is_image_question}, documents_with_images={len(documents_with_images)}")
            try:
                # Strategy 1: Search for chunks with image markers in parallel
                image_queries = [
                    "image diagram figure picture",
                    "drawer tool wrench socket",
                    "part number quantity tool list"
                ]
                
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                    futures = [executor.submit(search_images, q) for q in image_queries]
                    for future in concurrent.futures.as_completed(futures):
                        search_results = future.result()
                        for doc_result in search_results:
                            if hasattr(doc_result, 'page_content'):
                                has_marker = '<!-- image -->' in doc_result.page_content
                                has_metadata = False
                                if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                    has_metadata = any(doc_result.metadata.get(k) for k in ['images_detected', 'image_count', 'has_image'])
                                
                                if (has_marker or has_metadata) and doc_result not in relevant_docs:
                                    doc_source = doc_result.metadata.get('source', '') if hasattr(doc_result, 'metadata') and doc_result.metadata else ''
                                    if not documents_with_images or doc_source in documents_with_images or not doc_source:
                                        additional_image_docs.append(doc_result)
                
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
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        pass
                    # #endregion
                    relevant_docs = relevant_docs + additional_image_docs
                else:
                    logger.info("No additional image chunks found in expanded search")
                    # #region agent log
                    try:
                        with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                            import json
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"B","location":"rag_system.py:2236","message":"No image chunks found in expanded search","data":{"queries_tried":len(image_queries)},"timestamp":int(time_module.time()*1000)})+"\n")
                    except Exception as e:
                        logger.warning(f"operation: {type(e).__name__}: {e}")
                        pass
                    # #endregion
            except Exception as e:
                logger.warning(f"Error in image chunk search: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Phase 2: Expand search for tool/item names in image content
        if should_extract_image_content and tool_item_names:
            logger.info(f"🔍 Expanding search for tool/item names: {tool_item_names}")
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tool_item_names), 5)) as executor:
                    futures = {executor.submit(search_images, f"{name} image drawer tool part"): name for name in tool_item_names}
                    
                    for future in concurrent.futures.as_completed(futures):
                        item_name = futures[future]
                        try:
                            search_results = future.result()
                            for doc_result in search_results:
                                if hasattr(doc_result, 'page_content') and '<!-- image -->' in doc_result.page_content:
                                    if doc_result not in relevant_docs:
                                        relevant_docs.append(doc_result)
                                        logger.debug(f"Found chunk with '{item_name}' in image content")
                        except Exception as e:
                            logger.debug(f"Error searching for {item_name}: {e}")
                
                logger.info(f"✅ Expanded search completed for {len(tool_item_names)} tool/item name(s)")
            except Exception as e:
                logger.warning(f"Error in tool/item name search: {e}")
        
        if is_image_question and mentioned_documents:
            try:
                # Query for chunks with image metadata from mentioned documents
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(mentioned_documents), 5)) as executor:
                    # Search specifically for image-related chunks in mentioned documents
                    futures = {executor.submit(search_images, "image diagram figure picture"): doc for doc in mentioned_documents}
                    
                    for future in concurrent.futures.as_completed(futures):
                        mentioned_source = futures[future]
                        try:
                            search_results = future.result()
                            for doc_result in search_results:
                                if hasattr(doc_result, 'metadata') and doc_result.metadata:
                                    doc_source = doc_result.metadata.get('source', '')
                                    if doc_source == mentioned_source:
                                        # Check if it has image flags
                                        has_img = any(doc_result.metadata.get(k) for k in ['has_image', 'image_ref', 'images_detected'])
                                        if has_img or '<!-- image -->' in (doc_result.page_content if hasattr(doc_result, 'page_content') else ''):
                                            if doc_result not in relevant_docs:
                                                additional_image_docs.append(doc_result)
                        except Exception as e:
                            logger.debug(f"Could not retrieve additional image chunks for {mentioned_source}: {e}")
                
                if additional_image_docs:
                    logger.info(f"Found {len(additional_image_docs)} additional image chunks from mentioned documents")
                    relevant_docs = relevant_docs + additional_image_docs
            except Exception as e:
                logger.debug(f"Error expanding image search: {e}")
        
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
                marker_count = chunk_text.count('<!-- image -->')
                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"C","location":"rag_system.py:2314","message":"Chunks with markers count","data":{"chunks_with_markers":chunks_with_markers,"total_chunks":len(chunks_to_check)},"timestamp":int(time_module.time()*1000)})+"\n")
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            pass
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
                    # CRITICAL: Ensure page is never 0 - default to 1
                    page = doc.metadata.get('page', 1)
                    if page == 0:
                        page = 1
                    
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
                        except Exception as e:
                            logger.warning(f"operation: {type(e).__name__}: {e}")
                            pass
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
                            except Exception as e:
                                logger.warning(f"operation: {type(e).__name__}: {e}")
                                pass
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
                                except Exception as e:
                                    logger.warning(f"operation: {type(e).__name__}: {e}")
                                    pass
                                # #endregion
                            elif image_context_before:
                                # Fallback: use text before if no OCR after
                                image_context = f"[IMAGE {image_num} - Text near image]\n{image_context_before}"
                                # #region agent log
                                try:
                                    with open('/home/senarios/Desktop/aris/.cursor/debug.log', 'a') as f:
                                        import json
                                        f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"D","location":"rag_system.py:2372","message":"Using fallback context","data":{"image_num":image_num,"context_length":len(image_context_before)},"timestamp":int(time_module.time()*1000)})+"\n")
                                except Exception as e:
                                    logger.warning(f"operation: {type(e).__name__}: {e}")
                                    pass
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
        
        # CRITICAL FIX: Also query OpenSearch images index directly
        # This ensures we get image content even if text chunks don't have image markers
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            
            if self.opensearch_domain:
                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv('OPENAI_API_KEY'),
                    model=self.embedding_model
                )
                
                images_store = OpenSearchImagesStore(
                    embeddings=embeddings,
                    domain=self.opensearch_domain,
                    region=getattr(self, 'region', None)
                )
                
                # Query images index with the question
                image_results = images_store.search_images(
                    query=question,
                    source=self.active_sources[0] if self.active_sources and len(self.active_sources) == 1 else None,
                    k=min(10, k * 2) if k else 10
                )
                
                if image_results:
                    logger.info(f"📷 Found {len(image_results)} images from OpenSearch images index")
                    
                    # Add images to image_content_map
                    # Use a counter for unique image numbers per source when original image_number isn't unique
                    images_per_source = {}
                    for img in image_results:
                        source = img.get('source', 'Unknown')
                        image_number = img.get('image_number')
                        ocr_text = img.get('ocr_text', '')
                        page = img.get('page', 1)
                        
                        # Ensure page is valid
                        if page is None or page == 0:
                            page = 1
                        
                        # Ensure image_number is valid - use page-based numbering if not
                        if image_number is None or image_number == 0:
                            # Use page number as a base for image numbering
                            if source not in images_per_source:
                                images_per_source[source] = {}
                            if page not in images_per_source[source]:
                                images_per_source[source][page] = 0
                            images_per_source[source][page] += 1
                            image_number = images_per_source[source][page]
                        
                        if ocr_text and len(ocr_text) > 20:  # Only add if meaningful OCR text
                            # Use (source, page, image_number) as unique key to avoid collisions
                            key = (source, f"{page}_{image_number}")
                            if key not in image_content_map:
                                image_content_map[key] = []
                            
                            # Check if this OCR text is not already in the map
                            existing_ocr = [c.get('ocr_text', '')[:100] for c in image_content_map[key]]
                            if ocr_text[:100] not in existing_ocr:
                                image_content_map[key].append({
                                    'content': f"[IMAGE {image_number} - Page {page} - From OpenSearch Images Index]\n{ocr_text}",
                                    'page': page,
                                    'full_chunk': ocr_text,
                                    'ocr_text': ocr_text,
                                    'source': 'opensearch_images',
                                    'image_number': image_number  # Store explicit image_number
                                })
                                logger.info(f"📷 Added image {image_number} from {os.path.basename(source)} Page {page} ({len(ocr_text)} chars OCR)")
        except ImportError:
            logger.debug("OpenSearch images store not available for query integration")
        except Exception as e:
            logger.warning(f"Could not query OpenSearch images index: {e}")
        
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
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            pass
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
            except Exception as e:
                logger.warning(f"operation: {type(e).__name__}: {e}")
                pass
            # #endregion
            
            # Debug: Log a preview of the Image Content section (first 500 chars)
            import logging
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Image Content section preview: {image_content_section[:500]}...")
            
            # CRITICAL: Add image citations for images from the images index
            # This ensures images used in answers get proper citation attribution
            next_citation_id = len(citations)  # Start after existing text chunk citations
            for key, contents in image_content_map.items():
                # Handle both old format (source, img_idx) and new format (source, "page_img")
                if isinstance(key, tuple) and len(key) == 2:
                    source = key[0]
                    key_part = key[1]
                    # Try to parse "page_img" format
                    if isinstance(key_part, str) and '_' in key_part:
                        try:
                            # New format: (source, "page_imgnum")
                            parts = key_part.split('_')
                            # img_idx will be extracted from content_info below
                        except Exception as e:
                            logger.debug(f"operation: {type(e).__name__}: {e}")
                            pass
                else:
                    source = 'Unknown'
                
                for content_info in contents:
                    # Only add citation if it's from the OpenSearch images index
                    if content_info.get('source') == 'opensearch_images':
                        stored_page = content_info.get('page', 0)  # Don't default to 1
                        # Get image_number from content_info (explicit) or fallback
                        img_idx = content_info.get('image_number', 1)
                        ocr_text = content_info.get('ocr_text', '') or content_info.get('full_chunk', '')
                        
                        # CRITICAL: Always try to extract correct page from OCR text
                        # Page markers in text are MORE RELIABLE than stored metadata
                        # (stored metadata often has wrong default value of 1)
                        import re
                        page = None
                        

                        # Improved Page Extraction Logic
                        # Prioritize stored metadata if it looks valid (>1), as it comes from parser context
                        # OCR text often contains "Page X" references to OTHER pages, which is misleading
                        
                        # PRIORITY 1: Stored metadata (if valid)
                        if stored_page and stored_page > 1:
                            page = stored_page
                            logger.info(f"📄 [IMAGE CITATION] Page {page} from stored metadata (Priority 1)")
                        
                        # PRIORITY 2: "--- Page X ---" markers (explicit delimiters)
                        elif ocr_text:
                            page_markers = re.findall(r'---\s*Page\s+(\d+)\s*---', ocr_text)
                            if page_markers:
                                page = int(page_markers[0])
                                logger.info(f"📄 [IMAGE CITATION] Page {page} from '--- Page X ---' marker")
                        
                        # PRIORITY 3: Fallback to other text patterns only if no page found yet
                        if page is None and ocr_text:
                            # "Page X" at line end
                            page_match = re.search(r'Page\s+(\d+)\s*$', ocr_text, re.IGNORECASE | re.MULTILINE)
                            if page_match:
                                page = int(page_match.group(1))
                                logger.info(f"📄 [IMAGE CITATION] Page {page} from 'Page X' at line end")
                            
                            # "Page X" in text (lowest confidence)
                            if page is None:
                                page_match = re.search(r'\bPage\s+(\d+)\b', ocr_text, re.IGNORECASE)
                                if page_match:
                                    possible_page = int(page_match.group(1))
                                    # Only accept if reasonable (e.g. within 5 pages of expected?)
                                    # For now, just log valid
                                    page = possible_page
                                    logger.info(f"📄 [IMAGE CITATION] Page {page} from 'Page X' in text")

                        # Fallback to 1 only as last resort
                        if page is None or page == 0:
                            page = stored_page if stored_page else 1
                            if page == 1:
                                logger.warning(f"📄 [IMAGE CITATION] Using fallback page {page} (no markers found)")
                        if img_idx is None or img_idx == 0:
                            img_idx = 1
                        
                        # Create snippet from OCR text
                        snippet = ocr_text[:300].strip() + "..." if len(ocr_text) > 300 else ocr_text.strip()
                        
                        image_citation = {
                            'id': next_citation_id,
                            'source': source if source else 'Unknown',
                            'source_confidence': 1.0,  # High confidence from images index
                            'page': page,
                            'image_number': img_idx,
                            'page_confidence': 1.0,
                            'page_extraction_method': 'opensearch_images_index',
                            'section': None,
                            'snippet': snippet,
                            'full_text': ocr_text,
                            'start_char': None,
                            'end_char': None,
                            'chunk_index': None,
                            'image_ref': {'page': page, 'has_image': True},
                            'image_info': f"Image content on Page {page}",
                            'source_location': f"Page {page}",  # Don't show misleading image numbers
                            'content_type': 'image',
                            'extraction_method': 'opensearch_images_index',
                            'similarity_score': 0.85,  # Good score for direct image match
                            's3_url': None
                        }
                        citations.append(image_citation)
                        next_citation_id += 1
                        logger.info(f"📷 Added image citation: {os.path.basename(source)} Page {page}")
        
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
        except Exception as e:
            logger.warning(f"operation: {type(e).__name__}: {e}")
            pass
        # #endregion

        # Choose synthesis function based on backend (Cerebras or OpenAI)
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras(
                question, context, relevant_docs, 
                mentioned_documents, question_doc_number, response_language,
                model=target_llm_model
            )
        else:
            if not self.openai_api_key:
                answer, response_tokens = self._query_offline(question, context, relevant_docs)
            else:
                answer, response_tokens = self._query_openai(
                    question, context, relevant_docs, 
                    mentioned_documents, question_doc_number, response_language,
                    model=target_llm_model
                )
        
        response_time = time_module.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        logger.info(f"Retrieval: [ReqID: {req_id}] Query finished in {response_time:.2f}s. Tokens: {total_tokens} ({context_tokens} context, {response_tokens} response)")
        
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
        
        # FIX: Only include sources that have citations (filtered sources)
        # This prevents showing irrelevant documents in the sources list
        citation_sources = list(set([c.get('source', 'Unknown') for c in citations if c.get('source')]))
        if not citation_sources:
            # Fallback to retrieved docs if no citations
            citation_sources = list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs]))
        
        return {
            "answer": answer,
            "sources": citation_sources,  # Only sources with citations
            "context_chunks": [doc.page_content for doc in relevant_docs],  # Full chunk text for citation display
            "citations": citations,  # Detailed citation information with page numbers and snippets
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens
        }

