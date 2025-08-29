"""Session memory manager for AI agents."""

import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import asyncio

from .models import MemoryItem, MemoryMetadata, MemoryStats, calculate_size
from .storage import StorageBackend, InMemoryStorage


class SessionMemoryManager:
    """
    Manages session memory for AI agents.
    
    This is NOT exposed as tools to the LLM. Instead, it's used internally
    by the agent to store and retrieve data during tool execution.
    """
    
    def __init__(
        self, 
        storage_backend: Optional[StorageBackend] = None,
        auto_store_results: bool = True,
        max_size_mb: float = 100.0
    ):
        """
        Initialize the memory manager.
        
        Args:
            storage_backend: Storage backend to use (defaults to InMemoryStorage)
            auto_store_results: Automatically store tool results when result_variable_name is provided
            max_size_mb: Maximum memory size in MB (soft limit)
        """
        self.storage = storage_backend or InMemoryStorage()
        self.auto_store_results = auto_store_results
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.logger = logging.getLogger("core.memory")
        
        # Callbacks for memory events
        self._on_store_callbacks: List[Callable] = []
        self._on_retrieve_callbacks: List[Callable] = []
    
    async def store(
        self,
        key: str,
        value: Any,
        tool_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        overwrite: bool = True
    ) -> bool:
        """
        Store a value in memory.
        
        Args:
            key: Unique identifier for the value
            value: The value to store
            tool_name: Name of the tool that generated this value
            tags: Optional tags for categorization
            overwrite: Whether to overwrite existing values
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            # Check if key exists and overwrite is False
            if not overwrite:
                existing = await self.storage.get(key)
                if existing:
                    self.logger.warning(f"Key '{key}' already exists and overwrite=False")
                    return False
            
            # Calculate size
            size_bytes = calculate_size(value)
            
            # Check size limit (soft limit - warn but allow)
            current_stats = await self.get_stats()
            if current_stats.total_size_bytes + size_bytes > self.max_size_bytes:
                self.logger.warning(
                    f"Memory size limit exceeded: {current_stats.total_size_mb:.2f}MB + "
                    f"{size_bytes/1024/1024:.2f}MB > {self.max_size_bytes/1024/1024:.2f}MB"
                )
            
            # Create metadata
            metadata = MemoryMetadata(
                created_at=datetime.now(),
                tool_name=tool_name,
                data_type=type(value).__name__,
                size_bytes=size_bytes,
                tags=tags or []
            )
            
            # Create memory item
            item = MemoryItem(key=key, value=value, metadata=metadata)
            
            # Store in backend
            await self.storage.set(key, item)
            
            self.logger.info(
                f"📝 Stored '{key}' from tool '{tool_name}' "
                f"(type: {metadata.data_type}, size: {size_bytes} bytes)"
            )
            
            # Trigger callbacks
            for callback in self._on_store_callbacks:
                try:
                    await callback(key, value, metadata)
                except Exception as e:
                    self.logger.error(f"Error in store callback: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to store '{key}': {str(e)}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from memory.
        
        Args:
            key: The key to retrieve
            default: Default value if key not found
            
        Returns:
            The stored value or default
        """
        try:
            item = await self.storage.get(key)
            if item:
                self.logger.debug(f"📖 Retrieved '{key}' (access #{item.metadata.accessed_count})")
                
                # Trigger callbacks
                for callback in self._on_retrieve_callbacks:
                    try:
                        await callback(key, item.value, item.metadata)
                    except Exception as e:
                        self.logger.error(f"Error in retrieve callback: {e}")
                
                return item.value
            return default
            
        except Exception as e:
            self.logger.error(f"Failed to retrieve '{key}': {str(e)}")
            return default
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in memory."""
        item = await self.storage.get(key)
        return item is not None
    
    async def delete(self, keys: List[str]) -> Dict[str, bool]:
        """
        Delete specific keys from memory.
        
        Args:
            keys: List of keys to delete
            
        Returns:
            Dictionary mapping keys to deletion success
        """
        results = {}
        for key in keys:
            try:
                success = await self.storage.delete(key)
                results[key] = success
                if success:
                    self.logger.info(f"🗑️ Deleted '{key}' from memory")
                else:
                    self.logger.warning(f"Key '{key}' not found for deletion")
            except Exception as e:
                self.logger.error(f"Failed to delete '{key}': {str(e)}")
                results[key] = False
        return results
    
    async def clear(self) -> int:
        """
        Clear all memory.
        
        Returns:
            Number of items cleared
        """
        try:
            count = await self.storage.clear()
            self.logger.info(f"🧹 Cleared {count} items from memory")
            return count
        except Exception as e:
            self.logger.error(f"Failed to clear memory: {str(e)}")
            return 0
    
    async def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        List all keys in memory.
        
        Args:
            pattern: Optional pattern to filter keys (simple substring match)
            
        Returns:
            List of keys
        """
        keys = await self.storage.list_keys()
        
        if pattern:
            keys = [k for k in keys if pattern in k]
        
        return sorted(keys)
    
    async def get_items(self, include_values: bool = False) -> List[Dict[str, Any]]:
        """
        Get all items with metadata.
        
        Args:
            include_values: Whether to include actual values (can be large)
            
        Returns:
            List of item dictionaries
        """
        items = await self.storage.get_all()
        return [item.to_dict(include_value=include_values) for item in items.values()]
    
    async def get_stats(self) -> MemoryStats:
        """
        Get memory usage statistics.
        
        Returns:
            MemoryStats object with usage information
        """
        items = await self.storage.get_all()
        
        stats = MemoryStats()
        stats.total_items = len(items)
        
        for item in items.values():
            stats.total_size_bytes += item.metadata.size_bytes
            
            # Track by type
            data_type = item.metadata.data_type or "unknown"
            stats.items_by_type[data_type] = stats.items_by_type.get(data_type, 0) + 1
            
            # Track by tool
            if item.metadata.tool_name:
                stats.items_by_tool[item.metadata.tool_name] = \
                    stats.items_by_tool.get(item.metadata.tool_name, 0) + 1
            
            # Track dates
            if not stats.oldest_item or item.metadata.created_at < stats.oldest_item:
                stats.oldest_item = item.metadata.created_at
            if not stats.newest_item or item.metadata.created_at > stats.newest_item:
                stats.newest_item = item.metadata.created_at
        
        # Find most accessed keys
        if items:
            sorted_items = sorted(
                items.values(),
                key=lambda x: x.metadata.accessed_count,
                reverse=True
            )[:5]
            stats.most_accessed_keys = [
                (item.key, item.metadata.accessed_count) for item in sorted_items
            ]
        
        return stats
    
    async def search_by_tag(self, tag: str) -> List[str]:
        """
        Search for items by tag.
        
        Args:
            tag: Tag to search for
            
        Returns:
            List of keys that have the specified tag
        """
        items = await self.storage.get_all()
        matching_keys = []
        
        for key, item in items.items():
            if tag in item.metadata.tags:
                matching_keys.append(key)
        
        return matching_keys
    
    async def search_by_tool(self, tool_name: str) -> List[str]:
        """
        Search for items created by a specific tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            List of keys created by the specified tool
        """
        items = await self.storage.get_all()
        matching_keys = []
        
        for key, item in items.items():
            if item.metadata.tool_name == tool_name:
                matching_keys.append(key)
        
        return matching_keys
    
    def add_store_callback(self, callback: Callable) -> None:
        """Add a callback to be called when items are stored."""
        self._on_store_callbacks.append(callback)
    
    def add_retrieve_callback(self, callback: Callable) -> None:
        """Add a callback to be called when items are retrieved."""
        self._on_retrieve_callbacks.append(callback)
    
    async def handle_tool_result(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any
    ) -> Any:
        """
        Handle tool execution result with automatic storage.
        
        This method should be called by the tool executor after successful
        tool execution. It checks for 'result_variable_name' in arguments
        and automatically stores the result if present.
        
        Args:
            tool_name: Name of the executed tool
            arguments: Tool arguments (may contain 'result_variable_name')
            result: Tool execution result
            
        Returns:
            The original result (unchanged)
        """
        # Check if we should auto-store the result
        if self.auto_store_results and not isinstance(result, dict) or "error" not in result:
            variable_name = arguments.get("result_variable_name")
            if variable_name:
                # Auto-store the result
                await self.store(
                    key=variable_name,
                    value=result,
                    tool_name=tool_name,
                    tags=["auto_stored", "tool_result"]
                )
                self.logger.info(
                    f"🔄 Auto-stored tool result as '{variable_name}' from {tool_name}"
                )
        
        return result
    
    def get_summary(self) -> str:
        """
        Get a human-readable summary of memory contents.
        
        Returns:
            Formatted string summary
        """
        # This is synchronous for convenience in logging
        loop = asyncio.get_event_loop()
        stats = loop.run_until_complete(self.get_stats())
        items = loop.run_until_complete(self.get_items())
        
        lines = [
            "📊 Memory Summary:",
            f"  Total items: {stats.total_items}",
            f"  Total size: {stats.total_size_mb:.2f} MB",
            f"  Types: {', '.join(f'{k}({v})' for k, v in stats.items_by_type.items())}",
        ]
        
        if items:
            lines.append("  Stored variables:")
            for item in items[:10]:  # Show first 10
                lines.append(f"    • {item['key']}: {item['preview']}")
            if len(items) > 10:
                lines.append(f"    ... and {len(items) - 10} more")
        
        return "\n".join(lines)
