"""
Unit tests for configuration module
"""
import os
import pytest
from unittest.mock import patch
from config.settings import ARISConfig


class TestARISConfig:
    """Test ARISConfig class"""
    
    def test_config_initialization(self):
        """Test that ARISConfig initializes correctly"""
        assert ARISConfig is not None
        assert hasattr(ARISConfig, 'VECTOR_STORE_TYPE')
        assert hasattr(ARISConfig, 'EMBEDDING_MODEL')
        assert hasattr(ARISConfig, 'OPENAI_MODEL')
    
    def test_default_values(self):
        """Test default values when env vars not set"""
        # These should have defaults even if env vars are not set
        assert ARISConfig.VECTOR_STORE_TYPE is not None
        assert ARISConfig.EMBEDDING_MODEL is not None
        assert ARISConfig.OPENAI_MODEL is not None
        assert ARISConfig.CHUNKING_STRATEGY is not None
    
    def test_get_vectorstore_path(self):
        """Test get_vectorstore_path method"""
        path = ARISConfig.get_vectorstore_path()
        assert isinstance(path, str)
        assert len(path) > 0
    
    def test_get_opensearch_config(self):
        """Test get_opensearch_config method"""
        config = ARISConfig.get_opensearch_config()
        assert isinstance(config, dict)
        assert 'domain' in config
        assert 'index' in config
        assert 'access_key_id' in config
        assert 'secret_access_key' in config
        assert 'region' in config
    
    def test_get_model_config(self):
        """Test get_model_config method"""
        config = ARISConfig.get_model_config()
        assert isinstance(config, dict)
        assert 'use_cerebras' in config
        assert 'embedding_model' in config
        assert 'openai_model' in config
        assert 'cerebras_model' in config
    
    def test_get_chunking_config(self):
        """Test get_chunking_config method"""
        config = ARISConfig.get_chunking_config()
        assert isinstance(config, dict)
        assert 'strategy' in config
    
    @patch.dict(os.environ, {'VECTOR_STORE_TYPE': 'opensearch'})
    def test_environment_variable_override(self):
        """Test that environment variables override defaults"""
        # Reload module to pick up new env var
        import importlib
        import config.settings
        importlib.reload(config.settings)
        
        # Note: This test may not work perfectly due to module caching,
        # but it demonstrates the concept
        assert config.settings.ARISConfig.VECTOR_STORE_TYPE == 'opensearch'

