"""Storage backends for memory management."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import asyncio
from pathlib import Path

from .models import MemoryItem, MemoryMetadata, calculate_size


class StorageBackend(ABC):
    """Abstract base class for memory storage backends."""
    
    @abstractmethod
    async def set(self, key: str, item: MemoryItem) -> None:
        """Store an item."""
        pass
    
    @abstractmethod
    async def get(self, key: str) -> Optional[MemoryItem]:
        """Retrieve an item by key."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an item. Returns True if item existed."""
        pass
    
    @abstractmethod
    async def clear(self) -> int:
        """Clear all items. Returns number of items cleared."""
        pass
    
    @abstractmethod
    async def list_keys(self) -> List[str]:
        """List all stored keys."""
        pass
    
    @abstractmethod
    async def get_all(self) -> Dict[str, MemoryItem]:
        """Get all stored items."""
        pass


class InMemoryStorage(StorageBackend):
    """In-memory storage backend (default)."""
    
    def __init__(self):
        self._storage: Dict[str, MemoryItem] = {}
        self._lock = asyncio.Lock()
    
    async def set(self, key: str, item: MemoryItem) -> None:
        """Store an item in memory."""
        async with self._lock:
            self._storage[key] = item
    
    async def get(self, key: str) -> Optional[MemoryItem]:
        """Retrieve an item from memory."""
        async with self._lock:
            item = self._storage.get(key)
            if item:
                # Update access metadata
                item.metadata.accessed_count += 1
                item.metadata.last_accessed = datetime.now()
            return item
    
    async def delete(self, key: str) -> bool:
        """Delete an item from memory."""
        async with self._lock:
            if key in self._storage:
                del self._storage[key]
                return True
            return False
    
    async def clear(self) -> int:
        """Clear all items from memory."""
        async with self._lock:
            count = len(self._storage)
            self._storage.clear()
            return count
    
    async def list_keys(self) -> List[str]:
        """List all keys in memory."""
        async with self._lock:
            return list(self._storage.keys())
    
    async def get_all(self) -> Dict[str, MemoryItem]:
        """Get all items from memory."""
        async with self._lock:
            return self._storage.copy()


class FileStorage(StorageBackend):
    """File-based storage backend for persistence."""
    
    def __init__(self, storage_dir: str = "/tmp/agent_memory"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
    
    def _get_file_path(self, key: str) -> Path:
        """Get file path for a key."""
        # Sanitize key for filesystem
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.storage_dir / f"{safe_key}.json"
    
    async def set(self, key: str, item: MemoryItem) -> None:
        """Store an item to file."""
        async with self._lock:
            file_path = self._get_file_path(key)
            data = {
                "key": item.key,
                "value": item.value,
                "metadata": item.metadata.to_dict()
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(data, f, default=str, indent=2)
    
    async def get(self, key: str) -> Optional[MemoryItem]:
        """Retrieve an item from file."""
        async with self._lock:
            file_path = self._get_file_path(key)
            if not file_path.exists():
                return None
            
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct metadata
                metadata_dict = data["metadata"]
                metadata = MemoryMetadata(
                    created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                    tool_name=metadata_dict.get("tool_name"),
                    data_type=metadata_dict.get("data_type"),
                    size_bytes=metadata_dict.get("size_bytes", 0),
                    accessed_count=metadata_dict.get("accessed_count", 0) + 1,
                    last_accessed=datetime.now(),
                    tags=metadata_dict.get("tags", [])
                )
                
                # Update access count in file
                data["metadata"]["accessed_count"] = metadata.accessed_count
                data["metadata"]["last_accessed"] = metadata.last_accessed.isoformat()
                with open(file_path, 'w') as f:
                    json.dump(data, f, default=str, indent=2)
                
                return MemoryItem(
                    key=data["key"],
                    value=data["value"],
                    metadata=metadata
                )
            except Exception:
                return None
    
    async def delete(self, key: str) -> bool:
        """Delete an item from file storage."""
        async with self._lock:
            file_path = self._get_file_path(key)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
    
    async def clear(self) -> int:
        """Clear all items from file storage."""
        async with self._lock:
            count = 0
            for file_path in self.storage_dir.glob("*.json"):
                file_path.unlink()
                count += 1
            return count
    
    async def list_keys(self) -> List[str]:
        """List all keys in file storage."""
        async with self._lock:
            keys = []
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        keys.append(data["key"])
                except:
                    continue
            return keys
    
    async def get_all(self) -> Dict[str, MemoryItem]:
        """Get all items from file storage."""
        items = {}
        keys = await self.list_keys()
        for key in keys:
            item = await self.get(key)
            if item:
                items[key] = item
        return items
