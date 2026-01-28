"""
Synchronization Manager for Microservices
Ensures all services stay in sync with shared state (document registry, index map, etc.)
Provides AUTOMATIC synchronization without manual intervention.
"""
import os
import time
import json
import asyncio
import threading
import logging
from typing import Dict, Optional, List, Callable, Any
from pathlib import Path
from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from scripts.setup_logging import get_logger

logger = get_logger("aris_rag.sync_manager")


class SyncManager:
    """
    Manages automatic synchronization across microservices.
    
    Features:
    - Automatic periodic sync in background
    - File change detection via mtime
    - Cross-service sync coordination
    - Sync hooks for operations
    """
    
    _instances: Dict[str, 'SyncManager'] = {}
    _lock = threading.Lock()
    
    def __new__(cls, service_name: str = "default"):
        """Singleton per service to avoid multiple sync tasks."""
        with cls._lock:
            if service_name not in cls._instances:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instances[service_name] = instance
            return cls._instances[service_name]
    
    def __init__(self, service_name: str = "default"):
        if self._initialized:
            return
            
        self.service_name = service_name
        self.registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        self.index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        
        # Initialize registry
        try:
            self.document_registry = DocumentRegistry(self.registry_path)
        except Exception as e:
            logger.warning(f"Could not initialize registry: {e}")
            self.document_registry = None
        
        # File modification tracking
        self._index_map_mtime = 0
        self._registry_mtime = 0
        self._last_sync_time = 0
        self._sync_interval = 30.0  # Check for changes every 30 seconds (reduced from 3s for performance)
        
        # Background sync task control
        self._background_task: Optional[asyncio.Task] = None
        self._stop_event = threading.Event()
        self._sync_callbacks: List[Callable] = []
        
        # Cached data
        self._cached_index_map: Optional[Dict[str, str]] = None
        self._cached_registry_data: Optional[Dict] = None
        
        # Stats
        self._sync_count = 0
        self._last_sync_result: Optional[Dict] = None
        
        self._initialized = True
        logger.info(f"✅ SyncManager initialized for service: {service_name}")
    
    def register_sync_callback(self, callback: Callable):
        """Register a callback to be called after each sync."""
        if callback not in self._sync_callbacks:
            self._sync_callbacks.append(callback)
            logger.info(f"Registered sync callback: {callback.__name__}")
    
    def unregister_sync_callback(self, callback: Callable):
        """Unregister a sync callback."""
        if callback in self._sync_callbacks:
            self._sync_callbacks.remove(callback)
    
    def _notify_callbacks(self, sync_result: Dict):
        """Notify all registered callbacks of a sync event."""
        for callback in self._sync_callbacks:
            try:
                callback(sync_result)
            except Exception as e:
                logger.warning(f"Sync callback {callback.__name__} failed: {e}")
    
    def sync_document_registry(self, force: bool = False) -> bool:
        """
        Sync document registry from disk/S3.
        
        Args:
            force: If True, reload even if file hasn't changed
            
        Returns:
            True if registry was reloaded, False otherwise
        """
        try:
            if os.path.exists(self.registry_path):
                current_mtime = os.path.getmtime(self.registry_path)
                if force or current_mtime > self._registry_mtime:
                    # Reload registry
                    self.document_registry = DocumentRegistry(self.registry_path)
                    self._registry_mtime = current_mtime
                    
                    # Update cache
                    try:
                        with open(self.registry_path, 'r') as f:
                            self._cached_registry_data = json.load(f)
                    except:
                        pass
                    
                    doc_count = len(self.document_registry.list_documents()) if self.document_registry else 0
                    logger.info(f"✅ [{self.service_name}] Synced document registry ({doc_count} documents)")
                    return True
            else:
                # Create empty registry if doesn't exist
                os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
                with open(self.registry_path, 'w') as f:
                    json.dump({}, f)
                self._registry_mtime = os.path.getmtime(self.registry_path)
                logger.info(f"✅ [{self.service_name}] Created empty document registry")
            return False
        except Exception as e:
            logger.warning(f"[{self.service_name}] Could not sync document registry: {e}")
            return False
    
    def sync_index_map(self, force: bool = False) -> Optional[Dict[str, str]]:
        """
        Sync document index map from disk.
        
        Args:
            force: If True, reload even if file hasn't changed
            
        Returns:
            Updated index map dict, or None if no changes
        """
        try:
            if os.path.exists(self.index_map_path):
                current_mtime = os.path.getmtime(self.index_map_path)
                if force or current_mtime > self._index_map_mtime:
                    with open(self.index_map_path, 'r') as f:
                        index_map = json.load(f)
                    self._index_map_mtime = current_mtime
                    self._cached_index_map = index_map
                    logger.info(f"✅ [{self.service_name}] Synced index map ({len(index_map)} mappings)")
                    return index_map
            else:
                # Create empty index map if doesn't exist
                os.makedirs(os.path.dirname(self.index_map_path), exist_ok=True)
                with open(self.index_map_path, 'w') as f:
                    json.dump({}, f)
                self._index_map_mtime = os.path.getmtime(self.index_map_path)
                self._cached_index_map = {}
                logger.info(f"✅ [{self.service_name}] Created empty index map")
                return {}
            return None
        except Exception as e:
            logger.warning(f"[{self.service_name}] Could not sync index map: {e}")
            return None
    
    def check_and_sync(self) -> Dict[str, Any]:
        """
        Check for changes and sync if needed.
        
        Returns:
            Dict with sync status for each component
        """
        now = time.time()
        
        # Only check periodically to avoid excessive I/O
        if now - self._last_sync_time < self._sync_interval:
            return {"registry": False, "index_map": False, "skipped": True}
        
        self._last_sync_time = now
        
        registry_synced = self.sync_document_registry()
        index_map_result = self.sync_index_map()
        index_map_synced = index_map_result is not None
        
        result = {
            "registry": registry_synced,
            "index_map": index_map_synced,
            "timestamp": now,
            "service": self.service_name
        }
        
        if registry_synced or index_map_synced:
            self._sync_count += 1
            self._last_sync_result = result
            self._notify_callbacks(result)
        
        return result
    
    def force_full_sync(self) -> Dict[str, Any]:
        """
        Force a full synchronization of all shared state.
        
        Returns:
            Dict with sync results
        """
        logger.info(f"🔄 [{self.service_name}] Forcing full synchronization...")
        
        registry_synced = self.sync_document_registry(force=True)
        index_map = self.sync_index_map(force=True)
        
        doc_count = 0
        if self.document_registry:
            try:
                doc_count = len(self.document_registry.list_documents())
            except:
                pass
        
        result = {
            "registry": {
                "synced": registry_synced,
                "document_count": doc_count
            },
            "index_map": {
                "synced": index_map is not None,
                "mapping_count": len(index_map) if index_map else 0
            },
            "timestamp": time.time(),
            "service": self.service_name,
            "sync_count": self._sync_count
        }
        
        self._sync_count += 1
        self._last_sync_result = result
        self._notify_callbacks(result)
        
        logger.info(f"✅ [{self.service_name}] Full sync complete: {doc_count} docs, {len(index_map) if index_map else 0} mappings")
        return result
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current synchronization status.
        
        Returns:
            Dict with sync status information
        """
        registry_exists = os.path.exists(self.registry_path)
        index_map_exists = os.path.exists(self.index_map_path)
        
        registry_mtime = os.path.getmtime(self.registry_path) if registry_exists else 0
        index_map_mtime = os.path.getmtime(self.index_map_path) if index_map_exists else 0
        
        doc_count = 0
        if registry_exists and self.document_registry:
            try:
                doc_count = len(self.document_registry.list_documents())
            except:
                pass
        
        index_map_count = 0
        if index_map_exists:
            try:
                if self._cached_index_map:
                    index_map_count = len(self._cached_index_map)
                else:
                    with open(self.index_map_path, 'r') as f:
                        index_map_count = len(json.load(f))
            except:
                pass
        
        return {
            "service": self.service_name,
            "registry": {
                "exists": registry_exists,
                "last_modified": registry_mtime,
                "document_count": doc_count,
                "in_sync": self._registry_mtime >= registry_mtime
            },
            "index_map": {
                "exists": index_map_exists,
                "last_modified": index_map_mtime,
                "mapping_count": index_map_count,
                "in_sync": self._index_map_mtime >= index_map_mtime
            },
            "last_sync": self._last_sync_time,
            "sync_count": self._sync_count,
            "sync_interval": self._sync_interval,
            "background_task_running": self._background_task is not None and not self._background_task.done()
        }
    
    def get_cached_index_map(self) -> Dict[str, str]:
        """Get cached index map without disk I/O."""
        if self._cached_index_map is None:
            self.sync_index_map(force=True)
        return self._cached_index_map or {}
    
    def get_cached_registry(self) -> Dict:
        """Get cached registry data without disk I/O."""
        if self._cached_registry_data is None:
            self.sync_document_registry(force=True)
        return self._cached_registry_data or {}
    
    async def _background_sync_loop(self):
        """Background task that periodically syncs state."""
        logger.info(f"🔄 [{self.service_name}] Starting background sync loop (interval: {self._sync_interval}s)")
        
        while not self._stop_event.is_set():
            try:
                # Check and sync
                result = self.check_and_sync()
                
                if result.get("registry") or result.get("index_map"):
                    logger.debug(f"[{self.service_name}] Background sync detected changes: {result}")
                
            except Exception as e:
                logger.warning(f"[{self.service_name}] Background sync error: {e}")
            
            # Sleep with interrupt check
            await asyncio.sleep(self._sync_interval)
        
        logger.info(f"🛑 [{self.service_name}] Background sync loop stopped")
    
    def start_background_sync(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        """Start the background sync task."""
        if self._background_task is not None and not self._background_task.done():
            logger.info(f"[{self.service_name}] Background sync already running")
            return
        
        self._stop_event.clear()
        
        try:
            if loop is None:
                loop = asyncio.get_event_loop()
            
            self._background_task = loop.create_task(self._background_sync_loop())
            logger.info(f"✅ [{self.service_name}] Background sync task started")
        except RuntimeError:
            # No event loop running, use threading
            logger.info(f"[{self.service_name}] No asyncio loop, using threaded sync")
            self._start_threaded_sync()
    
    def _start_threaded_sync(self):
        """Start sync using threading for non-async contexts."""
        def sync_thread():
            while not self._stop_event.is_set():
                try:
                    self.check_and_sync()
                except Exception as e:
                    logger.warning(f"[{self.service_name}] Threaded sync error: {e}")
                self._stop_event.wait(self._sync_interval)
        
        thread = threading.Thread(target=sync_thread, daemon=True)
        thread.start()
        logger.info(f"✅ [{self.service_name}] Threaded sync started")
    
    def stop_background_sync(self):
        """Stop the background sync task."""
        self._stop_event.set()
        if self._background_task is not None:
            self._background_task.cancel()
            self._background_task = None
        logger.info(f"🛑 [{self.service_name}] Background sync stopped")
    
    def update_index_map(self, document_name: str, index_name: str) -> bool:
        """
        Update index map with a new mapping and save to disk.
        
        Args:
            document_name: Document name
            index_name: Index name
            
        Returns:
            True if successful
        """
        try:
            # Load current map
            current_map = self.get_cached_index_map()
            current_map[document_name] = index_name
            
            # Save
            os.makedirs(os.path.dirname(self.index_map_path), exist_ok=True)
            with open(self.index_map_path, 'w') as f:
                json.dump(current_map, f, indent=2)
            
            # Update cache and mtime
            self._cached_index_map = current_map
            self._index_map_mtime = os.path.getmtime(self.index_map_path)
            
            logger.info(f"✅ [{self.service_name}] Updated index map: {document_name} -> {index_name}")
            return True
        except Exception as e:
            logger.error(f"[{self.service_name}] Failed to update index map: {e}")
            return False
    
    def remove_from_index_map(self, document_name: str) -> bool:
        """
        Remove a document from the index map.
        
        Args:
            document_name: Document name to remove
            
        Returns:
            True if successful
        """
        try:
            current_map = self.get_cached_index_map()
            if document_name in current_map:
                del current_map[document_name]
                
                with open(self.index_map_path, 'w') as f:
                    json.dump(current_map, f, indent=2)
                
                self._cached_index_map = current_map
                self._index_map_mtime = os.path.getmtime(self.index_map_path)
                
                logger.info(f"✅ [{self.service_name}] Removed from index map: {document_name}")
                return True
            return False
        except Exception as e:
            logger.error(f"[{self.service_name}] Failed to remove from index map: {e}")
            return False


# Global function to get sync manager instance
def get_sync_manager(service_name: str = "default") -> SyncManager:
    """Get or create a SyncManager instance for a service."""
    return SyncManager(service_name)


# Async context manager for automatic sync
class AutoSyncContext:
    """Context manager that ensures sync before and after operations."""
    
    def __init__(self, sync_manager: SyncManager, operation: str = "operation"):
        self.sync_manager = sync_manager
        self.operation = operation
    
    async def __aenter__(self):
        # Sync before operation
        self.sync_manager.check_and_sync()
        logger.debug(f"[{self.sync_manager.service_name}] Pre-{self.operation} sync completed")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Force sync after operation
        self.sync_manager.force_full_sync()
        logger.debug(f"[{self.sync_manager.service_name}] Post-{self.operation} sync completed")
        return False
