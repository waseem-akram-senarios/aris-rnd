"""Pydantic Input/Output models for ARIS RAG MCP Server tools.

Follows the Intelycx MCP server pattern with typed schemas for every tool,
enabling proper validation, OpenAPI docs, and agent-friendly discovery.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class SearchMode(str, Enum):
    """Available search modes."""
    QUICK = "quick"
    RESEARCH = "research"
    SEARCH = "search"


class SearchStrategy(str, Enum):
    """Underlying search strategy."""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    SUCCESS = "success"
    FAILED = "failed"


# ============================================================================
# Retrieval Tool — Input / Output
# ============================================================================

class CitationOutput(BaseModel):
    """A single citation from the retrieval results."""
    content: str = Field(description="Full text content of the citation")
    snippet: Optional[str] = Field(None, description="Short excerpt highlighting the match")
    source: str = Field(description="Source document filename")
    document_id: Optional[str] = Field(None, description="Unique document identifier")
    page: Optional[int] = Field(None, description="Page number in the source document")
    source_location: Optional[str] = Field(None, description="Human-readable location (e.g. 'Page 14')")
    content_type: Optional[str] = Field(None, description="Content type: text, image, etc.")
    page_confidence: Optional[float] = Field(None, description="Confidence of page extraction (0-1)")
    page_extraction_method: Optional[str] = Field(None, description="Method used to determine page")
    source_confidence: Optional[float] = Field(None, description="Confidence of source attribution (0-1)")
    rerank_score: Optional[float] = Field(None, description="FlashRank cross-encoder relevance score (0-1)")
    confidence: Optional[float] = Field(None, description="Overall confidence score (0-100)")
    confidence_percentage: Optional[int] = Field(None, description="Confidence as integer percentage (0-100)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class RetrievalOutput(BaseModel):
    """Output from the retrieval (search) tool."""
    success: bool = Field(description="Whether the search completed successfully")
    query: str = Field(description="Original search query")
    answer: Optional[str] = Field(None, description="AI-generated answer grounded in documents")
    results: List[CitationOutput] = Field(default_factory=list, description="Ranked search results")
    citations: List[CitationOutput] = Field(default_factory=list, description="Source citations for the answer")
    sources: List[str] = Field(default_factory=list, description="List of source document filenames")
    total_results: int = Field(0, description="Total number of matching results")
    search_mode: Optional[str] = Field(None, description="Search strategy used")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Filters applied to the search")
    accuracy_info: Optional[Dict[str, Any]] = Field(None, description="Search accuracy metadata")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


# ============================================================================
# Ingestion Tool — Input / Output
# ============================================================================

class IngestDocumentOutput(BaseModel):
    """Output from document ingestion."""
    success: bool = Field(description="Whether the ingestion succeeded")
    document_id: Optional[str] = Field(None, description="Unique document identifier")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class DocumentInfo(BaseModel):
    """Document information in list responses."""
    document_id: str = Field(description="Unique document identifier")
    document_name: str = Field(description="Document filename")
    status: str = Field(description="Processing status")
    chunks_created: int = Field(0, description="Number of chunks created")
    images_stored: int = Field(0, description="Number of images stored")
    language: Optional[str] = Field(None, description="Detected language code")
    text_index: Optional[str] = Field(None, description="OpenSearch text index name")
    images_index: Optional[str] = Field(None, description="OpenSearch images index name")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class ListDocumentsOutput(BaseModel):
    """Output from listing documents."""
    success: bool = Field(description="Whether the operation succeeded")
    documents: List[DocumentInfo] = Field(default_factory=list, description="List of documents")
    total: int = Field(0, description="Total document count")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class GetDocumentOutput(BaseModel):
    """Output from getting a single document."""
    success: bool = Field(description="Whether the operation succeeded")
    document: Optional[DocumentInfo] = Field(None, description="Document details")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class UpdateDocumentOutput(BaseModel):
    """Output from updating a document."""
    success: bool = Field(description="Whether the update succeeded")
    document_id: Optional[str] = Field(None, description="Updated document ID")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class DeleteDocumentOutput(BaseModel):
    """Output from deleting a document."""
    success: bool = Field(description="Whether the deletion succeeded")
    document_id: Optional[str] = Field(None, description="Deleted document ID")
    deleted: bool = Field(False, description="Whether the document was actually deleted")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


# ============================================================================
# Index Management — Output
# ============================================================================

class IndexInfo(BaseModel):
    """Information about a vector index."""
    index_name: str = Field(description="Index name in OpenSearch")
    document_count: int = Field(0, description="Number of documents in the index")
    chunk_count: int = Field(0, description="Number of chunks/vectors")
    index_type: Optional[str] = Field(None, description="Index type")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    size_bytes: int = Field(0, description="Index size in bytes")


class ListIndexesOutput(BaseModel):
    """Output from listing indexes."""
    success: bool = Field(description="Whether the operation succeeded")
    indexes: List[IndexInfo] = Field(default_factory=list, description="List of indexes")
    total: int = Field(0, description="Total index count")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


# ============================================================================
# Chunk Management — Output
# ============================================================================

class ChunkInfo(BaseModel):
    """Information about a text chunk."""
    chunk_id: str = Field(description="Unique chunk identifier")
    text: Optional[str] = Field(None, description="Chunk text content")
    source: Optional[str] = Field(None, description="Source document")
    page: Optional[int] = Field(None, description="Page number")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")


class ListChunksOutput(BaseModel):
    """Output from listing chunks."""
    success: bool = Field(description="Whether the operation succeeded")
    chunks: List[ChunkInfo] = Field(default_factory=list, description="List of chunks")
    total: int = Field(0, description="Total chunk count")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


class ChunkOperationOutput(BaseModel):
    """Output from chunk create/update/delete/get operations."""
    success: bool = Field(description="Whether the operation succeeded")
    chunk_id: Optional[str] = Field(None, description="Chunk identifier")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


# ============================================================================
# Monitoring Tool — Output
# ============================================================================

class ProcessingStats(BaseModel):
    """Document processing statistics."""
    total_documents: Optional[int] = Field(None, description="Total documents in the system")
    total_chunks: Optional[int] = Field(None, description="Total text chunks")
    total_pages: Optional[int] = Field(None, description="Total pages processed")
    total_images: Optional[int] = Field(None, description="Total images stored")
    language_distribution: Dict[str, int] = Field(default_factory=dict, description="Documents per language")


class QueryStats(BaseModel):
    """Query performance statistics."""
    total_queries: int = Field(0, description="Total queries served")
    successful_queries: int = Field(0, description="Successful queries")
    failed_queries: int = Field(0, description="Failed queries")
    success_rate: float = Field(0.0, description="Query success rate (0-1)")
    avg_response_time: Optional[float] = Field(None, description="Average response time in seconds")
    avg_answer_length: Optional[float] = Field(None, description="Average answer length in characters")
    api_usage: Dict[str, int] = Field(default_factory=dict, description="API usage by provider")


class CostStats(BaseModel):
    """API cost statistics."""
    embedding_cost_usd: float = Field(0.0, description="Embedding API cost in USD")
    query_cost_usd: float = Field(0.0, description="Query/LLM API cost in USD")
    total_cost_usd: float = Field(0.0, description="Total API cost in USD")


class MonitoringOutput(BaseModel):
    """Output from the monitoring tool."""
    success: bool = Field(description="Whether the stats retrieval succeeded")
    stats: Optional[Dict[str, Any]] = Field(None, description="System statistics")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")


# ============================================================================
# Health Check
# ============================================================================

class HealthCheckOutput(BaseModel):
    """Health check response."""
    status: str = Field(description="Server health status: healthy, degraded, unhealthy")
    service: str = Field(description="Service name")
    server_name: str = Field(description="MCP server name")
    tools: List[str] = Field(default_factory=list, description="Available tool names")
    total_tools: int = Field(0, description="Total number of tools")
    accuracy_features: Dict[str, bool] = Field(default_factory=dict, description="Enabled accuracy features")
    timestamp: str = Field(description="ISO timestamp")
