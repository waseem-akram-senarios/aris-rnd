"""
Service container for RAG system components
"""
import os
import logging
from typing import Dict, Optional, List
from dotenv import load_dotenv
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector
from utils.chunking_strategies import get_chunking_params
from config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from scripts.setup_logging import get_logger

load_dotenv()

logger = get_logger("aris_rag.service")


class ServiceContainer:
    """Container for RAG system services"""
    
    def __init__(
        self,
        use_cerebras: bool = False,
        embedding_model: str = "text-embedding-3-small",
        openai_model: str = "gpt-3.5-turbo",
        cerebras_model: str = "llama3.1-8b",
        vector_store_type: str = "faiss",
        opensearch_domain: Optional[str] = None,
        opensearch_index: Optional[str] = None,
        chunk_size: int = 384,
        chunk_overlap: int = 75
    ):
        """
        Initialize service container with RAG system components.
        
        Args:
            use_cerebras: Whether to use Cerebras API
            embedding_model: Embedding model name
            openai_model: OpenAI model name
            cerebras_model: Cerebras model name
            vector_store_type: Vector store type ('faiss' or 'opensearch')
            opensearch_domain: OpenSearch domain name (if using OpenSearch)
            opensearch_index: OpenSearch index name (if using OpenSearch)
            chunk_size: Chunk size in tokens
            chunk_overlap: Chunk overlap in tokens
        """
        logger.info("=" * 60)
        logger.info("[STEP 1] ServiceContainer: Initializing MetricsCollector...")
        # Initialize metrics collector
        self.metrics_collector = MetricsCollector()
        logger.info("✅ [STEP 1] MetricsCollector initialized")
        
        logger.info("[STEP 2] ServiceContainer: Initializing RAGSystem...")
        logger.info(f"   Configuration: vector_store={vector_store_type}, embedding={embedding_model}, "
                   f"chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")
        # Initialize RAG system
        self.rag_system = RAGSystem(
            use_cerebras=use_cerebras,
            metrics_collector=self.metrics_collector,
            embedding_model=embedding_model,
            openai_model=openai_model,
            cerebras_model=cerebras_model,
            vector_store_type=vector_store_type,
            opensearch_domain=opensearch_domain,
            opensearch_index=opensearch_index,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        logger.info("✅ [STEP 2] RAGSystem initialized")
        
        logger.info("[STEP 3] ServiceContainer: Initializing DocumentProcessor...")
        # Initialize document processor
        self.document_processor = DocumentProcessor(self.rag_system)
        logger.info("✅ [STEP 3] DocumentProcessor initialized")
        
        logger.info("[STEP 4] ServiceContainer: Initializing DocumentRegistry...")
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        logger.info(f"   Registry path: {registry_path}")
        # Use shared document registry instead of in-memory storage
        self.document_registry = DocumentRegistry(registry_path)
        logger.info("✅ [STEP 4] DocumentRegistry initialized")
        logger.info("=" * 60)
        logger.info("✅ ServiceContainer fully initialized")
        logger.info("=" * 60)
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """Get document metadata by ID"""
        logger.info(f"[STEP 1] ServiceContainer: Retrieving document: {document_id}")
        doc = self.document_registry.get_document(document_id)
        if doc:
            logger.info(f"✅ [STEP 1] Document retrieved: {document_id}")
        else:
            logger.warning(f"⚠️ [STEP 1] Document not found: {document_id}")
        return doc
    
    def list_documents(self) -> list:
        """List all documents"""
        logger.info("[STEP 1] ServiceContainer: Listing all documents...")
        documents = self.document_registry.list_documents()
        logger.info(f"✅ [STEP 1] Retrieved {len(documents)} document(s) from registry")
        return documents
    
    def add_document(self, document_id: str, result: Dict):
        """Add document metadata"""
        doc_name = result.get('document_name', 'unknown')
        logger.info(f"[STEP 1] ServiceContainer: Adding document to registry: id={document_id}, name={doc_name}")
        self.document_registry.add_document(document_id, result)
        logger.info(f"✅ [STEP 1] Document added to registry: {document_id}")
    
    def remove_document(self, document_id: str) -> bool:
        """Remove document metadata"""
        logger.info(f"[STEP 1] ServiceContainer: Removing document from registry: {document_id}")
        result = self.document_registry.remove_document(document_id)
        if result:
            logger.info(f"✅ [STEP 1] Document removed from registry: {document_id}")
        else:
            logger.warning(f"⚠️ [STEP 1] Document not found for removal: {document_id}")
        return result
    
    def clear_documents(self):
        """Clear all documents"""
        logger.info("[STEP 1] ServiceContainer: Clearing all documents from registry...")
        self.document_registry.clear_all()
        logger.info("✅ [STEP 1] All documents cleared from registry")
    
    def query_text_only(self, question: str, k: int = 6, document_id: Optional[str] = None, use_mmr: bool = True) -> Dict:
        """
        Query only text content from main index (excludes images).
        
        Args:
            question: Query question
            k: Number of chunks to retrieve
            document_id: Optional document ID to filter by
            use_mmr: Use Maximum Marginal Relevance
            
        Returns:
            Query response with text-only results
        """
        logger.info(f"[STEP 1] ServiceContainer: Querying text-only content: question='{question[:50]}...', k={k}, document_id={document_id}")
        
        # Set document filter if provided (using active_sources)
        original_sources = self.rag_system.active_sources
        original_index_map = getattr(self.rag_system, 'document_index_map', None)
        if document_id:
            try:
                doc = self.get_document(document_id)
                if doc:
                    doc_name = doc.get('document_name') or doc.get('original_document_name')
                    if doc_name:
                        self.rag_system.active_sources = [doc_name]
                        logger.info(f"Filtering text query to document: {doc_name}")
                        if self.rag_system.vector_store_type.lower() == 'opensearch':
                            doc_text_index = doc.get('text_index')
                            if doc_text_index:
                                try:
                                    if not hasattr(self.rag_system, 'document_index_map') or self.rag_system.document_index_map is None:
                                        self.rag_system.document_index_map = {}
                                    self.rag_system.document_index_map[doc_name] = doc_text_index
                                except Exception as e:
                                    logger.warning(f"Could not set document_index_map for '{doc_name}': {e}")
            except Exception as e:
                logger.warning(f"Could not filter to document_id {document_id}: {e}")
                self.rag_system.active_sources = None
        else:
            self.rag_system.active_sources = None
        
        try:
            # Use the main query method but ensure it only queries text index
            # The RAG system should already separate text and images by index
            result = self.rag_system.query_with_rag(
                question=question,
                k=k,
                use_mmr=use_mmr
            )
        finally:
            # Restore original active_sources
            self.rag_system.active_sources = original_sources
            # Restore original index map reference if it was missing (best-effort)
            if original_index_map is None:
                try:
                    self.rag_system.document_index_map = None
                except Exception:
                    pass
        
        # Ensure we're only getting text results (no image content)
        # Filter out any citations that might be from images
        if 'citations' in result:
            text_citations = [
                cit for cit in result['citations']
                if cit.get('content_type', 'text') == 'text'
            ]
            result['citations'] = text_citations
            result['num_chunks_used'] = len(text_citations)
        
        logger.info(f"✅ [STEP 1] Text-only query completed: {result.get('num_chunks_used', 0)} chunks")
        return result
    
    def query_images_only(self, question: str, k: int = 5, source: Optional[str] = None) -> List[Dict]:
        """
        Query only image OCR content from images index (excludes regular text).
        
        Args:
            question: Query question
            k: Number of images to retrieve
            source: Optional document source to filter by
            
        Returns:
            List of image results with OCR text
        """
        logger.info(f"[STEP 1] ServiceContainer: Querying images-only content: question='{question[:50]}...', k={k}, source={source}")
        
        # Use the existing query_images method which already queries images index
        result = self.rag_system.query_images(
            question=question,
            source=source,
            k=k
        )
        
        logger.info(f"✅ [STEP 1] Images-only query completed: {len(result)} images")
        return result
    
    def get_storage_status(self, document_id: str) -> Dict:
        """
        Get separate storage status for text and images.
        
        Args:
            document_id: Document ID to check
            
        Returns:
            Dictionary with storage status for text and images
        """
        logger.info(f"[STEP 1] ServiceContainer: Getting storage status for document: {document_id}")
        
        # Get document metadata
        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        doc_name = doc.get('document_name', 'unknown')
        doc_text_index = doc.get('text_index') or getattr(self.rag_system, 'opensearch_index', None) or 'aris-rag-index'
        
        # Initialize status response
        status = {
            'document_id': document_id,
            'document_name': doc_name,
            'text_index': doc_text_index,
            'text_chunks_count': doc.get('chunks_created', 0),
            'text_storage_status': 'completed' if doc.get('chunks_created', 0) > 0 else 'pending',
            'text_last_updated': None,
            'images_index': 'aris-rag-images-index',
            'images_count': doc.get('image_count', 0),
            'images_storage_status': 'completed' if doc.get('images_detected', False) and doc.get('image_count', 0) > 0 else 'pending',
            'images_last_updated': None,
            'ocr_enabled': str(doc.get('parser_used', '')).lower() == 'docling',
            'total_ocr_text_length': 0
        }
        
        # Try to get actual counts from OpenSearch if available
        vector_store_type = getattr(self.rag_system, 'vector_store_type', None)
        if vector_store_type and vector_store_type.lower() == 'opensearch':
            try:
                # Get text chunks count from OpenSearch (authoritative)
                from vectorstores.opensearch_store import OpenSearchVectorStore
                from langchain_openai import OpenAIEmbeddings

                embeddings = OpenAIEmbeddings(
                    openai_api_key=os.getenv('OPENAI_API_KEY'),
                    model=self.rag_system.embedding_model
                )

                text_store = OpenSearchVectorStore(
                    embeddings=embeddings,
                    domain=self.rag_system.opensearch_domain,
                    index_name=doc_text_index,
                    region=getattr(self.rag_system, 'region', None)
                )

                status['text_chunks_count'] = text_store.count_documents()
                status['text_storage_status'] = 'completed' if status['text_chunks_count'] > 0 else status['text_storage_status']

                from vectorstores.opensearch_images_store import OpenSearchImagesStore

                # Get images count
                images_store = OpenSearchImagesStore(
                    embeddings=embeddings,
                    domain=self.rag_system.opensearch_domain,
                    region=getattr(self.rag_system, 'region', None)
                )
                
                # Count images for this document (best effort: by source)
                status['images_count'] = images_store.count_images_by_source(doc_name)
                status['images_storage_status'] = 'completed' if status['images_count'] > 0 else status['images_storage_status']
                
                # Calculate total OCR text length (requires fetching docs; keep as best-effort)
                images = images_store.get_images_by_source(doc_name, limit=1000)
                status['total_ocr_text_length'] = sum(len(img.get('ocr_text', '')) for img in images)
                
            except Exception as e:
                logger.warning(f"Could not get detailed storage status from OpenSearch: {e}")
        
        logger.info(f"✅ [STEP 1] Storage status retrieved: text_chunks={status['text_chunks_count']}, images={status['images_count']}")
        return status


def create_service_container(
    use_cerebras: Optional[bool] = None,
    embedding_model: Optional[str] = None,
    openai_model: Optional[str] = None,
    cerebras_model: Optional[str] = None,
    vector_store_type: Optional[str] = None,
    opensearch_domain: Optional[str] = None,
    opensearch_index: Optional[str] = None,
    chunking_strategy: Optional[str] = None
) -> ServiceContainer:
    """
    Create a service container with configuration from ARISConfig.
    
    Args:
        use_cerebras: Whether to use Cerebras API (defaults to ARISConfig)
        embedding_model: Embedding model name (defaults to ARISConfig)
        openai_model: OpenAI model name (defaults to ARISConfig)
        cerebras_model: Cerebras model name (defaults to ARISConfig)
        vector_store_type: Vector store type (defaults to ARISConfig)
        opensearch_domain: OpenSearch domain (defaults to ARISConfig)
        opensearch_index: OpenSearch index (defaults to ARISConfig)
        chunking_strategy: Chunking strategy (defaults to ARISConfig)
    
    Returns:
        ServiceContainer instance
    """
    # Use ARISConfig defaults if not provided
    use_cerebras = use_cerebras if use_cerebras is not None else ARISConfig.USE_CEREBRAS
    embedding_model = embedding_model or ARISConfig.EMBEDDING_MODEL
    openai_model = openai_model or ARISConfig.OPENAI_MODEL
    cerebras_model = cerebras_model or ARISConfig.CEREBRAS_MODEL
    vector_store_type = vector_store_type or ARISConfig.VECTOR_STORE_TYPE
    chunking_strategy = chunking_strategy or ARISConfig.CHUNKING_STRATEGY

    if vector_store_type.lower() == "opensearch":
        has_creds = bool(os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') and os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'))
        has_domain = bool(os.getenv('AWS_OPENSEARCH_DOMAIN') or os.getenv('OPENSEARCH_DOMAIN'))
        if not (has_creds and has_domain):
            vector_store_type = "faiss"
    
    # Get chunking parameters from strategy
    chunk_size, chunk_overlap = get_chunking_params(chunking_strategy)
    
    # Get OpenSearch config from ARISConfig if not provided
    if vector_store_type.lower() == "opensearch":
        opensearch_config = ARISConfig.get_opensearch_config()
        opensearch_domain = opensearch_domain or opensearch_config['domain']
        opensearch_index = opensearch_index or opensearch_config['index']
    
    return ServiceContainer(
        use_cerebras=use_cerebras,
        embedding_model=embedding_model,
        openai_model=openai_model,
        cerebras_model=cerebras_model,
        vector_store_type=vector_store_type,
        opensearch_domain=opensearch_domain,
        opensearch_index=opensearch_index,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

