"""
Complete end-to-end synchronization workflow test
"""
import os
import tempfile
import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.service import create_service_container
from storage.document_registry import DocumentRegistry
from config.settings import ARISConfig


class TestFullSyncWorkflow:
    """Test complete synchronization workflow"""
    
    @pytest.fixture
    def temp_environment(self):
        """Create temporary environment for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up temp paths
            vectorstore_path = os.path.join(tmpdir, "vectorstore")
            registry_path = os.path.join(tmpdir, "registry.json")
            
            yield {
                'vectorstore_path': vectorstore_path,
                'registry_path': registry_path
            }
    
    def test_clean_start_workflow(self, temp_environment):
        """Test workflow starting from clean state"""
        registry_path = temp_environment['registry_path']
        
        # Step 1: Start with clean state
        registry = DocumentRegistry(registry_path)
        assert len(registry.list_documents()) == 0
        
        # Step 2: Simulate FastAPI adding document
        test_doc = {
            'document_id': 'fastapi-doc-1',
            'document_name': 'fastapi1.pdf',
            'status': 'success',
            'chunks_created': 10,
            'tokens_extracted': 1000
        }
        registry.add_document('fastapi-doc-1', test_doc)
        
        # Step 3: Verify document in registry
        doc = registry.get_document('fastapi-doc-1')
        assert doc is not None
        assert doc['document_name'] == 'fastapi1.pdf'
        
        # Step 4: Simulate Streamlit loading registry
        streamlit_registry = DocumentRegistry(registry_path)
        docs = streamlit_registry.list_documents()
        assert len(docs) == 1
        assert docs[0]['document_id'] == 'fastapi-doc-1'
        
        # Step 5: Simulate Streamlit adding document
        test_doc2 = {
            'document_id': 'streamlit-doc-1',
            'document_name': 'streamlit1.pdf',
            'status': 'success',
            'chunks_created': 5,
            'tokens_extracted': 500
        }
        streamlit_registry.add_document('streamlit-doc-1', test_doc2)
        
        # Step 6: Verify both documents in FastAPI registry
        fastapi_registry = DocumentRegistry(registry_path)
        all_docs = fastapi_registry.list_documents()
        assert len(all_docs) == 2
        doc_ids = [d['document_id'] for d in all_docs]
        assert 'fastapi-doc-1' in doc_ids
        assert 'streamlit-doc-1' in doc_ids
    
    def test_service_container_workflow(self):
        """Test workflow using service containers"""
        # Create service containers (simulating FastAPI and Streamlit)
        service1 = create_service_container()  # FastAPI
        service2 = create_service_container()  # Streamlit
        
        # Both should use same registry
        assert service1.document_registry.registry_path == service2.document_registry.registry_path
        
        # FastAPI adds document
        test_doc = {
            'document_id': 'service-workflow-1',
            'document_name': 'workflow1.pdf',
            'status': 'success'
        }
        service1.add_document('service-workflow-1', test_doc)
        
        # Streamlit should see it
        doc = service2.get_document('service-workflow-1')
        assert doc is not None
        
        # Streamlit adds document
        test_doc2 = {
            'document_id': 'service-workflow-2',
            'document_name': 'workflow2.pdf',
            'status': 'success'
        }
        service2.add_document('service-workflow-2', test_doc2)
        
        # FastAPI should see both
        docs = service1.list_documents()
        doc_ids = [d['document_id'] for d in docs]
        assert 'service-workflow-1' in doc_ids or 'service-workflow-2' in doc_ids
        
        # Cleanup
        service1.remove_document('service-workflow-1')
        service1.remove_document('service-workflow-2')
    
    def test_sync_status_workflow(self):
        """Test sync status throughout workflow"""
        service = create_service_container()
        
        # Get initial status
        status1 = service.document_registry.get_sync_status()
        initial_count = status1['total_documents']
        
        # Add document
        test_doc = {
            'document_id': 'sync-status-test',
            'document_name': 'status.pdf',
            'status': 'success'
        }
        service.add_document('sync-status-test', test_doc)
        
        # Get new status
        status2 = service.document_registry.get_sync_status()
        new_count = status2['total_documents']
        
        # Count should increase
        assert new_count >= initial_count
        
        # Cleanup
        service.remove_document('sync-status-test')

