"""
ARIS RAG MCP Server — Model Context Protocol for Document Intelligence

FastMCP server providing AI-powered document search, ingestion lifecycle
management, and system monitoring for the ARIS RAG platform.

Tools (7):
- search_knowledge_base    — AI-powered semantic search with hybrid search + FlashRank reranking
- ingest_document          — Ingest a document (text, file, or S3 URI) into the knowledge base
- list_documents           — List all documents with status and chunk counts
- get_document_status      — Get processing status and details of a specific document
- delete_document          — Remove a document and all its data from the system
- manage_index             — Manage vector indexes: list, inspect, or delete
- get_system_stats         — System monitoring: document counts, query metrics, costs
"""

import os
import sys
import logging
from typing import Optional, Dict, Any, List, Annotated
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Filter to exclude health check requests from uvicorn access logs
class HealthCheckAccessLogFilter(logging.Filter):
    """Filter to exclude health check requests from access logs."""
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            if 'GET /health' in msg or '"GET /health' in msg:
                return False
        return True

# Apply filter to uvicorn access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthCheckAccessLogFilter())


# Import FastMCP
try:
    from fastmcp import FastMCP, Context
except ImportError:
    raise ImportError(
        "FastMCP is not installed. Install it with: pip install fastmcp"
    )

from pydantic import Field


# Import MCP Engine
from services.mcp.engine import MCPEngine

# Global engine — lazy init
_engine: Optional[MCPEngine] = None


def get_engine() -> MCPEngine:
    """Get or create the MCP engine (lazy initialization)."""
    global _engine
    if _engine is None:
        logger.info("🚀 Initializing ARIS RAG MCP Engine...")
        _engine = MCPEngine()
        logger.info("✅ MCP Engine initialized successfully")
    return _engine


# Initialize the MCP server
mcp = FastMCP(
    name="ARIS RAG MCP Server",
    on_duplicate_tools="warn",
    instructions="""ARIS RAG MCP Server — AI-powered document intelligence platform.

7 tools available:

1. search_knowledge_base  — Semantic search with hybrid retrieval + FlashRank reranking.
                            Modes: "quick" (fast), "research" (deep analysis), "search" (custom).
2. ingest_document        — Ingest documents (text, file upload, or S3 URI) into the knowledge base.
3. list_documents         — List all documents with status, language, and chunk counts.
4. get_document_status    — Get full details and processing status of a document.
5. delete_document        — Permanently remove a document and all its indexed data.
6. manage_index           — Manage vector indexes: list all, get details, or delete an index.
7. get_system_stats       — Real-time system monitoring: document counts, query metrics, API costs.
"""
)


# ============================================================================
# TOOL 1: search_knowledge_base
# ============================================================================

@mcp.tool(
    name="search_knowledge_base",
    description="Search the knowledge base using AI-powered hybrid search (semantic + keyword) with FlashRank cross-encoder reranking",
    tags={"rag", "search", "retrieval", "knowledge-base", "semantic",
          "capability:knowledge_search", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "search",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "knowledge_search",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 1
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
        description="Search query for finding relevant knowledge in documents",
        min_length=1,
        max_length=2000
    )],
    mode: Annotated[str, Field(
        description='Search mode: "quick" (fast, k=5), "research" (deep, agentic RAG), "search" (custom)'
    )] = "search",
    k: Annotated[int, Field(
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )] = 10,
    search_mode: Annotated[str, Field(
        description='Underlying search strategy: "hybrid" (default), "semantic", or "keyword"'
    )] = "hybrid",
    filters: Annotated[Optional[Dict[str, Any]], Field(
        None,
        description='Filter results, e.g. {"source": "filename.pdf"} to restrict to one document'
    )] = None,
    use_agentic_rag: Annotated[Optional[bool], Field(
        None,
        description="Force agentic RAG on/off. None = auto (on for research mode)"
    )] = None,
    include_answer: Annotated[bool, Field(
        description="Generate an AI-synthesized answer from the results"
    )] = True,
    response_language: Annotated[Optional[str], Field(
        None,
        description='Language for the answer: "English", "Spanish", etc. Defaults to English.'
    )] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Search documents and get AI-generated answers using RAG.

    Uses hybrid search (semantic + keyword) with FlashRank cross-encoder
    reranking for high accuracy. Returns ranked citations with confidence
    scores, page numbers, and source attribution.

    Modes:
      "quick"    — Fast answer, fewer results (k=5, no agentic RAG)
      "research" — Deep analysis with sub-queries (k=15+, agentic RAG)
      "search"   — Full control over all parameters (default)

    Examples:
        search_knowledge_base("What is the LME approach?")
        search_knowledge_base("safety protocols", mode="research", k=15)
        search_knowledge_base("maintenance", filters={"source": "manual.pdf"})
    """
    engine = get_engine()

    if ctx:
        await ctx.info(
            "🔍 Starting knowledge base search...",
            extra={
                "stage": "search_start",
                "query": query[:100],
                "mode": mode,
                "k": k,
                "search_mode": search_mode,
                "tool_version": "2.0"
            }
        )
        await ctx.report_progress(progress=10, total=100)

    try:
        if ctx:
            await ctx.info("🧠 Processing query and retrieving documents...",
                           extra={"stage": "retrieval"})
            await ctx.report_progress(progress=30, total=100)

        if mode == "quick":
            result = engine.search(
                query=query, filters=filters, k=min(k, 5),
                search_mode="hybrid", use_agentic_rag=False,
                include_answer=include_answer, response_language=response_language
            )
        elif mode == "research":
            result = engine.search(
                query=query, filters=filters, k=max(k, 15),
                search_mode="hybrid", use_agentic_rag=True,
                include_answer=include_answer, response_language=response_language
            )
        else:
            uar = use_agentic_rag if use_agentic_rag is not None else True
            result = engine.search(
                query=query, filters=filters, k=k,
                search_mode=search_mode, use_agentic_rag=uar,
                include_answer=include_answer, response_language=response_language
            )

        if ctx:
            await ctx.info(
                f"✅ Search completed — {result.get('total_results', 0)} results found",
                extra={
                    "stage": "search_complete",
                    "total_results": result.get("total_results", 0),
                    "sources": result.get("sources", []),
                }
            )
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Knowledge base search failed: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "search_exception",
                                   "exception_class": type(e).__name__})
        logger.error(f"search_knowledge_base error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 2: ingest_document
# ============================================================================

@mcp.tool(
    name="ingest_document",
    description="Ingest a document into the knowledge base with automatic chunking, embedding, and vector indexing",
    tags={"rag", "documents", "ingestion", "knowledge-base",
          "capability:document_ingestion", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "document_management",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "document_ingestion",
        "domain": "document_intelligence",
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
    content: Annotated[Optional[str], Field(
        None,
        description="Text content or S3 URI (s3://bucket/key) to ingest"
    )] = None,
    file_content: Annotated[Optional[str], Field(
        None,
        description="Base64-encoded file content for file upload"
    )] = None,
    filename: Annotated[Optional[str], Field(
        None,
        description="Filename for the uploaded file (required with file_content)"
    )] = None,
    metadata: Annotated[Optional[Dict[str, Any]], Field(
        None,
        description="Additional metadata to attach to the document"
    )] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Ingest a document into the ARIS knowledge base.

    The system automatically: parses the document (PDF/TXT/images),
    detects language, chunks text into ~800-token pieces, generates
    embeddings via OpenAI, and indexes everything in OpenSearch.

    Two ingestion methods:
      1. content — Raw text or S3 URI (s3://bucket/key)
      2. file_content + filename — Base64-encoded file upload

    Examples:
        ingest_document(content="Important policy text here...")
        ingest_document(content="s3://my-bucket/docs/manual.pdf")
        ingest_document(file_content="<base64>", filename="report.pdf")
    """
    engine = get_engine()

    if ctx:
        await ctx.info("📄 Starting document ingestion...",
                       extra={"stage": "ingestion_start",
                              "has_content": bool(content),
                              "has_file": bool(file_content and filename),
                              "tool_version": "2.0"})
        await ctx.report_progress(progress=10, total=100)

    try:
        if file_content and filename:
            if ctx:
                await ctx.info(f"📤 Uploading file: {filename}",
                               extra={"stage": "file_upload", "filename": filename})
                await ctx.report_progress(progress=40, total=100)
            result = engine.upload_document(file_content, filename, metadata)
        elif content:
            if ctx:
                await ctx.info("⚙️ Processing text content...",
                               extra={"stage": "text_processing",
                                      "content_length": len(content)})
                await ctx.report_progress(progress=40, total=100)
            result = engine.ingest(content, metadata)
        else:
            return {"success": False,
                    "error": "Provide content (text or s3://uri) OR file_content + filename"}

        if ctx:
            await ctx.info(
                f"✅ Document ingested successfully!",
                extra={"stage": "ingestion_complete",
                       "document_id": result.get("document_id")}
            )
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Document ingestion failed: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "ingestion_exception",
                                   "exception_class": type(e).__name__})
        logger.error(f"ingest_document error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 3: list_documents
# ============================================================================

@mcp.tool(
    name="list_documents",
    description="List all documents in the knowledge base with status, language, and chunk counts",
    tags={"rag", "documents", "knowledge-base",
          "capability:document_listing", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "document_management",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "document_listing",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 3
    },
    annotations={
        "title": "List Documents",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def list_documents(
    ctx: Context = None
) -> Dict[str, Any]:
    """
    List all documents in the ARIS knowledge base.

    Returns document IDs, filenames, processing status, chunk counts,
    detected language, and index information for every document.

    Examples:
        list_documents()
    """
    engine = get_engine()

    if ctx:
        await ctx.info("📋 Listing documents...", extra={"stage": "list_start"})
        await ctx.report_progress(progress=30, total=100)

    try:
        result = engine.list_documents()

        if ctx:
            total = result.get("total", 0)
            await ctx.info(f"✅ Found {total} documents",
                           extra={"stage": "list_complete", "total": total})
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Failed to list documents: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "list_exception"})
        logger.error(f"list_documents error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 4: get_document_status
# ============================================================================

@mcp.tool(
    name="get_document_status",
    description="Get the processing status and details of a specific document",
    tags={"rag", "documents", "knowledge-base",
          "capability:document_status", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "document_management",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "document_status",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 3
    },
    annotations={
        "title": "Get Document Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_document_status(
    document_id: Annotated[str, Field(
        description="Unique document identifier",
        min_length=1
    )],
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Get the processing status and details of a document.

    Returns document name, status, chunk count, language, index names,
    and metadata for the specified document ID.

    Examples:
        get_document_status("dd6364bb-e0ae-4ab3-ab05-3d92861d8ca5")
    """
    engine = get_engine()

    if ctx:
        await ctx.info(f"🔎 Getting status for document {document_id[:12]}...",
                       extra={"stage": "status_start", "document_id": document_id})
        await ctx.report_progress(progress=30, total=100)

    try:
        result = engine.get_document(document_id)

        if ctx:
            await ctx.info(f"✅ Document status retrieved",
                           extra={"stage": "status_complete",
                                  "document_id": document_id})
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Failed to get document status: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "status_exception"})
        logger.error(f"get_document_status error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 5: delete_document
# ============================================================================

@mcp.tool(
    name="delete_document",
    description="Delete a document and all its indexed data from the knowledge base",
    tags={"rag", "documents", "knowledge-base",
          "capability:document_deletion", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "document_management",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "document_deletion",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 3
    },
    annotations={
        "title": "Delete Document",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def delete_document(
    document_id: Annotated[str, Field(
        description="Unique document identifier to delete",
        min_length=1
    )],
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Permanently delete a document and all its data from the knowledge base.

    Removes the document record, all text chunks, embeddings, and images
    from both OpenSearch and the document registry.

    This operation is destructive and cannot be undone.

    Examples:
        delete_document("dd6364bb-e0ae-4ab3-ab05-3d92861d8ca5")
    """
    engine = get_engine()

    if ctx:
        await ctx.info(f"🗑️ Deleting document {document_id[:12]}...",
                       extra={"stage": "delete_start", "document_id": document_id})
        await ctx.report_progress(progress=20, total=100)

    try:
        result = engine.delete_document(document_id)

        if ctx:
            success = result.get("success", False)
            icon = "✅" if success else "❌"
            await ctx.info(f"{icon} Delete {'completed' if success else 'failed'}",
                           extra={"stage": "delete_complete",
                                  "document_id": document_id,
                                  "success": success})
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Failed to delete document: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "delete_exception"})
        logger.error(f"delete_document error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 6: manage_index
# ============================================================================

@mcp.tool(
    name="manage_index",
    description="Manage vector indexes: list all indexes, get index details, or delete an index",
    tags={"rag", "indexes", "knowledge-base",
          "capability:index_management", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "index_management",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "index_management",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 4
    },
    annotations={
        "title": "Index Management",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def manage_index(
    action: Annotated[str, Field(
        description='Action: "list" (all indexes), "info" (one index), "delete" (remove index)'
    )],
    index_name: Annotated[Optional[str], Field(
        None,
        description="Index name (required for info and delete actions)"
    )] = None,
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Manage OpenSearch vector indexes.

    Actions:
      "list"   — List all vector indexes with chunk counts and sizes
      "info"   — Get detailed information about a specific index
      "delete" — Delete an index and all its chunks (destructive!)

    Examples:
        manage_index(action="list")
        manage_index(action="info", index_name="aris-doc-abc123")
        manage_index(action="delete", index_name="aris-doc-abc123")
    """
    engine = get_engine()

    if ctx:
        await ctx.info(f"🗂️ Managing indexes: {action}...",
                       extra={"stage": "index_start", "action": action,
                              "index_name": index_name})
        await ctx.report_progress(progress=20, total=100)

    try:
        if action == "list":
            result = engine.list_indexes()
        elif action == "info":
            if not index_name:
                return {"success": False, "error": "index_name is required for 'info' action"}
            result = engine.get_index_info(index_name)
        elif action == "delete":
            if not index_name:
                return {"success": False, "error": "index_name is required for 'delete' action"}
            result = engine.delete_index(index_name)
        else:
            return {"success": False,
                    "error": f"Unknown action '{action}'. Valid: list, info, delete"}

        if ctx:
            await ctx.info(f"✅ Index {action} completed",
                           extra={"stage": "index_complete", "action": action})
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Index management failed: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "index_exception"})
        logger.error(f"manage_index error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# TOOL 7: get_system_stats
# ============================================================================

@mcp.tool(
    name="get_system_stats",
    description="Get real-time system statistics: document counts, query metrics, performance, and API costs",
    tags={"monitoring", "stats", "health",
          "capability:system_monitoring", "domain:document_intelligence", "requires_auth:false"},
    meta={
        "version": "2.0",
        "category": "monitoring",
        "author": "intelycx",
        "server_type": "rag",
        "capability": "system_monitoring",
        "domain": "document_intelligence",
        "requires_auth": False,
        "priority": 5
    },
    annotations={
        "title": "System Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def get_system_stats(
    ctx: Context = None
) -> Dict[str, Any]:
    """
    Get real-time system monitoring statistics.

    Returns:
    - Document counts, chunk counts, page counts, image counts
    - Language distribution across documents
    - Query performance: total queries, success rate, avg response time
    - API costs: embedding and query costs in USD
    - Error summary

    Examples:
        get_system_stats()
    """
    engine = get_engine()

    if ctx:
        await ctx.info("📊 Gathering system statistics...",
                       extra={"stage": "stats_start", "tool_version": "2.0"})
        await ctx.report_progress(progress=20, total=100)

    try:
        result = engine.get_stats()

        if ctx:
            await ctx.info("✅ Statistics retrieved successfully",
                           extra={"stage": "stats_complete"})
            await ctx.report_progress(progress=100, total=100)

        return result

    except Exception as e:
        error_msg = f"Failed to get system stats: {str(e)}"
        if ctx:
            await ctx.error(f"❌ {error_msg}",
                            extra={"stage": "stats_exception"})
        logger.error(f"get_system_stats error: {e}")
        return {"success": False, "error": error_msg}


# ============================================================================
# HEALTH CHECK — @mcp.custom_route (matches Intelycx pattern)
# ============================================================================

from starlette.requests import Request
from starlette.responses import JSONResponse


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    try:
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "status": "healthy",
            "service": "aris-rag-mcp-server",
            "server_name": "ARIS RAG MCP Server",
            "version": "6.0.0",
            "transport": "http",
            "tools": [
                "search_knowledge_base",
                "ingest_document",
                "list_documents",
                "get_document_status",
                "delete_document",
                "manage_index",
                "get_system_stats",
            ],
            "total_tools": 7,
            "accuracy_features": {
                "hybrid_search": ARISConfig.DEFAULT_USE_HYBRID_SEARCH,
                "reranking": ARISConfig.ENABLE_RERANKING,
                "agentic_rag": ARISConfig.DEFAULT_USE_AGENTIC_RAG,
                "auto_translate": ARISConfig.ENABLE_AUTO_TRANSLATE
            },
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return JSONResponse(
            {"status": "unhealthy", "error": str(e)},
            status_code=500
        )


# ============================================================================
# HELPER — sync manager singleton
# ============================================================================

_mcp_sync_manager = None


def get_mcp_sync_manager():
    """Get or create sync manager for MCP service."""
    global _mcp_sync_manager
    if _mcp_sync_manager is None:
        from shared.utils.sync_manager import get_sync_manager
        _mcp_sync_manager = get_sync_manager("mcp")
    return _mcp_sync_manager


# ============================================================================
# INPUT VALIDATION — shared validators for Starlette handlers
# ============================================================================

def _validate_search_body(body: dict) -> tuple:
    """Validate /api/search request body."""
    query = (body.get("query") or "").strip()
    if not query:
        return None, "query is required and cannot be empty"
    k = body.get("k", 5)
    if not isinstance(k, int) or k < 1 or k > 50:
        return None, "k must be an integer between 1 and 50"
    search_mode = body.get("search_mode", "hybrid")
    if search_mode not in ("semantic", "keyword", "hybrid"):
        return None, "search_mode must be one of: semantic, keyword, hybrid"
    body["query"] = query
    body["k"] = k
    body["search_mode"] = search_mode
    return body, None


def _validate_ingest_body(body: dict) -> tuple:
    """Validate /api/ingest request body."""
    content = (body.get("content") or "").strip()
    if not content:
        return None, "content is required and cannot be empty"
    body["content"] = content
    return body, None


def _validate_upload_body(body: dict) -> tuple:
    """Validate /api/upload request body."""
    file_content = (body.get("file_content") or "").strip()
    filename = (body.get("filename") or "").strip()
    if not file_content:
        return None, "file_content is required"
    if not filename:
        return None, "filename is required"
    body["file_content"] = file_content
    body["filename"] = filename
    return body, None


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def run_combined_server():
    """
    Run combined FastAPI + MCP server.
    Uses FastMCP's http_app as the base and mounts REST routes on it.
    """
    import uvicorn
    from starlette.routing import Route

    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")

    logger.info(f"🚀 Starting ARIS RAG MCP Server on {host}:{port}")
    logger.info(f"   MCP endpoint: http://{host}:{port}/mcp")
    logger.info(f"   Health: http://{host}:{port}/health")
    logger.info(f"   Tools: 7 MCP tools (Intelycx pattern)")

    # Get the MCP's HTTP app (Starlette-based)
    mcp_http_app = mcp.http_app()

    engine = get_engine()

    # ------------------------------------------------------------------
    # Info / tools / sse redirect
    # ------------------------------------------------------------------
    async def info_handler(request):
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "service": "ARIS RAG MCP Server",
            "version": "6.0.0",
            "description": "MCP server for document management and AI-powered search",
            "tools": {
                "search_knowledge_base": "AI-powered semantic search with hybrid retrieval + FlashRank reranking",
                "ingest_document": "Ingest documents (text, file, S3) into the knowledge base",
                "list_documents": "List all documents with status and chunk counts",
                "get_document_status": "Get processing status of a specific document",
                "delete_document": "Remove a document and all its indexed data",
                "manage_index": "Manage vector indexes: list, inspect, or delete",
                "get_system_stats": "System monitoring: document counts, query metrics, costs"
            },
            "total_tools": 7,
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
                "mcp": "/mcp"
            }
        })

    async def tools_handler(request):
        return JSONResponse({
            "total_tools": 7,
            "tools": [
                {"name": "search_knowledge_base", "description": "AI-powered semantic search with hybrid retrieval + FlashRank reranking (modes: quick, research, search)"},
                {"name": "ingest_document", "description": "Ingest documents (text, file, S3) into the knowledge base with automatic chunking and embedding"},
                {"name": "list_documents", "description": "List all documents with status, language, and chunk counts"},
                {"name": "get_document_status", "description": "Get processing status and details of a specific document"},
                {"name": "delete_document", "description": "Permanently delete a document and all its indexed data"},
                {"name": "manage_index", "description": "Manage vector indexes: list all, get details, or delete an index"},
                {"name": "get_system_stats", "description": "System monitoring: document counts, query performance, costs, and health metrics"}
            ]
        })

    async def sse_redirect(request):
        from starlette.responses import RedirectResponse
        query_string = request.url.query
        redirect_url = "/mcp" + ("?" + query_string if query_string else "")
        return RedirectResponse(url=redirect_url, status_code=307)

    # ------------------------------------------------------------------
    # Sync handlers
    # ------------------------------------------------------------------
    async def sync_force_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            result = sync_mgr.force_full_sync()
            from services.mcp.engine import _get_cached_document_registry
            if hasattr(_get_cached_document_registry, '_registry'):
                del _get_cached_document_registry._registry
            logger.info("✅ [MCP] Force sync completed, caches cleared")
            return JSONResponse({"success": True, "message": "MCP sync completed", "result": result})
        except Exception as e:
            logger.error(f"[MCP] Force sync failed: {e}")
            return JSONResponse({"success": False, "error": str(e)})

    async def sync_status_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            return JSONResponse({"success": True, "service": "mcp", "status": sync_mgr.get_sync_status()})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    async def sync_check_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            return JSONResponse({"success": True, "checked": True, "result": sync_mgr.check_and_sync()})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    async def sync_instant_handler(request):
        try:
            sync_mgr = get_mcp_sync_manager()
            return JSONResponse({"success": True, "message": "Instant sync completed", "result": sync_mgr.instant_sync()})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)})

    # ------------------------------------------------------------------
    # REST API handlers (for Streamlit UI and external REST clients)
    # ------------------------------------------------------------------
    async def api_search_handler(request):
        try:
            body = await request.json()
            body, err = _validate_search_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            result = engine.search(
                query=body["query"], filters=body.get("filters"),
                k=body["k"], search_mode=body["search_mode"],
                use_agentic_rag=body.get("use_agentic_rag", True),
                include_answer=body.get("include_answer", True),
                response_language=body.get("response_language"),
            )
            return JSONResponse(result)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            logger.error(f"/api/search error: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_ingest_handler(request):
        try:
            body = await request.json()
            body, err = _validate_ingest_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            return JSONResponse(engine.ingest(content=body["content"], metadata=body.get("metadata")))
        except Exception as e:
            logger.error(f"/api/ingest error: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_upload_handler(request):
        try:
            body = await request.json()
            body, err = _validate_upload_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            return JSONResponse(engine.upload_document(
                file_content=body["file_content"], filename=body["filename"],
                metadata=body.get("metadata")))
        except Exception as e:
            logger.error(f"/api/upload error: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_list_documents_handler(request):
        try:
            return JSONResponse(engine.list_documents())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_document_handler(request):
        try:
            return JSONResponse(engine.get_document(request.path_params["document_id"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_update_document_handler(request):
        try:
            body = await request.json()
            return JSONResponse(engine.update_document(request.path_params["document_id"], body))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_document_handler(request):
        try:
            return JSONResponse(engine.delete_document(request.path_params["document_id"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_stats_handler(request):
        try:
            return JSONResponse(engine.get_stats())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_list_indexes_handler(request):
        try:
            return JSONResponse(engine.list_indexes())
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_index_handler(request):
        try:
            return JSONResponse(engine.get_index_info(request.path_params["index_name"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_index_handler(request):
        try:
            return JSONResponse(engine.delete_index(request.path_params["index_name"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_list_chunks_handler(request):
        try:
            idx = request.path_params["index_name"]
            params = request.query_params
            return JSONResponse(engine.list_chunks(
                idx, source=params.get("source"),
                offset=int(params.get("offset", 0)),
                limit=int(params.get("limit", 20))))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_get_chunk_handler(request):
        try:
            return JSONResponse(engine.get_chunk(
                request.path_params["index_name"], request.path_params["chunk_id"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_create_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            body = await request.json()
            text = (body.get("text") or "").strip()
            if not text:
                return JSONResponse({"success": False, "error": "text is required"}, status_code=400)
            return JSONResponse(engine.create_chunk(
                idx, text, source=body.get("source", "manual_entry"),
                page=body.get("page"), metadata=body.get("metadata")))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_update_chunk_handler(request):
        try:
            body = await request.json()
            if body.get("text") is None and body.get("page") is None and body.get("metadata") is None:
                return JSONResponse({"success": False, "error": "Provide text, page, or metadata"}, status_code=400)
            return JSONResponse(engine.update_chunk(
                request.path_params["index_name"], request.path_params["chunk_id"],
                text=body.get("text"), page=body.get("page"), metadata=body.get("metadata")))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_delete_chunk_handler(request):
        try:
            return JSONResponse(engine.delete_chunk(
                request.path_params["index_name"], request.path_params["chunk_id"]))
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    # ------------------------------------------------------------------
    # Mount routes
    # ------------------------------------------------------------------
    routes_to_add = [
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

    logger.info(f"   Routes: /health, /info, /tools, /api/*, /sync/*, /sse → /mcp")
    uvicorn.run(mcp_http_app, host=host, port=port)


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting ARIS RAG MCP Server with FastMCP")
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("MCP_SERVER_PORT", "8503")))


if __name__ == "__main__":
    mode = os.getenv("MCP_MODE", "combined")
    if mode == "mcp":
        main()
    else:
        run_combined_server()
