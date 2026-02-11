"""
MCP Microservice - Model Context Protocol Server

This microservice provides an MCP server with FastAPI health endpoints
for document ingestion and semantic search in the ARIS RAG system.

Endpoints:
- GET /health - Health check endpoint
- GET /info - Service information
- SSE /sse - MCP Server-Sent Events endpoint

MCP Tools:
- rag_query, rag_documents, rag_indexes, rag_chunks, rag_stats (5 consolidated tools)
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

4 CONSOLIDATED TOOLS (all 18 functionalities covered):

1. rag_query - Search with mode: "quick"|"research"|"search"
2. rag_documents - Document & Chunk CRUD with action: "list"|"get"|"create"|"update"|"delete"|"list_chunks"|"get_chunk"|"create_chunk"|"update_chunk"|"delete_chunk"
3. rag_indexes - Manage indexes with action: "list"|"info"|"delete"
4. rag_stats - System statistics
"""
)


# ============================================================================
# MCP TOOLS (4 consolidated tools - all 18 functionalities covered)
# ============================================================================

@mcp.tool()
def rag_query(
    query: str,
    mode: str = "search",
    filters: Optional[Dict[str, Any]] = None,
    k: int = 10,
    search_mode: str = "hybrid",
    use_agentic_rag: Optional[bool] = None,
    include_answer: bool = True
) -> Dict[str, Any]:
    """
    Search the RAG system. Use mode to choose speed vs depth.
    
    mode: "quick" = fast/simple (gpt-4o-mini), "research" = deep analysis (gpt-4o + agentic),
          "search" = customizable (default). Other params: filters, k, search_mode, include_answer.
    """
    if mode == "quick":
        return mcp_engine.search(query=query, filters=filters, k=min(k, 5), search_mode="hybrid",
                                 use_agentic_rag=False, include_answer=include_answer)
    if mode == "research":
        return mcp_engine.search(query=query, filters=filters, k=max(k, 15), search_mode="hybrid",
                                use_agentic_rag=True, include_answer=include_answer)
    uar = use_agentic_rag if use_agentic_rag is not None else True
    return mcp_engine.search(query=query, filters=filters, k=k, search_mode=search_mode,
                             use_agentic_rag=uar, include_answer=include_answer)


@mcp.tool()
def rag_documents(
    action: str,
    document_id: Optional[str] = None,
    content: Optional[str] = None,
    file_content: Optional[str] = None,
    filename: Optional[str] = None,
    document_name: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    index_name: Optional[str] = None,
    chunk_id: Optional[str] = None,
    text: Optional[str] = None,
    source: str = "manual_entry",
    page: Optional[int] = None,
    offset: int = 0,
    limit: int = 20,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Document & Chunk CRUD — unified tool.

    DOCUMENT actions (no index_name needed):
      action="list"   — list all documents
      action="get"    — get document details (document_id required)
      action="create" — ingest text/S3 via content, OR upload binary via file_content+filename
      action="update" — update document metadata (document_id required; optional document_name, status, language, metadata)
      action="delete" — delete a document (document_id required)

    CHUNK actions (index_name required):
      action="list_chunks"   — list chunks in an index (optional source, offset, limit)
      action="get_chunk"     — get a single chunk (chunk_id required)
      action="create_chunk"  — create a chunk (text required; optional source, page, metadata)
      action="update_chunk"  — update a chunk (chunk_id required; optional text, page, metadata)
      action="delete_chunk"  — delete a chunk (chunk_id required)
    """
    # ---- Document actions ----
    if action == "list":
        return mcp_engine.list_documents()
    if action == "get":
        if not document_id:
            return {"success": False, "error": "document_id required for action=get"}
        return mcp_engine.get_document(document_id)
    if action == "delete":
        if not document_id:
            return {"success": False, "error": "document_id required for action=delete"}
        return mcp_engine.delete_document(document_id)
    if action == "update":
        if not document_id:
            return {"success": False, "error": "document_id required for action=update"}
        updates = {}
        if document_name is not None: updates["document_name"] = document_name
        if status is not None: updates["status"] = status
        if language is not None: updates["language"] = language
        if metadata is not None: updates["metadata"] = metadata
        if not updates:
            return {"success": False, "message": "Provide at least one of: document_name, status, language, metadata"}
        return mcp_engine.update_document(document_id, updates)
    if action == "create":
        if file_content and filename:
            return mcp_engine.upload_document(file_content, filename, metadata)
        if content:
            return mcp_engine.ingest(content, metadata)
        return {"success": False, "error": "For create use content (text or s3://uri) OR file_content+filename"}

    # ---- Chunk actions (require index_name) ----
    if action in ("list_chunks", "get_chunk", "create_chunk", "update_chunk", "delete_chunk"):
        if not index_name:
            return {"success": False, "error": f"index_name required for action={action}"}

    if action == "list_chunks":
        return mcp_engine.list_chunks(index_name, source=source, offset=offset, limit=limit)
    if action == "get_chunk":
        if not chunk_id:
            return {"success": False, "error": "chunk_id required for action=get_chunk"}
        return mcp_engine.get_chunk(index_name, chunk_id)
    if action == "delete_chunk":
        if not chunk_id:
            return {"success": False, "error": "chunk_id required for action=delete_chunk"}
        return mcp_engine.delete_chunk(index_name, chunk_id)
    if action == "create_chunk":
        if not text:
            return {"success": False, "error": "text required for action=create_chunk"}
        return mcp_engine.create_chunk(index_name, text, source=source, page=page, metadata=metadata)
    if action == "update_chunk":
        if not chunk_id:
            return {"success": False, "error": "chunk_id required for action=update_chunk"}
        return mcp_engine.update_chunk(index_name, chunk_id, text=text, page=page, metadata=metadata)

    return {"success": False, "error": f"Unknown action: {action}. Use: list, get, create, update, delete, list_chunks, get_chunk, create_chunk, update_chunk, delete_chunk"}


@mcp.tool()
def rag_indexes(
    action: str = "list",
    index_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Index management: action="list"|"info"|"delete".
    For info/delete, provide index_name.
    """
    if action == "list":
        return mcp_engine.list_indexes()
    if not index_name:
        return {"success": False, "error": "index_name required for action=info or delete"}
    if action == "info":
        return mcp_engine.get_index_info(index_name)
    if action == "delete":
        return mcp_engine.delete_index(index_name)
    return {"success": False, "error": f"Unknown action: {action}. Use: list, info, delete"}


@mcp.tool()
def rag_stats() -> Dict[str, Any]:
    """Get system statistics: documents, chunks, indexes, costs."""
    return mcp_engine.get_stats()


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Starting MCP Microservice...")
    logger.info(f"   Server: {mcp.name}")
    logger.info(f"   Tools: 4 MCP tools (rag_query, rag_documents, rag_indexes, rag_stats)")
    yield
    logger.info("👋 Shutting down MCP Microservice...")


app = FastAPI(
    title="ARIS RAG MCP Server",
    description="""
    **Model Context Protocol (MCP) Server for ARIS RAG System**
    
    This microservice provides MCP tools for AI agents to interact with 
    the ARIS RAG document system.
    
    ## MCP Tools Available
    
    - **rag_query**: Search (mode: quick|research|search)
    - **rag_documents**: Document & Chunk CRUD (action: list|get|create|update|delete|list_chunks|get_chunk|create_chunk|update_chunk|delete_chunk)
    - **rag_indexes**: Index management (action: list|info|delete)
    - **rag_stats**: System statistics
    
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
            "query": ["rag_query"],
            "documents_and_chunks": ["rag_documents"],
            "indexes": ["rag_indexes"],
            "system": ["rag_stats"]
        },
        "total_tools": 4,
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
                "tools": ["rag_query"],
                "description": "Search with mode: quick|research|search"
            },
            "documents_and_chunks": {
                "tools": ["rag_documents"],
                "description": "Document & Chunk CRUD: list|get|create|update|delete + list_chunks|get_chunk|create_chunk|update_chunk|delete_chunk"
            },
            "indexes": {
                "tools": ["rag_indexes"],
                "description": "Index management: list|info|delete"
            },
            "system": {
                "tools": ["rag_stats"],
                "description": "System statistics"
            }
        },
        "total_tools": 4,
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
    """List all available MCP tools (4 consolidated tools)."""
    return {
        "total_tools": 4,
        "categories": {
            "query": ["rag_query"],
            "documents_and_chunks": ["rag_documents"],
            "indexes": ["rag_indexes"],
            "system": ["rag_stats"]
        },
        "tools": [
            {"name": "rag_query", "category": "query", "description": "Search with mode: quick|research|search"},
            {"name": "rag_documents", "category": "documents_and_chunks", "description": "Document & Chunk CRUD: list|get|create|update|delete + list_chunks|get_chunk|create_chunk|update_chunk|delete_chunk"},
            {"name": "rag_indexes", "category": "indexes", "description": "Index management: action list|info|delete"},
            {"name": "rag_stats", "category": "system", "description": "System statistics"}
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
    logger.info(f"   Tools: 4 MCP tools (rag_query, rag_documents, rag_indexes, rag_stats)")
    
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
                "query": ["rag_query"],
                "documents_and_chunks": ["rag_documents"],
                "indexes": ["rag_indexes"],
                "system": ["rag_stats"]
            },
            "total_tools": 4,
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
                    "tools": ["rag_query"],
                    "description": "Search with mode: quick|research|search"
                },
                "documents_and_chunks": {
                    "tools": ["rag_documents"],
                    "description": "Document & Chunk CRUD: list|get|create|update|delete + list_chunks|get_chunk|create_chunk|update_chunk|delete_chunk"
                },
                "indexes": {
                    "tools": ["rag_indexes"],
                    "description": "Index management: list|info|delete"
                },
                "system": {
                    "tools": ["rag_stats"],
                    "description": "System statistics"
                }
            },
            "total_tools": 4,
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
            "total_tools": 4,
            "tools": [
                {"name": "rag_query", "category": "query", "description": "Search with mode: quick|research|search"},
                {"name": "rag_documents", "category": "documents_and_chunks", "description": "Document & Chunk CRUD: list|get|create|update|delete + list_chunks|get_chunk|create_chunk|update_chunk|delete_chunk"},
                {"name": "rag_indexes", "category": "indexes", "description": "Index management: action list|info|delete"},
                {"name": "rag_stats", "category": "system", "description": "System statistics"}
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
    logger.info(f"   Tools: 4 MCP tools (rag_query, rag_documents, rag_indexes, rag_stats)")
    
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

