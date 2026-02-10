"""
Shared configuration module for ARIS RAG System.
Provides centralized configuration for ALL services (Gateway, Ingestion, Retrieval, MCP, UI).

🎯 OPTIMIZED FOR MAXIMUM ACCURACY (R&D Settings)
"""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class ARISConfig:
    """
    Centralized configuration for ARIS RAG System
    
    ⚠️ ALL SERVICES USE THESE SETTINGS - Keep in sync!
    - Gateway Service (8500)
    - Ingestion Service (8501)  
    - Retrieval Service (8502)
    - MCP Server (8503)
    - Streamlit UI (80)
    """
    
    # =========================================================================
    # API Configuration
    # =========================================================================
    USE_CEREBRAS: bool = os.getenv('USE_CEREBRAS', 'false').lower() == 'true'
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    CEREBRAS_API_KEY: Optional[str] = os.getenv('CEREBRAS_API_KEY')
    
    # =========================================================================
    # 🎯 MODEL CONFIGURATION - Maximum Quality
    # =========================================================================
    # Embedding: text-embedding-3-large has 3072 dimensions (highest quality)
    EMBEDDING_MODEL: str = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-large')
    
    # LLM: GPT-4o is the latest and most capable model
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4o')
    CEREBRAS_MODEL: str = os.getenv('CEREBRAS_MODEL', 'llama-3.3-70b')
    
    # Dual-Model Strategy: Simple (fast) vs Deep (thorough) queries
    SIMPLE_QUERY_MODEL: str = os.getenv('SIMPLE_QUERY_MODEL', 'gpt-4o-mini')
    DEEP_QUERY_MODEL: str = os.getenv('DEEP_QUERY_MODEL', 'gpt-4o')
    
    # =========================================================================
    # VECTOR STORE CONFIGURATION
    # =========================================================================
    VECTOR_STORE_TYPE: str = os.getenv('VECTOR_STORE_TYPE', 'opensearch').lower()
    VECTORSTORE_PATH: str = os.getenv('VECTORSTORE_PATH', 'vectorstore')
    
    # OpenSearch Configuration
    AWS_OPENSEARCH_DOMAIN: Optional[str] = os.getenv('AWS_OPENSEARCH_DOMAIN', 'intelycx-waseem-os')
    AWS_OPENSEARCH_INDEX: str = os.getenv('AWS_OPENSEARCH_INDEX', 'aris-rag-index')
    AWS_OPENSEARCH_ACCESS_KEY_ID: Optional[str] = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    AWS_OPENSEARCH_SECRET_ACCESS_KEY: Optional[str] = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    AWS_OPENSEARCH_REGION: str = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
    
    # S3 Storage Configuration
    ENABLE_S3_STORAGE: bool = os.getenv('ENABLE_S3_STORAGE', 'true').lower() == 'true'
    AWS_S3_BUCKET: str = os.getenv('AWS_S3_BUCKET', 'intelycx-waseem-s3-bucket')
    
    # =========================================================================
    # 🎯 CHUNKING CONFIGURATION - Optimized for Accuracy
    # =========================================================================
    # Strategy: 'comprehensive' uses semantic boundaries for better chunks
    CHUNKING_STRATEGY: str = os.getenv('CHUNKING_STRATEGY', 'comprehensive')
    
    # Chunk Size: 800 tokens is optimal for:
    # - Enough context for understanding
    # - Not too large to dilute relevance
    # - Good for reranking (needs sufficient context)
    DEFAULT_CHUNK_SIZE: int = int(os.getenv('DEFAULT_CHUNK_SIZE', '800'))
    
    # Chunk Overlap: 200 tokens (~25% overlap)
    # - Ensures context continuity across chunk boundaries
    # - Captures information that spans chunks
    DEFAULT_CHUNK_OVERLAP: int = int(os.getenv('DEFAULT_CHUNK_OVERLAP', '200'))
    
    # =========================================================================
    # 🎯 RETRIEVAL CONFIGURATION - Maximum Accuracy
    # =========================================================================
    # K value: 25 chunks for comprehensive retrieval
    # - More chunks = better chance of finding relevant info
    # - Reranking will filter to top results
    DEFAULT_RETRIEVAL_K: int = int(os.getenv('DEFAULT_RETRIEVAL_K', '25'))
    
    # MMR (Maximal Marginal Relevance) - Disabled for reranking
    DEFAULT_MMR_FETCH_K: int = int(os.getenv('DEFAULT_MMR_FETCH_K', '50'))
    DEFAULT_MMR_LAMBDA: float = float(os.getenv('DEFAULT_MMR_LAMBDA', '0.5'))
    DEFAULT_USE_MMR: bool = os.getenv('DEFAULT_USE_MMR', 'false').lower() == 'true'
    
    # 🎯 RERANKING - CRITICAL FOR ACCURACY
    # FlashRank reranking significantly improves result quality
    ENABLE_RERANKING: bool = os.getenv('ENABLE_RERANKING', 'true').lower() == 'true'
    RERANK_TOP_K: int = int(os.getenv('RERANK_TOP_K', '10'))  # Return top 10 after reranking
    
    # =========================================================================
    # 🎯 GENERATION CONFIGURATION - Factual & Comprehensive
    # =========================================================================
    # Temperature: 0.1 for highly factual, consistent answers
    DEFAULT_TEMPERATURE: float = float(os.getenv('DEFAULT_TEMPERATURE', '0.1'))
    
    # Max Tokens: 2500 for detailed, comprehensive answers
    DEFAULT_MAX_TOKENS: int = int(os.getenv('DEFAULT_MAX_TOKENS', '2500'))
    
    # =========================================================================
    # 🎯 HYBRID SEARCH CONFIGURATION - Balanced for Accuracy
    # =========================================================================
    # Hybrid search combines semantic understanding with keyword matching
    DEFAULT_USE_HYBRID_SEARCH: bool = os.getenv('DEFAULT_USE_HYBRID_SEARCH', 'true').lower() == 'true'
    
    # Semantic Weight: 0.6 - Emphasize meaning understanding
    # Keyword Weight: 0.4 - Capture exact term matches
    DEFAULT_SEMANTIC_WEIGHT: float = float(os.getenv('DEFAULT_SEMANTIC_WEIGHT', '0.6'))
    DEFAULT_KEYWORD_WEIGHT: float = float(os.getenv('DEFAULT_KEYWORD_WEIGHT', '0.4'))
    DEFAULT_SEARCH_MODE: str = os.getenv('DEFAULT_SEARCH_MODE', 'hybrid')
    
    # =========================================================================
    # 🎯 AGENTIC RAG CONFIGURATION - Smart Query Handling
    # =========================================================================
    # Agentic RAG decomposes complex queries for better retrieval
    DEFAULT_USE_AGENTIC_RAG: bool = os.getenv('DEFAULT_USE_AGENTIC_RAG', 'true').lower() == 'true'
    
    # Sub-queries: 3 for balanced decomposition
    DEFAULT_MAX_SUB_QUERIES: int = int(os.getenv('DEFAULT_MAX_SUB_QUERIES', '3'))
    
    # Chunks per sub-query: 10 for comprehensive coverage
    DEFAULT_CHUNKS_PER_SUBQUERY: int = int(os.getenv('DEFAULT_CHUNKS_PER_SUBQUERY', '10'))
    
    # Decomposition model: gpt-4o-mini for speed (decomposition doesn't need full power)
    QUERY_DECOMPOSITION_MODEL: str = os.getenv('QUERY_DECOMPOSITION_MODEL', 'gpt-4o-mini')
    
    # Total chunks limit after deduplication
    DEFAULT_MAX_TOTAL_CHUNKS: int = int(os.getenv('DEFAULT_MAX_TOTAL_CHUNKS', '30'))
    
    # Deduplication threshold: 0.92 to remove near-duplicates
    DEFAULT_DEDUPLICATION_THRESHOLD: float = float(os.getenv('DEFAULT_DEDUPLICATION_THRESHOLD', '0.92'))
    
    # =========================================================================
    # SUMMARY QUERY CONFIGURATION
    # =========================================================================
    DEFAULT_SUMMARY_QUERY_K_MULTIPLIER: float = float(os.getenv('DEFAULT_SUMMARY_QUERY_K_MULTIPLIER', '2.0'))
    DEFAULT_SUMMARY_QUERY_MIN_K: int = int(os.getenv('DEFAULT_SUMMARY_QUERY_MIN_K', '20'))
    DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES: bool = os.getenv('DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES', 'true').lower() == 'true'
    
    # =========================================================================
    # DOCUMENT STORAGE CONFIGURATION
    # =========================================================================
    DOCUMENT_REGISTRY_PATH: str = os.getenv('DOCUMENT_REGISTRY_PATH', 'storage/document_registry.json')
    DOCUMENT_REGISTRY_INDEX: str = os.getenv('DOCUMENT_REGISTRY_INDEX', 'aris-document-registry')
    DOCUMENT_REGISTRY_SYNC_INTERVAL_SECONDS: int = int(os.getenv('DOCUMENT_REGISTRY_SYNC_INTERVAL_SECONDS', '30'))
    
    # =========================================================================
    # 🎯 PARSER CONFIGURATION - Best Quality Extraction
    # =========================================================================
    # Docling: Best for accuracy & robustness (layout-aware, handles tables)
    # PyMuPDF: Fast but less accurate for complex layouts
    # LlamaScan: Best for highly visual documents
    DEFAULT_PARSER: str = os.getenv('DEFAULT_PARSER', 'docling')
    DOCLING_MAX_TIMEOUT: int = int(os.getenv('DOCLING_MAX_TIMEOUT', '1800'))  # 30 minutes
    
    # Parser fallback chain for robustness
    PARSER_FALLBACK_CHAIN: str = os.getenv('PARSER_FALLBACK_CHAIN', 'docling,pymupdf,llama_scan')
    
    # =========================================================================
    # INGESTION PERFORMANCE CONFIGURATION
    # =========================================================================
    EMBEDDING_BATCH_SIZE: int = int(os.getenv('EMBEDDING_BATCH_SIZE', '500'))
    OPENSEARCH_BULK_SIZE: int = int(os.getenv('OPENSEARCH_BULK_SIZE', '5000'))
    MAX_PAGE_BLOCKS_PER_DOC: int = int(os.getenv('MAX_PAGE_BLOCKS_PER_DOC', '2000'))
    
    # =========================================================================
    # MULTILINGUAL CONFIGURATION
    # =========================================================================
    ENABLE_AUTO_TRANSLATE: bool = os.getenv('ENABLE_AUTO_TRANSLATE', 'true').lower() == 'true'
    TRANSLATE_DOCUMENTS_ON_INGESTION: bool = os.getenv('TRANSLATE_DOCUMENTS_ON_INGESTION', 'false').lower() == 'true'
    TRANSLATION_PROVIDER: str = os.getenv('TRANSLATION_PROVIDER', 'openai')
    DEFAULT_DOCUMENT_LANGUAGE: str = os.getenv('DEFAULT_DOCUMENT_LANGUAGE', 'eng')
    DEFAULT_RESPONSE_LANGUAGE: str = os.getenv('DEFAULT_RESPONSE_LANGUAGE', 'auto')
    ENABLE_DUAL_SEARCH: bool = os.getenv('ENABLE_DUAL_SEARCH', 'true').lower() == 'true'
    AUTO_DETECT_LANGUAGE: bool = os.getenv('AUTO_DETECT_LANGUAGE', 'true').lower() == 'true'
    SUPPORTED_LANGUAGES: str = os.getenv('SUPPORTED_LANGUAGES', 'eng,spa,fra,deu,por,ita,rus,jpn,kor,zho,ara')
    
    # OCR Configuration
    OCR_DEFAULT_DPI: int = int(os.getenv('OCR_DEFAULT_DPI', '300'))
    OCR_CJK_DPI: int = int(os.getenv('OCR_CJK_DPI', '400'))
    OCR_TIMEOUT_PER_PAGE: int = int(os.getenv('OCR_TIMEOUT_PER_PAGE', '180'))
    
    # =========================================================================
    # 🎯 CONFIDENCE & ACCURACY THRESHOLDS
    # =========================================================================
    # Minimum confidence for citations to be shown
    MIN_CITATION_CONFIDENCE: float = float(os.getenv('MIN_CITATION_CONFIDENCE', '0.3'))
    
    # Fuzzy matching threshold for keyword matching (typo tolerance)
    FUZZY_MATCH_THRESHOLD: float = float(os.getenv('FUZZY_MATCH_THRESHOLD', '0.75'))
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @classmethod
    def get_multilingual_config(cls) -> dict:
        """Get multilingual configuration"""
        return {
            'enable_auto_translate': cls.ENABLE_AUTO_TRANSLATE,
            'translate_on_ingestion': cls.TRANSLATE_DOCUMENTS_ON_INGESTION,
            'translation_provider': cls.TRANSLATION_PROVIDER,
            'default_language': cls.DEFAULT_DOCUMENT_LANGUAGE,
            'default_response_language': cls.DEFAULT_RESPONSE_LANGUAGE,
            'enable_dual_search': cls.ENABLE_DUAL_SEARCH,
            'auto_detect_language': cls.AUTO_DETECT_LANGUAGE,
            'supported_languages': [lang.strip() for lang in cls.SUPPORTED_LANGUAGES.split(',')],
            'ocr_default_dpi': cls.OCR_DEFAULT_DPI,
            'ocr_cjk_dpi': cls.OCR_CJK_DPI,
            'ocr_timeout_per_page': cls.OCR_TIMEOUT_PER_PAGE,
        }
    
    @classmethod
    def get_vectorstore_path(cls, embedding_model: Optional[str] = None) -> str:
        """Get vectorstore path, optionally with model-specific subdirectory"""
        base_path = cls.VECTORSTORE_PATH
        if embedding_model:
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
    def get_retrieval_config(cls) -> dict:
        """Get retrieval configuration for maximum accuracy"""
        return {
            'k': cls.DEFAULT_RETRIEVAL_K,
            'use_mmr': cls.DEFAULT_USE_MMR,
            'mmr_fetch_k': cls.DEFAULT_MMR_FETCH_K,
            'mmr_lambda': cls.DEFAULT_MMR_LAMBDA,
            'enable_reranking': cls.ENABLE_RERANKING,
            'rerank_top_k': cls.RERANK_TOP_K,
        }
    
    @classmethod
    def get_hybrid_search_config(cls) -> dict:
        """Get hybrid search configuration"""
        semantic_weight = cls.DEFAULT_SEMANTIC_WEIGHT
        keyword_weight = cls.DEFAULT_KEYWORD_WEIGHT
        total = semantic_weight + keyword_weight
        if total > 0:
            semantic_weight = semantic_weight / total
            keyword_weight = keyword_weight / total
        else:
            semantic_weight = 0.6
            keyword_weight = 0.4
        
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
            'deduplication_threshold': cls.DEFAULT_DEDUPLICATION_THRESHOLD,
            'decomposition_model': cls.QUERY_DECOMPOSITION_MODEL
        }
    
    @classmethod
    def get_generation_config(cls) -> dict:
        """Get generation configuration"""
        return {
            'temperature': cls.DEFAULT_TEMPERATURE,
            'max_tokens': cls.DEFAULT_MAX_TOKENS,
        }
    
    @classmethod
    def get_summary_query_config(cls) -> dict:
        """Get summary query configuration"""
        return {
            'k_multiplier': cls.DEFAULT_SUMMARY_QUERY_K_MULTIPLIER,
            'min_k': cls.DEFAULT_SUMMARY_QUERY_MIN_K,
            'auto_enable_agentic': cls.DEFAULT_AUTO_ENABLE_AGENTIC_FOR_SUMMARIES
        }
    
    @classmethod
    def get_knn_performance_config(cls) -> dict:
        """
        Get k-NN (vector search) performance tuning configuration.
        Used by OpenSearch hybrid_search for ef_search, min_score, caching.
        """
        return {
            'ef_search': int(os.getenv('KNN_EF_SEARCH', '512')),
            'min_score': float(os.getenv('KNN_MIN_SCORE', '0.0')),
            'cache_ttl_seconds': int(os.getenv('KNN_CACHE_TTL_SECONDS', '300')),
            'max_fetch_multiplier': int(os.getenv('KNN_MAX_FETCH_MULTIPLIER', '4')),
        }
    
    @classmethod
    def get_accuracy_config(cls) -> dict:
        """Get all accuracy-related configuration"""
        return {
            'chunking': cls.get_chunking_config(),
            'retrieval': cls.get_retrieval_config(),
            'hybrid_search': cls.get_hybrid_search_config(),
            'agentic_rag': cls.get_agentic_rag_config(),
            'generation': cls.get_generation_config(),
            'knn_performance': cls.get_knn_performance_config(),
            'min_citation_confidence': cls.MIN_CITATION_CONFIDENCE,
            'fuzzy_match_threshold': cls.FUZZY_MATCH_THRESHOLD,
        }
