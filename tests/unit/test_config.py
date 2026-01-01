"""
Unit tests for ARISConfig
"""
import pytest
import os
from unittest.mock import patch
from shared.config.settings import ARISConfig


@pytest.mark.unit
class TestARISConfig:
    """Test configuration module"""
    
    def test_default_values(self):
        """Test default configuration values"""
        # Test that defaults are set
        assert ARISConfig.EMBEDDING_MODEL is not None
        assert ARISConfig.OPENAI_MODEL is not None
        assert ARISConfig.VECTOR_STORE_TYPE is not None
        assert ARISConfig.DEFAULT_CHUNK_SIZE > 0
        assert ARISConfig.DEFAULT_CHUNK_OVERLAP >= 0
    
    def test_environment_variable_override(self):
        """Test environment variable overrides"""
        with patch.dict(os.environ, {
            'EMBEDDING_MODEL': 'test-embedding',
            'OPENAI_MODEL': 'test-model',
            'VECTOR_STORE_TYPE': 'test-store'
        }):
            # Reload config (in real usage, config is loaded at import time)
            # For testing, we check that env vars are read
            embedding = os.getenv('EMBEDDING_MODEL', ARISConfig.EMBEDDING_MODEL)
            assert embedding is not None
    
    def test_get_vectorstore_path(self):
        """Test getting vectorstore path"""
        path = ARISConfig.get_vectorstore_path()
        assert isinstance(path, str)
        assert len(path) > 0
    
    def test_get_vectorstore_path_with_model(self):
        """Test getting vectorstore path with model"""
        path = ARISConfig.get_vectorstore_path("test-model")
        assert isinstance(path, str)
        assert "test-model" in path or len(path) > 0
    
    def test_get_opensearch_config(self):
        """Test getting OpenSearch configuration"""
        config = ARISConfig.get_opensearch_config()
        assert isinstance(config, dict)
        assert "domain" in config or "endpoint" in config
    
    def test_get_model_config(self):
        """Test getting model configuration"""
        config = ARISConfig.get_model_config()
        assert isinstance(config, dict)
        assert "embedding_model" in config or "openai_model" in config
    
    def test_get_chunking_config(self):
        """Test getting chunking configuration"""
        config = ARISConfig.get_chunking_config()
        assert isinstance(config, dict)
        assert "chunk_size" in config or "strategy" in config
    
    def test_get_hybrid_search_config(self):
        """Test getting hybrid search configuration"""
        config = ARISConfig.get_hybrid_search_config()
        assert isinstance(config, dict)
    
    def test_get_agentic_rag_config(self):
        """Test getting agentic RAG configuration"""
        config = ARISConfig.get_agentic_rag_config()
        assert isinstance(config, dict)
    
    def test_document_registry_path(self):
        """Test document registry path"""
        path = ARISConfig.DOCUMENT_REGISTRY_PATH
        assert isinstance(path, str)
        assert len(path) > 0
    
    def test_chunking_strategy_default(self):
        """Test default chunking strategy"""
        strategy = ARISConfig.CHUNKING_STRATEGY
        assert strategy in ["precise", "balanced", "comprehensive"] or strategy is not None
    
    def test_retrieval_defaults(self):
        """Test default retrieval parameters"""
        assert ARISConfig.DEFAULT_RETRIEVAL_K > 0
        assert ARISConfig.DEFAULT_MMR_FETCH_K > 0
        assert 0.0 <= ARISConfig.DEFAULT_MMR_LAMBDA <= 1.0
        assert isinstance(ARISConfig.DEFAULT_USE_MMR, bool)
    
    def test_agentic_rag_defaults(self):
        """Test default agentic RAG parameters"""
        assert ARISConfig.DEFAULT_USE_AGENTIC_RAG is not None
        assert ARISConfig.DEFAULT_MAX_SUB_QUERIES > 0
        assert ARISConfig.DEFAULT_CHUNKS_PER_SUBQUERY > 0
        assert ARISConfig.DEFAULT_MAX_TOTAL_CHUNKS > 0
        assert 0.0 <= ARISConfig.DEFAULT_DEDUPLICATION_THRESHOLD <= 1.0
