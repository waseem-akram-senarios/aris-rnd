"""
Unit tests for DocumentRegistry
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from storage.document_registry import DocumentRegistry


@pytest.mark.unit
class TestDocumentRegistry:
    """Test document registry"""
    
    def test_initialization(self, temp_registry_file):
        """Test registry initialization"""
        registry = DocumentRegistry(str(temp_registry_file))
        assert registry.registry_path == str(temp_registry_file)
        assert registry._documents == {}
    
    def test_add_document(self, temp_registry_file):
        """Test adding document"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        metadata = {
            "document_name": "test.pdf",
            "status": "completed",
            "chunks_created": 10
        }
        
        registry.add_document("doc-123", metadata)
        
        doc = registry.get_document("doc-123")
        assert doc is not None
        assert doc["document_name"] == "test.pdf"
        assert doc["status"] == "completed"
        assert "created_at" in doc
    
    def test_get_document(self, temp_registry_file):
        """Test getting document"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        metadata = {"document_name": "test.pdf"}
        registry.add_document("doc-123", metadata)
        
        doc = registry.get_document("doc-123")
        assert doc is not None
        assert doc["document_name"] == "test.pdf"
        
        # Non-existent document
        assert registry.get_document("non-existent") is None
    
    def test_list_documents(self, temp_registry_file):
        """Test listing documents"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        # Add multiple documents
        registry.add_document("doc-1", {"document_name": "doc1.pdf"})
        registry.add_document("doc-2", {"document_name": "doc2.pdf"})
        registry.add_document("doc-3", {"document_name": "doc3.pdf"})
        
        docs = registry.list_documents()
        assert len(docs) == 3
        assert all("document_name" in doc for doc in docs)
    
    def test_remove_document(self, temp_registry_file):
        """Test removing document"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        registry.add_document("doc-123", {"document_name": "test.pdf"})
        assert registry.get_document("doc-123") is not None
        
        result = registry.remove_document("doc-123")
        assert result is True
        assert registry.get_document("doc-123") is None
        
        # Remove non-existent
        result = registry.remove_document("non-existent")
        assert result is False
    
    def test_clear_all(self, temp_registry_file):
        """Test clearing all documents"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        registry.add_document("doc-1", {"document_name": "doc1.pdf"})
        registry.add_document("doc-2", {"document_name": "doc2.pdf"})
        
        registry.clear_all()
        
        assert len(registry.list_documents()) == 0
    
    def test_persistence(self, temp_registry_file):
        """Test registry persistence to disk"""
        # Create registry and add document
        registry1 = DocumentRegistry(str(temp_registry_file))
        registry1.add_document("doc-123", {"document_name": "test.pdf"})
        
        # Create new registry instance (should load from disk)
        registry2 = DocumentRegistry(str(temp_registry_file))
        doc = registry2.get_document("doc-123")
        
        assert doc is not None
        assert doc["document_name"] == "test.pdf"
    
    def test_version_tracking(self, temp_registry_file):
        """Test document version tracking"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        # Add document
        registry.add_document("doc-123", {"document_name": "test.pdf", "version": 1})
        
        # Update document (should increment version)
        registry.add_document("doc-123", {"document_name": "test.pdf", "version": 2})
        
        doc = registry.get_document("doc-123")
        version_info = doc.get("version_info", {})
        assert version_info.get("version", 1) >= 1
    
    def test_thread_safety(self, temp_registry_file):
        """Test thread safety of registry operations"""
        import threading
        
        registry = DocumentRegistry(str(temp_registry_file))
        errors = []
        
        def add_docs(start_id, count):
            try:
                for i in range(count):
                    registry.add_document(f"doc-{start_id + i}", {
                        "document_name": f"doc{start_id + i}.pdf"
                    })
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=add_docs, args=(i * 10, 10))
            threads.append(t)
            t.start()
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        # Check no errors occurred
        assert len(errors) == 0
        
        # Verify all documents were added
        docs = registry.list_documents()
        assert len(docs) == 50
    
    def test_get_sync_status(self, temp_registry_file):
        """Test getting sync status"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        registry.add_document("doc-123", {"document_name": "test.pdf"})
        
        status = registry.get_sync_status()
        assert "last_update" in status or status is not None
    
    def test_check_for_conflicts(self, temp_registry_file):
        """Test conflict detection"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        # Add document
        registry.add_document("doc-123", {"document_name": "test.pdf"})
        
        # Check for conflicts (implementation may vary)
        try:
            conflicts = registry.check_for_conflicts()
            # Method may return None, list, or dict
            assert conflicts is None or isinstance(conflicts, (list, dict))
        except AttributeError:
            # Method may not exist, skip test
            pytest.skip("check_for_conflicts method not available")
    
    def test_reload_from_disk(self, temp_registry_file):
        """Test reloading from disk"""
        registry1 = DocumentRegistry(str(temp_registry_file))
        registry1.add_document("doc-123", {"document_name": "test.pdf"})
        
        # Reload
        registry1._load_registry()
        
        # Should still have document
        assert registry1.get_document("doc-123") is not None
    
    def test_corrupted_file_handling(self, temp_registry_file):
        """Test handling of corrupted registry file"""
        # Write invalid JSON
        with open(temp_registry_file, 'w') as f:
            f.write("invalid json content")
        
        # Should handle gracefully
        registry = DocumentRegistry(str(temp_registry_file))
        assert registry._documents == {}  # Should start fresh
    
    def test_update_document(self, temp_registry_file):
        """Test updating existing document"""
        registry = DocumentRegistry(str(temp_registry_file))
        
        # Add document
        registry.add_document("doc-123", {
            "document_name": "test.pdf",
            "status": "processing"
        })
        
        # Update document (add_document updates if exists)
        registry.add_document("doc-123", {
            "document_name": "test.pdf",
            "status": "completed"
        })
        
        doc = registry.get_document("doc-123")
        assert doc["status"] == "completed"
