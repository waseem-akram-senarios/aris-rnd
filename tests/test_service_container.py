"""
Unit tests for service container
"""
import os
import sys
from pathlib import Path
import pytest

# Add project root to path - must be before any imports
project_root = Path(__file__).parent.parent
current_dir = str(project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Also add current working directory
if '.' not in sys.path:
    sys.path.insert(0, '.')

from api.service import ServiceContainer, create_service_container


class TestServiceContainer:
    """Test ServiceContainer class"""
    
    def test_create_service_container_defaults(self):
        """Test creating service container with defaults"""
        service = create_service_container()
        
        assert service is not None
        assert isinstance(service, ServiceContainer)
        assert service.rag_system is not None
        assert service.document_processor is not None
        assert service.document_registry is not None
        assert service.metrics_collector is not None
    
    def test_create_service_container_custom(self):
        """Test creating service container with custom params"""
        service = create_service_container(
            use_cerebras=False,
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunking_strategy="balanced"
        )
        
        assert service is not None
        assert service.rag_system.embedding_model == "text-embedding-3-small"
        assert service.rag_system.openai_model == "gpt-3.5-turbo"
        assert service.rag_system.vector_store_type == "faiss"
    
    def test_service_container_components(self):
        """Test that service container has all required components"""
        service = create_service_container()
        
        # Check all components exist
        assert hasattr(service, 'rag_system')
        assert hasattr(service, 'document_processor')
        assert hasattr(service, 'document_registry')
        assert hasattr(service, 'metrics_collector')
        
        # Check components are initialized
        assert service.rag_system is not None
        assert service.document_processor is not None
        assert service.document_registry is not None
        assert service.metrics_collector is not None
    
    def test_document_operations_through_service(self):
        """Test document operations through service container"""
        service = create_service_container()
        
        # Test adding document
        test_doc = {
            'document_id': 'test-service-123',
            'document_name': 'test_service.pdf',
            'status': 'success',
            'chunks_created': 5,
            'tokens_extracted': 500
        }
        service.add_document('test-service-123', test_doc)
        
        # Test getting document
        doc = service.get_document('test-service-123')
        assert doc is not None
        assert doc['document_name'] == 'test_service.pdf'
        
        # Test listing documents
        docs = service.list_documents()
        assert len(docs) >= 1
        assert any(d['document_id'] == 'test-service-123' for d in docs)
        
        # Test removing document
        removed = service.remove_document('test-service-123')
        assert removed is True
        
        # Verify removed
        doc = service.get_document('test-service-123')
        assert doc is None
    
    def test_service_uses_shared_registry(self):
        """Test that service uses shared registry"""
        service1 = create_service_container()
        service2 = create_service_container()
        
        # Both should use the same registry path
        assert service1.document_registry.registry_path == service2.document_registry.registry_path
        
        # Add document via service1
        test_doc = {
            'document_id': 'test-shared',
            'document_name': 'shared.pdf',
            'status': 'success'
        }
        service1.add_document('test-shared', test_doc)
        
        # Should be accessible via service2 (same registry)
        doc = service2.get_document('test-shared')
        assert doc is not None
        
        # Cleanup
        service1.remove_document('test-shared')

