"""FastMCP RAG Server for Intelycx Knowledge Base."""

import os
import logging
from typing import Any, Dict, List, Optional, Annotated
from datetime import datetime

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from .models import (
    DocumentStatus, KnowledgeDomain,
    IngestDocumentInput, IngestDocumentOutput,
    SearchKnowledgeBaseInput, SearchResponse,
    GetDocumentStatusInput, GetDocumentStatusOutput,
    ListDocumentsInput, ListDocumentsOutput,
    DeleteDocumentInput, DeleteDocumentOutput
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Filter to exclude health check requests from uvicorn access logs
class HealthCheckAccessLogFilter(logging.Filter):
    """Filter to exclude health check requests from access logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out health check paths from uvicorn access logs
        # Format: "172.31.23.238:51492 - \"GET /health HTTP/1.1\" 200 OK"
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            # Exclude /health paths from uvicorn access logs
            if 'GET /health' in msg or '"GET /health' in msg:
                return False
        return True

# Apply filter to uvicorn access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthCheckAccessLogFilter())

# Create FastMCP server with enhanced configuration
mcp = FastMCP(
    "Intelycx RAG Knowledge Base",
    on_duplicate_tools="warn"  # Warn about duplicate tool registrations
)

# Global service instances - will be initialized on first use
db_manager = None
opensearch_client = None
embedding_service = None
document_processor = None
search_service = None


async def get_services():
    """Initialize services on first access (lazy initialization)."""
    global db_manager, opensearch_client, embedding_service, document_processor, search_service
    
    if db_manager is None:
        from .config import settings
        from .services.database import DatabaseManager
        from .services.opensearch_client import OpenSearchClient
        from .services.embeddings import EmbeddingService
        from .services.document_processor import DocumentProcessor
        from .services.search_service import SearchService
        
        logger.info("🚀 Initializing RAG services...")
        
        db_manager = DatabaseManager(settings.database_url)
        await db_manager.initialize()
        
        opensearch_client = OpenSearchClient(settings)
        await opensearch_client.initialize()
        
        embedding_service = EmbeddingService(settings)
        await embedding_service.initialize()
        
        document_processor = DocumentProcessor(
            settings, db_manager, opensearch_client, embedding_service
        )
        
        search_service = SearchService(
            settings, opensearch_client, embedding_service
        )
        
        logger.info("✅ RAG services initialized successfully")
    
    return db_manager, opensearch_client, embedding_service, document_processor, search_service


@mcp.tool(
    name="ingest_document",
    description="Ingest a document from S3 into the knowledge base with semantic chunking and vector indexing",
    tags={"rag", "documents", "ingestion", "knowledge-base", "capability:document_ingestion", "domain:manufacturing", "requires_auth:false"},
    meta={
        "version": "1.0", 
        "category": "document_management", 
        "author": "intelycx",
        "server_type": "rag",
        "capability": "document_ingestion",
        "domain": "manufacturing",
        "requires_auth": False,
        "priority": 2
    },
    annotations={
        "title": "Document Ingestion",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def ingest_document(
    bucket: Annotated[str, Field(
        description="S3 bucket containing the document",
        min_length=1
    )],
    key: Annotated[str, Field(
        description="S3 key/path to the document",
        min_length=1
    )],
    domain: KnowledgeDomain = KnowledgeDomain.MANUFACTURING,
    metadata: Annotated[Optional[Dict[str, Any]], Field(
        None,
        description="Additional metadata for the document"
    )] = None,
    force_reprocess: bool = False,
    ctx: Context = None
) -> IngestDocumentOutput:
    """
    Ingest a document from S3 into the knowledge base.
    
    This tool processes documents by:
    1. Downloading from S3 and extracting text content
    2. Chunking the content semantically for optimal retrieval
    3. Generating embeddings using AWS Bedrock Titan
    4. Indexing in OpenSearch for fast vector similarity search
    5. Storing metadata in PostgreSQL for tracking
    
    Args:
        bucket: S3 bucket containing the document
        key: S3 key/path to the document  
        domain: Knowledge domain (default: manufacturing)
        metadata: Additional metadata for the document
        force_reprocess: Force reprocessing if document exists
        
    Returns:
        Dictionary containing:
        - document_id: Unique identifier for the ingested document
        - status: Processing status (pending, processing, completed, failed)
        - message: Status message with details
        - processing_started: Whether processing was initiated
        
    Examples:
        # Ingest a manufacturing manual
        result = ingest_document("my-docs", "manuals/machine-guide.pdf")
        
        # Ingest with custom metadata
        result = ingest_document(
            "my-docs", 
            "procedures/safety.docx",
            metadata={"department": "safety", "version": "2.1"}
        )
    """
    # Enhanced multi-stage progress with structured logging
    await ctx.info(
        "📄 Starting document ingestion...",
        extra={
            "stage": "ingestion_start",
            "bucket": bucket,
            "key": key,
            "domain": domain.value,
            "force_reprocess": force_reprocess,
            "tool_version": "1.0"
        }
    )
    await ctx.report_progress(progress=5, total=100)
    
    logger.info(f"Document ingestion started: {bucket}/{key}")
    
    try:
        # Initialize services if needed
        _, _, _, document_processor, _ = await get_services()
        
        # Stage 1: Document validation (5-15%)
        await ctx.info(
            "🔍 Validating document location...",
            extra={"stage": "validation", "s3_path": f"s3://{bucket}/{key}"}
        )
        await ctx.report_progress(progress=15, total=100)
        
        # Stage 2: Document processing (15-85%)
        await ctx.info(
            "⚙️ Processing document content...",
            extra={"stage": "processing", "domain": domain.value}
        )
        await ctx.report_progress(progress=30, total=100)
        
        result = await document_processor.ingest_document(
            bucket=bucket,
            key=key,
            domain=domain,
            metadata=metadata or {},
            force_reprocess=force_reprocess
        )
        
        # Stage 3: Completion (85-100%)
        await ctx.info(
            f"✅ Document ingestion completed successfully!",
            extra={
                "stage": "ingestion_complete",
                "document_id": result.document_id,
                "status": result.status,
                "processing_started": result.processing_started
            }
        )
        await ctx.report_progress(progress=100, total=100)
        
        logger.info(f"Document ingestion completed: {result.document_id}")
        return result
        
    except Exception as e:
        error_msg = f"Document ingestion failed: {str(e)}"
        await ctx.error(
            f"❌ {error_msg}",
            extra={
                "stage": "ingestion_exception",
                "error_type": "exception",
                "exception_class": type(e).__name__,
                "bucket": bucket,
                "key": key
            }
        )
        logger.error(f"Document ingestion error: {str(e)}")
        
        return IngestDocumentOutput(
            document_id="",
            status=DocumentStatus.FAILED,
            message=error_msg,
            processing_started=False
        )


@mcp.tool(
    name="search_knowledge_base",
    description="Search the knowledge base using semantic similarity and hybrid search techniques",
    tags={"rag", "search", "knowledge-base", "semantic", "capability:knowledge_search", "domain:manufacturing", "requires_auth:false"},
    meta={
        "version": "1.0", 
        "category": "search", 
        "author": "intelycx",
        "server_type": "rag",
        "capability": "knowledge_search",
        "domain": "manufacturing",
        "requires_auth": False,
        "priority": 2
    },
    annotations={
        "title": "Knowledge Base Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def search_knowledge_base(
    query: Annotated[str, Field(
        description="Search query for finding relevant knowledge",
        min_length=1,
        max_length=500
    )],
    domain: Annotated[Optional[KnowledgeDomain], Field(
        None,
        description="Filter by knowledge domain (defaults to all domains)"
    )] = None,
    limit: Annotated[int, Field(
        5,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )] = 5,
    threshold: Annotated[float, Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold (0.0-1.0)"
    )] = 0.7,
    include_metadata: bool = True,
    ctx: Context = None
) -> SearchResponse:
    """
    Search the knowledge base using semantic similarity and hybrid search.
    
    This tool performs advanced search combining:
    1. Vector similarity using Titan embeddings for semantic understanding
    2. Keyword matching for exact terms and phrases
    3. Domain and metadata filtering for precise results
    4. Relevance scoring and ranking
    
    Args:
        query: Search query for finding relevant knowledge
        domain: Filter by knowledge domain (optional)
        limit: Maximum number of results to return (1-50)
        threshold: Minimum similarity threshold (0.0-1.0)
        include_metadata: Include document metadata in results
        
    Returns:
        Dictionary containing:
        - query: Original search query
        - results: Array of matching knowledge chunks with scores
        - total_results: Total number of matching results
        - search_time_ms: Search execution time in milliseconds
        - used_filters: Applied filters and parameters
        
    Examples:
        # Basic semantic search
        result = search_knowledge_base("machine maintenance procedures")
        
        # Filtered search with high precision
        result = search_knowledge_base(
            "safety protocols",
            domain="manufacturing",
            limit=10,
            threshold=0.8
        )
    """
    # Enhanced multi-stage progress with structured logging
    await ctx.info(
        "🔍 Starting knowledge base search...",
        extra={
            "stage": "search_start",
            "query": query,
            "domain": domain.value if domain else "all",
            "limit": limit,
            "threshold": threshold,
            "tool_version": "1.0"
        }
    )
    await ctx.report_progress(progress=10, total=100)
    
    logger.info(f"Knowledge base search started: '{query}'")
    
    try:
        # Initialize services if needed
        _, _, _, _, search_service = await get_services()
        
        # Stage 1: Query processing (10-30%)
        await ctx.info(
            "🧠 Processing search query...",
            extra={"stage": "query_processing", "query_length": len(query)}
        )
        await ctx.report_progress(progress=30, total=100)
        
        # Stage 2: Semantic search (30-80%)
        await ctx.info(
            "🔎 Performing semantic search...",
            extra={
                "stage": "semantic_search",
                "domain_filter": domain.value if domain else None,
                "similarity_threshold": threshold
            }
        )
        await ctx.report_progress(progress=60, total=100)
        
        result = await search_service.search(
            query=query,
            domain=domain,
            limit=limit,
            threshold=threshold,
            include_metadata=include_metadata
        )
        
        # Stage 3: Results processing (80-100%)
        await ctx.info(
            f"✅ Search completed successfully!",
            extra={
                "stage": "search_complete",
                "results_count": len(result.results),
                "total_results": result.total_results,
                "search_time_ms": result.search_time_ms,
                "avg_score": sum(r.score for r in result.results) / len(result.results) if result.results else 0
            }
        )
        await ctx.report_progress(progress=100, total=100)
        
        logger.info(f"Search completed: {len(result.results)} results in {result.search_time_ms}ms")
        return result
        
    except Exception as e:
        error_msg = f"Knowledge base search failed: {str(e)}"
        await ctx.error(
            f"❌ {error_msg}",
            extra={
                "stage": "search_exception",
                "error_type": "exception",
                "exception_class": type(e).__name__,
                "query": query
            }
        )
        logger.error(f"Search error: {str(e)}")
        
        return SearchResponse(
            query=query,
            results=[],
            total_results=0,
            search_time_ms=0.0,
            used_filters={"error": error_msg}
        )


@mcp.tool()
async def get_document_status(params: GetDocumentStatusInput) -> GetDocumentStatusOutput:
    """
    Get the processing status of a document in the knowledge base.
    """
    try:
        document = await db_manager.get_document(params.document_id)
        if not document:
            raise ValueError(f"Document not found: {params.document_id}")
        
        return GetDocumentStatusOutput(
            document_id=document.document_id,
            status=document.status,
            chunk_count=document.chunk_count,
            error_message=document.error_message,
            created_at=document.created_at,
            updated_at=document.updated_at
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to get document status: {e}")
        raise


@mcp.tool()
async def list_documents(params: ListDocumentsInput) -> ListDocumentsOutput:
    """
    List documents in the knowledge base with optional filtering.
    """
    try:
        documents, total_count = await db_manager.list_documents(
            domain=params.domain,
            status=params.status,
            limit=params.limit,
            offset=params.offset
        )
        
        return ListDocumentsOutput(
            documents=documents,
            total_count=total_count,
            has_more=(params.offset + len(documents)) < total_count
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to list documents: {e}")
        raise


@mcp.tool()
async def delete_document(params: DeleteDocumentInput) -> DeleteDocumentOutput:
    """
    Delete a document from the knowledge base.
    
    This removes the document and all its chunks from both the database and OpenSearch index.
    """
    try:
        success = await document_processor.delete_document(
            document_id=params.document_id,
            force=params.force
        )
        
        return DeleteDocumentOutput(
            document_id=params.document_id,
            deleted=success,
            message="Document deleted successfully" if success else "Failed to delete document"
        )
        
    except Exception as e:
        logger.error(f"❌ Failed to delete document: {e}")
        return DeleteDocumentOutput(
            document_id=params.document_id,
            deleted=False,
            message=f"Deletion failed: {str(e)}"
        )


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    # Don't log routine health checks to reduce noise
    # Only log on startup or if there are issues
    
    try:
        # Check service health (lazy init if needed)
        opensearch_ok = False
        database_ok = False
        bedrock_ok = False
        
        if opensearch_client:
            opensearch_ok = await opensearch_client.health_check()
        if db_manager:
            database_ok = await db_manager.health_check()
        if embedding_service:
            bedrock_ok = await embedding_service.health_check()
        
        health_status = {
            "status": "healthy" if all([opensearch_ok, database_ok, bedrock_ok]) else "degraded",
            "service": "intelycx-rag-mcp-server",
            "version": "1.0.0",
            "transport": "http",
            "opensearch_connected": opensearch_ok,
            "database_connected": database_ok,
            "bedrock_available": bedrock_ok,
            "timestamp": datetime.now().isoformat()
        }
        
        return JSONResponse(content=health_status, status_code=200)
        
    except Exception as e:
        # Don't log health check failures to reduce noise
        return JSONResponse(
            content={"status": "unhealthy", "error": str(e)},
            status_code=500
        )


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx RAG MCP Server with FastMCP")
    
    # Log configuration
    from .config import settings
    logger.info(f"📊 OpenSearch endpoint: {settings.opensearch_endpoint}")
    logger.info(f"🧠 Embedding model: {settings.embedding_model}")
    logger.info(f"🏭 Default domain: {settings.default_domain}")
    
    # Run HTTP server on port 8082
    mcp.run(transport="http", host="0.0.0.0", port=8082)


if __name__ == "__main__":
    main()
