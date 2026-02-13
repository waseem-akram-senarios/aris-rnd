"""
MCP Microservice - Model Context Protocol Server

This microservice provides an MCP server with FastAPI health endpoints
for document ingestion and semantic search in the ARIS RAG system.

Endpoints:
- GET /health - Health check endpoint
- GET /info - Service information
- SSE /sse - MCP Server-Sent Events endpoint

MCP Tools (3):
- search      — Query documents with quick/research/custom modes
- documents   — Full document lifecycle: CRUD on docs, chunks, and indexes
- system_info — System statistics and health metrics
"""

import os
import sys
import logging
import asyncio
from typing import Optional, Dict, Any
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
    instructions="""MCP server for the ARIS document management and search system.

3 tools available:

1. search      — Find information in documents. Modes: "quick" (fast), "research" (thorough), "search" (custom).
2. documents   — Full document lifecycle management. Actions for docs (list, get, create, update, delete),
                  chunks (list_chunks, get_chunk, create_chunk, update_chunk, delete_chunk),
                  and indexes (list_indexes, index_info, delete_index).
3. system_info — View system statistics (document counts, query metrics, costs).
"""
)


# ============================================================================
# MCP TOOLS — 3 clean tools
# ============================================================================

@mcp.tool()
def search(
    query: str,
    mode: str = "search",
    filters: Optional[Dict[str, Any]] = None,
    k: int = 10,
    search_mode: str = "hybrid",
    use_agentic_rag: Optional[bool] = None,
    include_answer: bool = True,
    response_language: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search documents and get AI-generated answers.

    Modes:
      "quick"    — Fast answer, fewer results (best for simple questions)
      "research" — Deep analysis with sub-queries (best for complex topics)
      "search"   — Full control over all parameters (default)

    Filters: {"source": "filename.pdf"} to restrict to a specific document.
    response_language: "English", "Spanish", etc. Defaults to English.
    """
    if mode == "quick":
        return mcp_engine.search(query=query, filters=filters, k=min(k, 5), search_mode="hybrid",
                                 use_agentic_rag=False, include_answer=include_answer,
                                 response_language=response_language)
    if mode == "research":
        return mcp_engine.search(query=query, filters=filters, k=max(k, 15), search_mode="hybrid",
                                use_agentic_rag=True, include_answer=include_answer,
                                response_language=response_language)
    uar = use_agentic_rag if use_agentic_rag is not None else True
    return mcp_engine.search(query=query, filters=filters, k=k, search_mode=search_mode,
                             use_agentic_rag=uar, include_answer=include_answer,
                             response_language=response_language)


@mcp.tool()
def documents(
    action: str,
    document_id: Optional[str] = None,
    index_name: Optional[str] = None,
    chunk_id: Optional[str] = None,
    content: Optional[str] = None,
    text: Optional[str] = None,
    file_content: Optional[str] = None,
    filename: Optional[str] = None,
    document_name: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    source: Optional[str] = None,
    page: Optional[int] = None,
    offset: int = 0,
    limit: int = 20,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Manage everything about documents: docs, chunks, and indexes.

    Document actions:
      "list"           — List all documents with status and chunk counts
      "get"            — Get details of one document (needs document_id)
      "create"         — Add a document: content (text/s3 uri) OR file_content+filename
      "update"         — Update document metadata (needs document_id)
      "delete"         — Remove a document and all its data (needs document_id)

    Chunk actions (need index_name):
      "list_chunks"    — List chunks in an index (optional: source, offset, limit)
      "get_chunk"      — Get one chunk (needs index_name + chunk_id)
      "create_chunk"   — Add a chunk (needs index_name + text)
      "update_chunk"   — Edit a chunk (needs index_name + chunk_id)
      "delete_chunk"   — Remove a chunk (needs index_name + chunk_id)

    Index actions:
      "list_indexes"   — List all vector indexes with sizes
      "index_info"     — Get index details (needs index_name)
      "delete_index"   — Delete an index and all chunks (needs index_name)
    """
    # --- Document actions ---
    if action == "list":
        return mcp_engine.list_documents()
    if action == "get":
        if not document_id:
            return {"success": False, "error": "document_id is required"}
        return mcp_engine.get_document(document_id)
    if action == "delete":
        if not document_id:
            return {"success": False, "error": "document_id is required"}
        return mcp_engine.delete_document(document_id)
    if action == "update":
        if not document_id:
            return {"success": False, "error": "document_id is required"}
        updates = {}
        if document_name is not None: updates["document_name"] = document_name
        if status is not None: updates["status"] = status
        if language is not None: updates["language"] = language
        if metadata is not None: updates["metadata"] = metadata
        if not updates:
            return {"success": False, "error": "Provide at least one field to update: document_name, status, language, or metadata"}
        return mcp_engine.update_document(document_id, updates)
    if action == "create":
        if file_content and filename:
            return mcp_engine.upload_document(file_content, filename, metadata)
        if content:
            return mcp_engine.ingest(content, metadata)
        return {"success": False, "error": "Provide content (text or s3://uri) OR file_content + filename"}

    # --- Chunk actions ---
    if action == "list_chunks":
        if not index_name:
            return {"success": False, "error": "index_name is required"}
        return mcp_engine.list_chunks(index_name, source=source or "manual_entry", offset=offset, limit=limit)
    if action == "get_chunk":
        if not index_name or not chunk_id:
            return {"success": False, "error": "index_name and chunk_id are required"}
        return mcp_engine.get_chunk(index_name, chunk_id)
    if action == "create_chunk":
        if not index_name:
            return {"success": False, "error": "index_name is required"}
        if not text:
            return {"success": False, "error": "text is required to create a chunk"}
        return mcp_engine.create_chunk(index_name, text, source=source or "manual_entry", page=page, metadata=metadata)
    if action == "update_chunk":
        if not index_name or not chunk_id:
            return {"success": False, "error": "index_name and chunk_id are required"}
        return mcp_engine.update_chunk(index_name, chunk_id, text=text, page=page, metadata=metadata)
    if action == "delete_chunk":
        if not index_name or not chunk_id:
            return {"success": False, "error": "index_name and chunk_id are required"}
        return mcp_engine.delete_chunk(index_name, chunk_id)

    # --- Index actions ---
    if action == "list_indexes":
        return mcp_engine.list_indexes()
    if action == "index_info":
        if not index_name:
            return {"success": False, "error": "index_name is required"}
        return mcp_engine.get_index_info(index_name)
    if action == "delete_index":
        if not index_name:
            return {"success": False, "error": "index_name is required"}
        return mcp_engine.delete_index(index_name)

    valid = "list, get, create, update, delete, list_chunks, get_chunk, create_chunk, update_chunk, delete_chunk, list_indexes, index_info, delete_index"
    return {"success": False, "error": f"Unknown action '{action}'. Valid actions: {valid}"}


@mcp.tool()
def system_info() -> Dict[str, Any]:
    """
    Get system statistics: document counts, chunk counts, query metrics, costs, and language distribution.
    """
    return mcp_engine.get_stats()


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
    """
    Validate /api/search request body.
    Returns (cleaned_body, error_message).  error_message is None when valid.
    """
    query = (body.get("query") or "").strip()
    if not query:
        return None, "query is required and cannot be empty"
    k = body.get("k", 5)
    if not isinstance(k, int) or k < 1 or k > 50:
        return None, "k must be an integer between 1 and 50"
    search_mode = body.get("search_mode", "hybrid")
    if search_mode not in ("semantic", "keyword", "hybrid"):
        return None, f"search_mode must be one of: semantic, keyword, hybrid"
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
    logger.info(f"   Tools: 3 MCP tools (search, documents, system_info)")
    
    # Get the MCP's HTTP app (Starlette-based)
    mcp_http_app = mcp.http_app()
    
    # Create health check handler
    async def health_handler(request):
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "status": "healthy",
            "service": "mcp",
            "server_name": mcp.name,
            "tools": ["search", "documents", "system_info"],
            "total_tools": 3,
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
            "version": "5.0.0",
            "description": "MCP server for document management and AI-powered search",
            "tools": {
                "search": "Search documents with quick/research/custom modes",
                "documents": "Full document lifecycle: docs, chunks, and indexes (13 actions)",
                "system_info": "System statistics and health metrics"
            },
            "total_tools": 3,
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
            "total_tools": 3,
            "tools": [
                {"name": "search", "description": "Search documents and get AI-generated answers (modes: quick, research, search)"},
                {"name": "documents", "description": "Full document lifecycle: docs, chunks, and indexes (13 actions)"},
                {"name": "system_info", "description": "View system statistics (documents, queries, costs)"}
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
    # Input validation is applied before calling MCPEngine.
    # ----------------------------------------------------------------
    async def api_search_handler(request):
        """Search documents via MCP Engine (validated)."""
        try:
            body = await request.json()
            body, err = _validate_search_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            result = mcp_engine.search(
                query=body["query"],
                filters=body.get("filters"),
                k=body["k"],
                search_mode=body["search_mode"],
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
        """Ingest text/S3-URI content via MCP Engine (validated)."""
        try:
            body = await request.json()
            body, err = _validate_ingest_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            result = mcp_engine.ingest(
                content=body["content"],
                metadata=body.get("metadata"),
            )
            return JSONResponse(result)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            logger.error(f"/api/ingest error: {type(e).__name__}: {e}")
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_upload_handler(request):
        """Upload a document via MCP Engine (validated)."""
        try:
            body = await request.json()
            body, err = _validate_upload_body(body)
            if err:
                return JSONResponse({"success": False, "error": err}, status_code=400)
            result = mcp_engine.upload_document(
                file_content=body["file_content"],
                filename=body["filename"],
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
            text = (body.get("text") or "").strip()
            if not text:
                return JSONResponse({"success": False, "error": "text is required to create a chunk"}, status_code=400)
            return JSONResponse(mcp_engine.create_chunk(
                idx, text,
                source=body.get("source", "manual_entry"),
                page=body.get("page"),
                metadata=body.get("metadata"),
            ))
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=500)

    async def api_update_chunk_handler(request):
        try:
            idx = request.path_params["index_name"]
            cid = request.path_params["chunk_id"]
            body = await request.json()
            text = body.get("text")
            page = body.get("page")
            metadata = body.get("metadata")
            if text is None and page is None and metadata is None:
                return JSONResponse({"success": False, "error": "Provide at least one field: text, page, or metadata"}, status_code=400)
            return JSONResponse(mcp_engine.update_chunk(
                idx, cid,
                text=text,
                page=page,
                metadata=metadata,
            ))
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
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
    logger.info(f"   Tools: 3 MCP tools (search, documents, system_info)")
    
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", host=host, port=port)


if __name__ == "__main__":
    # Determine mode from environment
    # 'combined' (default) - REST endpoints + MCP SSE on one port
    # 'mcp' - MCP server only (SSE/stdio)
    mode = os.getenv("MCP_MODE", "combined")
    
    if mode == "mcp":
        run_mcp_only()
    else:
        run_combined_server()

