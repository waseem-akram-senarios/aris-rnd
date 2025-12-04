"""
Pydantic models for FastAPI request/response schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for querying documents"""
    question: str = Field(..., description="The question to answer")
    k: int = Field(default=6, ge=1, le=20, description="Number of chunks to retrieve")
    use_mmr: bool = Field(default=True, description="Use Maximum Marginal Relevance for diverse results")


class Citation(BaseModel):
    """Citation information for a source"""
    id: int
    source: str
    page: Optional[int] = None
    snippet: str
    full_text: str
    source_location: str
    content_type: str = "text"
    image_ref: Optional[Dict[str, Any]] = None
    image_info: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for query results"""
    answer: str
    sources: List[str]
    citations: List[Citation]
    num_chunks_used: int
    response_time: float
    context_tokens: int
    response_tokens: int
    total_tokens: int


class DocumentMetadata(BaseModel):
    """Document metadata model"""
    document_id: Optional[str] = None
    document_name: str
    status: str
    chunks_created: int = 0
    tokens_extracted: int = 0
    parser_used: Optional[str] = None
    processing_time: float = 0.0
    extraction_percentage: float = 0.0
    images_detected: bool = False
    pages: Optional[int] = None
    error: Optional[str] = None


class DocumentListResponse(BaseModel):
    """Response model for listing documents"""
    documents: List[DocumentMetadata]
    total: int


class StatsResponse(BaseModel):
    """Response model for system statistics"""
    rag_stats: Dict[str, Any]
    metrics: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None

