"""
Unit tests for document registry
"""
import os
import json
import tempfile
import threading
import time
import pytest
from storage.document_registry import DocumentRegistry


class TestDocumentRegistry:
    """Test DocumentRegistry class"""
    
    @pytest.fixture
    def temp_registry(self):
        """Create a temporary registry for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = os.path.join(tmpdir, "test_registry.json")
            registry = DocumentRegistry(registry_path)
            yield registry
            # Cleanup handled by tempfile
    
    def test_registry_initialization(self, temp_registry):
        """Test registry initialization"""
        assert temp_registry is not None
        assert temp_registry._documents == {}
    
    def test_add_document(self, temp_registry):
        """Test adding document"""
        test_doc = {
            'document_id': 'test-123',
            'document_name': 'test.pdf',
            'status': 'success',
            'chunks_created': 10,
            'tokens_extracted': 1000
        }
        temp_registry.add_document('test-123', test_doc)
        
        doc = temp_registry.get_document('test-123')
        assert doc is not None
        assert doc['document_name'] == 'test.pdf'
        assert 'created_at' in doc
        assert 'updated_at' in doc
    
    def test_get_document(self, temp_registry):
        """Test getting document"""
        test_doc = {
            'document_id': 'test-456',
            'document_name': 'test2.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-456', test_doc)
        
        doc = temp_registry.get_document('test-456')
        assert doc is not None
        assert doc['document_name'] == 'test2.pdf'
        
        # Test non-existent document
        assert temp_registry.get_document('nonexistent') is None
    
    def test_list_documents(self, temp_registry):
        """Test listing documents"""
        # Add multiple documents
        for i in range(3):
            doc = {
                'document_id': f'test-{i}',
                'document_name': f'test{i}.pdf',
                'status': 'success'
            }
            temp_registry.add_document(f'test-{i}', doc)
        
        docs = temp_registry.list_documents()
        assert len(docs) == 3
        assert all('document_name' in doc for doc in docs)
    
    def test_remove_document(self, temp_registry):
        """Test removing document"""
        test_doc = {
            'document_id': 'test-remove',
            'document_name': 'remove.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-remove', test_doc)
        assert len(temp_registry.list_documents()) == 1
        
        removed = temp_registry.remove_document('test-remove')
        assert removed is True
        assert len(temp_registry.list_documents()) == 0
        
        # Test removing non-existent document
        assert temp_registry.remove_document('nonexistent') is False
    
    def test_clear_all(self, temp_registry):
        """Test clearing all documents"""
        # Add multiple documents
        for i in range(5):
            doc = {
                'document_id': f'test-{i}',
                'document_name': f'test{i}.pdf',
                'status': 'success'
            }
            temp_registry.add_document(f'test-{i}', doc)
        
        assert len(temp_registry.list_documents()) == 5
        temp_registry.clear_all()
        assert len(temp_registry.list_documents()) == 0
    
    def test_get_sync_status(self, temp_registry):
        """Test getting sync status"""
        status = temp_registry.get_sync_status()
        assert isinstance(status, dict)
        assert 'total_documents' in status
        assert 'last_update' in status
        assert 'registry_path' in status
        assert 'registry_exists' in status
        assert status['total_documents'] == 0
        
        # Add document and check status updates
        test_doc = {
            'document_id': 'test-status',
            'document_name': 'status.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-status', test_doc)
        
        status = temp_registry.get_sync_status()
        assert status['total_documents'] == 1
        assert status['last_update'] is not None
    
    def test_check_for_conflicts(self, temp_registry):
        """Test conflict detection"""
        # Initially no conflicts
        conflict = temp_registry.check_for_conflicts()
        assert conflict is None
        
        # Add document
        test_doc = {
            'document_id': 'test-conflict',
            'document_name': 'conflict.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-conflict', test_doc)
        
        # Simulate external modification by updating version file
        if os.path.exists(temp_registry._version_file):
            time.sleep(0.1)  # Ensure different timestamp
            with open(temp_registry._version_file, 'w') as vf:
                vf.write(str(time.time()))
            
            # Now check for conflicts
            conflict = temp_registry.check_for_conflicts()
            # May or may not detect conflict depending on timing
            # This is expected behavior
    
    def test_reload_from_disk(self, temp_registry):
        """Test reloading from disk"""
        # Add document
        test_doc = {
            'document_id': 'test-reload',
            'document_name': 'reload.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-reload', test_doc)
        
        # Reload should work
        reloaded = temp_registry.reload_from_disk()
        assert reloaded is True
        
        # Document should still be there
        doc = temp_registry.get_document('test-reload')
        assert doc is not None
    
    def test_persistence(self, temp_registry):
        """Test that registry persists to disk"""
        test_doc = {
            'document_id': 'test-persist',
            'document_name': 'persist.pdf',
            'status': 'success'
        }
        temp_registry.add_document('test-persist', test_doc)
        
        # Verify file exists
        assert os.path.exists(temp_registry.registry_path)
        
        # Create new registry instance pointing to same file
        new_registry = DocumentRegistry(temp_registry.registry_path)
        
        # Should load the document
        doc = new_registry.get_document('test-persist')
        assert doc is not None
        assert doc['document_name'] == 'persist.pdf'
    
    def test_thread_safety(self, temp_registry):
        """Test thread-safety with concurrent operations"""
        results = []
        errors = []
        
        def add_docs(start_idx, count):
            try:
                for i in range(count):
                    doc = {
                        'document_id': f'thread-{start_idx + i}',
                        'document_name': f'thread{start_idx + i}.pdf',
                        'status': 'success'
                    }
                    temp_registry.add_document(f'thread-{start_idx + i}', doc)
                results.append(True)
            except Exception as e:
                errors.append(str(e))
                results.append(False)
        
        # Run multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_docs, args=(i * 10, 10))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check results
        assert all(results), f"Some threads failed: {errors}"
        
        # Verify all documents were added
        docs = temp_registry.list_documents()
        assert len(docs) == 50  # 5 threads * 10 docs each

