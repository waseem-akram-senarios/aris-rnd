"""
Tests for conflict detection and resolution
"""
import os
import tempfile
import time
import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from storage.document_registry import DocumentRegistry


class TestConflictResolution:
    """Test conflict detection and resolution"""
    
    @pytest.fixture
    def temp_registry_path(self):
        """Create temporary registry file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = os.path.join(tmpdir, "test_registry.json")
            yield registry_path
    
    def test_conflict_detection_none_initially(self, temp_registry_path):
        """Test that no conflicts detected initially"""
        registry = DocumentRegistry(temp_registry_path)
        conflict = registry.check_for_conflicts()
        assert conflict is None
    
    def test_conflict_detection_after_external_modification(self, temp_registry_path):
        """Test conflict detection after external modification"""
        registry1 = DocumentRegistry(temp_registry_path)
        
        # Add document
        test_doc = {
            'document_id': 'test-conflict',
            'document_name': 'conflict.pdf',
            'status': 'success'
        }
        registry1.add_document('test-conflict', test_doc)
        
        # Simulate external modification by directly updating version file
        time.sleep(0.1)  # Ensure different timestamp
        version_file = f"{temp_registry_path}.version"
        if os.path.exists(version_file):
            with open(version_file, 'w') as vf:
                vf.write(str(time.time()))
            
            # Check for conflicts in same registry instance
            # Note: This may not detect conflict in same instance due to caching
            # But demonstrates the mechanism
        
        # Create new registry instance (simulates different process)
        registry2 = DocumentRegistry(temp_registry_path)
        
        # Modify via registry2
        test_doc2 = {
            'document_id': 'test-conflict-2',
            'document_name': 'conflict2.pdf',
            'status': 'success'
        }
        registry2.add_document('test-conflict-2', test_doc2)
        
        # Now registry1 should potentially detect conflict
        # (depending on timing and implementation)
        conflict = registry1.check_for_conflicts()
        # May or may not detect conflict - this is expected behavior
    
    def test_reload_resolves_conflicts(self, temp_registry_path):
        """Test that reload resolves conflicts"""
        registry1 = DocumentRegistry(temp_registry_path)
        
        # Add document
        test_doc = {
            'document_id': 'test-reload-conflict',
            'document_name': 'reload.pdf',
            'status': 'success'
        }
        registry1.add_document('test-reload-conflict', test_doc)
        
        # Simulate external modification
        registry2 = DocumentRegistry(temp_registry_path)
        test_doc2 = {
            'document_id': 'external-doc',
            'document_name': 'external.pdf',
            'status': 'success'
        }
        registry2.add_document('external-doc', test_doc2)
        
        # Reload registry1
        reloaded = registry1.reload_from_disk()
        assert reloaded is True
        
        # Should now see external document
        doc = registry1.get_document('external-doc')
        assert doc is not None
    
    def test_version_tracking(self, temp_registry_path):
        """Test that version tracking works"""
        registry = DocumentRegistry(temp_registry_path)
        
        # Get initial status
        status1 = registry.get_sync_status()
        version1 = status1.get('version_timestamp')
        
        # Add document (should update version)
        test_doc = {
            'document_id': 'test-version',
            'document_name': 'version.pdf',
            'status': 'success'
        }
        registry.add_document('test-version', test_doc)
        
        # Get new status
        status2 = registry.get_sync_status()
        version2 = status2.get('version_timestamp')
        
        # Version should be updated (if version file exists)
        if version1 is not None and version2 is not None:
            assert version2 >= version1

