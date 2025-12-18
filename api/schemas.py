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
    use_hybrid_search: Optional[bool] = Field(default=None, description="Use hybrid search combining semantic and keyword search")
    semantic_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Weight for semantic search in hybrid mode (0.0-1.0)")
    search_mode: Optional[str] = Field(default=None, description="Search mode: 'semantic', 'keyword', or 'hybrid'")
    use_agentic_rag: Optional[bool] = Field(default=None, description="Use Agentic RAG with query decomposition and synthesis")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature for LLM response generation (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4000, description="Maximum tokens for LLM response (1-4000)")
    document_id: Optional[str] = Field(default=None, description="Optional document ID to filter query to specific document. If not provided, queries all documents in the RAG system.")


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
    # Additional optional fields that may be present
    source_confidence: Optional[float] = None
    page_confidence: Optional[float] = None
    section: Optional[str] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    chunk_index: Optional[int] = None
    extraction_method: Optional[str] = None
    similarity_score: Optional[float] = None


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
    image_count: int = 0  # Number of images extracted
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


class ImageQueryRequest(BaseModel):
    """Request model for querying images"""
    question: str = Field(..., description="The search query for images")
    source: Optional[str] = Field(default=None, description="Optional document source to filter by")
    k: int = Field(default=5, ge=1, le=50, description="Number of images to retrieve")


class ImageResult(BaseModel):
    """Image search result model"""
    image_id: str
    source: str
    image_number: int
    page: Optional[int] = None
    ocr_text: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class ImageQueryResponse(BaseModel):
    """Response model for image queries"""
    images: List[ImageResult]
    total: int


class DocumentUpdateRequest(BaseModel):
    """Request model for updating document metadata"""
    document_name: Optional[str] = Field(default=None, description="Updated document name")
    status: Optional[str] = Field(default=None, description="Updated status")
    error: Optional[str] = Field(default=None, description="Updated error message")

