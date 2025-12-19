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
    # Text and image separation fields
    text_chunks_stored: int = 0  # Number of text chunks stored
    images_stored: int = 0  # Number of images with OCR stored
    text_index: str = "aris-rag-index"  # OpenSearch index for text
    images_index: str = "aris-rag-images-index"  # OpenSearch index for images
    text_storage_status: str = "pending"  # pending, completed, failed
    images_storage_status: str = "pending"  # pending, completed, failed
    # Enhanced metadata fields
    file_hash: Optional[str] = None  # File hash for duplicate detection
    upload_metadata: Optional[Dict[str, Any]] = None  # Upload info, timestamps, file size, MIME type
    pdf_metadata: Optional[Dict[str, Any]] = None  # PDF properties (author, title, dates, etc.)
    processing_metadata: Optional[Dict[str, Any]] = None  # Processing stats, performance metrics
    ocr_quality_metrics: Optional[Dict[str, Any]] = None  # OCR confidence, accuracy scores
    version_info: Optional[Dict[str, Any]] = None  # Version number, history, update tracking


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
    content_type: str = "image_ocr"  # Always "image_ocr" for this endpoint
    images_index: str = "aris-rag-images-index"  # Index used for query


class DocumentUpdateRequest(BaseModel):
    """Request model for updating document metadata"""
    document_name: Optional[str] = Field(default=None, description="Updated document name")
    status: Optional[str] = Field(default=None, description="Updated status")
    error: Optional[str] = Field(default=None, description="Updated error message")


class TextQueryRequest(BaseModel):
    """Request model for querying text content only"""
    question: str = Field(..., description="The question to answer")
    k: int = Field(default=6, ge=1, le=20, description="Number of text chunks to retrieve")
    document_id: Optional[str] = Field(default=None, description="Optional document ID to filter query to specific document")
    use_mmr: bool = Field(default=True, description="Use Maximum Marginal Relevance for diverse results")


class TextQueryResponse(BaseModel):
    """Response model for text-only query results"""
    answer: str
    sources: List[str]
    citations: List[Citation]  # Text-only citations
    num_chunks_used: int
    response_time: float
    content_type: str = "text"  # Always "text" for this endpoint
    total_text_chunks: int = 0  # Total chunks in text index
    context_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0


class StorageStatusResponse(BaseModel):
    """Response model for storage status (text vs images separation)"""
    document_id: str
    document_name: str
    
    # Text storage info
    text_index: str
    text_chunks_count: int
    text_storage_status: str
    text_last_updated: Optional[datetime] = None
    
    # Image storage info
    images_index: str
    images_count: int
    images_storage_status: str
    images_last_updated: Optional[datetime] = None
    
    # OCR info
    ocr_enabled: bool
    total_ocr_text_length: int = 0


class CombinedQueryResponse(BaseModel):
    """Response model for combined text and image queries"""
    text_results: TextQueryResponse
    image_results: ImageQueryResponse
    total_response_time: float


class TextStorageResponse(BaseModel):
    """Response model for text storage operation"""
    document_id: str
    document_name: str
    text_chunks_stored: int
    text_index: str
    status: str
    message: str


class ImageStorageResponse(BaseModel):
    """Response model for image OCR storage operation"""
    document_id: str
    document_name: str
    images_stored: int
    images_index: str
    total_ocr_text_length: int
    status: str
    message: str
    reprocessed: Optional[bool] = False  # True if document was re-processed with file upload
    extraction_method: Optional[str] = None  # Parser used (e.g., "docling")


class ImageDetailResult(BaseModel):
    """Detailed image information result"""
    image_id: str
    source: str
    image_number: int
    page: Optional[int] = None
    ocr_text: str
    ocr_text_length: int
    metadata: Dict[str, Any]
    extraction_method: Optional[str] = None
    extraction_timestamp: Optional[str] = None
    marker_detected: Optional[bool] = None
    full_chunk: Optional[str] = None
    context_before: Optional[str] = None
    score: Optional[float] = None


class AllImagesResponse(BaseModel):
    """Response model for getting all image information"""
    document_id: str
    document_name: str
    images: List[ImageDetailResult]
    total: int
    images_index: str
    total_ocr_text_length: int
    average_ocr_length: float
    images_with_ocr: int


class PageTextChunk(BaseModel):
    """Text chunk from a specific page"""
    chunk_index: int
    text: str
    page: int
    source: str
    token_count: Optional[int] = None
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class PageInformationResponse(BaseModel):
    """Response model for getting all information from a specific page"""
    document_id: str
    document_name: str
    page_number: int
    text_chunks: List[PageTextChunk]
    images: List[ImageDetailResult]
    total_text_chunks: int
    total_images: int
    total_text_length: int
    total_ocr_text_length: int
    text_index: str
    images_index: str


class ImageVerification(BaseModel):
    """Verification result for a single image"""
    image_id: str
    page_number: int
    image_index: int
    ocr_accuracy: float
    character_accuracy: Optional[float] = None
    word_accuracy: Optional[float] = None
    missing_content: List[str] = []
    extra_content: List[str] = []
    status: str  # 'accurate', 'needs_review', 'inaccurate'
    stored_ocr_length: int = 0
    verified_ocr_length: int = 0


class PageVerification(BaseModel):
    """Verification result for a single page"""
    page_number: int
    text_accuracy: Optional[float] = None
    images_accuracy: Optional[float] = None
    issues: List[str] = []
    image_verifications: List[ImageVerification] = []


class VerificationReport(BaseModel):
    """Complete verification report for a document"""
    document_id: str
    document_name: str
    verification_timestamp: str
    overall_accuracy: float
    page_verifications: List[PageVerification]
    image_verifications: List[ImageVerification]
    issues_found: List[str]
    recommendations: List[str]
    auto_fix_applied: bool = False
    auto_fix_details: Optional[Dict[str, Any]] = None


class AccuracyCheckResponse(BaseModel):
    """Quick accuracy check response"""
    document_id: str
    document_name: str
    overall_accuracy: Optional[float] = None
    ocr_accuracy: Optional[float] = None
    text_accuracy: Optional[float] = None
    last_verification: Optional[str] = None
    verification_needed: bool = True
    status: str  # 'accurate', 'needs_review', 'inaccurate', 'not_verified'


class ImageByNumberItem(BaseModel):
    """Simple image information by number"""
    image_number: int
    page: Optional[int] = None
    ocr_text: str
    ocr_text_length: int
    image_id: Optional[str] = None


class ImagesSummaryResponse(BaseModel):
    """Summary response for images by number"""
    document_id: str
    document_name: str
    total_images: int
    images: List[ImageByNumberItem]  # Sorted by image_number


class ImageByNumberResponse(BaseModel):
    """Response for a specific image by number"""
    document_id: str
    document_name: str
    image_number: int
    page: Optional[int] = None
    ocr_text: str
    ocr_text_length: int
    image_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

