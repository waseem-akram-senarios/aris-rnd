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
    instructions="""MCP server for ARIS RAG system - document ingestion and semantic search.

ACCURACY FEATURES:
- Hybrid search combining semantic (vector) and keyword (BM25) search
- FlashRank cross-encoder reranking for precision
- Agentic RAG with automatic query decomposition for complex questions
- Multi-language support with auto-translation
- Confidence scores for result quality assessment

TOOLS:
1. rag_ingest - Add documents (text or S3 URI) with metadata
2. rag_upload_document - Upload documents directly (PDF, DOCX, TXT, etc.) with base64 encoding
3. rag_search - Query with filters, returns ranked results with confidence scores
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
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Starting MCP Microservice...")
    logger.info(f"   Server: {mcp.name}")
    logger.info(f"   Tools: rag_ingest, rag_upload_document, rag_search")
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
        "tools": ["rag_ingest", "rag_upload_document", "rag_search"],
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
        "version": "1.0.0",
        "description": "Model Context Protocol server for document ingestion and search",
        "tools": {
            "rag_ingest": {
                "description": "Add documents to RAG system",
                "parameters": ["content (required)", "metadata (optional)"],
                "supports": ["plain text", "S3 URIs"]
            },
            "rag_upload_document": {
                "description": "Upload documents directly with base64 encoding",
                "parameters": ["file_content (required)", "filename (required)", "metadata (optional)"],
                "supports": ["PDF", "DOCX", "DOC", "TXT", "MD", "HTML"],
                "note": "Binary files (PDF, DOCX, DOC) must be base64-encoded"
            },
            "rag_search": {
                "description": "Query RAG system with advanced search",
                "parameters": ["query (required)", "filters", "k", "search_mode", "use_agentic_rag", "include_answer"],
                "search_modes": ["hybrid", "semantic", "keyword"]
            }
        },
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
            "mcp_sse": "/sse"
        }
    }


@app.get("/tools")
async def list_tools():
    """List available MCP tools."""
    return {
        "tools": [
            {
                "name": "rag_ingest",
                "description": "Add content to the RAG system for indexing (text or S3 URI)",
                "parameters": {
                    "content": {"type": "string", "required": True, "description": "Plain text or S3 URI (s3://bucket/key)"},
                    "metadata": {"type": "object", "required": False, "description": "Optional metadata (language, domain, etc.)"}
                }
            },
            {
                "name": "rag_upload_document",
                "description": "Upload documents directly with base64 encoding (PDF, DOCX, TXT, etc.)",
                "parameters": {
                    "file_content": {"type": "string", "required": True, "description": "Base64-encoded content for binary files, or plain text"},
                    "filename": {"type": "string", "required": True, "description": "Filename with extension (e.g., 'manual.pdf')"},
                    "metadata": {"type": "object", "required": False, "description": "Optional metadata (language, domain, etc.)"}
                },
                "supported_formats": ["PDF", "DOCX", "DOC", "TXT", "MD", "HTML"]
            },
            {
                "name": "rag_search",
                "description": "Query the RAG system with advanced search",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "filters": {"type": "object", "required": False},
                    "k": {"type": "integer", "default": 10},
                    "search_mode": {"type": "string", "default": "hybrid"},
                    "use_agentic_rag": {"type": "boolean", "default": True},
                    "include_answer": {"type": "boolean", "default": True}
                }
            }
        ]
    }


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
    logger.info(f"   Tools: rag_ingest, rag_upload_document, rag_search")
    
    # Get the MCP's HTTP app (Starlette-based)
    mcp_http_app = mcp.http_app()
    
    # Create health check handler
    async def health_handler(request):
        from shared.config.settings import ARISConfig
        return JSONResponse({
            "status": "healthy",
            "service": "mcp",
            "server_name": mcp.name,
            "tools": ["rag_ingest", "rag_upload_document", "rag_search"],
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
            "version": "1.0.0",
            "description": "Model Context Protocol server for document ingestion and search",
            "tools": {
                "rag_ingest": {
                    "description": "Add documents to RAG system",
                    "supports": ["plain text", "S3 URIs"]
                },
                "rag_upload_document": {
                    "description": "Upload documents directly with base64 encoding",
                    "supports": ["PDF", "DOCX", "DOC", "TXT", "MD", "HTML"]
                },
                "rag_search": {
                    "description": "Query RAG system with advanced search",
                    "search_modes": ["hybrid", "semantic", "keyword"]
                }
            },
            "configuration": {
                "embedding_model": ARISConfig.EMBEDDING_MODEL,
                "chunk_size": ARISConfig.DEFAULT_CHUNK_SIZE,
                "reranking_enabled": ARISConfig.ENABLE_RERANKING,
                "agentic_rag_enabled": ARISConfig.DEFAULT_USE_AGENTIC_RAG
            },
            "endpoints": {
                "health": "/health",
                "info": "/info",
                "mcp_sse": "/sse"
            }
        })
    
    # Create tools list handler
    async def tools_handler(request):
        return JSONResponse({
            "tools": [
                {
                    "name": "rag_ingest",
                    "description": "Add content to the RAG system for indexing (text or S3 URI)",
                    "parameters": {
                        "content": {"type": "string", "required": True},
                        "metadata": {"type": "object", "required": False}
                    }
                },
                {
                    "name": "rag_upload_document",
                    "description": "Upload documents directly with base64 encoding",
                    "parameters": {
                        "file_content": {"type": "string", "required": True, "description": "Base64-encoded for binary, or plain text"},
                        "filename": {"type": "string", "required": True, "description": "Filename with extension"},
                        "metadata": {"type": "object", "required": False}
                    },
                    "supported_formats": ["PDF", "DOCX", "DOC", "TXT", "MD", "HTML"]
                },
                {
                    "name": "rag_search",
                    "description": "Query the RAG system with advanced search",
                    "parameters": {
                        "query": {"type": "string", "required": True},
                        "filters": {"type": "object", "required": False},
                        "k": {"type": "integer", "default": 10},
                        "search_mode": {"type": "string", "default": "hybrid"},
                        "use_agentic_rag": {"type": "boolean", "default": True},
                        "include_answer": {"type": "boolean", "default": True}
                    }
                }
            ]
        })
    
    # Create a redirect from /sse to /mcp for backwards compatibility
    async def sse_redirect(request):
        from starlette.responses import RedirectResponse
        # Include any query parameters
        query_string = request.url.query
        redirect_url = "/mcp" + ("?" + query_string if query_string else "")
        return RedirectResponse(url=redirect_url, status_code=307)
    
    # Add custom routes to the MCP HTTP app
    # Note: Routes are matched in order, so insert at beginning
    mcp_http_app.routes.insert(0, Route("/health", health_handler, methods=["GET"]))
    mcp_http_app.routes.insert(1, Route("/info", info_handler, methods=["GET"]))
    mcp_http_app.routes.insert(2, Route("/tools", tools_handler, methods=["GET"]))
    mcp_http_app.routes.insert(3, Route("/sse", sse_redirect, methods=["GET", "POST"]))
    
    # Run the combined server
    logger.info(f"   Available routes: /health, /info, /tools, /sse (→ /mcp), /mcp")
    uvicorn.run(mcp_http_app, host=host, port=port)


def run_mcp_only():
    """Run the MCP server only with SSE transport."""
    port = int(os.getenv("MCP_SERVER_PORT", "8503"))
    host = os.getenv("MCP_SERVER_HOST", "0.0.0.0")
    transport = os.getenv("MCP_TRANSPORT", "sse")
    
    logger.info(f"🚀 Starting MCP Server on {host}:{port}")
    logger.info(f"   Transport: {transport}")
    logger.info(f"   Tools: rag_ingest, rag_upload_document, rag_search")
    
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

