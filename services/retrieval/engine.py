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

class RetrievalEngine:
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
                except Exception:
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
        """Count tokens in text using tiktoken."""
        if not text:
            return 0
        try:
            import tiktoken
            # Use cl100k_base for OpenAI models (GPT-3.5/4)
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
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
        from shared.config.settings import ARISConfig
        
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
        try:
            from shared.config.settings import ARISConfig
            import json
            from datetime import datetime, timedelta

            registry_path = getattr(ARISConfig, 'DOCUMENT_REGISTRY_PATH', None)
            if registry_path and os.path.exists(registry_path):
                with open(registry_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)

                docs = list(raw.values()) if isinstance(raw, dict) else (raw or [])
                cutoff = datetime.now() - timedelta(hours=max_age_hours)

                recent: List[tuple] = []
                for d in docs:
                    if not isinstance(d, dict):
                        continue
                    name = d.get('document_name') or d.get('original_document_name')
                    ts = d.get('updated_at') or d.get('created_at')
                    if not name or not ts:
                        continue
                    try:
                        dt = datetime.fromisoformat(ts)
                    except Exception:
                        continue
                    if dt >= cutoff:
                        recent.append((dt, name))

                recent.sort(key=lambda x: x[0], reverse=True)
                return [name for _, name in recent]

        except Exception:
            pass

        # Fallback: if no registry timestamps, use known indexed documents (best-effort)
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

    def _detect_occurrence_query(self, question: str) -> tuple:
        """Detect if a question is asking to find all occurrences of a term.

        Returns:
            (is_occurrence_query, term)
        """
        if not question:
            return False, ""

        q = question.strip()
        ql = q.lower()

        triggers = [
            "where does",
            "where is",
            "find ",
            "locate ",
            "occurrence",
            "occurrences",
            "all occurrences",
            "show me all",
            "highlight",
        ]
        if not any(t in ql for t in triggers):
            return False, ""

        import re

        # Prefer quoted term: find "Cape Verde"
        m = re.search(r'"([^"]+)"', q)
        if m and m.group(1).strip():
            return True, m.group(1).strip()

        # Patterns like: where does X appear
        m = re.search(r"(?:where\s+does|where\s+is)\s+(.+?)\s+(?:appear|occur|show\s+up)\b", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()

        # Patterns like: occurrences of X
        m = re.search(r"occurrences?\s+of\s+(.+)$", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()

        # Patterns like: find X
        m = re.search(r"\bfind\s+(.+)$", ql)
        if m and m.group(1).strip():
            return True, q[m.start(1):m.end(1)].strip()

        return True, q.strip()

    def _build_occurrence_answer(self, term: str, source: str, occurrences: List[Dict], truncated: bool) -> str:
        """Build a human-readable answer string for occurrence results."""
        safe_term = term.strip()
        total = len(occurrences)
        header = f"Found {total} occurrence(s) of '{safe_term}' in {source}."
        if truncated:
            header += " (Results truncated.)"

        lines = [header, ""]
        for occ in occurrences:
            page = occ.get('page')
            image_idx = occ.get('image_index')
            snippet = (occ.get('snippet') or "").strip()
            loc_parts = []
            if page:
                loc_parts.append(f"Page {page}")
            if image_idx is not None:
                loc_parts.append(f"Image {image_idx}")
            loc = " | ".join(loc_parts) if loc_parts else "Text"
            if snippet:
                lines.append(f"- {loc}: {snippet}")
            else:
                lines.append(f"- {loc}")
        return "\n".join(lines)

    def _find_occurrences_opensearch(self, term: str, max_hits: int = 5000) -> List:
        """Fetch chunks containing term from OpenSearch for the active document."""
        if not hasattr(self, 'multi_index_manager'):
            from vectorstores.opensearch_store import OpenSearchMultiIndexManager
            self.multi_index_manager = OpenSearchMultiIndexManager(
                embeddings=self.embeddings,
                domain=self.opensearch_domain,
                region=getattr(self, 'region', None)
            )

        indexes_to_search = []
        if self.active_sources:
            for doc_name in self.active_sources:
                if doc_name in self.document_index_map:
                    indexes_to_search.append(self.document_index_map[doc_name])
        if not indexes_to_search:
            return []

        # Lucene query_string escaping (minimal)
        q = term.replace('\\', '\\\\').replace('"', '\\"')
        query = f'"{q}"'

        results = []
        page_size = 500
        for index_name in indexes_to_search:
            try:
                store = self.multi_index_manager.get_or_create_index_store(index_name)
                client = store.vectorstore.client
                offset = 0
                while offset < max_hits:
                    body = {
                        "from": offset,
                        "size": min(page_size, max_hits - offset),
                        "query": {
                            "query_string": {
                                "query": query,
                                "fields": ["text"],
                                "default_operator": "AND"
                            }
                        }
                    }
                    resp = client.search(index=index_name, body=body)
                    hits = resp.get("hits", {}).get("hits", [])
                    if not hits:
                        break
                    results.extend(hits)
                    if len(hits) < page_size:
                        break
                    offset += page_size
            except Exception as e:
                logger.warning(f"Occurrence search failed for index '{index_name}': {e}")
                continue

        # Convert to LangChain documents (best-effort)
        from langchain_core.documents import Document
        docs = []
        for h in results:
            src = h.get('_source', {}) or {}
            text = src.get('text', '')
            meta = src.get('metadata', {}) or {}
            try:
                docs.append(Document(page_content=text, metadata=meta))
            except Exception:
                continue
        return docs

    def find_all_occurrences(self, term: str, max_results: int = 200) -> Dict:
        """Find all occurrences of a term in the active document and return an answer + citations."""
        import re

        if not term or not term.strip():
            return {
                "answer": "Please provide a word or phrase to find.",
                "sources": [],
                "citations": [],
                "context_chunks": [],
                "num_chunks_used": 0
            }

        if not self.active_sources:
            return {
                "answer": "Select one document (Active Document) first, then ask again.",
                "sources": [],
                "citations": [],
                "context_chunks": [],
                "num_chunks_used": 0
            }

        term_clean = term.strip()
        # Pull candidate chunks
        if self.vector_store_type == 'opensearch':
            candidate_docs = self._find_occurrences_opensearch(term_clean)
        else:
            # FAISS fallback: retrieve a large set of chunks then scan
            try:
                candidate_docs = self.vectorstore.similarity_search(term_clean, k=1000)
            except Exception:
                candidate_docs = []

        occurrences = []
        for doc in candidate_docs:
            text = getattr(doc, 'page_content', '') or ''
            if not text:
                continue

            # Strict-ish matching: match whole word when term is a single token; else substring
            if ' ' in term_clean:
                pattern = re.compile(re.escape(term_clean), re.IGNORECASE)
            else:
                pattern = re.compile(rf"\b{re.escape(term_clean)}\b", re.IGNORECASE)

            for m in pattern.finditer(text):
                start = max(0, m.start() - 80)
                end = min(len(text), m.end() + 80)
                snippet = text[start:end].replace('\n', ' ').strip()
                page = None
                if hasattr(doc, 'metadata') and doc.metadata:
                    page = doc.metadata.get('source_page') or doc.metadata.get('page')
                image_ref = doc.metadata.get('image_ref') if hasattr(doc, 'metadata') and doc.metadata else None
                image_index = None
                if isinstance(image_ref, dict):
                    image_index = image_ref.get('image_index')
                elif hasattr(doc, 'metadata') and doc.metadata:
                    image_index = doc.metadata.get('image_index')

                # Ensure page is always set (fallback to 1 if None)
                if page is None:
                    page = 1
                
                occurrences.append({
                    "source": doc.metadata.get('source') if hasattr(doc, 'metadata') and doc.metadata else None,
                    "page": int(page),  # Always guaranteed to be an integer >= 1
                    "snippet": snippet,
                    "image_index": image_index,
                    "start_char": doc.metadata.get('start_char') if hasattr(doc, 'metadata') and doc.metadata else None,
                    "end_char": doc.metadata.get('end_char') if hasattr(doc, 'metadata') and doc.metadata else None,
                })

        # Sort by page then snippet
        occurrences.sort(key=lambda x: (x.get('page') or 10**9, x.get('image_index') or 10**9, x.get('start_char') or 10**9))

        truncated = False
        if len(occurrences) > max_results:
            occurrences = occurrences[:max_results]
            truncated = True

        source_name = self.active_sources[0] if self.active_sources else 'selected document'
        answer = self._build_occurrence_answer(term_clean, source_name, occurrences, truncated)

        # Create citations-like objects so UI can render references
        citations = []
        for idx, occ in enumerate(occurrences, 1):
            # Ensure page is always set (fallback to 1 if None)
            page = occ.get('page')
            if page is None:
                page = 1
                logger.debug(f"find_all_occurrences citation {idx}: page was None, using fallback page 1")
            
            citations.append({
                'id': idx,
                'source': occ.get('source') or source_name,
                'page': page,  # Always guaranteed to be an integer >= 1
                'snippet': occ.get('snippet'),
                'full_text': occ.get('snippet') or '',
                'source_location': f"Page {page}",
                'content_type': 'image' if occ.get('image_index') is not None else 'text',
                'image_ref': {'image_index': occ.get('image_index'), 'page': page} if occ.get('image_index') is not None else None,
            })

        sources = [source_name]
        return {
            "answer": answer,
            "sources": sources,
            "citations": citations,
            "context_chunks": [],
            "num_chunks_used": len(citations),
            "occurrences": occurrences
        }
    
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
        active_sources: Optional[List[str]] = None  # NEW: Document filtering
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
        from shared.config.settings import ARISConfig
        
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
        
        # Determine active sources for this request
        if active_sources is None:
            active_sources = self.active_sources
            
        # Store UI configuration for citation extraction and LLM calls
        self.ui_config = {
            'temperature': temperature if temperature is not None else ARISConfig.DEFAULT_TEMPERATURE,
            'max_tokens': max_tokens if max_tokens is not None else ARISConfig.DEFAULT_MAX_TOKENS,
            'active_sources': active_sources
        }
        
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
                    # Verify index has documents
                    if hasattr(self.vectorstore, 'count_documents'):
                        doc_count = self.vectorstore.count_documents()
                        if doc_count == 0:
                            # Check document registry to provide better error message
                            try:
                                from storage.document_registry import DocumentRegistry
                                from shared.config.settings import ARISConfig
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
                            except Exception:
                                pass
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
            # For OpenSearch, initialize on-demand
            if self.vector_store_type == "opensearch":
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
            
            # If still None, check document registry for better error message
            if self.vectorstore is None:
                try:
                    from storage.document_registry import DocumentRegistry
                    from shared.config.settings import ARISConfig
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
                except Exception:
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
        except Exception:
            pass
        
        # Log active document filter status
        if active_sources:
            logger.info(f"Document filter active: {active_sources} - queries will only search within these documents")
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

        if use_agentic_rag and (not self.use_cerebras) and (not self.openai_api_key):
            use_agentic_rag = False
        
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
                        # Clear filter and search all
                        self.active_sources = None
                        active_sources = None
                        indexes_to_search = list(self.document_index_map.values()) if self.document_index_map else []
                    logger.info(f"Document filter not available, using fallback: {len(indexes_to_search)} index(es)")
            else:
                # No active_sources set - use recent documents for better isolation
                recent_docs = self._get_recent_documents(max_age_hours=24)
                if recent_docs:
                    indexes_to_search = [self.document_index_map[doc] for doc in recent_docs if doc in self.document_index_map]
                    logger.info(f"No active_sources set, using {len(indexes_to_search)} recent document indexes: {recent_docs}")
                else:
                    # Fallback: search all document indexes (but log warning)
                    indexes_to_search = list(self.document_index_map.values()) if hasattr(self, 'document_index_map') and self.document_index_map else []
                    if indexes_to_search:
                        logger.info(f"Searching all {len(indexes_to_search)} document indexes")
                    else:
                        logger.warning("No recent documents found, no document indexes available")
                
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
                            from shared.config.settings import ARISConfig
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
                        from shared.config.settings import ARISConfig
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
                from shared.config.settings import ARISConfig
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
            if active_sources and self.vector_store_type.lower() == "opensearch":
                # Filter out None/empty values and construct OpenSearch filter
                valid_sources = [s for s in active_sources if s and s.strip()]
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
                from shared.config.settings import ARISConfig
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
        if active_sources and not (self.vector_store_type == "opensearch" and self.document_index_map):
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
            snippet_clean = self._generate_context_snippet(chunk_text, question, max_length=500)
            
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
            # Priority order: OpenSearch score (from hybrid_search) > doc_scores > order_scores > position-based
            similarity_score = None
            import hashlib
            
            # PRIORITY 1: Check metadata for OpenSearch score from hybrid_search (most accurate)
            if hasattr(doc, 'metadata') and doc.metadata:
                # Check for OpenSearch score from hybrid_search (highest priority)
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
                # Use index position (i starts at 1, so first doc gets highest score)
                position_score = 1.0 - ((i - 1) / max(len(relevant_docs), 1)) * 0.5
                similarity_score = 0.5 + position_score  # Map to 0.5-1.0 range
                logger.warning(f"Citation {i}: Using position-based similarity score {similarity_score:.3f} (no actual score available)")
            
            # Ensure page is always set (fallback to 1 if None)
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Citation {i}: page was None, using fallback page 1. Source: {source_name}")
            
            # Get page_extraction_method from chunk metadata for debugging
            page_extraction_method = doc.metadata.get('page_extraction_method', 'unknown')
            
            # Build citation entry with enhanced metadata including confidence scores
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'source_confidence': source_confidence,
                'page': page,  # Always guaranteed to be an integer >= 1
                'page_confidence': page_confidence,
                'page_extraction_method': page_extraction_method,  # How page was determined
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
                'similarity_score': similarity_score,  # Vector similarity score for ranking
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
        
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras(question, context, relevant_docs, mentioned_documents, question_doc_number)
        else:
            if not self.openai_api_key:
                answer, response_tokens = self._query_offline(question, context, relevant_docs)
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

    def _query_offline(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        parts = []
        if relevant_docs:
            for doc in relevant_docs[:3]:
                try:
                    source = doc.metadata.get('source', 'Unknown') if hasattr(doc, 'metadata') and doc.metadata else 'Unknown'
                    page = doc.metadata.get('page', None) if hasattr(doc, 'metadata') and doc.metadata else None
                    # Ensure page is always set (fallback to 1)
                    if page is None:
                        page = 1
                    snippet = (doc.page_content or '').strip().replace('\n', ' ')
                    if len(snippet) > 350:
                        snippet = snippet[:350] + "..."
                    # Page is always set now, so always include it
                    parts.append(f"- ({source}, page {page}) {snippet}")
                except Exception:
                    continue
        if not parts:
            preview = (context or '').strip().replace('\n', ' ')
            if len(preview) > 800:
                preview = preview[:800] + "..."
            if preview:
                parts = [preview]
        answer = "OpenAI is not configured (missing OPENAI_API_KEY). Retrieved context:\n" + "\n".join(parts)
        return answer, self.count_tokens(answer)
    
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
        from shared.config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Truncate context if it exceeds model's token limit
        # Most OpenAI models have 128k context limit, reserve space for prompt and response
        MAX_CONTEXT_TOKENS = 100000  # Reserve ~28k for prompt, question, and response
        context_tokens = self.count_tokens(context)
        
        if context_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Context too large ({context_tokens:,} tokens > {MAX_CONTEXT_TOKENS:,} limit). "
                f"Truncating to fit within model limits..."
            )
            
            # Intelligent truncation: try to preserve important sections
            # 1. Check if there's an image content section - preserve it if present
            image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)')
            image_section_end = context.find('\n\n---\n\n', image_section_start + 100) if image_section_start >= 0 else -1
            
            # 2. Calculate how much we need to truncate
            question_tokens = self.count_tokens(question)
            system_prompt_estimate = 500  # Rough estimate for system prompt
            buffer_tokens = 2000  # Safety buffer
            available_context_tokens = MAX_CONTEXT_TOKENS - question_tokens - system_prompt_estimate - buffer_tokens
            
            # 3. If image section exists, preserve it and truncate from the end
            if image_section_start >= 0 and image_section_end >= 0:
                image_section = context[image_section_start:image_section_end]
                image_section_tokens = self.count_tokens(image_section)
                remaining_tokens = available_context_tokens - image_section_tokens
                
                if remaining_tokens > 0:
                    # Keep image section + truncate main context
                    main_context = context[:image_section_start]
                    # Truncate main context to fit
                    truncated_main = self._truncate_text_by_tokens(main_context, remaining_tokens)
                    context = truncated_main + "\n\n" + image_section
                    logger.info(f"Preserved image section ({image_section_tokens:,} tokens), truncated main context to {remaining_tokens:,} tokens")
                else:
                    # Image section itself is too large, truncate everything
                    context = self._truncate_text_by_tokens(context, available_context_tokens)
                    logger.warning("Image section too large, truncating entire context")
            else:
                # No image section, truncate from the end
                context = self._truncate_text_by_tokens(context, available_context_tokens)
            
            final_context_tokens = self.count_tokens(context)
            logger.info(f"Context truncated: {context_tokens:,} -> {final_context_tokens:,} tokens")
        
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

CRITICAL: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images. This section contains OCR text extracted from images and is the PRIMARY and MOST RELIABLE source for answering questions about image content.

CITATION RULES:
1. For EVERY technical claim, fact, or specification you provide, you MUST include a citation.
2. Citations MUST follow this exact format: [Source X: filename (Page Y)].
3. Source numbers (X), filenames, and page numbers (Y) are provided in the context headers: [Source X: filename (Page Y)].
4. If information spans multiple sources, cite all of them: [Source 1: docA.pdf (Page 5), Source 2: docB.pdf (Page 12)].
5. ALWAYS use the page number provided in the context header. This is the authoritative page number.
6. Citations must be placed at the end of the sentence or paragraph they support.

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
2. Search the OCR text for the tool/item name or part number
3. Look for drawer numbers, locations, or quantities associated with the item
4. Provide specific information from the OCR text, including drawer numbers, page numbers, and quantities
5. DO NOT say "context does not contain" if you haven't thoroughly searched the Image Content section

CRITICAL RULES:
- Synthesize information from ALL provided context chunks to answer the question
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
- Be specific and cite exact values, measurements, and specifications when available. ALWAYS CITE YOUR SOURCES.
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- If multiple sources provide information, synthesize them clearly
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- End your answer when you have provided the information - do not add unnecessary text

MULTILINGUAL INSTRUCTIONS:
- Detect the language of the user's question.
- ANSWER IN THE SAME LANGUAGE AS THE USER'S QUESTION.
- If the retrieved context is in a different language, TRANSLATE the relevant information into the language of the question.
- Do NOT answer in English if the user asks in Spanish, French, etc. (unless explicitly asked to)."""
        
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
        from shared.config.settings import ARISConfig
        # Synthesis-friendly prompt for Cerebras
        prompt = f"""You are a precise technical assistant. Synthesize information from the provided context to answer the question. Be specific and accurate.

CITATION RULES:
1. For EVERY technical claim, fact, or specification you provide, you MUST include a citation.
2. Citations MUST follow this exact format: [Source X: filename (Page Y)].
3. Source numbers (X), filenames, and page numbers (Y) are provided in the context headers: [Source X: filename (Page Y)].
4. If information spans multiple sources, cite all of them: [Source 1: docA.pdf (Page 5), Source 2: docB.pdf (Page 12)].
5. ALWAYS use the page number provided in the context header.
6. Citations must be placed at the end of the sentence or paragraph they support.

CRITICAL: DO NOT add greetings, signatures, or closing statements. DO NOT repeat phrases. End your answer when you have provided the information.

Context:
{context}

Question: {question}

Instructions:
- Synthesize information from ALL context chunks to answer the question
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- Only say information is not available if you have thoroughly checked ALL chunks and found nothing relevant
- Be specific with numbers, measurements, and technical details. ALWAYS CITE YOUR SOURCES.
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
        search_mode: str,
        active_sources: List[str] = None
    ) -> List:
        """
        Retrieves chunks with optional Reranking (FlashRank) for higher accuracy.
        Wrapper around _retrieve_chunks_raw.
        """
        # 1. Expand retrieval window for Reranking
        # Retrieve 4x chunks to give Reranker candidates to choose from
        initial_k = k
        if self.ranker:
            initial_k = k * 4
        
        # 2. Get Raw Candidates
        relevant_docs = self._retrieve_chunks_raw(
            query, 
            initial_k, 
            use_mmr, 
            use_hybrid_search, 
            semantic_weight, 
            keyword_weight, 
            search_mode,
            active_sources # Pass active_sources to raw retrieval
        )
        
        # 3. Rerank Results
        if self.ranker and relevant_docs:
            try:
                # Prepare Rerank Request
                passages = [
                    {"id": str(i), "text": doc.page_content, "meta": doc.metadata} 
                    for i, doc in enumerate(relevant_docs)
                ]
                
                logger.info(f"⚡ Reranking {len(passages)} chunks with FlashRank...")
                rerank_request = RerankRequest(query=query, passages=passages)
                results = self.ranker.rerank(rerank_request)
                
                # Reconstruct sorted document list
                # Map back to original documents using index/id
                reranked_docs = []
                for res in results:
                    original_idx = int(res['id'])
                    # Update metadata with rerank score
                    doc = relevant_docs[original_idx]
                    doc.metadata['rerank_score'] = res['score']
                    reranked_docs.append(doc)
                
                # Slice to requested k
                return reranked_docs[:k]
                
            except Exception as e:
                logger.warning(f"Reranking failed: {e}. Returning raw results.")
                return relevant_docs[:k]
        
        return relevant_docs[:k]

    def _retrieve_chunks_raw(
        self,
        query: str,
        k: int,
        use_mmr: bool,
        use_hybrid_search: bool,
        semantic_weight: float,
        keyword_weight: float,
        search_mode: str,
        active_sources: List[str] = None
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
            active_sources: List of document sources to filter by (optional)
        
        Returns:
            List of Document objects
        """
        # For OpenSearch: Use per-document indexes instead of metadata filtering
        if self.vector_store_type == "opensearch":
            # Determine which index(es) to search
            indexes_to_search = []
            
            if active_sources:
                # Map active sources to their respective OpenSearch indexes
                found_indexes = set()
                for doc_name in active_sources:
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
                    from shared.config.settings import ARISConfig
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
                from shared.config.settings import ARISConfig
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
            from shared.config.settings import ARISConfig
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
    
    def _get_page_from_char_position(self, start_char: Optional[int], end_char: Optional[int], 
                                     page_blocks: List[Dict]) -> Optional[int]:
        """
        Find page number using precise character position matching.
        This is the most accurate method when character positions are available.
        
        Args:
            start_char: Starting character position of chunk in document
            end_char: Ending character position of chunk in document
            page_blocks: List of page block dictionaries with start_char, end_char, page
        
        Returns:
            Page number with maximum overlap, or None if no match found
        """
        if start_char is None or not page_blocks:
            return None
        
        # Use end_char if available, otherwise estimate from start_char
        chunk_end = end_char if end_char is not None else start_char + 500  # Estimate 500 chars
        
        # Calculate overlap with each page
        page_overlaps = {}
        
        for block in page_blocks:
            if not isinstance(block, dict):
                continue
            
            block_start = block.get('start_char')
            block_end = block.get('end_char')
            block_page = block.get('page')
            
            # Skip if missing required fields
            if block_start is None or block_page is None:
                continue
            
            # Use block_end if available, otherwise estimate
            if block_end is None:
                block_text = block.get('text', '')
                block_end = block_start + len(block_text) if block_text else block_start + 1000
            
            # Calculate overlap
            overlap_start = max(start_char, block_start)
            overlap_end = min(chunk_end, block_end)
            
            if overlap_start < overlap_end:
                overlap_chars = overlap_end - overlap_start
                chunk_size = chunk_end - start_char
                
                # Calculate overlap percentage
                if chunk_size > 0:
                    overlap_ratio = overlap_chars / chunk_size
                    
                    # Track page with maximum overlap
                    if block_page not in page_overlaps:
                        page_overlaps[block_page] = {
                            'overlap_chars': 0,
                            'overlap_ratio': 0.0,
                            'start_char': block_start,
                            'end_char': block_end
                        }
                    
                    # Accumulate overlap for this page
                    page_overlaps[block_page]['overlap_chars'] += overlap_chars
                    if overlap_ratio > page_overlaps[block_page]['overlap_ratio']:
                        page_overlaps[block_page]['overlap_ratio'] = overlap_ratio
        
        if not page_overlaps:
            return None
        
        # Find page with maximum overlap
        # Prefer page with most character overlap, then highest ratio
        best_page = max(page_overlaps.keys(), 
                       key=lambda p: (page_overlaps[p]['overlap_chars'], 
                                     page_overlaps[p]['overlap_ratio']))
        
        # Only return if there's significant overlap (>10% of chunk)
        if page_overlaps[best_page]['overlap_ratio'] > 0.1:
            return int(best_page)
        
        return None

    def _validate_page_assignment(self, page: int, doc, chunk_text: str, page_blocks: List[Dict]) -> tuple:
        """
        Cross-validate a proposed page number against multiple signals to improve accuracy.

        Returns:
            (validated_page, confidence_score)
        """
        import re
        from scripts.setup_logging import get_logger

        logger = get_logger("aris_rag.rag_system")

        validation_sources = []

        # 1) source_page metadata
        source_page = doc.metadata.get("source_page", None)
        if source_page is not None:
            try:
                if int(source_page) == int(page):
                    validation_sources.append(("source_page", 1.0))
            except Exception:
                pass

        # 2) page metadata
        page_meta = doc.metadata.get("page", None)
        if page_meta is not None:
            try:
                if int(page_meta) == int(page):
                    validation_sources.append(("page_metadata", 0.8))
            except Exception:
                pass

        # 3) character-position match (highest quality when available)
        start_char = doc.metadata.get("start_char", None)
        end_char = doc.metadata.get("end_char", None)
        if start_char is not None and page_blocks:
            try:
                page_from_pos = self._get_page_from_char_position(start_char, end_char, page_blocks)
                if page_from_pos is not None and int(page_from_pos) == int(page):
                    validation_sources.append(("char_position", 1.0))
            except Exception:
                pass

        # 4) explicit text marker in chunk
        page_match = re.search(r"---\s*Page\s+(\d+)\s*---", chunk_text or "")
        if page_match:
            try:
                if int(page_match.group(1)) == int(page):
                    validation_sources.append(("text_marker", 0.6))
            except Exception:
                pass

        if len(validation_sources) >= 2:
            max_conf = max(s[1] for s in validation_sources)
            confidence = min(1.0, max_conf + 0.1)  # small boost when signals agree
            logger.debug(f"Page {page} validated by multiple sources: {validation_sources} (confidence={confidence:.2f})")
            return int(page), confidence

        if len(validation_sources) == 1:
            src, conf = validation_sources[0]
            logger.debug(f"Page {page} validated by {src} (confidence={conf:.2f})")
            return int(page), conf

        # No corroboration; still return the candidate but with reduced confidence
        logger.debug(f"Page {page} could not be corroborated; returning lower confidence")
        return int(page), 0.5
    
    def _extract_page_number(self, doc, chunk_text: str) -> tuple:
        """
        Extract and validate page number from multiple sources with enhanced accuracy.
        PRIORITY: Character position matching > source_page > page_blocks > page > text markers
        
        Args:
            doc: Document object with metadata
            chunk_text: Chunk text content
        
        Returns:
            Tuple of (page_number, confidence_score)
            confidence: 1.0 (char position) > 1.0 (source_page) > 0.9 (page_blocks) > 0.8 (page) > 0.6 (text marker) > 0.4 (fallback)
        """
        import re
        from typing import Optional
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
        
        # PRIORITY 1: Character position-based matching (HIGHEST ACCURACY)
        start_char = doc.metadata.get('start_char', None)
        end_char = doc.metadata.get('end_char', None)
        page_blocks = doc.metadata.get('page_blocks', [])
        
        if start_char is not None and page_blocks:
            page_from_position = self._get_page_from_char_position(start_char, end_char, page_blocks)
            if page_from_position and validate_against_doc(page_from_position):
                logger.debug(f"Page extracted from character position: {page_from_position} (start_char={start_char}, end_char={end_char})")
                return int(page_from_position), 1.0  # Highest confidence for position-based matching
        
        # Cross-validate with page_blocks metadata if available (enhanced accuracy)
        def get_page_from_page_blocks(chunk_text: str, page_blocks: list) -> Optional[int]:
            """Extract page number from page_blocks metadata using character positions or text matching."""
            if not page_blocks:
                return None
            
            # PRIORITY: Character position matching (most accurate)
            if start_char is not None:
                page_from_pos = self._get_page_from_char_position(start_char, end_char, page_blocks)
                if page_from_pos:
                    logger.debug(f"Page from character position matching: {page_from_pos}")
                    return page_from_pos
            
            # Fallback: Text-based matching (for chunks without character positions)
            if not chunk_text:
                return None
            
            chunk_preview = chunk_text[:200].strip()
            if not chunk_preview:
                return None
            
            # Enhanced text matching: try to match with page-level blocks
            # Some page_blocks have nested structure with 'blocks' array
            best_match = None
            best_match_score = 0.0
            
            for block in page_blocks:
                if not isinstance(block, dict):
                    continue
                
                block_page = block.get('page')
                if not block_page:
                    continue
                
                # Check page-level text
                block_text = block.get('text', '')
                if block_text:
                    # Calculate text similarity
                    chunk_words = set(chunk_preview[:100].lower().split())
                    block_words = set(block_text[:200].lower().split())
                    if chunk_words and block_words:
                        overlap = len(chunk_words.intersection(block_words))
                        total = len(chunk_words.union(block_words))
                        similarity = overlap / total if total > 0 else 0.0
                        
                        if similarity > best_match_score and similarity > 0.3:  # 30% threshold
                            best_match_score = similarity
                            best_match = int(block_page)
                
                # Also check nested blocks if available
                nested_blocks = block.get('blocks', [])
                if isinstance(nested_blocks, list):
                    for nested_block in nested_blocks:
                        if isinstance(nested_block, dict):
                            nested_text = nested_block.get('text', '')
                            if nested_text:
                                chunk_words = set(chunk_preview[:100].lower().split())
                                nested_words = set(nested_text[:150].lower().split())
                                if chunk_words and nested_words:
                                    overlap = len(chunk_words.intersection(nested_words))
                                    total = len(chunk_words.union(nested_words))
                                    similarity = overlap / total if total > 0 else 0.0
                                    
                                    if similarity > best_match_score and similarity > 0.3:
                                        best_match_score = similarity
                                        best_match = int(block_page)
            
            if best_match:
                logger.debug(f"Page from text matching: {best_match} (similarity: {best_match_score:.2f})")
                return best_match
            
            return None
        
        # PRIORITY 2: Try source_page metadata (high confidence: 1.0)
        page = doc.metadata.get('source_page', None)
        if page is not None:
            if validate_against_doc(page):
                # Cross-validate with character position if available
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page), doc, chunk_text, page_blocks
                )
                if validated_confidence >= 0.8:
                    logger.debug(f"Page {validated_page} validated from source_page with cross-validation (confidence: {validated_confidence:.2f})")
                    return validated_page, validated_confidence
                else:
                    logger.debug(f"Page extracted from source_page metadata: {page}")
                    return int(page), 1.0
            else:
                logger.warning(f"Invalid page number in source_page metadata: {page} (doc has {doc_pages} pages)")
        
        # PRIORITY 3: Try page_blocks (confidence: 0.9 baseline; boosted if corroborated)
        page_blocks = doc.metadata.get('page_blocks', [])
        if page_blocks:
            page_from_blocks = get_page_from_page_blocks(chunk_text, page_blocks)
            if page_from_blocks and validate_against_doc(page_from_blocks):
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page_from_blocks), doc, chunk_text, page_blocks
                )
                logger.debug(
                    f"Page extracted from page_blocks: {validated_page} "
                    f"(confidence: {validated_confidence:.2f})"
                )
                return validated_page, max(0.9, validated_confidence)
        
        # PRIORITY 4: Try page metadata (confidence: 0.8)
        page = doc.metadata.get('page', None)
        if page is not None:
            if validate_against_doc(page):
                # Cross-validate
                validated_page, validated_confidence = self._validate_page_assignment(
                    int(page), doc, chunk_text, page_blocks
                )
                logger.debug(f"Page extracted from page metadata: {validated_page} (confidence: {validated_confidence:.2f})")
                return validated_page, validated_confidence
            else:
                logger.warning(f"Invalid page number in page metadata: {page} (doc has {doc_pages} pages)")
        
        # Extract from text markers: "--- Page X ---" (confidence: 0.6)
        # Enhanced pattern matching with better validation
        page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (--- Page X ---): {page_num}")
                return page_num, 0.6
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Extract from text markers: "Page X" or "Document Page X" or "VUORMAR Page X" (confidence: 0.4)
        # Enhanced: Look for "Page X" patterns including document name prefixes
        # Pattern 1: "VUORMAR Page 10" or "Document Page 5" (document name + Page + number)
        # Handle both with and without newlines/whitespace
        page_match = re.search(r'(\w+)\s+Page\s+(\d+)', chunk_text, re.IGNORECASE | re.MULTILINE)
        if page_match:
            page_num = int(page_match.group(2))
            # More lenient validation - if doc_pages is None, still accept reasonable page numbers
            if doc_pages is None or page_num <= doc_pages:
                if validate_page(page_num):  # Basic range check (1-10000)
                    logger.info(f"Page extracted from text marker ({page_match.group(1)} Page {page_num}): {page_num}")
                    return page_num, 0.5  # Slightly higher confidence for document name + page pattern
        
        # Pattern 2: Standalone "Page X" at line start or after newline
        page_match = re.search(r'(?:^|\n)\s*Page\s+(\d+)(?:\s|$|\.|,|;|:)', chunk_text, re.IGNORECASE | re.MULTILINE)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (Page X): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from text marker {page_num} exceeds document pages {doc_pages}")
        
        # Pattern 3: "Page X of Y" or "Page X/Y" (take first number)
        page_match = re.search(r'Page\s+(\d+)(?:\s+of\s+\d+|\s*/\s*\d+)', chunk_text, re.IGNORECASE)
        if page_match:
            page_num = int(page_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from text marker (Page X of Y): {page_num}")
                return page_num, 0.4
        
        # Try page range patterns: "Page 5-7" or "Pages 10-12" (take first page, confidence: 0.4)
        page_range_match = re.search(r'Pages?\s+(\d+)[-\s]+(\d+)', chunk_text, re.IGNORECASE)
        if page_range_match:
            page_num = int(page_range_match.group(1))
            if validate_against_doc(page_num):
                logger.debug(f"Page extracted from page range (first page): {page_num}")
                return page_num, 0.4
            else:
                logger.warning(f"Page from page range {page_num} exceeds document pages {doc_pages}")
        
        # Try to extract from chunk_index if available (confidence: 0.3) - NEW
        chunk_index = doc.metadata.get('chunk_index', None)
        if chunk_index is not None and page_blocks:
            # Estimate page from chunk position (rough heuristic)
            try:
                # If we have page_blocks, try to infer page from chunk position
                total_chunks = len([b for b in page_blocks if isinstance(b, dict) and b.get('text')])
                if total_chunks > 0:
                    # Rough estimate: assume chunks are distributed evenly across pages
                    estimated_page = min(int((chunk_index / max(total_chunks, 1)) * (doc_pages or 1)) + 1, doc_pages or 1)
                    if validate_against_doc(estimated_page):
                        logger.debug(f"Page estimated from chunk_index: {estimated_page}")
                        return estimated_page, 0.3
            except Exception:
                pass
        
        # No valid page found - use fallback: page 1 with low confidence
        # This ensures every citation has a page number, even if we can't determine it
        source = doc.metadata.get('source', 'Unknown')
        logger.warning(f"No page number found in chunk, using fallback page 1. Source: {source}")
        return 1, 0.1  # Fallback to page 1 with very low confidence
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate semantic similarity between two texts using embeddings.
        Generic, dynamic approach that works for any document type.
        
        Args:
            text1: First text
            text2: Second text
        
        Returns:
            Similarity score between 0 and 1
        """
        try:
            # Use embeddings to calculate semantic similarity
            if hasattr(self, 'embeddings') and self.embeddings:
                # Get embeddings for both texts
                emb1 = self.embeddings.embed_query(text1[:1000])  # Limit length for efficiency
                emb2 = self.embeddings.embed_query(text2[:1000])
                
                # Calculate cosine similarity
                import numpy as np
                dot_product = np.dot(emb1, emb2)
                norm1 = np.linalg.norm(emb1)
                norm2 = np.linalg.norm(emb2)
                
                if norm1 > 0 and norm2 > 0:
                    similarity = dot_product / (norm1 * norm2)
                    return float(similarity)
        except Exception:
            pass
        
        # Fallback to word overlap similarity if embeddings fail
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0.0
    
    def _generate_context_snippet(self, chunk_text: str, query: str, max_length: int = 500) -> str:
        """
        Generate snippet centered around query-relevant content using dynamic semantic matching.
        Generic solution that works for all document types without hardcoded mappings.
        
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
        
        # Strategy 1: Try semantic similarity-based sentence extraction (most generic)
        try:
            semantic_snippet = self._extract_semantic_snippet(cleaned_text, query, max_length)
            if semantic_snippet and len(semantic_snippet) > 50:  # Only use if meaningful
                return semantic_snippet
        except Exception as e:
            logger.debug(f"Semantic snippet extraction failed: {e}")
        
        # Strategy 2: Fallback to keyword-based matching with dynamic word extraction
        query_words = re.findall(r'\b\w+\b', query.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might', 'must', 'can', 'about', 'tell', 'me', 'what', 'when', 'where', 'who', 'why', 'how'}
        query_keywords = [w for w in query_words if w not in stop_words and len(w) > 2]
        
        # If no meaningful keywords, use sentence-level semantic extraction
        if not query_keywords:
            return self._extract_sentences_snippet(cleaned_text, max_length, query=query)
        
        # Find positions of query keywords in text (with fuzzy matching)
        keyword_positions = []
        text_lower = cleaned_text.lower()
        
        for keyword in query_keywords:
            # Exact matches
            start = 0
            while True:
                pos = text_lower.find(keyword, start)
                if pos == -1:
                    break
                keyword_positions.append(pos)
                start = pos + 1
            
            # Partial word matches for longer keywords (dynamic, not hardcoded)
            if len(keyword) > 4:
                # Try stem-like matching (first 4-5 chars)
                stem_length = min(5, len(keyword) - 1)
                stem = keyword[:stem_length]
                start = 0
                while True:
                    pos = text_lower.find(stem, start)
                    if pos == -1:
                        break
                    # Check word boundaries
                    if (pos == 0 or not text_lower[pos-1].isalnum()) and \
                       (pos + len(stem) >= len(text_lower) or not text_lower[pos + len(stem)].isalnum()):
                        keyword_positions.append(pos)
                    start = pos + 1
        
        if not keyword_positions:
            # No keyword matches found, use semantic sentence extraction
            return self._extract_sentences_snippet(cleaned_text, max_length, query_keywords, query=query)
        
        # Find the center of keyword positions
        keyword_positions.sort()
        center_pos = keyword_positions[len(keyword_positions) // 2]
        
        # Extract context around center position
        start_pos = max(0, center_pos - max_length // 2)
        end_pos = min(len(cleaned_text), start_pos + max_length)
        
        # Adjust to preserve sentence boundaries
        if start_pos > 0:
            search_start = max(0, start_pos - 100)
            period = cleaned_text.rfind('.', search_start, start_pos)
            exclamation = cleaned_text.rfind('!', search_start, start_pos)
            question = cleaned_text.rfind('?', search_start, start_pos)
            sentence_end = max(period, exclamation, question)
            if sentence_end > start_pos - 50:
                start_pos = sentence_end + 1
                while start_pos < len(cleaned_text) and cleaned_text[start_pos].isspace():
                    start_pos += 1
        
        if end_pos < len(cleaned_text):
            period = cleaned_text.find('.', end_pos - 50, end_pos + 50)
            exclamation = cleaned_text.find('!', end_pos - 50, end_pos + 50)
            question = cleaned_text.find('?', end_pos - 50, end_pos + 50)
            sentence_end = min([p for p in [period, exclamation, question] if p != -1], default=-1)
            if sentence_end != -1 and sentence_end > end_pos - 50:
                end_pos = sentence_end + 1
        
        snippet = cleaned_text[start_pos:end_pos].strip()
        
        if start_pos > 0:
            snippet = "..." + snippet
        if end_pos < len(cleaned_text):
            snippet = snippet + "..."
        
        return snippet
    
    def _extract_semantic_snippet(self, text: str, query: str, max_length: int) -> str:
        """
        Extract snippet using semantic similarity - enhanced approach for better accuracy.
        
        Args:
            text: Full text to extract from
            query: Query to match against
            max_length: Maximum snippet length
        
        Returns:
            Most semantically relevant snippet
        """
        import re
        
        # Split into sentences with better pattern matching
        # Enhanced: Handle abbreviations, decimals, and other edge cases
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])|(?<=\d)\.\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
        
        if not sentences:
            return text[:max_length] + ("..." if len(text) > max_length else "")
        
        # Score each sentence by semantic similarity to query (enhanced)
        scored_sentences = []
        query_lower = query.lower()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        for sentence in sentences:
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            # Calculate semantic similarity
            similarity = self._calculate_semantic_similarity(sentence, query)
            
            # Boost score if query keywords appear in sentence (hybrid approach)
            sentence_lower = sentence.lower()
            sentence_words = set(re.findall(r'\b\w+\b', sentence_lower))
            keyword_overlap = len(query_words.intersection(sentence_words))
            keyword_boost = min(0.2, keyword_overlap * 0.05)  # Max 0.2 boost
            
            # Combined score: semantic similarity + keyword boost
            combined_score = min(1.0, similarity + keyword_boost)
            
            scored_sentences.append((combined_score, similarity, sentence))
        
        if not scored_sentences:
            return text[:max_length] + ("..." if len(text) > max_length else "")
        
        # Sort by combined score (highest first), then by semantic similarity
        scored_sentences.sort(key=lambda x: (x[0], x[1]), reverse=True)
        
        # Select top sentences up to max_length (using combined score)
        selected = []
        total_length = 0
        for combined_score, semantic_score, sentence in scored_sentences:
            if total_length + len(sentence) + 1 <= max_length:
                selected.append(sentence)
                total_length += len(sentence) + 1
            else:
                # Try to fit partial sentence if close to max_length
                remaining = max_length - total_length - 3  # Reserve for "..."
                if remaining > 50 and len(sentence) > remaining:
                    # Try to break at sentence boundary
                    partial = sentence[:remaining].rsplit('.', 1)[0]
                    if partial and len(partial) > 30:
                        selected.append(partial + "...")
                break
        
        if selected:
            snippet = " ".join(selected)
            if total_length < len(text):
                snippet += "..."
            return snippet
        
        # Fallback: return highest scoring sentence
        if scored_sentences:
            return scored_sentences[0][2][:max_length] + ("..." if len(scored_sentences[0][2]) > max_length else "")
        
        # Last resort: return beginning of text
        return text[:max_length] + ("..." if len(text) > max_length else "")
    
    def _extract_sentences_snippet(self, text: str, max_length: int, keywords: Optional[List[str]] = None, query: Optional[str] = None) -> str:
        """
        Extract snippet by scoring sentences dynamically - generic approach for any document.
        Uses semantic similarity when available, falls back to keyword matching.
        
        Args:
            text: Full text to extract from
            max_length: Maximum snippet length
            keywords: Optional keywords to score sentences against
            query: Optional query for semantic matching
        
        Returns:
            Snippet composed of most relevant sentences
        """
        import re
        
        # Split into sentences
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            snippet = text[:max_length]
            if len(text) > max_length:
                snippet += "..."
            return snippet
        
        scored_sentences = []
        
        # Strategy 1: Use semantic similarity if query provided and embeddings available
        if query and hasattr(self, 'embeddings') and self.embeddings:
            try:
                for sentence in sentences:
                    if len(sentence) < 10:  # Skip very short sentences
                        continue
                    similarity = self._calculate_semantic_similarity(sentence, query)
                    scored_sentences.append((similarity, sentence, 'semantic'))
            except Exception:
                pass  # Fall back to keyword matching
        
        # Strategy 2: Keyword-based scoring (dynamic, no hardcoded patterns)
        if not scored_sentences and keywords:
            text_lower = text.lower()
            for sentence in sentences:
                if len(sentence) < 10:
                    continue
                score = 0
                sentence_lower = sentence.lower()
                
                # Count keyword matches (exact and partial)
                for keyword in keywords:
                    if keyword in sentence_lower:
                        score += 1.0
                    # Dynamic partial matching for longer keywords
                    elif len(keyword) > 4:
                        stem = keyword[:min(5, len(keyword)-1)]
                        if stem in sentence_lower:
                            score += 0.5
                
                if score > 0:
                    scored_sentences.append((score, sentence, 'keyword'))
        
        # Strategy 3: If no scoring worked, use sentence position (earlier = potentially more relevant)
        if not scored_sentences:
            for idx, sentence in enumerate(sentences):
                if len(sentence) >= 10:
                    # Earlier sentences get slightly higher score
                    position_score = 1.0 - (idx / max(len(sentences), 1)) * 0.3
                    scored_sentences.append((position_score, sentence, 'position'))
        
        # Sort by score (highest first)
        scored_sentences.sort(key=lambda x: x[0], reverse=True)
        
        # Select top sentences up to max_length
        selected = []
        total_length = 0
        for score, sentence, method in scored_sentences:
            sentence_with_space = sentence + " "
            if total_length + len(sentence_with_space) <= max_length:
                selected.append(sentence)
                total_length += len(sentence_with_space)
            else:
                # Try to fit partial sentence if close to max_length
                remaining = max_length - total_length
                if remaining > 50 and len(sentence) > remaining:
                    # Take first part of sentence
                    partial = sentence[:remaining].rsplit('.', 1)[0] + "."
                    if partial:
                        selected.append(partial)
                break
        
        if selected:
            snippet = " ".join(selected)
            if total_length < len(text):
                snippet += "..."
            return snippet
        
        # Final fallback: return highest scoring sentence or first sentence
        if scored_sentences:
            best_sentence = scored_sentences[0][1]
            return best_sentence[:max_length] + ("..." if len(best_sentence) > max_length else "")
        
        # Last resort: first few sentences
        snippet = " ".join(sentences[:3])[:max_length]
        if len(text) > max_length:
            snippet += "..."
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
        # Ensure all citations have page numbers before grouping
        citation_groups = {}
        import os
        for citation in citations:
            source = citation.get('source', 'Unknown')
            # Normalize source (take basename to avoid path vs filename duplicates)
            if source and ('/' in source or '\\' in source):
                source = os.path.basename(source)
            page = citation.get('page')
            # Ensure page is always set (fallback to 1)
            if page is None or page < 1:
                page = 1
                citation['page'] = 1
                citation['page_confidence'] = citation.get('page_confidence', 0.1)
                logger.debug(f"Deduplication: Citation missing page, set to 1 for source '{source}'")
            key = (source, page)
            
            if key not in citation_groups:
                citation_groups[key] = []
            citation_groups[key].append(citation)
        
        # Merge citations in each group
        merged_citations = []
        for group_key, group_citations in citation_groups.items():
            if len(group_citations) == 1:
                # No duplicates, keep as is but use normalized source
                citation = group_citations[0]
                citation['source'] = group_key[0]
                merged_citations.append(citation)
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
                best_citation['source'] = group_key[0] # Use normalized source (basename)
                best_citation['source_confidence'] = max(
                    c.get('source_confidence', 0) for c in group_citations
                )
                best_citation['page_confidence'] = max(
                    c.get('page_confidence', 0) for c in group_citations
                )
                
                # Ensure page is always set (double-check after merge)
                if best_citation.get('page') is None or best_citation.get('page') < 1:
                    best_citation['page'] = group_key[1] if group_key[1] else 1
                    best_citation['page_confidence'] = best_citation.get('page_confidence', 0.1)
                    logger.debug(f"Deduplication: Merged citation missing page, set to {best_citation['page']}")
                
                # Merge other metadata if available
                if any(c.get('section') for c in group_citations):
                    sections = [c.get('section') for c in group_citations if c.get('section')]
                    best_citation['section'] = sections[0] if sections else None
                
                merged_citations.append(best_citation)
                logger.debug(f"Merged {len(group_citations)} duplicate citations for {group_key}")
        
        # Re-number IDs sequentially and ensure all citations have page numbers
        for i, citation in enumerate(merged_citations, 1):
            citation['id'] = i
            # Final check: ensure page is always set
            if citation.get('page') is None or citation.get('page') < 1:
                citation['page'] = 1
                citation['page_confidence'] = citation.get('page_confidence', 0.1)
                logger.warning(f"Deduplication: Final citation {i} missing page, set to 1")
        
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
        Rank citations by similarity score - most similar first.
        Uses vector similarity scores from similarity_search_with_score.
        Automatically handles both distance-based (lower = more similar) and 
        similarity-based (higher = more similar) scoring systems.
        
        Args:
            citations: List of citation dictionaries with similarity_score field
            query: User query string (used for logging/debugging)
        
        Returns:
            Ranked list of citations sorted by similarity_score (most similar first)
        """
        import re
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        if not citations or not query:
            return citations
        
        # Check if we have similarity scores
        similarity_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        if not similarity_scores:
            logger.warning("No similarity scores found in citations. Citations will be returned in original order.")
            return citations
        
        # Determine if scores are distance-based (lower is better) or similarity-based (higher is better)
        # Distance-based scores are typically > 1.0, similarity-based are typically <= 1.0
        min_score = min(similarity_scores)
        max_score = max(similarity_scores)
        
        # If scores are mostly > 1.0, they're likely distance-based
        # If scores are mostly <= 1.0, they're likely similarity-based
        # Also check if scores are in the position-based fallback range (0.5-1.0)
        # Position-based scores are in narrow range and decrease uniformly
        is_position_based = (max_score <= 1.0 and min_score >= 0.5 and 
                            (max_score - min_score) < 0.5 and len(similarity_scores) > 1)
        is_distance_based = max_score > 1.0 and min_score > 0.5 and not is_position_based
        
        if is_position_based:
            logger.warning(f"Detected position-based fallback scores (range: {min_score:.3f}-{max_score:.3f}). "
                          f"Actual similarity scores may not be available. Consider using similarity_search_with_score.")
        
        # Sort by similarity score with enhanced tie-breaking
        # For distance-based scores (lower = more similar), sort ascending
        # For similarity-based scores (higher = more similar), sort descending
        # Enhanced: Use page_confidence and source_confidence as tie-breakers for better accuracy
        if is_distance_based:
            # Distance-based: lower score = more similar, so sort ascending
            citations.sort(key=lambda c: (
                c.get('similarity_score', 999) if c.get('similarity_score') is not None else 999,  # Primary: similarity (ascending for distance)
                -c.get('page_confidence', 0.0),  # Secondary: higher page confidence = better (descending)
                -c.get('source_confidence', 0.0),  # Tertiary: higher source confidence = better (descending)
                c.get('id', 0)  # Quaternary: original order (ascending) for final tie-breaking
            ))
            logger.debug(f"Sorted citations by distance-based similarity with confidence tie-breakers")
        else:
            # Similarity-based: higher score = more similar, so sort descending
            citations.sort(key=lambda c: (
                -c.get('similarity_score', -999) if c.get('similarity_score') is not None else 999,  # Primary: similarity (descending for similarity)
                -c.get('page_confidence', 0.0),  # Secondary: higher page confidence = better (descending)
                -c.get('source_confidence', 0.0),  # Tertiary: higher source confidence = better (descending)
                c.get('id', 0)  # Quaternary: original order (ascending) for final tie-breaking
            ))
            logger.debug(f"Sorted citations by similarity-based score with confidence tie-breakers")
        
        # Get sorted scores for validation and percentage calculation
        sorted_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        # Validate sorting is correct
        if citations and sorted_scores and len(sorted_scores) > 1:
            if is_distance_based:
                # For distance: scores should increase (first is lowest/most similar)
                is_sorted = all(sorted_scores[i] <= sorted_scores[i+1] for i in range(len(sorted_scores)-1))
            else:
                # For similarity: scores should decrease (first is highest/most similar)
                is_sorted = all(sorted_scores[i] >= sorted_scores[i+1] for i in range(len(sorted_scores)-1))
            
            if not is_sorted:
                logger.warning("Citations not properly sorted by similarity! Re-sorting...")
                if is_distance_based:
                    citations.sort(key=lambda c: c.get('similarity_score', 999) if c.get('similarity_score') is not None else 999)
                else:
                    citations.sort(key=lambda c: -c.get('similarity_score', -999) if c.get('similarity_score') is not None else 999)
                # Re-get sorted scores after re-sorting
                sorted_scores = [c.get('similarity_score') for c in citations if c.get('similarity_score') is not None]
        
        # Calculate similarity percentages (100% for most similar, decreasing for others)
        # Get the best (most similar) score to use as 100% baseline
        if sorted_scores and len(sorted_scores) > 0:
            if is_distance_based:
                # For distance: best score is the minimum (lowest distance = most similar)
                best_score = min(sorted_scores)
                worst_score = max(sorted_scores)
            else:
                # For similarity: best score is the maximum (highest similarity = most similar)
                best_score = max(sorted_scores)
                worst_score = min(sorted_scores)
            
            # Calculate percentage for each citation
            # Use absolute value to handle both positive and negative ranges
            score_range = abs(worst_score - best_score) if worst_score != best_score else 1.0
            
            logger.info(f"Calculating percentages: best={best_score:.4f}, worst={worst_score:.4f}, range={score_range:.4f}, is_distance={is_distance_based}, num_scores={len(sorted_scores)}")
            
            # Calculate percentages for all citations
            for citation in citations:
                sim_score = citation.get('similarity_score')
                if sim_score is not None:
                    if is_distance_based:
                        # For distance: lower score = higher percentage
                        # Invert: (worst - current) / (worst - best) * 100
                        if score_range > 0.0001:  # Use small epsilon to avoid division issues
                            similarity_percentage = ((worst_score - sim_score) / score_range) * 100.0
                            # Ensure percentage is in valid range
                            similarity_percentage = max(0.0, min(100.0, similarity_percentage))
                            citation['similarity_percentage'] = round(similarity_percentage, 2)
                        else:
                            # All same distance - cannot compute meaningful percentage
                            citation['similarity_percentage'] = None  # Will display as "N/A" in UI
                            logger.debug(f"Citation {citation.get('id')}: All scores equal (distance={sim_score:.4f}), setting similarity_percentage to None")
                    else:
                        # For similarity: higher score = higher percentage
                        # Normalize: (current - worst) / (best - worst) * 100
                        if score_range > 0.0001:  # Use small epsilon to avoid division issues
                            similarity_percentage = ((sim_score - worst_score) / score_range) * 100.0
                            # Ensure percentage is in valid range
                            similarity_percentage = max(0.0, min(100.0, similarity_percentage))
                            citation['similarity_percentage'] = round(similarity_percentage, 2)
                        else:
                            # All same similarity - cannot compute meaningful percentage
                            citation['similarity_percentage'] = None  # Will display as "N/A" in UI
                            logger.debug(f"Citation {citation.get('id')}: All scores equal (similarity={sim_score:.4f}), setting similarity_percentage to None")
                    
                    # Debug logging for all citations to see what's happening
                    if citation.get('id', 0) <= 6:
                        logger.info(f"Citation {citation.get('id')}: score={sim_score:.4f}, calculated_percentage={similarity_percentage:.2f}%, source={citation.get('source', 'Unknown')[:40]}")
                else:
                    citation['similarity_percentage'] = 0.0  # No score = 0%
                    logger.warning(f"Citation {citation.get('id')} has no similarity_score, setting percentage to 0%")
        else:
            # No scores available - set all to 0%
            logger.warning("No similarity scores available for percentage calculation")
            for citation in citations:
                citation['similarity_percentage'] = 0.0
        
        # Re-number IDs after sorting (1 = most similar, highest similarity score)
        for i, citation in enumerate(citations, 1):
            citation['id'] = i
            # Log top 3 for debugging
            if i <= 3:
                sim_score = citation.get('similarity_score', 'N/A')
                sim_percent = citation.get('similarity_percentage', 'N/A')
                sim_str = f"{sim_score:.4f}" if isinstance(sim_score, (int, float)) else str(sim_score)
                logger.debug(f"Rank {i}: similarity={sim_str} ({sim_percent}%), "
                            f"source={citation.get('source', 'Unknown')[:50]}")
        
        top_3_scores = [f'{c.get("similarity_score", "N/A")} ({c.get("similarity_percentage", 0):.1f}%)' for c in citations[:3]]
        logger.info(f"Ranked {len(citations)} citations by similarity (highest to lowest). Top 3: {top_3_scores}")
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
            
            # Ensure page is always set (fallback to 1 if None)
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Agentic RAG Citation {i}: page was None, using fallback page 1. Source: {source_name}")
            
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
                    image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}"  # page is always set (>= 1)
            
            # Generate context-aware snippet using original question
            snippet_clean = self._generate_context_snippet(chunk_text, question, max_length=500)
            
            # Build source location - page is always guaranteed to be set (>= 1) at this point
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
            
            # Ensure page is always set (fallback to 1 if None) - double check for agentic RAG
            if page is None:
                page = 1
                page_confidence = 0.1
                source_name = doc.metadata.get('source', 'Unknown')
                logger.warning(f"Agentic RAG Citation {i}: page was None in citation dict, using fallback page 1. Source: {source_name}")
            
            # Get page_extraction_method from chunk metadata for debugging
            page_extraction_method = doc.metadata.get('page_extraction_method', 'unknown')
            
            citation = {
                'id': i,
                'source': source if source and source != 'Unknown' else 'Unknown',
                'source_confidence': source_confidence,
                'page': page,  # Always guaranteed to be an integer >= 1
                'page_confidence': page_confidence,
                'page_extraction_method': page_extraction_method,  # How page was determined
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
            logger.debug(f"Agentic RAG Citation {i}: source='{source}', page={page}, method={page_extraction_method}, chunk_index={citation.get('chunk_index', 'N/A')}")
            
            page_info = f" (Page {page})"  # page is always set
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{chunk_text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Count tokens
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # Generate answer using synthesis prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras_agentic(question, sub_queries, context, relevant_docs)
        else:
            if not self.openai_api_key:
                answer, response_tokens = self._query_offline(question, context, relevant_docs)
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
        from shared.config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Truncate context if it exceeds model's token limit
        MAX_CONTEXT_TOKENS = 100000  # Reserve ~28k for prompt, question, and response
        context_tokens = self.count_tokens(context)
        
        if context_tokens > MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Agentic RAG: Context too large ({context_tokens:,} tokens > {MAX_CONTEXT_TOKENS:,} limit). "
                f"Truncating to fit within model limits..."
            )
            
            # Intelligent truncation: preserve important sections
            image_section_start = context.find('IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)')
            image_section_end = context.find('\n\n---\n\n', image_section_start + 100) if image_section_start >= 0 else -1
            
            question_tokens = self.count_tokens(question)
            sub_queries_tokens = sum(self.count_tokens(sq) for sq in sub_queries)
            system_prompt_estimate = 800  # Rough estimate for agentic system prompt
            buffer_tokens = 2000  # Safety buffer
            available_context_tokens = MAX_CONTEXT_TOKENS - question_tokens - sub_queries_tokens - system_prompt_estimate - buffer_tokens
            
            if image_section_start >= 0 and image_section_end >= 0:
                image_section = context[image_section_start:image_section_end]
                image_section_tokens = self.count_tokens(image_section)
                remaining_tokens = available_context_tokens - image_section_tokens
                
                if remaining_tokens > 0:
                    main_context = context[:image_section_start]
                    truncated_main = self._truncate_text_by_tokens(main_context, remaining_tokens)
                    context = truncated_main + "\n\n" + image_section
                    logger.info(f"Agentic RAG: Preserved image section ({image_section_tokens:,} tokens), truncated main context to {remaining_tokens:,} tokens")
                else:
                    context = self._truncate_text_by_tokens(context, available_context_tokens)
                    logger.warning("Agentic RAG: Image section too large, truncating entire context")
            else:
                context = self._truncate_text_by_tokens(context, available_context_tokens)
            
            final_context_tokens = self.count_tokens(context)
            logger.info(f"Agentic RAG: Context truncated: {context_tokens:,} -> {final_context_tokens:,} tokens")
        
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

IMPORTANT: If the context includes an "IMAGE CONTENT (OCR TEXT EXTRACTED FROM IMAGES)" section (look for ⚠️⚠️⚠️ markers or "=== IMAGE CONTENT" header), you MUST USE THIS SECTION to answer questions about what is inside images.

CITATION RULES:
1. For EVERY technical claim, fact, or specification you provide, you MUST include a citation.
2. Citations MUST follow this exact format: [Source X: filename (Page Y)].
3. Source numbers (X), filenames, and page numbers (Y) are provided in the context headers: [Source X: filename (Page Y)].
4. If information spans multiple sources, cite all of them: [Source 1: docA.pdf (Page 5), Source 2: docB.pdf (Page 12)].
5. ALWAYS use the page number provided in the context header. This is the authoritative page number.
6. Citations must be placed at the end of the sentence or paragraph they support.

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

CRITICAL RULES:
- Synthesize information from ALL provided context chunks
- Work with the information that IS available in the context
- If the context contains relevant information (even if not a perfect match), synthesize it to answer the question
- DO NOT say "context does not contain" unless you have thoroughly analyzed ALL chunks and found absolutely no relevant information
- Address all relevant sub-queries and synthesize their results
- Be specific and cite exact values, measurements, and specifications when available. ALWAYS CITE YOUR SOURCES.
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- End your answer when you have provided the information - do not add unnecessary text

MULTILINGUAL INSTRUCTIONS:
- Detect the language of the user's question.
- ANSWER IN THE SAME LANGUAGE AS THE USER'S QUESTION.
- If the retrieved context is in a different language, TRANSLATE the relevant information into the language of the question.
- Do NOT answer in English if the user asks in Spanish, French, etc. (unless explicitly asked to)."""
            
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
        from shared.config.settings import ARISConfig
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
        from shared.config.settings import ARISConfig
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
                from shared.utils.image_extraction_logger import image_logger
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
            if len(results) == 0:
                logger.debug(f"No images found for query: '{question}'. Source filter: {source}")
            return results
        except ImportError as e:
            logger.warning(f"OpenSearch images store not available: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Failed to search images: {str(e)}")
            return []
