"""
Database models for ARIS agent persistent storage.
Uses SQLAlchemy with async support for PostgreSQL.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, Numeric,
    ForeignKey, Index, CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import text

Base = declarative_base()


class Chat(Base):
    """Core chat sessions with user information and metadata."""
    
    __tablename__ = 'chats'
    
    id = Column(String(50), primary_key=True)  # e.g., "1758852782787-xig8s"
    user_id = Column(String(100), nullable=False)  # "Nemanja"
    agent_type = Column(String(50), default='manufacturing')
    model_id = Column(String(100))  # "us.anthropic.claude-3-7-sonnet..."
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    last_activity_at = Column(DateTime(timezone=True), default=func.now())
    status = Column(String(20), default='active')  # active, archived, expired
    extra_data = Column(JSONB, default={})  # Additional session data
    
    # Relationships
    plans = relationship("Plan", back_populates="chat", cascade="all, delete-orphan")
    memory_items = relationship("SessionMemory", back_populates="chat", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived', 'expired')", name='chk_chats_status'),
        Index('idx_chats_user_activity', 'user_id', 'last_activity_at'),
        Index('idx_chats_status', 'status', postgresql_where=text("status = 'active'")),
    )


class Plan(Base):
    """Execution plans representing user requests within chats."""
    
    __tablename__ = 'plans'
    
    id = Column(String(50), primary_key=True)  # UUID from agent
    chat_id = Column(String(50), ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    summary = Column(Text, nullable=False)  # Plan description
    status = Column(String(20), nullable=False)  # new, in_progress, completed, failed
    user_query = Column(Text, nullable=False)  # Original user question
    model_id = Column(String(100))  # Model used for this plan
    temperature = Column(Numeric(3,2))  # LLM temperature setting
    total_actions = Column(Integer, default=0)  # Count of actions in plan
    completed_actions = Column(Integer, default=0)  # Count of completed actions
    failed_actions = Column(Integer, default=0)  # Count of failed actions
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    execution_duration_ms = Column(Integer)  # Total execution time
    extra_data = Column(JSONB, default={})  # Additional plan data
    
    # Relationships
    chat = relationship("Chat", back_populates="plans")
    actions = relationship("Action", back_populates="plan", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('new', 'in_progress', 'completed', 'failed', 'cancelled')", name='chk_plans_status'),
        Index('idx_plans_chat_created', 'chat_id', 'created_at'),
        Index('idx_plans_status', 'status'),
        Index('idx_plans_user_query_fts_english', text("to_tsvector('english', user_query)"), postgresql_using='gin'),
    )


class Action(Base):
    """Individual actions/steps within execution plans."""
    
    __tablename__ = 'actions'
    
    id = Column(String(50), primary_key=True)  # UUID from plan
    plan_id = Column(String(50), ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)  # "Create PDF with ARIS description"
    description = Column(Text)  # Detailed description
    type = Column(String(20), nullable=False)  # tool_call, analysis, response, clarification
    tool_name = Column(String(100))  # create_pdf, search_memory, etc.
    arguments = Column(JSONB)  # Tool arguments
    depends_on = Column(JSONB, default=[])  # Array of dependency action IDs
    status = Column(String(20), nullable=False, default='pending')  # pending, starting, in_progress, completed, failed
    result = Column(JSONB)  # Tool execution result
    error_message = Column(Text)  # If failed
    execution_order = Column(Integer)  # Order of execution within plan
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    execution_duration_ms = Column(Integer)  # Action execution time
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    plan = relationship("Plan", back_populates="actions")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'starting', 'in_progress', 'completed', 'failed', 'cancelled')", name='chk_actions_status'),
        CheckConstraint("type IN ('tool_call', 'analysis', 'response', 'clarification')", name='chk_actions_type'),
        Index('idx_actions_plan_order', 'plan_id', 'execution_order'),
        Index('idx_actions_tool_status', 'tool_name', 'status'),
        Index('idx_actions_type_status', 'type', 'status'),
        Index('idx_actions_depends_on', 'depends_on', postgresql_using='gin'),
    )


class SessionMemory(Base):
    """Persistent session memory for tool results and data storage."""
    
    __tablename__ = 'session_memory'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), ForeignKey('chats.id', ondelete='CASCADE'), nullable=False)
    memory_key = Column(String(255), nullable=False)  # "tool_result_action_id", "current_execution_plan"
    tool_name = Column(String(100))  # create_pdf, get_fake_data, etc.
    tags = Column(JSONB, default=[])  # ["pdf", "file", "manufacturing"]
    value = Column(JSONB, nullable=False)  # Actual stored data
    size_bytes = Column(Integer)  # Data size for monitoring
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True))  # For automatic cleanup
    access_count = Column(Integer, default=0)  # Usage tracking
    last_accessed_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    chat = relationship("Chat", back_populates="memory_items")
    
    # Constraints
    __table_args__ = (
        Index('idx_memory_chat_key', 'chat_id', 'memory_key', unique=True),
        Index('idx_memory_tool_created', 'tool_name', 'created_at'),
        Index('idx_memory_tags', 'tags', postgresql_using='gin'),
        Index('idx_memory_expires', 'expires_at', postgresql_where=text("expires_at IS NOT NULL")),
        Index('idx_memory_value_file_search', text("(value->'file_url')"), postgresql_using='gin', postgresql_where=text("value ? 'file_url'")),
    )


# Metadata classes for type hints
class ChatMetadata:
    """Type hints for chat metadata JSONB field."""
    environment: Optional[str] = None
    created_by: Optional[str] = None
    client_info: Optional[Dict[str, Any]] = None


class PlanMetadata:
    """Type hints for plan metadata JSONB field."""
    rag_params: Optional[Dict[str, Any]] = None
    force_deep_research: Optional[bool] = None
    force_online_search: Optional[bool] = None
    enable_formatting: Optional[bool] = None


class MemoryMetadata:
    """Type hints for memory value JSONB field."""
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    filename: Optional[str] = None
    name: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None
