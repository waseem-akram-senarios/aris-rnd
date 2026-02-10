"""
MCP Microservice - Model Context Protocol Server

This microservice provides an MCP server with FastAPI health endpoints
for document ingestion and semantic search in the ARIS RAG system.

Endpoints:
- GET /health - Health check endpoint
- GET /info - Service information
- SSE /sse - MCP Server-Sent Events endpoint

MCP Tools:
- rag_ingest - Add documents to the RAG system
- rag_search - Query documents with advanced search capabilities
"""

import os
import sys
import logging
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import FastMCP
try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError(
        "FastMCP is not installed. Install it with: pip install fastmcp"
    )

# Import MCP Engine
from services.mcp.engine import MCPEngine

# Initialize the MCP Engine
mcp_engine = MCPEngine()

# Initialize the MCP server
mcp = FastMCP(
    name="ARIS RAG MCP Server",
    instructions="""MCP server for ARIS RAG system - full document management with CRUD operations.

This server provides professional-grade RAG (Retrieval Augmented Generation) tools
with complete Create, Read, Update, Delete capabilities.

QUERY TOOLS:
1. rag_quick_query - FAST search for simple questions (gpt-4o-mini)
2. rag_research_query - DEEP search for complex research (gpt-4o + Agentic RAG)
3. rag_search - General search with configurable toggles

DOCUMENT CRUD:
4. rag_ingest - Add documents (text or S3 URI)
5. rag_upload_document - Upload documents directly (PDF, DOCX, TXT, etc.)
6. rag_list_documents - List all documents in the system
7. rag_get_document - Get details of a specific document
8. rag_update_document - Update document metadata
9. rag_delete_document - Delete a document and all its data

INDEX & CHUNK MANAGEMENT:
10. rag_list_indexes - List all vector indexes
11. rag_get_index_info - Get details of a specific index
12. rag_delete_index - Delete a vector index
13. rag_list_chunks - List chunks in an index
14. rag_get_chunk - Get a specific chunk
15. rag_create_chunk - Create a new chunk
16. rag_update_chunk - Update a chunk's text/metadata
17. rag_delete_chunk - Delete a specific chunk

SYSTEM:
18. rag_get_stats - Get system statistics
"""
)


# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
def rag_ingest(
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Add content to the RAG system for indexing with high accuracy parsing.
    
    This tool ingests content into the RAG vector database. The content can be:
    - Plain text: Raw text data to be indexed directly
    - S3 URI: A URI pointing to a document in S3 (e.g., s3://bucket/path/to/file.pdf)
    
    When an S3 URI is provided, the document is automatically fetched and parsed
    using the best available parser (Docling for accuracy, PyMuPDF for speed).
    
    ACCURACY FEATURES:
    - Automatic parser selection for optimal text extraction
    - Token-aware chunking (512 tokens, 128 overlap) for better retrieval
    - Page-level metadata for accurate citations
    - OCR support for scanned documents
    
    Supported formats for S3 documents: PDF, DOCX, DOC, TXT, MD, HTML
    
    Args:
        content: Raw text data OR an S3 URI pointing to a document.
                For S3, use format: s3://bucket-name/path/to/document.pdf
        metadata: Optional key-value pairs for categorization. Examples:
                 - language: Document language code (e.g., "en", "es", "de")
                 - domain: Content domain (e.g., "ticket", "machine_manual", "policy")
                 - source: Identifier for origin system
                 - Any custom fields as needed
    
    Returns:
        Dictionary containing:
        - success: Whether ingestion was successful
        - document_id: Unique identifier for the ingested document
        - chunks_created: Number of chunks created
        - tokens_added: Approximate token count
        - message: Status message
        - metadata: The metadata attached to the document
        - accuracy_info: Information about parsing quality
    
    Examples:
        # Ingest plain text
        rag_ingest(
            content="This is the content of my document...",
            metadata={"domain": "policy", "language": "en"}
        )
        
        # Ingest from S3
        rag_ingest(
            content="s3://my-bucket/documents/manual.pdf",
            metadata={"domain": "machine_manual", "language": "de"}
        )
    """
    return mcp_engine.ingest(content, metadata)


@mcp.tool()
def rag_upload_document(
    file_content: str,
    filename: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Upload and ingest a document directly into the RAG system.
    
    This tool allows you to upload documents directly without needing S3.
    The file content should be base64-encoded for binary files (PDF, DOCX, DOC)
    or can be plain text for text-based files (TXT, MD, HTML).
    
    SUPPORTED FORMATS:
    - PDF: Portable Document Format (base64-encoded)
    - DOCX: Microsoft Word Document (base64-encoded)
    - DOC: Legacy Word Document (base64-encoded)
    - TXT: Plain text file (plain text or base64)
    - MD: Markdown file (plain text or base64)
    - HTML/HTM: HTML file (plain text or base64)
    
    ACCURACY FEATURES:
    - Automatic parser selection for optimal text extraction
    - Token-aware chunking (512 tokens, 128 overlap) for better retrieval
    - Page-level metadata for accurate citations
    - OCR support for scanned PDF documents
    
    Args:
        file_content: The document content. For binary files (PDF, DOCX, DOC),
                     this MUST be base64-encoded. For text files (TXT, MD, HTML),
                     this can be either plain text or base64-encoded.
        filename: The filename with extension (e.g., "manual.pdf", "policy.docx").
                 The extension is used to determine the file type and parser.
        metadata: Optional key-value pairs for categorization. Examples:
                 - language: Document language code (e.g., "en", "es", "de")
                 - domain: Content domain (e.g., "ticket", "machine_manual", "policy")
                 - source: Identifier for origin system
                 - Any custom fields as needed
    
    Returns:
        Dictionary containing:
        - success: Whether upload and ingestion was successful
        - document_id: Unique identifier for the ingested document
        - chunks_created: Number of chunks created
        - tokens_added: Approximate token count
        - pages_extracted: Number of pages (for PDF/DOCX)
        - message: Status message
        - metadata: The metadata attached to the document
        - accuracy_info: Information about parsing quality
    
    Examples:
        # Upload a PDF document (base64-encoded)
        import base64
        with open("manual.pdf", "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
        rag_upload_document(
            file_content=content,
            filename="manual.pdf",
            metadata={"domain": "machine_manual", "language": "en"}
        )
        
        # Upload a plain text file
        rag_upload_document(
            file_content="This is the content of my document...",
            filename="notes.txt",
            metadata={"domain": "notes"}
        )
        
        # Upload a Markdown file
        rag_upload_document(
            file_content="# Title\\n\\nThis is markdown content...",
            filename="readme.md",
            metadata={"domain": "documentation"}
        )
    """
    return mcp_engine.upload_document(file_content, filename, metadata)


@mcp.tool()
def rag_quick_query(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 5,
    include_answer: bool = True
) -> Dict[str, Any]:
    """
    ⚡ QUICK QUERY: FAST response for simple questions.
    
    Uses Simple Mode (gpt-4o-mini) for maximum speed. Best for direct lookups
    and simple informational questions where speed is prioritized over deep analysis.
    
    Args:
        query: Specific question or lookup (e.g., "What is the contact email?")
        filters: Metadata constraints (e.g., {"source": "manual.pdf"})
        k: Number of results to return (default: 5)
        include_answer: Generate a direct answer (default: True)
    """
    return mcp_engine.search(
        query=query,
        filters=filters,
        k=k,
        search_mode="hybrid",
        use_agentic_rag=False,  # Force FAST mode
        include_answer=include_answer
    )


@mcp.tool()
def rag_research_query(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 15,
    include_answer: bool = True
) -> Dict[str, Any]:
    """
    🧠 RESEARCH SEARCH: DEEP analysis for complex questions.
    
    Uses Agent Mode (gpt-4o) with Query Decomposition. Breaks complex questions 
    into sub-queries to find information across multiple sections or documents.
    Best for "How does X work?", "Summarize Y", or multi-part questions.
    
    Args:
        query: Complex research question (e.g., "How do I maintain the EM10 engine?")
        filters: Metadata constraints
        k: Number of chunks to analyze (default: 15)
        include_answer: Generate a comprehensive analysis (default: True)
    """
    return mcp_engine.search(
        query=query,
        filters=filters,
        k=k,
        search_mode="hybrid",
        use_agentic_rag=True,  # Force DEEP/AGENT mode
        include_answer=include_answer
    )


@mcp.tool()
def rag_search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 10,
    search_mode: str = "hybrid",
    use_agentic_rag: bool = True,
    include_answer: bool = True
) -> Dict[str, Any]:
    """
    Query the RAG system with high-accuracy retrieval and answer generation.
    
    This tool searches the RAG vector database using multiple accuracy-enhancing
    techniques to provide the most relevant results.
    
    ACCURACY FEATURES:
    - Hybrid Search: Combines semantic (vector) and keyword (BM25) search
    - FlashRank Reranking: Cross-encoder reranking for precision
    - Agentic RAG: Automatic query decomposition for complex questions
    - Confidence Scores: Each result includes a confidence percentage
    - Cross-language Support: Auto-translates queries for better matching
    
    Args:
        query: The search query/prompt. Should be a clear question or description
               of what you're looking for. Works best with specific questions.
        filters: Optional metadata constraints to narrow results. Examples:
                - {"domain": "ticket"} - Only search ticket-related content
                - {"language": "en"} - Only search English documents
                - {"source": "manual.pdf"} - Only search a specific document
                Can combine multiple filters: {"domain": "policy", "language": "es"}
        k: Number of results to return (default: 10, max: 50)
        search_mode: Search strategy (default: "hybrid" for best accuracy)
                    - "hybrid": Combined semantic + keyword (recommended)
                    - "semantic": Pure vector similarity search
                    - "keyword": Pure BM25 text matching
        use_agentic_rag: Enable query decomposition for complex questions (default: True)
                        Breaks complex queries into sub-queries for better coverage.
        include_answer: Generate an LLM-synthesized answer (default: True)
    
    Returns:
        Dictionary containing:
        - success: Whether search was successful
        - query: The original query
        - answer: LLM-generated answer (if include_answer=True)
        - results: List of ranked results, each with:
            - content: The text content of the chunk
            - snippet: Brief excerpt
            - source: Source document name
            - page: Page number (if available)
            - confidence: Relevance score (0-100, higher is better)
            - metadata: All metadata associated with the chunk
        - total_results: Number of results returned
        - search_mode: The search mode used
        - accuracy_info: Details about search accuracy settings
    
    Examples:
        # Basic search with answer
        rag_search(query="How do I reset the machine?")
        
        # Search without answer generation (faster)
        rag_search(query="error codes", include_answer=False)
        
        # Search with domain filter
        rag_search(
            query="What is the warranty policy?",
            filters={"domain": "policy"}
        )
        
        # Complex question with Agentic RAG
        rag_search(
            query="Compare the maintenance procedures for Model X and Model Y",
            use_agentic_rag=True
        )
    """
    return mcp_engine.search(
        query=query,
        filters=filters,
        k=k,
        search_mode=search_mode,
        use_agentic_rag=use_agentic_rag,
        include_answer=include_answer
    )


# ============================================================================
# CRUD TOOLS - Document Management
# ============================================================================

@mcp.tool()
def rag_list_documents() -> Dict[str, Any]:
    """
    List all documents stored in the RAG system.
    
    Returns a list of all ingested documents with their metadata including:
    document ID, name, status, number of chunks, language, and timestamps.
    
    Use this to discover what documents are available for querying,
    or to find a specific document_id for further operations.
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - documents: List of document objects with id, name, status, chunks, etc.
        - total: Total number of documents
        - total_chunks: Total chunks across all documents
        - total_images: Total images across all documents
    
    Examples:
        # List all documents
        rag_list_documents()
    """
    return mcp_engine.list_documents()


@mcp.tool()
def rag_get_document(document_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific document by its ID.
    
    Retrieves full metadata for a single document including its status,
    chunk count, associated indexes, language, and custom metadata.
    
    Args:
        document_id: The unique identifier of the document (e.g., "doc-20250209-abc123def456")
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - document: Full document metadata object
        - message: Status message
    
    Examples:
        rag_get_document(document_id="doc-20250209-abc123def456")
    """
    return mcp_engine.get_document(document_id)


@mcp.tool()
def rag_update_document(
    document_id: str,
    document_name: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update metadata or properties of an existing document.
    
    Allows you to modify a document's name, status, language, or custom metadata
    without re-ingesting it. Only the fields you provide will be updated.
    
    Args:
        document_id: The unique identifier of the document to update
        document_name: New name for the document (optional)
        status: New status (e.g., "processed", "archived", "pending") (optional)
        language: New language code (e.g., "en", "es", "de") (optional)
        metadata: Dictionary of custom metadata to merge/update (optional)
    
    Returns:
        Dictionary containing:
        - success: Whether the update was successful
        - document_id: The document that was updated
        - updated_fields: List of fields that were changed
        - document: The updated document object
    
    Examples:
        # Update document name
        rag_update_document(document_id="doc-123", document_name="Updated Manual v2")
        
        # Update custom metadata
        rag_update_document(
            document_id="doc-123",
            metadata={"department": "engineering", "version": "2.0"}
        )
    """
    updates = {}
    if document_name is not None:
        updates["document_name"] = document_name
    if status is not None:
        updates["status"] = status
    if language is not None:
        updates["language"] = language
    if metadata is not None:
        updates["metadata"] = metadata
    
    if not updates:
        return {
            "success": False,
            "message": "No fields provided to update. Specify at least one of: document_name, status, language, metadata"
        }
    
    return mcp_engine.update_document(document_id, updates)


@mcp.tool()
def rag_delete_document(document_id: str) -> Dict[str, Any]:
    """
    Delete a document and ALL its associated data from the RAG system.
    
    WARNING: This permanently removes the document, its vector embeddings,
    any stored images, and the registry entry. This action cannot be undone.
    
    Args:
        document_id: The unique identifier of the document to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - document_id: The deleted document's ID
        - document_name: The deleted document's name
        - vector_deleted: Whether vector data was removed
        - s3_deleted: Whether S3 data was removed
        - registry_deleted: Whether registry entry was removed
    
    Examples:
        rag_delete_document(document_id="doc-20250209-abc123def456")
    """
    return mcp_engine.delete_document(document_id)


@mcp.tool()
def rag_get_stats() -> Dict[str, Any]:
    """
    Get overall system statistics for the RAG system.
    
    Returns aggregated statistics about documents, chunks, indexes,
    and system health. Useful for monitoring and understanding the
    current state of the RAG system.
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - stats: Object with total documents, chunks, indexes, etc.
    
    Examples:
        rag_get_stats()
    """
    return mcp_engine.get_stats()


# ============================================================================
# CRUD TOOLS - Vector Index Management
# ============================================================================

@mcp.tool()
def rag_list_indexes() -> Dict[str, Any]:
    """
    List all vector indexes in the RAG system.
    
    Each document is stored in one or more vector indexes. This tool
    lists all indexes with their chunk counts and metadata.
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - indexes: List of index objects with name, chunk_count, etc.
        - total: Total number of indexes
    
    Examples:
        rag_list_indexes()
    """
    return mcp_engine.list_indexes()


@mcp.tool()
def rag_get_index_info(index_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific vector index.
    
    Args:
        index_name: The name of the vector index (e.g., "aris_doc_20250209_abc123")
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - index: Detailed index information including chunk count, settings, etc.
    
    Examples:
        rag_get_index_info(index_name="aris_doc_20250209_abc123")
    """
    return mcp_engine.get_index_info(index_name)


@mcp.tool()
def rag_delete_index(index_name: str) -> Dict[str, Any]:
    """
    Delete a vector index and all its chunks.
    
    WARNING: This permanently removes the index and all chunks stored in it.
    This action cannot be undone.
    
    Args:
        index_name: The name of the vector index to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - index_name: The deleted index name
        - chunks_deleted: Number of chunks that were removed
    
    Examples:
        rag_delete_index(index_name="aris_doc_20250209_abc123")
    """
    return mcp_engine.delete_index(index_name)


# ============================================================================
# CRUD TOOLS - Chunk-level Management
# ============================================================================

@mcp.tool()
def rag_list_chunks(
    index_name: str,
    source: Optional[str] = None,
    offset: int = 0,
    limit: int = 20
) -> Dict[str, Any]:
    """
    List chunks stored in a vector index with optional filtering.
    
    Chunks are the individual text segments that documents are split into
    for vector search. Use this to inspect what content is stored in an index.
    
    Args:
        index_name: The vector index to list chunks from
        source: Optional source document name filter (e.g., "manual.pdf")
        offset: Pagination offset (default: 0)
        limit: Maximum chunks to return (default: 20, max: 100)
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - chunks: List of chunk objects with id, text preview, source, page
        - total: Total chunks available (for pagination)
        - offset: Current offset
        - limit: Current limit
    
    Examples:
        # List first 20 chunks
        rag_list_chunks(index_name="aris_doc_20250209_abc123")
        
        # List chunks from a specific source
        rag_list_chunks(index_name="aris_doc_20250209_abc123", source="manual.pdf")
        
        # Paginate through chunks
        rag_list_chunks(index_name="aris_doc_20250209_abc123", offset=20, limit=20)
    """
    return mcp_engine.list_chunks(index_name, source=source, offset=offset, limit=limit)


@mcp.tool()
def rag_get_chunk(index_name: str, chunk_id: str) -> Dict[str, Any]:
    """
    Get the full content and metadata of a specific chunk.
    
    Args:
        index_name: The vector index containing the chunk
        chunk_id: The unique identifier of the chunk
    
    Returns:
        Dictionary containing:
        - success: Whether the operation was successful
        - chunk: Full chunk object with text, source, page, metadata
        - index_name: The index the chunk belongs to
    
    Examples:
        rag_get_chunk(index_name="aris_doc_20250209_abc123", chunk_id="chunk-abc123")
    """
    return mcp_engine.get_chunk(index_name, chunk_id)


@mcp.tool()
def rag_create_chunk(
    index_name: str,
    text: str,
    source: str = "manual_entry",
    page: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new chunk in a vector index.
    
    Adds a new text chunk with its vector embedding to the specified index.
    The embedding is automatically generated from the text content.
    
    Args:
        index_name: The vector index to add the chunk to
        text: The text content of the chunk
        source: Source identifier (default: "manual_entry")
        page: Optional page number for citation tracking
        metadata: Optional additional metadata dictionary
    
    Returns:
        Dictionary containing:
        - success: Whether creation was successful
        - chunk_id: The ID of the newly created chunk
        - index_name: The index the chunk was added to
    
    Examples:
        rag_create_chunk(
            index_name="aris_doc_20250209_abc123",
            text="This is new content to add to the index.",
            source="manual_update",
            page=5
        )
    """
    return mcp_engine.create_chunk(index_name, text, source=source, page=page, metadata=metadata)


@mcp.tool()
def rag_update_chunk(
    index_name: str,
    chunk_id: str,
    text: Optional[str] = None,
    page: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Update an existing chunk's text, page number, or metadata.
    
    If the text content is changed, the vector embedding is automatically
    regenerated to keep search results accurate.
    
    Args:
        index_name: The vector index containing the chunk
        chunk_id: The unique identifier of the chunk to update
        text: New text content (optional - triggers embedding regeneration)
        page: New page number (optional)
        metadata: New metadata to merge (optional)
    
    Returns:
        Dictionary containing:
        - success: Whether the update was successful
        - chunk_id: The updated chunk's ID
        - updated_fields: List of fields that were changed
        - embedding_regenerated: Whether the embedding was recomputed
    
    Examples:
        # Update text content (embedding will be regenerated)
        rag_update_chunk(
            index_name="aris_doc_20250209_abc123",
            chunk_id="chunk-abc123",
            text="Updated content with corrections."
        )
        
        # Update just the page number
        rag_update_chunk(
            index_name="aris_doc_20250209_abc123",
            chunk_id="chunk-abc123",
            page=7
        )
    """
    return mcp_engine.update_chunk(index_name, chunk_id, text=text, page=page, metadata=metadata)


@mcp.tool()
def rag_delete_chunk(index_name: str, chunk_id: str) -> Dict[str, Any]:
    """
    Delete a specific chunk from a vector index.
    
    Removes the chunk and its vector embedding permanently.
    This action cannot be undone.
    
    Args:
        index_name: The vector index containing the chunk
        chunk_id: The unique identifier of the chunk to delete
    
    Returns:
        Dictionary containing:
        - success: Whether deletion was successful
        - chunk_id: The deleted chunk's ID
        - index_name: The index the chunk was removed from
    
    Examples:
        rag_delete_chunk(index_name="aris_doc_20250209_abc123", chunk_id="chunk-abc123")
    """
    return mcp_engine.delete_chunk(index_name, chunk_id)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Starting MCP Microservice...")
    logger.info(f"   Server: {mcp.name}")
    logger.info(f"   Tools: 18 MCP tools (query, document CRUD, index/chunk management, system)")
    yield
    logger.info("👋 Shutting down MCP Microservice...")


app = FastAPI(
    title="ARIS RAG MCP Server",
    description="""
    **Model Context Protocol (MCP) Server for ARIS RAG System**
    
    This microservice provides MCP tools for AI agents to interact with 
    the ARIS RAG document system.
    
    ## MCP Tools Available
    
    - **rag_ingest**: Add documents to the RAG system (text or S3 URI)
    - **rag_upload_document**: Upload documents directly (PDF, DOCX, TXT, MD, HTML) with base64 encoding
    - **rag_search**: Query documents with advanced search capabilities
    
    ## Accuracy Features
    
    - Hybrid Search (semantic + keyword)
    - FlashRank Reranking
    - Agentic RAG Query Decomposition
    - Confidence Scoring
    - Cross-language Support
    
    ## Endpoints
    
    - `GET /health` - Health check
    - `GET /info` - Service information
    - `GET /sse` - MCP Server-Sent Events endpoint
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint for the MCP microservice."""
    from shared.config.settings import ARISConfig
    
    return {
        "status": "healthy",
        "service": "mcp",
        "server_name": mcp.name,
        "tools": {
            "query": ["rag_quick_query", "rag_research_query", "rag_search"],
            "document_crud": ["rag_ingest", "rag_upload_document", "rag_list_documents", "rag_get_document", "rag_update_document", "rag_delete_document"],
            "index_management": ["rag_list_indexes", "rag_get_index_info", "rag_delete_index"],
            "chunk_management": ["rag_list_chunks", "rag_get_chunk", "rag_create_chunk", "rag_update_chunk", "rag_delete_chunk"],
            "system": ["rag_get_stats"]
        },
        "total_tools": 18,
        "accuracy_features": {
            "hybrid_search": ARISConfig.DEFAULT_USE_HYBRID_SEARCH,
            "reranking": ARISConfig.ENABLE_RERANKING,
            "agentic_rag": ARISConfig.DEFAULT_USE_AGENTIC_RAG,
            "auto_translate": ARISConfig.ENABLE_AUTO_TRANSLATE
        },
        "timestamp": datetime.now().isoformat()
    }


@app.get("/info")
async def service_info():
    """Get detailed information about the MCP service."""
    from shared.config.settings import ARISConfig
    
    return {
        "service": "ARIS RAG MCP Server",
        "version": "2.0.0",
        "description": "Model Context Protocol server with full CRUD operations for document management and search",
        "tool_categories": {
            "query": {
                "tools": ["rag_quick_query", "rag_research_query", "rag_search"],
                "description": "Search and query documents with RAG"
            },
            "document_crud": {
                "tools": ["rag_ingest", "rag_upload_document", "rag_list_documents", "rag_get_document", "rag_update_document", "rag_delete_document"],
                "description": "Create, read, update, delete documents"
            },
            "index_management": {
                "tools": ["rag_list_indexes", "rag_get_index_info", "rag_delete_index"],
                "description": "Manage vector indexes"
            },
            "chunk_management": {
                "tools": ["rag_list_chunks", "rag_get_chunk", "rag_create_chunk", "rag_update_chunk", "rag_delete_chunk"],
                "description": "Manage individual chunks within indexes"
            },
            "system": {
                "tools": ["rag_get_stats"],
                "description": "System statistics and monitoring"
            }
        },
        "total_tools": 18,
        "configuration": {
            "embedding_model": ARISConfig.EMBEDDING_MODEL,
            "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
            "chunk_overlap": ARISConfig.DEFAULT_CHUNK_OVERLAP,
            "retrieval_k": ARISConfig.DEFAULT_RETRIEVAL_K,
            "semantic_weight": ARISConfig.DEFAULT_SEMANTIC_WEIGHT,
            "reranking_enabled": ARISConfig.ENABLE_RERANKING,
            "agentic_rag_enabled": ARISConfig.DEFAULT_USE_AGENTIC_RAG
        },
        "endpoints": {
            "health": "/health",
            "info": "/info",
            "tools": "/tools",
            "mcp_sse": "/sse"
        }
    }


@app.get("/tools")
async def list_tools():
    """List all available MCP tools organized by category."""
    return {
        "total_tools": 18,
        "categories": {
            "query": ["rag_quick_query", "rag_research_query", "rag_search"],
            "document_crud": ["rag_ingest", "rag_upload_document", "rag_list_documents", "rag_get_document", "rag_update_document", "rag_delete_document"],
            "index_management": ["rag_list_indexes", "rag_get_index_info", "rag_delete_index"],
            "chunk_management": ["rag_list_chunks", "rag_get_chunk", "rag_create_chunk", "rag_update_chunk", "rag_delete_chunk"],
            "system": ["rag_get_stats"]
        },
        "tools": [
            {"name": "rag_quick_query", "category": "query", "description": "Fast search for simple questions"},
            {"name": "rag_research_query", "category": "query", "description": "Deep search for complex research"},
            {"name": "rag_search", "category": "query", "description": "General search with configurable toggles"},
            {"name": "rag_ingest", "category": "document_crud", "description": "Add content (text or S3 URI) to the system"},
            {"name": "rag_upload_document", "category": "document_crud", "description": "Upload documents directly"},
            {"name": "rag_list_documents", "category": "document_crud", "description": "List all documents"},
            {"name": "rag_get_document", "category": "document_crud", "description": "Get document details by ID"},
            {"name": "rag_update_document", "category": "document_crud", "description": "Update document metadata"},
            {"name": "rag_delete_document", "category": "document_crud", "description": "Delete a document and all its data"},
            {"name": "rag_list_indexes", "category": "index_management", "description": "List all vector indexes"},
            {"name": "rag_get_index_info", "category": "index_management", "description": "Get vector index details"},
            {"name": "rag_delete_index", "category": "index_management", "description": "Delete a vector index"},
            {"name": "rag_list_chunks", "category": "chunk_management", "description": "List chunks in an index"},
            {"name": "rag_get_chunk", "category": "chunk_management", "description": "Get a specific chunk"},
            {"name": "rag_create_chunk", "category": "chunk_management", "description": "Create a new chunk"},
            {"name": "rag_update_chunk", "category": "chunk_management", "description": "Update a chunk"},
            {"name": "rag_delete_chunk", "category": "chunk_management", "description": "Delete a chunk"},
            {"name": "rag_get_stats", "category": "system", "description": "Get system statistics"}
        ]
    }


# ============================================================================
# REST API ENDPOINTS - HTTP interface for Streamlit UI and external clients
# These mirror the MCP tools so all consumers use the same validated code path.
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional as Opt


class SearchRequest(BaseModel):
    """Request body for /api/search."""
    query: str
    filters: Opt[Dict[str, Any]] = None
    k: int = Field(default=5, ge=1, le=50)
    search_mode: str = Field(default="hybrid")
    use_agentic_rag: bool = True
    include_answer: bool = True


class IngestRequest(BaseModel):
    """Request body for /api/ingest."""
    content: str
    metadata: Opt[Dict[str, Any]] = None


class UploadRequest(BaseModel):
    """Request body for /api/upload."""
    file_content: str  # base64 for binary, plain text for .txt/.md/.html
    filename: str
    metadata: Opt[Dict[str, Any]] = None


@app.post("/api/search")
async def api_search(req: SearchRequest):
    """
    Search documents via MCP Engine (HTTP wrapper).
    Used by Streamlit UI and any REST client.
    """
    try:
        result = mcp_engine.search(
            query=req.query,
            filters=req.filters,
            k=req.k,
            search_mode=req.search_mode,
            use_agentic_rag=req.use_agentic_rag,
            include_answer=req.include_answer,
        )
        return result
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"/api/search error: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/ingest")
async def api_ingest(req: IngestRequest):
    """
    Ingest text/S3-URI content via MCP Engine (HTTP wrapper).
    Used by Streamlit UI and any REST client.
    """
    try:
        result = mcp_engine.ingest(
            content=req.content,
            metadata=req.metadata,
        )
        return result
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"/api/ingest error: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/upload")
async def api_upload(req: UploadRequest):
    """
    Upload a document via MCP Engine (HTTP wrapper).
    file_content is base64-encoded for binary files (PDF, DOCX)
    or plain UTF-8 text for text files (TXT, MD, HTML).
    Used by Streamlit UI and any REST client.
    """
    try:
        result = mcp_engine.upload_document(
            file_content=req.file_content,
            filename=req.filename,
            metadata=req.metadata,
        )
        return result
    except ValueError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"/api/upload error: {type(e).__name__}: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# SYNC ENDPOINTS - Real-time cross-service synchronization
# ============================================================================

# Global sync manager for MCP service
_mcp_sync_manager = None

def get_mcp_sync_manager():
    """Get or create sync manager for MCP service."""
    global _mcp_sync_manager
    if _mcp_sync_manager is None:
        from shared.utils.sync_manager import get_sync_manager
        _mcp_sync_manager = get_sync_manager("mcp")
    return _mcp_sync_manager


@app.post("/sync/force")
async def force_sync():
    """Force full synchronization of MCP service state."""
    try:
        sync_mgr = get_mcp_sync_manager()
        result = sync_mgr.force_full_sync()
        
        # Clear cached document registry to force reload with fresh state
        from services.mcp.engine import _get_cached_document_registry
        if hasattr(_get_cached_document_registry, '_registry'):
            del _get_cached_document_registry._registry
        
        logger.info("✅ [MCP] Force sync completed, caches cleared")
        
        return {
            "success": True,
            "message": "MCP sync completed and caches cleared",
            "result": result
        }
    except Exception as e:
        logger.error(f"[MCP] Force sync failed: {e}")
        return {"success": False, "error": str(e)}


@app.get("/sync/status")
async def sync_status():
    """Get current synchronization status for MCP service."""
    try:
        sync_mgr = get_mcp_sync_manager()
        status = sync_mgr.get_sync_status()
        
        return {
            "success": True,
            "service": "mcp",
            "status": status
        }
    except Exception as e:
        logger.error(f"[MCP] Sync status failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/sync/check")
async def check_sync():
    """Check for changes and sync if needed."""
    try:
        sync_mgr = get_mcp_sync_manager()
        result = sync_mgr.check_and_sync()
        
        return {
            "success": True,
            "checked": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"[MCP] Sync check failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/sync/instant")
async def instant_sync():
    """Perform immediate synchronization without waiting for interval."""
    try:
        sync_mgr = get_mcp_sync_manager()
        result = sync_mgr.instant_sync()
        
        logger.info("⚡ [MCP] Instant sync completed")
        
        return {
            "success": True,
            "message": "Instant sync completed",
            "result": result
        }
    except Exception as e:
        logger.error(f"[MCP] Instant sync failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def run_combined_server():
    """
    Run combined FastAPI + MCP server.
    
    Uses FastMCP's http_app as the base and mounts FastAPI routes on it.
    """
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, Mount
    from starlette.responses import JSONResponse
    
    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting Combined MCP + FastAPI Server on {host}:{port}")
    logger.info(f"   MCP SSE endpoint: http://{host}:{port}/sse")
    logger.info(f"   Health endpoint: http://{host}:{port}/health")
    logger.info(f"   Tools: 18 MCP tools (query, document CRUD, index/chunk management, system)")
    
    # Get the MCP's HTTP app (Starlette-based)
    mcp_http_app = mcp.http_app()
    
    # Create health check handler
    async def health_handler(request):
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "status": "healthy",
            "service": "mcp",
            "server_name": mcp.name,
            "tools": {
                "query": ["rag_quick_query", "rag_research_query", "rag_search"],
                "document_crud": ["rag_ingest", "rag_upload_document", "rag_list_documents", "rag_get_document", "rag_update_document", "rag_delete_document"],
                "index_management": ["rag_list_indexes", "rag_get_index_info", "rag_delete_index"],
                "chunk_management": ["rag_list_chunks", "rag_get_chunk", "rag_create_chunk", "rag_update_chunk", "rag_delete_chunk"],
                "system": ["rag_get_stats"]
            },
            "total_tools": 18,
            "accuracy_features": {
                "hybrid_search": ARISConfig.DEFAULT_USE_HYBRID_SEARCH,
                "reranking": ARISConfig.ENABLE_RERANKING,
                "agentic_rag": ARISConfig.DEFAULT_USE_AGENTIC_RAG,
                "auto_translate": ARISConfig.ENABLE_AUTO_TRANSLATE
            },
            "timestamp": datetime.now().isoformat()
        })
    
    # Create info handler
    async def info_handler(request):
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "service": "ARIS RAG MCP Server",
            "version": "2.0.0",
            "description": "Model Context Protocol server with full CRUD operations for document management and search",
            "tool_categories": {
                "query": {
                    "tools": ["rag_quick_query", "rag_research_query", "rag_search"],
                    "description": "Search and query documents with RAG"
                },
                "document_crud": {
                    "tools": ["rag_ingest", "rag_upload_document", "rag_list_documents", "rag_get_document", "rag_update_document", "rag_delete_document"],
                    "description": "Create, read, update, delete documents"
                },
                "index_management": {
                    "tools": ["rag_list_indexes", "rag_get_index_info", "rag_delete_index"],
                    "description": "Manage vector indexes"
                },
                "chunk_management": {
                    "tools": ["rag_list_chunks", "rag_get_chunk", "rag_create_chunk", "rag_update_chunk", "rag_delete_chunk"],
                    "description": "Manage individual chunks within indexes"
                },
                "system": {
                    "tools": ["rag_get_stats"],
                    "description": "System statistics and monitoring"
                }
            },
            "total_tools": 18,
            "configuration": {
                "embedding_model": ARISConfig.EMBEDDING_MODEL,
                "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                "reranking_enabled": ARISConfig.ENABLE_RERANKING,
                "agentic_rag_enabled": ARISConfig.DEFAULT_USE_AGENTIC_RAG
            },
            "endpoints": {
                "health": "/health",
                "info": "/info",
                "tools": "/tools",
                "mcp_sse": "/sse"
            }
        })
    
    # Create tools list handler
    async def tools_handler(request):
        return JSONResponse({
            "total_tools": 18,
            "tools": [
                # --- Query Tools ---
                {"name": "rag_quick_query", "category": "query", "description": "Fast search for simple questions (gpt-4o-mini)",
                 "parameters": {"query": {"type": "string", "required": True}, "filters": {"type": "object"}, "k": {"type": "integer", "default": 5}, "include_answer": {"type": "boolean", "default": True}}},
                {"name": "rag_research_query", "category": "query", "description": "Deep search for complex research (gpt-4o + Agentic RAG)",
                 "parameters": {"query": {"type": "string", "required": True}, "filters": {"type": "object"}, "k": {"type": "integer", "default": 15}, "include_answer": {"type": "boolean", "default": True}}},
                {"name": "rag_search", "category": "query", "description": "General search with configurable toggles",
                 "parameters": {"query": {"type": "string", "required": True}, "filters": {"type": "object"}, "k": {"type": "integer", "default": 10}, "search_mode": {"type": "string", "default": "hybrid"}, "use_agentic_rag": {"type": "boolean", "default": True}, "include_answer": {"type": "boolean", "default": True}}},
                # --- Document CRUD ---
                {"name": "rag_ingest", "category": "document_crud", "description": "Add content (text or S3 URI) to the RAG system",
                 "parameters": {"content": {"type": "string", "required": True}, "metadata": {"type": "object"}}},
                {"name": "rag_upload_document", "category": "document_crud", "description": "Upload documents directly (PDF, DOCX, TXT, etc.)",
                 "parameters": {"file_content": {"type": "string", "required": True}, "filename": {"type": "string", "required": True}, "metadata": {"type": "object"}},
                 "supported_formats": ["PDF", "DOCX", "DOC", "TXT", "MD", "HTML"]},
                {"name": "rag_list_documents", "category": "document_crud", "description": "List all documents in the system",
                 "parameters": {}},
                {"name": "rag_get_document", "category": "document_crud", "description": "Get detailed info about a specific document",
                 "parameters": {"document_id": {"type": "string", "required": True}}},
                {"name": "rag_update_document", "category": "document_crud", "description": "Update document metadata",
                 "parameters": {"document_id": {"type": "string", "required": True}, "document_name": {"type": "string"}, "status": {"type": "string"}, "language": {"type": "string"}, "metadata": {"type": "object"}}},
                {"name": "rag_delete_document", "category": "document_crud", "description": "Delete a document and all its data",
                 "parameters": {"document_id": {"type": "string", "required": True}}},
                # --- Index Management ---
                {"name": "rag_list_indexes", "category": "index_management", "description": "List all vector indexes",
                 "parameters": {}},
                {"name": "rag_get_index_info", "category": "index_management", "description": "Get detailed info about a vector index",
                 "parameters": {"index_name": {"type": "string", "required": True}}},
                {"name": "rag_delete_index", "category": "index_management", "description": "Delete a vector index and all its chunks",
                 "parameters": {"index_name": {"type": "string", "required": True}}},
                # --- Chunk Management ---
                {"name": "rag_list_chunks", "category": "chunk_management", "description": "List chunks in a vector index",
                 "parameters": {"index_name": {"type": "string", "required": True}, "source": {"type": "string"}, "offset": {"type": "integer", "default": 0}, "limit": {"type": "integer", "default": 20}}},
                {"name": "rag_get_chunk", "category": "chunk_management", "description": "Get a specific chunk by ID",
                 "parameters": {"index_name": {"type": "string", "required": True}, "chunk_id": {"type": "string", "required": True}}},
                {"name": "rag_create_chunk", "category": "chunk_management", "description": "Create a new chunk in an index",
                 "parameters": {"index_name": {"type": "string", "required": True}, "text": {"type": "string", "required": True}, "source": {"type": "string", "default": "manual_entry"}, "page": {"type": "integer"}, "metadata": {"type": "object"}}},
                {"name": "rag_update_chunk", "category": "chunk_management", "description": "Update a chunk's text, page, or metadata",
                 "parameters": {"index_name": {"type": "string", "required": True}, "chunk_id": {"type": "string", "required": True}, "text": {"type": "string"}, "page": {"type": "integer"}, "metadata": {"type": "object"}}},
                {"name": "rag_delete_chunk", "category": "chunk_management", "description": "Delete a specific chunk",
                 "parameters": {"index_name": {"type": "string", "required": True}, "chunk_id": {"type": "string", "required": True}}},
                # --- System ---
                {"name": "rag_get_stats", "category": "system", "description": "Get overall system statistics",
                 "parameters": {}}
            ]
        })
    
    # Create a redirect from /sse to /mcp for backwards compatibility
    async def sse_redirect(request):
        from starlette.responses import RedirectResponse
        # Include any query parameters
        query_string = request.url.query
        redirect_url = "/mcp" + ("?" + query_string if query_string else "")
        return RedirectResponse(url=redirect_url, status_code=307)
    
    # Create sync handlers for cross-service synchronization
    async def sync_force_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            result = sync_mgr.force_full_sync()
            from services.mcp.engine import _get_cached_document_registry
            if hasattr(_get_cached_document_registry, '_registry'):
                del _get_cached_document_registry._registry
            logger.info("✅ [MCP] Force sync completed, caches cleared")
            return JSONResponse({"success": True, "message": "MCP sync completed and caches cleared", "result": result})
        except Exception as e:
            logger.error(f"[MCP] Force sync failed: {e}")
            return JSONResponse({"success": False, "error": str(e)})
    
    async def sync_status_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            status = sync_mgr.get_sync_status()
            return JSONResponse({"success": True, "service": "mcp", "status": status})
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)})
    
    async def sync_check_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            result = sync_mgr.check_and_sync()
            return JSONResponse({"success": True, "checked": True, "result": result})
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)})
    
    async def sync_instant_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            result = sync_mgr.instant_sync()
            return JSONResponse({"success": True, "message": "Instant sync completed", "result": result})
        except Exception as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)})
    
    # ----------------------------------------------------------------
    # REST API handlers (for Streamlit UI and external REST clients)
    # These mirror the MCP tools so all consumers use the same code path.
    # ----------------------------------------------------------------
    async def api_search_handler(request):
        """Search documents via MCP Engine."""
        try:
            body = await request.json()
            result = mcp_engine.search(
                query=body.get("query", ""),
                filters=body.get("filters"),
                k=body.get("k", 5),
                search_mode=body.get("search_mode", "hybrid"),
                use_agentic_rag=body.get("use_agentic_rag", True),
                include_answer=body.get("include_answer", True),
            )
            return JSONResponse(result)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            logger.error(f"/api/search error: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_ingest_handler(request):
        """Ingest text/S3-URI content via MCP Engine."""
        try:
            body = await request.json()
            result = mcp_engine.ingest(
                content=body.get("content", ""),
                metadata=body.get("metadata"),
            )
            return JSONResponse(result)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            logger.error(f"/api/ingest error: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_upload_handler(request):
        """Upload a document via MCP Engine."""
        try:
            body = await request.json()
            result = mcp_engine.upload_document(
                file_content=body.get("file_content", ""),
                filename=body.get("filename", ""),
                metadata=body.get("metadata"),
            )
            return JSONResponse(result)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            logger.error(f"/api/upload error: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # --- Document CRUD ---
    async def api_list_documents_handler(request):
        try:
            return JSONResponse(mcp_engine.list_documents())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_document_handler(request):
        try:
            doc_id = request.path_params["document_id"]
            return JSONResponse(mcp_engine.get_document(doc_id))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_update_document_handler(request):
        try:
            doc_id = request.path_params["document_id"]
            body = await request.json()
            return JSONResponse(mcp_engine.update_document(doc_id, body))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_document_handler(request):
        try:
            doc_id = request.path_params["document_id"]
            return JSONResponse(mcp_engine.delete_document(doc_id))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_stats_handler(request):
        try:
            return JSONResponse(mcp_engine.get_stats())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # --- Index Management ---
    async def api_list_indexes_handler(request):
        try:
            return JSONResponse(mcp_engine.list_indexes())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_index_handler(request):
        try:
            idx = request.path_params["index_name"]
            return JSONResponse(mcp_engine.get_index_info(idx))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_index_handler(request):
        try:
            idx = request.path_params["index_name"]
            return JSONResponse(mcp_engine.delete_index(idx))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # --- Chunk Management ---
    async def api_list_chunks_handler(request):
        try:
            idx = request.path_params["index_name"]
            params = request.query_params
            return JSONResponse(mcp_engine.list_chunks(
                idx,
                source=params.get("source"),
                offset=int(params.get("offset", 0)),
                limit=int(params.get("limit", 20)),
            ))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            cid = request.path_params["chunk_id"]
            return JSONResponse(mcp_engine.get_chunk(idx, cid))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_create_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            body = await request.json()
            return JSONResponse(mcp_engine.create_chunk(
                idx, body.get("text", ""),
                source=body.get("source", "manual_entry"),
                page=body.get("page"),
                metadata=body.get("metadata"),
            ))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_update_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            cid = request.path_params["chunk_id"]
            body = await request.json()
            return JSONResponse(mcp_engine.update_chunk(
                idx, cid,
                text=body.get("text"),
                page=body.get("page"),
                metadata=body.get("metadata"),
            ))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            cid = request.path_params["chunk_id"]
            return JSONResponse(mcp_engine.delete_chunk(idx, cid))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # Add custom routes to the MCP HTTP app
    # Note: Routes are matched in order, so insert at beginning
    routes_to_add = [
        Route("/health", health_handler, methods=["GET"]),
        Route("/info", info_handler, methods=["GET"]),
        Route("/tools", tools_handler, methods=["GET"]),
        Route("/sse", sse_redirect, methods=["GET", "POST"]),
        # Sync
        Route("/sync/force", sync_force_handler, methods=["POST"]),
        Route("/sync/status", sync_status_handler, methods=["GET"]),
        Route("/sync/check", sync_check_handler, methods=["POST"]),
        Route("/sync/instant", sync_instant_handler, methods=["POST"]),
        # Core API
        Route("/api/search", api_search_handler, methods=["POST"]),
        Route("/api/ingest", api_ingest_handler, methods=["POST"]),
        Route("/api/upload", api_upload_handler, methods=["POST"]),
        Route("/api/stats", api_stats_handler, methods=["GET"]),
        # Document CRUD
        Route("/api/documents", api_list_documents_handler, methods=["GET"]),
        Route("/api/documents/{document_id}", api_get_document_handler, methods=["GET"]),
        Route("/api/documents/{document_id}", api_update_document_handler, methods=["PUT"]),
        Route("/api/documents/{document_id}", api_delete_document_handler, methods=["DELETE"]),
        # Index Management
        Route("/api/indexes", api_list_indexes_handler, methods=["GET"]),
        Route("/api/indexes/{index_name}", api_get_index_handler, methods=["GET"]),
        Route("/api/indexes/{index_name}", api_delete_index_handler, methods=["DELETE"]),
        # Chunk Management
        Route("/api/indexes/{index_name}/chunks", api_list_chunks_handler, methods=["GET"]),
        Route("/api/indexes/{index_name}/chunks", api_create_chunk_handler, methods=["POST"]),
        Route("/api/indexes/{index_name}/chunks/{chunk_id}", api_get_chunk_handler, methods=["GET"]),
        Route("/api/indexes/{index_name}/chunks/{chunk_id}", api_update_chunk_handler, methods=["PUT"]),
        Route("/api/indexes/{index_name}/chunks/{chunk_id}", api_delete_chunk_handler, methods=["DELETE"]),
    ]
    for i, route in enumerate(routes_to_add):
        mcp_http_app.routes.insert(i, route)
    
    # Run the combined server
    logger.info(f"   Available routes: /health, /info, /tools, /api/*, /sync/*, /sse (→ /mcp), /mcp")
    uvicorn.run(mcp_http_app, host=host, port=port)


def run_mcp_only():
    """Run the MCP server only with SSE transport."""
    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    transport = os.getenv("MCP_TRANSPORT", "sse")
    
    logger.info(f"🚀 Starting MCP Server on {host}:{port}")
    logger.info(f"   Transport: {transport}")
    logger.info(f"   Tools: 18 MCP tools (query, document CRUD, index/chunk management, system)")
    
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=host, port=port)


def run_fastapi_only():
    """Run only the FastAPI server (without MCP)."""
    import uvicorn
    
    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    
    logger.info(f"🌐 Starting FastAPI on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Determine mode from environment
    # 'combined' (default) - Both FastAPI endpoints + MCP SSE
    # 'mcp' - MCP server only
    # 'api' - FastAPI only
    mode = os.getenv("MCP_MODE", "combined")
    
    if mode == "api":
        run_fastapi_only()
    elif mode == "mcp":
        run_mcp_only()
    else:
        run_combined_server()

