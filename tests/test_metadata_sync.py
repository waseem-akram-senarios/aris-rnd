"""
Tests for document metadata synchronization
"""
import os
import tempfile
import json
import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from storage.document_registry import DocumentRegistry
from api.service import create_service_container


class TestMetadataSync:
    """Test document metadata sharing"""
    
    @pytest.fixture
    def temp_registry_path(self):
        """Create temporary registry file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = os.path.join(tmpdir, "test_registry.json")
            yield registry_path
    
    def test_registry_file_persistence(self, temp_registry_path):
        """Test that registry persists to file"""
        registry1 = DocumentRegistry(temp_registry_path)
        
        # Add document
        test_doc = {
            'document_id': 'test-persist-1',
            'document_name': 'persist1.pdf',
            'status': 'success'
        }
        registry1.add_document('test-persist-1', test_doc)
        
        # Verify file exists
        assert os.path.exists(temp_registry_path)
        
        # Create new registry instance
        registry2 = DocumentRegistry(temp_registry_path)
        
        # Should load the document
        doc = registry2.get_document('test-persist-1')
        assert doc is not None
        assert doc['document_name'] == 'persist1.pdf'
    
    def test_cross_process_registry_access(self, temp_registry_path):
        """Test that registry can be accessed from different processes"""
        # Simulate FastAPI process
        registry1 = DocumentRegistry(temp_registry_path)
        test_doc1 = {
            'document_id': 'fastapi-doc',
            'document_name': 'fastapi.pdf',
            'status': 'success'
        }
        registry1.add_document('fastapi-doc', test_doc1)
        
        # Simulate Streamlit process
        registry2 = DocumentRegistry(temp_registry_path)
        
        # Should see document from FastAPI
        doc = registry2.get_document('fastapi-doc')
        assert doc is not None
        
        # Add document from Streamlit
        test_doc2 = {
            'document_id': 'streamlit-doc',
            'document_name': 'streamlit.pdf',
            'status': 'success'
        }
        registry2.add_document('streamlit-doc', test_doc2)
        
        # FastAPI should see both documents
        docs = registry1.list_documents()
        assert len(docs) == 2
        doc_ids = [d['document_id'] for d in docs]
        assert 'fastapi-doc' in doc_ids
        assert 'streamlit-doc' in doc_ids
    
    def test_service_container_uses_shared_registry(self):
        """Test that service container uses shared registry"""
        service1 = create_service_container()
        service2 = create_service_container()
        
        # Both should use same registry path
        assert service1.document_registry.registry_path == service2.document_registry.registry_path
        
        # Add via service1
        test_doc = {
            'document_id': 'service-shared',
            'document_name': 'shared.pdf',
            'status': 'success'
        }
        service1.add_document('service-shared', test_doc)
        
        # Access via service2
        doc = service2.get_document('service-shared')
        assert doc is not None
        
        # Cleanup
        service1.remove_document('service-shared')
    
    def test_concurrent_registry_access(self, temp_registry_path):
        """Test concurrent access to registry"""
        import threading
        
        results = []
        
        def add_docs(prefix, count):
            registry = DocumentRegistry(temp_registry_path)
            for i in range(count):
                doc = {
                    'document_id': f'{prefix}-{i}',
                    'document_name': f'{prefix}{i}.pdf',
                    'status': 'success'
                }
                registry.add_document(f'{prefix}-{i}', doc)
            results.append(True)
        
        # Run multiple threads
        threads = []
        for prefix in ['thread1', 'thread2', 'thread3']:
            t = threading.Thread(target=add_docs, args=(prefix, 5))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Verify all documents were added
        registry = DocumentRegistry(temp_registry_path)
        docs = registry.list_documents()
        assert len(docs) == 15  # 3 threads * 5 docs each

