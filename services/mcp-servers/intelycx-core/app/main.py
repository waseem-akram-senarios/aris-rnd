"""Main entry point for Intelycx Core MCP Server."""

import uvicorn
from .mcp_server import app


def main():
    """Main entry point."""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )


if __name__ == "__main__":
    main()
