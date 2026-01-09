"""
Pydantic models for FastAPI request/response schemas
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime


class QueryRequest(BaseModel):
    """Request model for querying documents"""
    question: str = Field(..., description="The question to answer")
    k: int = Field(default=6, ge=1, le=20, description="Number of chunks to retrieve")
    use_mmr: bool = Field(default=True, description="Use Maximum Marginal Relevance for diverse results")
    use_hybrid_search: Optional[bool] = Field(default=None, description="Use hybrid search combining semantic and keyword search")
    semantic_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Weight for semantic search in hybrid mode (0.0-1.0)")
    search_mode: Optional[Literal['semantic', 'keyword', 'hybrid']] = Field(default='hybrid', description="Search mode: 'semantic', 'keyword', or 'hybrid'")
    use_agentic_rag: Optional[bool] = Field(default=None, description="Use Agentic RAG with query decomposition and synthesis")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0, description="Temperature for LLM response generation (0.0-2.0)")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4000, description="Maximum tokens for LLM response (1-4000)")
    document_id: Optional[str] = Field(default=None, description="Optional document ID to filter query to specific document. If not provided, queries all documents in the RAG system.")
    active_sources: Optional[List[str]] = Field(default=None, description="Optional list of document names/IDs to filter query to. Overrides document_id if provided.")
    response_language: Optional[str] = Field(default=None, description="Language for the LLM response (e.g. 'English', 'Spanish', 'fr').")
    filter_language: Optional[str] = Field(default=None, description="Filter results by document language code (e.g. 'eng', 'spa', 'fra').")
    auto_translate: bool = Field(default=True, description="Automatically translate non-English queries to English for better semantic search.")


class ProcessingResult(BaseModel):
    """Result of document processing."""
    status: str  # 'success', 'failed', 'processing'
    document_name: str
    language: str = "eng"
    chunks_created: int = 0
    tokens_extracted: int = 0
    parser_used: Optional[str] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    extraction_percentage: float = 0.0
    images_detected: bool = False
    image_count: int = 0  # Number of images extracted


class Citation(BaseModel):
    """Citation information for a source"""
    id: int
    source: str
    page: int = Field(default=1, ge=1, description="Page number (always >= 1, defaults to 1 if not available)")
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
    similarity_percentage: Optional[float] = Field(default=None, ge=0.0, le=100.0, description="Similarity ranking as percentage (100% = most similar)")


class QueryResponse(BaseModel):
    """Response model for query results"""
    answer: str
    sources: List[str]
    citations: List[Citation]
    num_chunks_used: int = 0
    response_time: float = 0.0
    context_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0


class DocumentMetadata(BaseModel):
    """Document metadata model"""
    document_id: Optional[str] = None
    document_name: str
    status: str
    language: str = "eng"
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
    total_chunks: int = 0
    total_images: int = 0


class StatsResponse(BaseModel):
    """Response model for system statistics"""
    rag_stats: Dict[str, Any]
    metrics: Dict[str, Any]


class ErrorResponse(BaseModel):
    """Error response model"""


# Settings API Schemas
class ModelSettings(BaseModel):
    """Model configuration settings"""
    api_provider: Literal['openai', 'cerebras'] = Field(default='openai', description="API provider to use")
    openai_model: str = Field(default='gpt-4o', description="OpenAI model name")
    cerebras_model: str = Field(default='llama-3.3-70b', description="Cerebras model name")
    embedding_model: str = Field(default='text-embedding-3-large', description="Embedding model name")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=1200, ge=1, le=4000, description="Maximum tokens for response")


class ParserSettings(BaseModel):
    """Parser configuration settings"""
    parser: Literal['docling', 'pymupdf', 'pypdf2'] = Field(default='docling', description="Document parser to use")
    docling_timeout: int = Field(default=1800, ge=60, le=3600, description="Docling parser timeout in seconds")


class ChunkingSettings(BaseModel):
    """Chunking strategy settings"""
    strategy: Literal['comprehensive', 'balanced', 'fast'] = Field(default='comprehensive', description="Chunking strategy")
    chunk_size: int = Field(default=384, ge=100, le=2000, description="Chunk size in tokens")
    chunk_overlap: int = Field(default=120, ge=0, le=500, description="Chunk overlap in tokens")


class VectorStoreSettings(BaseModel):
    """Vector store configuration settings"""
    vector_store_type: Literal['faiss', 'opensearch'] = Field(default='opensearch', description="Vector store type")
    opensearch_domain: Optional[str] = Field(default='intelycx-waseem-os', description="OpenSearch domain name")
    opensearch_index: str = Field(default='aris-rag-index', description="OpenSearch index name")
    opensearch_region: str = Field(default='us-east-2', description="AWS region for OpenSearch")


class RetrievalSettings(BaseModel):
    """Retrieval configuration settings"""
    default_k: int = Field(default=12, ge=1, le=50, description="Default number of chunks to retrieve")
    use_mmr: bool = Field(default=True, description="Use Maximum Marginal Relevance")
    mmr_fetch_k: int = Field(default=50, ge=1, le=100, description="Number of candidates for MMR")
    mmr_lambda: float = Field(default=0.35, ge=0.0, le=1.0, description="MMR lambda for diversity")
    search_mode: Literal['semantic', 'keyword', 'hybrid'] = Field(default='hybrid', description="Default search mode")
    semantic_weight: float = Field(default=0.75, ge=0.0, le=1.0, description="Semantic search weight")
    keyword_weight: float = Field(default=0.25, ge=0.0, le=1.0, description="Keyword search weight")


class AgenticRAGSettings(BaseModel):
    """Agentic RAG configuration settings"""
    use_agentic_rag: bool = Field(default=True, description="Enable Agentic RAG")
    max_sub_queries: int = Field(default=4, ge=1, le=10, description="Maximum sub-queries")
    chunks_per_subquery: int = Field(default=6, ge=1, le=20, description="Chunks per sub-query")
    max_total_chunks: int = Field(default=25, ge=1, le=100, description="Maximum total chunks")
    deduplication_threshold: float = Field(default=0.95, ge=0.0, le=1.0, description="Deduplication threshold")


class SystemSettings(BaseModel):
    """Complete system settings"""
    model_settings: ModelSettings
    parser_settings: ParserSettings
    chunking_settings: ChunkingSettings
    vector_store_settings: VectorStoreSettings
    retrieval_settings: RetrievalSettings
    agentic_rag_settings: AgenticRAGSettings


class DocumentLibraryInfo(BaseModel):
    """Document library information"""
    total_documents: int = Field(description="Total number of documents stored")
    documents: List[DocumentMetadata] = Field(description="List of all documents")
    storage_persists: bool = Field(default=True, description="Whether storage persists across restarts")


class MetricsInfo(BaseModel):
    """R&D Metrics and Analytics"""
    total_documents_processed: int = Field(default=0, description="Total documents processed")
    total_chunks_created: int = Field(default=0, description="Total chunks created")
    total_images_extracted: int = Field(default=0, description="Total images extracted")
    average_processing_time: float = Field(default=0.0, description="Average processing time per document")
    total_queries: int = Field(default=0, description="Total queries processed")
    average_query_time: float = Field(default=0.0, description="Average query response time")
    parsers_used: Dict[str, int] = Field(default_factory=dict, description="Count of documents by parser")
    storage_stats: Dict[str, Any] = Field(default_factory=dict, description="Storage statistics")


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
    page: int = Field(default=1, ge=1, description="Page number where image appears (always >= 1, defaults to 1 if not available)")
    ocr_text: str
    metadata: Dict[str, Any]
    score: Optional[float] = None


class ImageQueryResponse(BaseModel):
    """Response model for image queries"""
    images: List[ImageResult]
    total: int
    content_type: str = "image_ocr"  # Always "image_ocr" for this endpoint
    images_index: str = "aris-rag-images-index"  # Index used for query
    message: Optional[str] = None  # Optional message for informational purposes


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


# ============================================================================
# CRUD SCHEMAS - Documents and Vector Database Management
# ============================================================================

class DocumentCreateRequest(BaseModel):
    """Request model for creating a document entry manually (without file upload)"""
    document_name: str = Field(..., description="Name of the document")
    document_id: Optional[str] = Field(default=None, description="Custom document ID (auto-generated if not provided)")
    language: str = Field(default="eng", description="Document language code")
    status: str = Field(default="pending", description="Initial status")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class DocumentUpdateRequest(BaseModel):
    """Request model for updating document metadata"""
    document_name: Optional[str] = Field(default=None, description="Updated document name")
    status: Optional[str] = Field(default=None, description="Updated status")
    language: Optional[str] = Field(default=None, description="Updated language code")
    error: Optional[str] = Field(default=None, description="Updated error message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata to merge")


class DocumentDeleteResponse(BaseModel):
    """Response for document deletion"""
    success: bool
    document_id: str
    document_name: Optional[str] = None
    message: str
    vector_deleted: bool = False
    s3_deleted: bool = False
    registry_deleted: bool = False


class BulkDocumentDeleteRequest(BaseModel):
    """Request for bulk document deletion"""
    document_ids: List[str] = Field(..., description="List of document IDs to delete")
    delete_vectors: bool = Field(default=True, description="Also delete vector data")
    delete_s3: bool = Field(default=True, description="Also delete S3 files")


class BulkDocumentDeleteResponse(BaseModel):
    """Response for bulk document deletion"""
    success: bool
    total_requested: int
    total_deleted: int
    failed: List[Dict[str, str]] = []
    message: str


# Vector Database CRUD Schemas

class VectorIndexInfo(BaseModel):
    """Information about a vector index"""
    index_name: str
    document_name: Optional[str] = None
    document_id: Optional[str] = None
    chunk_count: int = 0
    created_at: Optional[str] = None
    last_updated: Optional[str] = None
    dimension: Optional[int] = None
    status: str = "active"  # active, empty, error


class VectorIndexListResponse(BaseModel):
    """Response for listing all vector indexes"""
    indexes: List[VectorIndexInfo]
    total: int
    message: Optional[str] = None


class VectorChunkInfo(BaseModel):
    """Information about a vector chunk"""
    chunk_id: str
    text: str
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    source: Optional[str] = None
    language: Optional[str] = None
    metadata: Dict[str, Any] = {}
    score: Optional[float] = None


class VectorChunkListResponse(BaseModel):
    """Response for listing chunks in an index"""
    index_name: str
    chunks: List[VectorChunkInfo]
    total: int
    offset: int = 0
    limit: int = 100


class VectorChunkCreateRequest(BaseModel):
    """Request for manually creating a vector chunk"""
    text: str = Field(..., description="Text content for the chunk")
    index_name: str = Field(..., description="Target index name")
    page: int = Field(default=1, ge=1, description="Page number")
    source: Optional[str] = Field(default=None, description="Source document name")
    language: Optional[str] = Field(default="eng", description="Language code")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class VectorChunkUpdateRequest(BaseModel):
    """Request for updating a vector chunk"""
    text: Optional[str] = Field(default=None, description="Updated text content")
    page: Optional[int] = Field(default=None, ge=1, description="Updated page number")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata to merge")


class VectorIndexDeleteRequest(BaseModel):
    """Request for deleting a vector index"""
    index_name: str = Field(..., description="Index name to delete")
    confirm: bool = Field(default=False, description="Must be True to confirm deletion")


class VectorIndexDeleteResponse(BaseModel):
    """Response for vector index deletion"""
    success: bool
    index_name: str
    chunks_deleted: int = 0
    message: str


class BulkVectorIndexDeleteRequest(BaseModel):
    """Request for bulk vector index deletion"""
    index_names: List[str] = Field(..., description="List of index names to delete")
    confirm: bool = Field(default=False, description="Must be True to confirm deletion")


class BulkVectorIndexDeleteResponse(BaseModel):
    """Response for bulk vector index deletion"""
    success: bool
    total_requested: int
    total_deleted: int
    failed: List[Dict[str, str]] = []
    total_chunks_deleted: int = 0
    message: str


class VectorSearchRequest(BaseModel):
    """Request for searching vectors directly"""
    query: str = Field(..., description="Search query")
    index_names: Optional[List[str]] = Field(default=None, description="Specific indexes to search (None = all)")
    k: int = Field(default=10, ge=1, le=100, description="Number of results")
    use_hybrid: bool = Field(default=True, description="Use hybrid search")
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Semantic search weight")


class VectorSearchResponse(BaseModel):
    """Response for vector search"""
    query: str
    results: List[VectorChunkInfo]
    total: int
    indexes_searched: List[str]
    search_time_ms: float


class IndexMapEntry(BaseModel):
    """Entry in the document-to-index map"""
    document_name: str
    index_name: str
    document_id: Optional[str] = None
    created_at: Optional[str] = None


class IndexMapResponse(BaseModel):
    """Response for getting the index map"""
    entries: List[IndexMapEntry]
    total: int


class IndexMapUpdateRequest(BaseModel):
    """Request for updating the index map"""
    document_name: str = Field(..., description="Document name")
    index_name: str = Field(..., description="Index name to map to")
    document_id: Optional[str] = Field(default=None, description="Optional document ID")

