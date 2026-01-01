"""
Shared document registry for storing document metadata.
Thread-safe operations for concurrent access from FastAPI and Streamlit.
"""
import os
import json
import threading
import time
import fcntl
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
from shared.utils.s3_service import S3Service
from shared.config.settings import ARISConfig


class DocumentRegistry:
    """Thread-safe document metadata registry"""
    
    def __init__(self, registry_path: str = "storage/document_registry.json"):
        """
        Initialize document registry.
        
        Args:
            registry_path: Path to JSON file for storing metadata
        """
        self.registry_path = registry_path
        self._lock = threading.Lock()
        self._version_file = f"{registry_path}.version"
        self._ensure_directory()
        
        # Initialize S3 Service for synchronization
        self.s3_service = S3Service()
        self.s3_registry_key = f"configs/{os.path.basename(registry_path)}"
        
        # Sync from S3 on startup if enabled
        if ARISConfig.ENABLE_S3_STORAGE:
            self._sync_from_s3()
            
        self._load_registry()
    
    def _ensure_directory(self):
        """Ensure storage directory exists"""
        Path(self.registry_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_registry(self):
        """Load registry from disk"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r', encoding='utf-8') as f:
                    self._documents = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                # If file is corrupted or can't be read, start fresh
                self._documents = {}
        else:
            self._documents = {}

    def _sync_from_s3(self):
        """Try to download the registry from S3 if it's newer or local is missing."""
        if not self.s3_service.enabled:
            return

        try:
            # For simplicity, we just download it on startup if it exists in S3
            # In a more advanced version, we could check ETag or last modified
            if self.s3_service.download_file(self.s3_registry_key, self.registry_path):
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"🔄 Synced document registry from S3: {self.s3_registry_key}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Failed to sync registry from S3: {e}")
    
    def _save_registry(self):
        """Save registry to disk with file locking"""
        try:
            # Write to temp file first, then rename (atomic operation)
            temp_path = f"{self.registry_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                # Try to acquire file lock (non-blocking)
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except (IOError, OSError):
                    # Lock failed, wait a bit and retry
                    time.sleep(0.1)
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                json.dump(self._documents, f, indent=2, ensure_ascii=False)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            
            os.replace(temp_path, self.registry_path)
            
            # Update version file
            with open(self._version_file, 'w') as vf:
                fcntl.flock(vf.fileno(), fcntl.LOCK_EX)
                vf.write(str(time.time()))
                fcntl.flock(vf.fileno(), fcntl.LOCK_UN)
                
            # Sync to S3 if enabled
            if ARISConfig.ENABLE_S3_STORAGE:
                self._sync_to_s3()
                
        except IOError as e:
            # Log error but don't fail
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save document registry: {e}")

    def _sync_to_s3(self):
        """Upload the local registry to S3."""
        if not self.s3_service.enabled:
            return

        try:
            self.s3_service.upload_file(self.registry_path, self.s3_registry_key, content_type="application/json")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"⚠️ Failed to upload registry to S3: {e}")
    
    def add_document(self, document_id: str, metadata: Dict):
        """
        Add or update document metadata.
        
        Args:
            document_id: Unique document identifier
            metadata: Document metadata dictionary
        """
        with self._lock:
            # Check if document already exists (for version tracking)
            existing_doc = self._documents.get(document_id)
            
            # Add timestamp if not present
            if 'created_at' not in metadata:
                if existing_doc and existing_doc.get('created_at'):
                    metadata['created_at'] = existing_doc['created_at']
                else:
                    metadata['created_at'] = datetime.now().isoformat()
            
            # Track version if document exists
            if existing_doc:
                # Increment version
                existing_version = existing_doc.get('version_info', {}).get('version', 1)
                new_version = existing_version + 1
                
                # Store version history
                if 'version_history' not in metadata.get('version_info', {}):
                    version_info = metadata.get('version_info', {})
                    if 'version_history' not in version_info:
                        version_info['version_history'] = []
                    
                    # Add previous version to history
                    version_info['version_history'].append({
                        'version': existing_version,
                        'updated_at': existing_doc.get('updated_at'),
                        'changes': self._detect_changes(existing_doc, metadata)
                    })
                    version_info['version'] = new_version
                    metadata['version_info'] = version_info
                else:
                    version_info = metadata.get('version_info', {})
                    version_info['version'] = new_version
            
            metadata['updated_at'] = datetime.now().isoformat()
            
            self._documents[document_id] = metadata
            self._save_registry()
    
    def _detect_changes(self, old_metadata: Dict, new_metadata: Dict) -> List[str]:
        """
        Detect changes between old and new metadata.
        
        Args:
            old_metadata: Previous metadata
            new_metadata: New metadata
        
        Returns:
            List of change descriptions
        """
        changes = []
        
        # Check key fields
        key_fields = ['document_name', 'parser_used', 'chunks_created', 'images_stored', 'file_hash']
        for field in key_fields:
            if old_metadata.get(field) != new_metadata.get(field):
                changes.append(f"{field} changed from {old_metadata.get(field)} to {new_metadata.get(field)}")
        
        return changes
    
    def add_document_version(self, document_id: str, metadata: Dict):
        """
        Add new version of existing document.
        
        Args:
            document_id: Document identifier
            metadata: New version metadata
        """
        self.add_document(document_id, metadata)
    
    def get_document_versions(self, document_id: str) -> List[Dict]:
        """
        Get all versions of a document.
        
        Args:
            document_id: Document identifier
        
        Returns:
            List of version metadata dictionaries
        """
        with self._lock:
            doc = self._documents.get(document_id)
            if not doc:
                return []
            
            versions = [doc]  # Current version
            
            # Get version history if available
            version_info = doc.get('version_info', {})
            version_history = version_info.get('version_history', [])
            
            # Note: Full version history would require storing all versions
            # For now, we return current version with history metadata
            return versions
    
    def get_document(self, document_id: str) -> Optional[Dict]:
        """
        Get document metadata by ID.
        
        Args:
            document_id: Document identifier
        
        Returns:
            Document metadata or None if not found
        """
        with self._lock:
            return self._documents.get(document_id)
    
    def list_documents(self) -> List[Dict]:
        """
        List all documents.
        
        Returns:
            List of document metadata dictionaries (with document_id included)
        """
        with self._lock:
            # Include document_id in each document
            result = []
            for doc_id, doc in self._documents.items():
                doc_with_id = dict(doc)  # Copy to avoid modifying original
                if 'document_id' not in doc_with_id or not doc_with_id.get('document_id'):
                    doc_with_id['document_id'] = doc_id
                result.append(doc_with_id)
            return result
    
    def remove_document(self, document_id: str) -> bool:
        """
        Remove document from registry.
        
        Args:
            document_id: Document identifier
        
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            if document_id in self._documents:
                del self._documents[document_id]
                self._save_registry()
                return True
            return False
    
    def clear_all(self):
        """Clear all documents from registry"""
        with self._lock:
            self._documents = {}
            self._save_registry()
    
    def get_sync_status(self) -> Dict:
        """
        Get synchronization status.
        
        Returns:
            Dictionary with sync status information
        """
        with self._lock:
            last_update = None
            if self._documents:
                # Find most recent update
                updates = [doc.get('updated_at') for doc in self._documents.values() if doc.get('updated_at')]
                if updates:
                    last_update = max(updates)
            
            # Get version timestamp
            version_timestamp = None
            if os.path.exists(self._version_file):
                try:
                    with open(self._version_file, 'r') as vf:
                        version_timestamp = float(vf.read().strip())
                except (ValueError, IOError):
                    pass
            
            return {
                'total_documents': len(self._documents),
                'last_update': last_update,
                'registry_path': self.registry_path,
                'registry_exists': os.path.exists(self.registry_path),
                'version_timestamp': version_timestamp
            }
    
    def check_for_conflicts(self) -> Optional[Dict]:
        """
        Check if registry was modified externally.
        
        Returns:
            Conflict info dict if conflict detected, None otherwise
        """
        if not os.path.exists(self.registry_path):
            return None
        
        # Check version file
        if os.path.exists(self._version_file):
            try:
                with open(self._version_file, 'r') as vf:
                    disk_version = float(vf.read().strip())
                
                # Get current in-memory version
                current_status = self.get_sync_status()
                memory_version = current_status.get('version_timestamp')
                
                # If disk version is newer, there's a conflict
                if memory_version and disk_version > memory_version:
                    return {
                        'conflict': True,
                        'message': 'Registry was modified externally',
                        'disk_version': disk_version,
                        'memory_version': memory_version
                    }
            except (ValueError, IOError):
                pass
        
        return None
    
    def reload_from_disk(self) -> bool:
        """
        Reload registry from disk, discarding in-memory changes.
        
        Returns:
            True if reloaded successfully
        """
        with self._lock:
            try:
                self._load_registry()
                return True
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to reload registry: {e}")
                return False

