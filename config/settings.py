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
    
    # Model Configuration
    EMBEDDING_MODEL: str = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    CEREBRAS_MODEL: str = os.getenv('CEREBRAS_MODEL', 'llama3.1-8b')
    
    # Vector Store Configuration
    VECTOR_STORE_TYPE: str = os.getenv('VECTOR_STORE_TYPE', 'faiss').lower()
    VECTORSTORE_PATH: str = os.getenv('VECTORSTORE_PATH', 'vectorstore')
    AWS_OPENSEARCH_DOMAIN: Optional[str] = os.getenv('AWS_OPENSEARCH_DOMAIN', 'intelycx-waseem-os')
    AWS_OPENSEARCH_INDEX: str = os.getenv('AWS_OPENSEARCH_INDEX', 'aris-rag-index')
    AWS_OPENSEARCH_ACCESS_KEY_ID: Optional[str] = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    AWS_OPENSEARCH_SECRET_ACCESS_KEY: Optional[str] = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    AWS_OPENSEARCH_REGION: str = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
    
    # Chunking Configuration
    CHUNKING_STRATEGY: str = os.getenv('CHUNKING_STRATEGY', 'balanced')
    
    # Document Storage Configuration
    DOCUMENT_REGISTRY_PATH: str = os.getenv('DOCUMENT_REGISTRY_PATH', 'storage/document_registry.json')
    
    @classmethod
    def get_vectorstore_path(cls) -> str:
        """Get vectorstore path"""
        return cls.VECTORSTORE_PATH
    
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
            'strategy': cls.CHUNKING_STRATEGY
        }

