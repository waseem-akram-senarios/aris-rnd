"""
Service container for RAG system components
"""
import os
import logging
from typing import Dict, Optional
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

