"""
Tests for configuration synchronization
"""
import os
import pytest
from unittest.mock import patch
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import ARISConfig
from api.service import create_service_container


class TestConfigSync:
    """Test shared configuration"""
    
    def test_config_provides_defaults(self):
        """Test that ARISConfig provides consistent defaults"""
        assert ARISConfig.VECTOR_STORE_TYPE is not None
        assert ARISConfig.EMBEDDING_MODEL is not None
        assert ARISConfig.OPENAI_MODEL is not None
        assert ARISConfig.CHUNKING_STRATEGY is not None
    
    def test_fastapi_uses_config_defaults(self):
        """Test that FastAPI uses ARISConfig defaults"""
        service = create_service_container()
        
        # Service should use config defaults when no params provided
        assert service.rag_system.embedding_model == ARISConfig.EMBEDDING_MODEL
        assert service.rag_system.openai_model == ARISConfig.OPENAI_MODEL
        assert service.rag_system.vector_store_type == ARISConfig.VECTOR_STORE_TYPE
    
    def test_config_methods_return_consistent_values(self):
        """Test that config methods return consistent values"""
        vectorstore_path1 = ARISConfig.get_vectorstore_path()
        vectorstore_path2 = ARISConfig.get_vectorstore_path()
        assert vectorstore_path1 == vectorstore_path2
        
        opensearch_config1 = ARISConfig.get_opensearch_config()
        opensearch_config2 = ARISConfig.get_opensearch_config()
        assert opensearch_config1 == opensearch_config2
        
        model_config1 = ARISConfig.get_model_config()
        model_config2 = ARISConfig.get_model_config()
        assert model_config1 == model_config2
    
    def test_config_values_are_accessible(self):
        """Test that all config values are accessible"""
        # Test all main config attributes exist
        assert hasattr(ARISConfig, 'USE_CEREBRAS')
        assert hasattr(ARISConfig, 'EMBEDDING_MODEL')
        assert hasattr(ARISConfig, 'OPENAI_MODEL')
        assert hasattr(ARISConfig, 'CEREBRAS_MODEL')
        assert hasattr(ARISConfig, 'VECTOR_STORE_TYPE')
        assert hasattr(ARISConfig, 'VECTORSTORE_PATH')
        assert hasattr(ARISConfig, 'CHUNKING_STRATEGY')
        assert hasattr(ARISConfig, 'DOCUMENT_REGISTRY_PATH')
    
    def test_service_container_respects_config(self):
        """Test that service container respects config when created without params"""
        service = create_service_container()
        
        # Should use config defaults
        assert service.rag_system.embedding_model is not None
        assert service.rag_system.openai_model is not None
        assert service.rag_system.vector_store_type is not None

