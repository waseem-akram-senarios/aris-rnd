"""
MCP Server - Redirect to Microservice

This file redirects to the MCP microservice at services/mcp/main.py
It's kept for backwards compatibility with existing references.

For the actual implementation, see:
- services/mcp/main.py - Main entry point with MCP server and FastAPI
- services/mcp/engine.py - Core business logic
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and re-export from microservice
from services.mcp.main import mcp, mcp_engine, rag_ingest, rag_upload_document, rag_quick_query, rag_research_query, rag_search, app

# For backwards compatibility, expose the engine functions
def ingest(content, metadata=None):
    """Wrapper for MCP engine ingest."""
    return mcp_engine.ingest(content, metadata)

def upload_document(file_content, filename, metadata=None):
    """Wrapper for MCP engine upload_document."""
    return mcp_engine.upload_document(file_content, filename, metadata)

def search(query, filters=None, k=10, search_mode="hybrid", use_agentic_rag=True, include_answer=True):
    """Wrapper for MCP engine search."""
    return mcp_engine.search(query, filters, k, search_mode, use_agentic_rag, include_answer)


if __name__ == "__main__":
    # Run the MCP microservice (combined mode by default)
    from services.mcp.main import run_combined_server
    run_combined_server()
