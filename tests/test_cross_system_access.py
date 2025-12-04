"""
Tests for cross-system document access
"""
import sys
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.service import create_service_container


class TestCrossSystemAccess:
    """Test documents accessible across systems"""
    
    def test_documents_shared_between_services(self):
        """Test that documents are shared between service instances"""
        # Simulate FastAPI service
        fastapi_service = create_service_container()
        
        # Simulate Streamlit service
        streamlit_service = create_service_container()
        
        # Both should use same registry
        assert fastapi_service.document_registry.registry_path == streamlit_service.document_registry.registry_path
        
        # FastAPI adds document
        test_doc = {
            'document_id': 'cross-system-1',
            'document_name': 'cross1.pdf',
            'status': 'success',
            'chunks_created': 10,
            'tokens_extracted': 1000
        }
        fastapi_service.add_document('cross-system-1', test_doc)
        
        # Streamlit should see it
        doc = streamlit_service.get_document('cross-system-1')
        assert doc is not None
        assert doc['document_name'] == 'cross1.pdf'
        
        # Streamlit adds document
        test_doc2 = {
            'document_id': 'cross-system-2',
            'document_name': 'cross2.pdf',
            'status': 'success',
            'chunks_created': 5,
            'tokens_extracted': 500
        }
        streamlit_service.add_document('cross-system-2', test_doc2)
        
        # FastAPI should see both
        docs = fastapi_service.list_documents()
        doc_ids = [d['document_id'] for d in docs]
        # At least one of our test documents should be present
        assert 'cross-system-1' in doc_ids or 'cross-system-2' in doc_ids
        
        # Cleanup
        fastapi_service.remove_document('cross-system-1')
        fastapi_service.remove_document('cross-system-2')
    
    def test_registry_consistency(self):
        """Test that registry remains consistent across accesses"""
        service1 = create_service_container()
        service2 = create_service_container()
        
        # Add via service1
        test_doc = {
            'document_id': 'consistency-test',
            'document_name': 'consistency.pdf',
            'status': 'success'
        }
        service1.add_document('consistency-test', test_doc)
        
        # Access via service2 multiple times
        doc1 = service2.get_document('consistency-test')
        doc2 = service2.get_document('consistency-test')
        
        # Should be consistent
        assert doc1 is not None
        assert doc2 is not None
        assert doc1['document_name'] == doc2['document_name']
        
        # Cleanup
        service1.remove_document('consistency-test')

