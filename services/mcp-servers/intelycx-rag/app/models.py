"""Data models for the RAG knowledge base."""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class KnowledgeDomain(str, Enum):
    """Knowledge domain categories."""
    MANUFACTURING = "manufacturing"


class DocumentMetadata(BaseModel):
    """Document metadata structure."""
    filename: str
    file_type: str
    file_size: int
    upload_date: datetime
    domain: KnowledgeDomain = KnowledgeDomain.MANUFACTURING
    tags: List[str] = Field(default_factory=list)
    machine_tag: Optional[str] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """Document chunk representation."""
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    embedding_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeDocument(BaseModel):
    """Knowledge base document representation."""
    document_id: str
    original_filename: str
    s3_bucket: str
    s3_key: str
    domain: KnowledgeDomain
    status: DocumentStatus
    metadata: DocumentMetadata
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    chunk_count: int = 0
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResult(BaseModel):
    """Search result from knowledge base."""
    document_id: str
    chunk_id: str
    content: str
    score: float
    metadata: Dict[str, Any]
    source_filename: str
    chunk_index: int


class SearchResponse(BaseModel):
    """Response from knowledge base search."""
    query: str
    results: List[SearchResult]
    total_results: int
    search_time_ms: float
    used_filters: Dict[str, Any] = Field(default_factory=dict)


# MCP Tool Input/Output Models

class IngestDocumentInput(BaseModel):
    """Input for document ingestion."""
    bucket: str = Field(description="S3 bucket containing the document")
    key: str = Field(description="S3 key/path to the document")
    domain: KnowledgeDomain = Field(default=KnowledgeDomain.MANUFACTURING, description="Knowledge domain")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    force_reprocess: bool = Field(default=False, description="Force reprocessing if document exists")


class IngestDocumentOutput(BaseModel):
    """Output from document ingestion."""
    document_id: str
    status: DocumentStatus
    message: str
    processing_started: bool = True


class SearchKnowledgeBaseInput(BaseModel):
    """Input for knowledge base search."""
    query: str = Field(description="Search query")
    domain: Optional[KnowledgeDomain] = Field(default=None, description="Filter by domain")
    limit: int = Field(default=5, description="Maximum number of results")
    threshold: float = Field(default=0.7, description="Minimum similarity threshold")
    include_metadata: bool = Field(default=True, description="Include document metadata in results")


class GetDocumentStatusInput(BaseModel):
    """Input for getting document status."""
    document_id: str = Field(description="Document ID to check")


class GetDocumentStatusOutput(BaseModel):
    """Output for document status."""
    document_id: str
    status: DocumentStatus
    chunk_count: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ListDocumentsInput(BaseModel):
    """Input for listing documents."""
    domain: Optional[KnowledgeDomain] = Field(default=None, description="Filter by domain")
    status: Optional[DocumentStatus] = Field(default=None, description="Filter by status")
    limit: int = Field(default=50, description="Maximum number of documents")
    offset: int = Field(default=0, description="Offset for pagination")


class ListDocumentsOutput(BaseModel):
    """Output for listing documents."""
    documents: List[KnowledgeDocument]
    total_count: int
    has_more: bool


class DeleteDocumentInput(BaseModel):
    """Input for deleting a document."""
    document_id: str = Field(description="Document ID to delete")
    force: bool = Field(default=False, description="Force deletion even if indexing is in progress")


class DeleteDocumentOutput(BaseModel):
    """Output from document deletion."""
    document_id: str
    deleted: bool
    message: str


class HealthCheckOutput(BaseModel):
    """Health check response."""
    status: str
    opensearch_connected: bool
    database_connected: bool
    bedrock_available: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
