"""
Database-backed session memory manager for ARIS agent.
Replaces the in-memory storage with persistent PostgreSQL storage.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import select, delete, update, func, and_, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql import text

from .connection import db_manager
from .models import Chat, SessionMemory
from .serialization import serialize_for_database
from ..core.memory.models import MemoryMetadata

logger = logging.getLogger(__name__)


class DatabaseSessionMemoryManager:
    """Database-backed session memory manager with PostgreSQL persistence."""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.logger = logger.getChild(f"chat.{chat_id}")
    
    async def store(
        self, 
        key: str, 
        value: Any, 
        tool_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        expires_in_hours: Optional[int] = None
    ) -> None:
        """Store a value in session memory with optional expiration."""
        
        # Serialize value to JSON using enhanced serialization
        if isinstance(value, (dict, list)):
            json_value = value
        else:
            json_value = serialize_for_database(value)
        
        # Calculate size
        size_bytes = len(json.dumps(json_value, default=str))
        
        # Calculate expiration
        expires_at = None
        if expires_in_hours:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        # Ensure tool_name is a string and within length limit
        if tool_name and not isinstance(tool_name, str):
            self.logger.warning(f"⚠️ tool_name should be string, got {type(tool_name)}: {tool_name}")
            tool_name = str(tool_name)
        
        # Truncate tool_name to fit database constraint (VARCHAR(100))
        if tool_name and len(tool_name) > 100:
            tool_name = tool_name[:97] + "..."
            self.logger.debug(f"🔧 Truncated tool_name to fit database limit: {tool_name}")
        
        # Only log large items or errors
        if size_bytes > 1000:
            self.logger.debug(f"📝 Storing large item '{key}' (size: {size_bytes} bytes)")
        
        try:
            async with db_manager.get_session() as session:
                # Ensure chat exists
                await self._ensure_chat_exists(session)
                
                # Upsert memory item
                stmt = insert(SessionMemory).values(
                    chat_id=self.chat_id,
                    memory_key=key,
                    tool_name=tool_name,
                    tags=tags or [],
                    value=json_value,
                    size_bytes=size_bytes,
                    expires_at=expires_at,
                    access_count=0,
                    last_accessed_at=datetime.utcnow()
                )
                
                # On conflict, update the existing record
                stmt = stmt.on_conflict_do_update(
                    index_elements=['chat_id', 'memory_key'],
                    set_={
                        'tool_name': stmt.excluded.tool_name,
                        'tags': stmt.excluded.tags,
                        'value': stmt.excluded.value,
                        'size_bytes': stmt.excluded.size_bytes,
                        'updated_at': func.now(),
                        'expires_at': stmt.excluded.expires_at
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
                
                # Only log successful storage for large items
                if size_bytes > 1000:
                    self.logger.info(f"📝 Stored large item '{key}' (type: {type(value).__name__}, size: {size_bytes} bytes)")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to store memory item '{key}': {str(e)}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from session memory."""
        
        self.logger.debug(f"🔍 Attempting to retrieve key '{key}' for chat_id '{self.chat_id}'")
        
        try:
            async with db_manager.get_session() as session:
                # Get memory item and update access tracking
                result = await session.execute(
                    select(SessionMemory)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.memory_key == key,
                            or_(
                                SessionMemory.expires_at.is_(None),
                                SessionMemory.expires_at > datetime.utcnow()
                            )
                        )
                    )
                )
                
                memory_item = result.scalar_one_or_none()
                if memory_item is None:
                    self.logger.debug(f"🔍 Memory item '{key}' not found or expired")
                    return None
                
                # Update access tracking
                await session.execute(
                    update(SessionMemory)
                    .where(SessionMemory.id == memory_item.id)
                    .values(
                        access_count=SessionMemory.access_count + 1,
                        last_accessed_at=datetime.utcnow()
                    )
                )
                await session.commit()
                
                # Return the stored value
                value = memory_item.value
                if isinstance(value, dict) and "data" in value and "type" in value:
                    # Handle wrapped primitive types
                    return value["data"]
                else:
                    return value
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to retrieve memory item '{key}': {str(e)}")
            raise
    
    async def delete(self, key: str) -> bool:
        """Delete a memory item."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    delete(SessionMemory)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.memory_key == key
                        )
                    )
                )
                deleted_count = result.rowcount
                await session.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"🗑️ Deleted memory item '{key}'")
                    return True
                else:
                    self.logger.debug(f"🔍 Memory item '{key}' not found for deletion")
                    return False
                    
        except Exception as e:
            self.logger.error(f"❌ Failed to delete memory item '{key}': {str(e)}")
            raise
    
    async def list_keys(self) -> List[str]:
        """List all memory keys for this chat session."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(SessionMemory.memory_key)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            or_(
                                SessionMemory.expires_at.is_(None),
                                SessionMemory.expires_at > datetime.utcnow()
                            )
                        )
                    )
                    .order_by(SessionMemory.created_at.desc())
                )
                
                keys = [row[0] for row in result.fetchall()]
                self.logger.debug(f"🔍 Found {len(keys)} memory keys")
                return keys
                
        except Exception as e:
            self.logger.error(f"❌ Failed to list memory keys: {str(e)}")
            raise
    
    async def search_by_tool(self, tool_name: str) -> List[str]:
        """Search memory items by tool name."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(SessionMemory.memory_key)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.tool_name == tool_name,
                            or_(
                                SessionMemory.expires_at.is_(None),
                                SessionMemory.expires_at > datetime.utcnow()
                            )
                        )
                    )
                    .order_by(SessionMemory.created_at.desc())
                )
                
                keys = [row[0] for row in result.fetchall()]
                self.logger.debug(f"🔍 Found {len(keys)} memory items for tool '{tool_name}'")
                return keys
                
        except Exception as e:
            self.logger.error(f"❌ Failed to search by tool '{tool_name}': {str(e)}")
            raise
    
    async def search_by_tag(self, tag: str) -> List[str]:
        """Search memory items by tag."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(SessionMemory.memory_key)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.tags.op('@>')([tag]),
                            or_(
                                SessionMemory.expires_at.is_(None),
                                SessionMemory.expires_at > datetime.utcnow()
                            )
                        )
                    )
                    .order_by(SessionMemory.created_at.desc())
                )
                
                keys = [row[0] for row in result.fetchall()]
                self.logger.debug(f"🔍 Found {len(keys)} memory items with tag '{tag}'")
                return keys
                
        except Exception as e:
            self.logger.error(f"❌ Failed to search by tag '{tag}': {str(e)}")
            raise
    
    async def get_metadata(self, key: str) -> Optional[MemoryMetadata]:
        """Get metadata for a memory item."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(SessionMemory)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.memory_key == key
                        )
                    )
                )
                
                memory_item = result.scalar_one_or_none()
                if memory_item is None:
                    return None
                
                # Create metadata object
                metadata = MemoryMetadata(
                    tool_name=memory_item.tool_name,
                    tags=memory_item.tags or [],
                    created_at=memory_item.created_at,
                    size_bytes=memory_item.size_bytes,
                    access_count=memory_item.access_count,
                    last_accessed=memory_item.last_accessed_at  # Map database field to model field
                )
                
                return metadata
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get metadata for '{key}': {str(e)}")
            raise
    
    async def cleanup_expired(self) -> int:
        """Remove expired memory items and return count of deleted items."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    delete(SessionMemory)
                    .where(
                        and_(
                            SessionMemory.chat_id == self.chat_id,
                            SessionMemory.expires_at < datetime.utcnow()
                        )
                    )
                )
                deleted_count = result.rowcount
                await session.commit()
                
                if deleted_count > 0:
                    self.logger.info(f"🧹 Cleaned up {deleted_count} expired memory items")
                
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup expired items: {str(e)}")
            raise
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics for this chat session."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(text("""
                    SELECT 
                        COUNT(*) as total_items,
                        COUNT(CASE WHEN expires_at IS NULL THEN 1 END) as permanent_items,
                        COUNT(CASE WHEN expires_at > NOW() THEN 1 END) as active_temp_items,
                        COUNT(CASE WHEN expires_at <= NOW() THEN 1 END) as expired_items,
                        SUM(size_bytes) as total_size_bytes,
                        AVG(size_bytes) as avg_size_bytes,
                        COUNT(DISTINCT tool_name) as unique_tools,
                        SUM(access_count) as total_accesses
                    FROM session_memory 
                    WHERE chat_id = :chat_id
                """), {"chat_id": self.chat_id})
                
                stats = result.fetchone()
                
                return {
                    "total_items": stats[0],
                    "permanent_items": stats[1],
                    "active_temp_items": stats[2],
                    "expired_items": stats[3],
                    "total_size_bytes": stats[4] or 0,
                    "avg_size_bytes": round(stats[5] or 0, 2),
                    "unique_tools": stats[6],
                    "total_accesses": stats[7] or 0
                }
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get memory stats: {str(e)}")
            raise
    
    async def handle_tool_result(
        self, 
        action_id: str, 
        tool_name: str, 
        result: Dict[str, Any],
        action_name: str = "unknown"
    ) -> None:
        """Handle tool result storage (compatibility method for executioner)."""
        # Ensure tool_name is a string and within length limit
        if not isinstance(tool_name, str):
            self.logger.warning(f"⚠️ tool_name should be string, got {type(tool_name)}: {tool_name}")
            tool_name = str(tool_name)
        
        # Truncate tool_name to fit database constraint (VARCHAR(100))
        if len(tool_name) > 100:
            tool_name = tool_name[:97] + "..."
            self.logger.debug(f"🔧 Truncated tool_name to fit database limit: {tool_name}")
        
        await self.store(
            key=f"tool_result_{action_id}",
            value=result,
            tool_name=tool_name,
            tags=["tool_result", tool_name]
        )
        self.logger.info(f"📝 Handled tool result for {tool_name} (action: {action_name})")

    async def _ensure_chat_exists(self, session) -> None:
        """Ensure the chat record exists in the database."""
        
        # Check if chat exists
        result = await session.execute(
            select(Chat.id).where(Chat.id == self.chat_id)
        )
        
        if result.scalar_one_or_none() is None:
            # Create chat record
            chat = Chat(
                id=self.chat_id,
                user_id="unknown",  # Will be updated when we have user info
                agent_type="manufacturing",
                status="active"
            )
            session.add(chat)
            await session.flush()  # Ensure chat is created before memory items
            self.logger.info(f"📝 Created new chat record: {self.chat_id}")
    
    async def update_chat_info(
        self, 
        user_id: str, 
        agent_type: str = "manufacturing",
        model_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update chat information."""
        
        try:
            async with db_manager.get_session() as session:
                await session.execute(
                    update(Chat)
                    .where(Chat.id == self.chat_id)
                    .values(
                        user_id=user_id,
                        agent_type=agent_type,
                        model_id=model_id,
                        extra_data=metadata or {},
                        last_activity_at=datetime.utcnow()
                    )
                )
                await session.commit()
                
                self.logger.info(f"📝 Updated chat info: user={user_id}, agent={agent_type}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to update chat info: {str(e)}")
            raise
