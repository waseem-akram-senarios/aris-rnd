#!/usr/bin/env python3
"""
Start MCP Server for Testing
"""
import os
import sys
import subprocess
import time
from pathlib import Path

def main():
    """Start MCP server"""
    print("🚀 Starting MCP Server...")
    
    # Change to project root
    os.chdir(Path(__file__).parent)
    
    # Check if main.py exists
    mcp_main = Path("services/mcp/main.py")
    if not mcp_main.exists():
        print("❌ MCP server main.py not found")
        return
    
    print(f"📁 MCP Server: {mcp_main}")
    print("🌐 Server will start on: http://localhost:8503")
    print("📋 Available endpoints:")
    print("   - GET /health - Health check")
    print("   - GET /info - Server information")
    print("   - GET /sse - Server-Sent Events")
    
    try:
        # Start the MCP server
        print("\n🚀 Starting server...")
        subprocess.run([
            sys.executable, str(mcp_main)
        ], check=True)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")

if __name__ == "__main__":
    main()
