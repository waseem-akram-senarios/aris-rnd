"""MCP Server Manager using FastMCP Client."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastmcp import Client

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    name: str
    command: str
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None  # For HTTP-based servers


class MCPServerManager:
    """MCP Server Manager using FastMCP Client."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "mcp_servers.json"
        self.servers: Dict[str, MCPServerConfig] = {}
        self.clients: Dict[str, Client] = {}  # FastMCP clients
        self.connections: Dict[str, Any] = {}
        self.logger = logger
        
        # Load configuration
        self._load_config()
    
    def _load_config(self):
        """Load MCP server configuration from file."""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                
                mcp_servers = config.get("mcpServers", {})
                for server_name, server_config in mcp_servers.items():
                    if "url" in server_config:
                        # HTTP-based server
                        self.servers[server_name] = MCPServerConfig(
                            name=server_name,
                            command="",
                            url=server_config["url"]
                        )
                    else:
                        # Process-based server (not supported yet)
                        self.logger.warning(f"Process-based server {server_name} not yet supported with FastMCP")
                        continue
                
                self.logger.info(f"Loaded {len(self.servers)} MCP server configurations")
            else:
                self.logger.warning(f"MCP config file not found: {self.config_path}")
                
        except Exception as e:
            self.logger.error(f"Error loading MCP config: {str(e)}")
    
    async def start_server(self, server_name: str) -> bool:
        """Start an MCP server connection using FastMCP Client."""
        if server_name not in self.servers:
            self.logger.error(f"Server {server_name} not configured")
            return False
        
        server_config = self.servers[server_name]
        
        try:
            if server_config.url:
                # Create FastMCP client for HTTP server
                self.logger.info(f"🚀 Connecting to HTTP MCP server: {server_name} at {server_config.url}")
                
                # Configure authentication if needed
                auth_token = os.environ.get('MCP_API_KEY', 'mcp-dev-key-12345')
                
                # Create FastMCP client with authentication
                client = Client(
                    server_config.url,
                    auth=auth_token  # FastMCP handles Bearer token automatically
                )
                
                # Test the connection
                await client.__aenter__()  # Initialize connection
                await client.ping()  # Test connectivity
                
                # Store the client
                self.clients[server_name] = client
                self.connections[server_name] = {
                    "type": "http",
                    "url": server_config.url,
                    "client": client
                }
                
                self.logger.info(f"✅ Connected to FastMCP server: {server_name}")
                return True
            else:
                self.logger.error(f"Process-based servers not yet supported: {server_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to connect to MCP server {server_name}: {str(e)}")
            return False
    
    async def start_all_servers(self) -> Dict[str, bool]:
        """Start all configured MCP servers."""
        results = {}
        for server_name in self.servers:
            results[server_name] = await self.start_server(server_name)
        return results
    
    async def stop_server(self, server_name: str):
        """Stop an MCP server connection."""
        if server_name in self.clients:
            try:
                client = self.clients[server_name]
                await client.__aexit__(None, None, None)  # Properly close connection
                del self.clients[server_name]
                if server_name in self.connections:
                    del self.connections[server_name]
                self.logger.info(f"Stopped MCP server: {server_name}")
            except Exception as e:
                self.logger.error(f"Error stopping server {server_name}: {str(e)}")
    
    async def stop_all_servers(self):
        """Stop all MCP servers."""
        for server_name in list(self.clients.keys()):
            await self.stop_server(server_name)
    
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all MCP servers."""
        status = {}
        for server_name, server_config in self.servers.items():
            if server_name in self.connections:
                conn_info = self.connections[server_name]
                status[server_name] = {
                    "status": "connected",
                    "type": conn_info["type"],
                    "url": conn_info.get("url", ""),
                    "client_type": "fastmcp"
                }
            else:
                status[server_name] = {
                    "status": "stopped",
                    "type": "unknown",
                    "client_type": "fastmcp"
                }
        return status
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool using FastMCP Client."""
        try:
            # Route tools to appropriate servers
            server_name = self._get_server_for_tool(tool_name)
            
            if server_name not in self.clients:
                return {"error": f"MCP server {server_name} not connected"}
            
            client = self.clients[server_name]
            
            self.logger.info(f"🔧 FASTMCP TOOL CALL: {tool_name} -> {server_name}")
            self.logger.debug(f"📥 TOOL INPUT: {json.dumps(arguments, indent=2)}")
            
            # Use FastMCP client to call the tool with progress token support
            # Generate a progress token to receive progress updates
            import uuid
            progress_token = str(uuid.uuid4())
            
            # Note: FastMCP Client handles progress tokens automatically in newer versions
            # The progress updates will be logged by FastMCP internally
            result = await client.call_tool(tool_name, arguments)
            
            # FastMCP returns a ToolResult object, extract the data
            self.logger.info(f"🔍 Raw result type: {type(result)}")
            self.logger.info(f"🔍 Raw result hasattr data: {hasattr(result, 'data')}")
            if hasattr(result, 'data'):
                self.logger.info(f"🔍 result.data type: {type(result.data)}")
            
            tool_data = result.data if hasattr(result, 'data') else result
            
            # Handle FastMCP Root object - convert to dictionary for JSON serialization (recursive)
            def convert_root_objects(obj):
                """Recursively convert FastMCP objects (Root, Pydantic models) to dictionaries."""
                # Check if this is a FastMCP object (Root or Pydantic model from types module)
                obj_type_str = str(type(obj))
                is_fastmcp_object = (
                    hasattr(obj, '__class__') and (
                        'Root' in obj_type_str or 
                        'types.' in obj_type_str or  # FastMCP Pydantic models
                        (hasattr(obj, 'model_dump') and hasattr(obj, '__dict__'))  # Generic Pydantic model
                    )
                )
                
                if is_fastmcp_object:
                    # Convert FastMCP object to dictionary
                    if hasattr(obj, 'model_dump'):
                        obj = obj.model_dump()
                    elif hasattr(obj, 'dict'):
                        obj = obj.dict()
                    elif hasattr(obj, '__dict__'):
                        obj = {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
                    else:
                        return str(obj)  # Fallback to string
                
                # Recursively handle nested structures
                if isinstance(obj, dict):
                    return {k: convert_root_objects(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_root_objects(item) for item in obj]
                elif isinstance(obj, tuple):
                    return tuple(convert_root_objects(item) for item in obj)
                else:
                    return obj
            
            self.logger.info(f"🔍 Tool result type: {type(tool_data)}")
            self.logger.info(f"🔍 Tool result str(type): {str(type(tool_data))}")
            
            # Apply recursive FastMCP object conversion
            original_type = type(tool_data)
            tool_data = convert_root_objects(tool_data)
            self.logger.info(f"✅ After recursive conversion: {type(tool_data)} (was {original_type})")
            
            # Final JSON serialization test
            try:
                json.dumps(tool_data, default=str)
                self.logger.info(f"✅ Final JSON serialization test passed")
            except Exception as e:
                self.logger.error(f"❌ Final JSON serialization test failed: {e}")
                # Last resort: convert entire result to string
                tool_data = {"data": str(tool_data), "error": "JSON serialization failed, converted to string"}
                self.logger.warning(f"🔄 Converted entire result to string wrapper")
            
            self.logger.info(f"✅ FASTMCP TOOL SUCCESS: {tool_name}")
            # Log summary instead of full output to reduce duplication
            output_size = len(json.dumps(tool_data, default=str))
            self.logger.debug(f"📤 TOOL OUTPUT: {output_size} characters")
            
            return tool_data
                
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def _get_server_for_tool(self, tool_name: str) -> str:
        """Determine which MCP server should handle a specific tool."""
        # Tool routing logic - updated with new tools
        email_tools = ["send_email", "test_email_driver"]
        core_tools = ["intelycx_login", "get_machine", "get_machine_group", "get_production_summary", "get_fake_data"]
        
        if tool_name in email_tools:
            return "intelycx-email"
        elif tool_name in core_tools:
            return "intelycx-core"
        else:
            # Default to core server for unknown tools
            self.logger.warning(f"Unknown tool {tool_name}, routing to intelycx-core")
            return "intelycx-core"
    
    async def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available tools from servers using FastMCP."""
        tools = []
        
        servers_to_check = [server_name] if server_name else list(self.clients.keys())
        
        for srv_name in servers_to_check:
            if srv_name in self.clients:
                try:
                    client = self.clients[srv_name]
                    server_tools = await client.list_tools()
                    
                    for tool in server_tools:
                        tools.append({
                            "name": tool.name,
                            "description": tool.description,
                            "server": srv_name,
                            "inputSchema": tool.inputSchema
                        })
                        
                except Exception as e:
                    self.logger.error(f"Error listing tools from {srv_name}: {str(e)}")
        
        return tools
    
    async def get_server_info(self, server_name: str) -> Dict[str, Any]:
        """Get server information using FastMCP."""
        if server_name not in self.clients:
            return {"error": f"Server {server_name} not connected"}
        
        try:
            client = self.clients[server_name]
            # FastMCP clients can provide server info
            return {
                "name": server_name,
                "status": "connected",
                "type": "fastmcp",
                "url": self.connections[server_name].get("url", "")
            }
        except Exception as e:
            return {"error": f"Error getting server info: {str(e)}"}
