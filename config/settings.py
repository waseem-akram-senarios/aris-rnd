"""
Shared configuration module for ARIS RAG System.
Provides centralized configuration for both Streamlit and FastAPI.
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class ARISConfig:
    """Centralized configuration for ARIS RAG System"""
    
    # API Configuration
    USE_CEREBRAS: bool = os.getenv('USE_CEREBRAS', 'false').lower() == 'true'
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    CEREBRAS_API_KEY: Optional[str] = os.getenv('CEREBRAS_API_KEY')
    
    # Model Configuration - Best quality defaults
    EMBEDDING_MODEL: str = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')  # Best quality: 3072 dimensions
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4o')  # Best quality: Latest GPT-4o model
    CEREBRAS_MODEL: str = os.getenv('CEREBRAS_MODEL', 'llama-3.3-70b')  # Best quality: 70B parameter model
    
    # Vector Store Configuration
    VECTOR_STORE_TYPE: str = os.getenv('VECTOR_STORE_TYPE', 'opensearch').lower()
    VECTORSTORE_PATH: str = os.getenv('VECTORSTORE_PATH', 'vectorstore')
    AWS_OPENSEARCH_DOMAIN: Optional[str] = os.getenv('AWS_OPENSEARCH_DOMAIN', 'intelycx-waseem-os')
    AWS_OPENSEARCH_INDEX: str = os.getenv('AWS_OPENSEARCH_INDEX', 'aris-rag-index')
    AWS_OPENSEARCH_ACCESS_KEY_ID: Optional[str] = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    AWS_OPENSEARCH_SECRET_ACCESS_KEY: Optional[str] = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    AWS_OPENSEARCH_REGION: str = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
    
    # Chunking Configuration - Optimized for maximum accuracy
    CHUNKING_STRATEGY: str = os.getenv('CHUNKING_STRATEGY', 'comprehensive')
    
    # Default chunking parameters - Optimized for retrieval accuracy
    # Smaller chunks = more precise retrieval, larger overlap = better context continuity
    DEFAULT_CHUNK_SIZE: int = int(os.getenv('DEFAULT_CHUNK_SIZE', '384'))  # Optimal for precision
    DEFAULT_CHUNK_OVERLAP: int = int(os.getenv('DEFAULT_CHUNK_OVERLAP', '120'))  # Increased for better continuity
    
    # Retrieval Configuration - Optimized for best results and UX
    DEFAULT_RETRIEVAL_K: int = int(os.getenv('DEFAULT_RETRIEVAL_K', '12'))  # Increased for better coverage
    DEFAULT_MMR_FETCH_K: int = int(os.getenv('DEFAULT_MMR_FETCH_K', '50'))  # Larger candidate pool
    DEFAULT_MMR_LAMBDA: float = float(os.getenv('DEFAULT_MMR_LAMBDA', '0.35'))  # Balanced relevance/diversity
    DEFAULT_USE_MMR: bool = os.getenv('DEFAULT_USE_MMR', 'true').lower() == 'true'
    
    # Generation Configuration - Optimized for comprehensive answers
    DEFAULT_TEMPERATURE: float = float(os.getenv('DEFAULT_TEMPERATURE', '0.0'))  # Maximum determinism
    DEFAULT_MAX_TOKENS: int = int(os.getenv('DEFAULT_MAX_TOKENS', '1200'))  # Increased for detailed answers
    
    # Hybrid Search Configuration - Enabled by default for better accuracy
    DEFAULT_USE_HYBRID_SEARCH: bool = os.getenv('DEFAULT_USE_HYBRID_SEARCH', 'true').lower() == 'true'
    DEFAULT_SEMANTIC_WEIGHT: float = float(os.getenv('DEFAULT_SEMANTIC_WEIGHT', '0.75'))
    DEFAULT_KEYWORD_WEIGHT: float = float(os.getenv('DEFAULT_KEYWORD_WEIGHT', '0.25'))
    DEFAULT_SEARCH_MODE: str = os.getenv('DEFAULT_SEARCH_MODE', 'hybrid')  # 'semantic', 'keyword', 'hybrid'
    
    # Agentic RAG Configuration - Optimized for comprehensive synthesis
    DEFAULT_USE_AGENTIC_RAG: bool = os.getenv('DEFAULT_USE_AGENTIC_RAG', 'true').lower() == 'true'
    DEFAULT_MAX_SUB_QUERIES: int = int(os.getenv('DEFAULT_MAX_SUB_QUERIES', '4'))
    DEFAULT_CHUNKS_PER_SUBQUERY: int = int(os.getenv('DEFAULT_CHUNKS_PER_SUBQUERY', '6'))  # Increased for better coverage
    DEFAULT_MAX_TOTAL_CHUNKS: int = int(os.getenv('DEFAULT_MAX_TOTAL_CHUNKS', '25'))  # Increased for better synthesis
    DEFAULT_DEDUPLICATION_THRESHOLD: float = float(os.getenv('DEFAULT_DEDUPLICATION_THRESHOLD', '0.95'))
    
    # Summary Query Configuration
    DEFAULT_SUMMARY_QUERY_K_MULTIPLIER: float = float(os.getenv('DEFAULT_SUMMARY_QUERY_K_MULTIPLIER', '2.0'))
    DEFAULT_SUMMARY_QUERY_MIN_K: int = int(os.getenv('DEFAULT_SUMMARY_QUERY_MIN_K', '20'))
    DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES: bool = os.getenv('DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES', 'true').lower() == 'true'
    
    # Document Storage Configuration
    DOCUMENT_REGISTRY_PATH: str = os.getenv('DOCUMENT_REGISTRY_PATH', 'storage/document_registry.json')
    
    # Parser Configuration
    DOCLING_MAX_TIMEOUT: int = int(os.getenv('DOCLING_MAX_TIMEOUT', '1800'))  # 30 minutes default
    
    @classmethod
    def get_vectorstore_path(cls, embedding_model: Optional[str] = None) -> str:
        """Get vectorstore path, optionally with model-specific subdirectory"""
        base_path = cls.VECTORSTORE_PATH
        if embedding_model:
            # Create model-specific path to support multiple embedding models
            model_safe = embedding_model.replace("/", "_")
            return os.path.join(base_path, model_safe)
        return base_path
    
    @classmethod
    def get_opensearch_config(cls) -> dict:
        """Get OpenSearch configuration"""
        return {
            'domain': cls.AWS_OPENSEARCH_DOMAIN,
            'index': cls.AWS_OPENSEARCH_INDEX,
            'access_key_id': cls.AWS_OPENSEARCH_ACCESS_KEY_ID,
            'secret_access_key': cls.AWS_OPENSEARCH_SECRET_ACCESS_KEY,
            'region': cls.AWS_OPENSEARCH_REGION
        }
    
    @classmethod
    def get_model_config(cls) -> dict:
        """Get model configuration"""
        return {
            'use_cerebras': cls.USE_CEREBRAS,
            'embedding_model': cls.EMBEDDING_MODEL,
            'openai_model': cls.OPENAI_MODEL,
            'cerebras_model': cls.CEREBRAS_MODEL
        }
    
    @classmethod
    def get_chunking_config(cls) -> dict:
        """Get chunking configuration"""
        return {
            'strategy': cls.CHUNKING_STRATEGY,
            'chunk_size': cls.DEFAULT_CHUNK_SIZE,
            'chunk_overlap': cls.DEFAULT_CHUNK_OVERLAP
        }
    
    @classmethod
    def get_hybrid_search_config(cls) -> dict:
        """Get hybrid search configuration"""
        # Ensure weights sum to 1.0
        semantic_weight = cls.DEFAULT_SEMANTIC_WEIGHT
        keyword_weight = cls.DEFAULT_KEYWORD_WEIGHT
        total = semantic_weight + keyword_weight
        if total > 0:
            semantic_weight = semantic_weight / total
            keyword_weight = keyword_weight / total
        else:
            semantic_weight = 0.7
            keyword_weight = 0.3
        
        return {
            'use_hybrid_search': cls.DEFAULT_USE_HYBRID_SEARCH,
            'semantic_weight': semantic_weight,
            'keyword_weight': keyword_weight,
            'search_mode': cls.DEFAULT_SEARCH_MODE
        }
    
    @classmethod
    def get_agentic_rag_config(cls) -> dict:
        """Get Agentic RAG configuration"""
        return {
            'use_agentic_rag': cls.DEFAULT_USE_AGENTIC_RAG,
            'max_sub_queries': cls.DEFAULT_MAX_SUB_QUERIES,
            'chunks_per_subquery': cls.DEFAULT_CHUNKS_PER_SUBQUERY,
            'max_total_chunks': cls.DEFAULT_MAX_TOTAL_CHUNKS,
            'deduplication_threshold': cls.DEFAULT_DEDUPLICATION_THRESHOLD
        }
    
    @classmethod
    def get_summary_query_config(cls) -> dict:
        """Get summary query configuration"""
        return {
            'k_multiplier': cls.DEFAULT_SUMMARY_QUERY_K_MULTIPLIER,
            'min_k': cls.DEFAULT_SUMMARY_QUERY_MIN_K,
            'auto_enable_agentic': cls.DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES
        }

