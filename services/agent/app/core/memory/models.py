"""Data models for memory management."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, List
import json


@dataclass
class MemoryMetadata:
    """Metadata associated with a stored memory item."""
    
    created_at: datetime
    tool_name: Optional[str] = None
    data_type: Optional[str] = None
    size_bytes: int = 0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            "created_at": self.created_at.isoformat(),
            "tool_name": self.tool_name,
            "data_type": self.data_type,
            "size_bytes": self.size_bytes,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "tags": self.tags
        }


@dataclass
class MemoryItem:
    """A single item stored in memory."""
    
    key: str
    value: Any
    metadata: MemoryMetadata
    
    def get_preview(self, max_length: int = 100) -> str:
        """Get a preview of the stored value."""
        value_str = str(self.value)
        if len(value_str) > max_length:
            return value_str[:max_length] + "..."
        return value_str
    
    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "key": self.key,
            "preview": self.get_preview(),
            "metadata": self.metadata.to_dict()
        }
        if include_value:
            result["value"] = self.value
        return result


@dataclass
class MemoryStats:
    """Statistics about memory usage."""
    
    total_items: int = 0
    total_size_bytes: int = 0
    items_by_type: Dict[str, int] = field(default_factory=dict)
    items_by_tool: Dict[str, int] = field(default_factory=dict)
    oldest_item: Optional[datetime] = None
    newest_item: Optional[datetime] = None
    most_accessed_keys: List[tuple[str, int]] = field(default_factory=list)
    
    @property
    def total_size_mb(self) -> float:
        """Get total size in megabytes."""
        return round(self.total_size_bytes / (1024 * 1024), 2)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total_items": self.total_items,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": self.total_size_mb,
            "items_by_type": self.items_by_type,
            "items_by_tool": self.items_by_tool,
            "oldest_item": self.oldest_item.isoformat() if self.oldest_item else None,
            "newest_item": self.newest_item.isoformat() if self.newest_item else None,
            "most_accessed_keys": [
                {"key": k, "access_count": c} for k, c in self.most_accessed_keys
            ]
        }


def calculate_size(obj: Any) -> int:
    """Calculate approximate size of an object in bytes."""
    try:
        # Try to serialize to JSON to get size
        json_str = json.dumps(obj, default=str)
        return len(json_str.encode('utf-8'))
    except:
        # Fallback to string representation
        return len(str(obj).encode('utf-8'))
