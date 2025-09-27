"""MCP Server Manager using FastMCP Client."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from fastmcp import Client

if TYPE_CHECKING:
    from ..planning.models import ExecutionPlan
    from ..planning.observer import PlanManager

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
        
        # Dynamic discovery state
        self.tool_to_server_cache: Dict[str, str] = {}
        self.server_tools_cache: Dict[str, List[Dict[str, Any]]] = {}
        self.discovery_timestamp: Optional[float] = None
        
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
                        # HTTP-based server (simple configuration)
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
    
    async def execute_tool(
        self, 
        tool_name: str, 
        arguments: Dict[str, Any], 
        plan_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool using FastMCP Client with optional plan status updates.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            plan_context: Optional dict containing:
                - plan: ExecutionPlan object
                - action_id: ID of the action being executed
                - plan_manager: PlanManager instance for updates
                - logger: Logger for status updates
        """
        try:
            # Route tools to appropriate servers
            server_name = self._get_server_for_tool(tool_name)
            
            if server_name not in self.clients:
                return {"error": f"MCP server {server_name} not connected"}
            
            client = self.clients[server_name]
            
            self.logger.info(f"🔧 FASTMCP TOOL CALL: {tool_name} -> {server_name}")
            self.logger.debug(f"📥 TOOL INPUT: {json.dumps(arguments, indent=2)}")
            
            # Update plan status: starting
            await self._update_plan_status(plan_context, "starting", f"Starting {tool_name}...")
            
            # Use FastMCP client to call the tool with progress token support
            # Generate a progress token to receive progress updates
            import uuid
            progress_token = str(uuid.uuid4())
            
            # Update plan status: in_progress
            await self._update_plan_status(plan_context, "in_progress", f"Executing {tool_name}...")
            
            # Note: FastMCP Client handles progress tokens automatically in newer versions
            # The progress updates will be logged by FastMCP internally
            result = await client.call_tool(tool_name, arguments)
            
            # FastMCP returns a ToolResult object, extract the data
            # Reduced debug logging - only log on errors
            self.logger.debug(f"🔍 Raw result type: {type(result)}")
            
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
            
            self.logger.debug(f"🔍 Tool result type: {type(tool_data)}")
            
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
            
            # Update plan status: completed
            await self._update_plan_status(plan_context, "completed", f"Completed {tool_name}")
            
            return tool_data
                
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            
            # Update plan status: failed
            await self._update_plan_status(plan_context, "failed", f"Failed {tool_name}: {str(e)}")
            
            return {"error": f"Tool execution failed: {str(e)}"}
    
    async def _update_plan_status(
        self, 
        plan_context: Optional[Dict[str, Any]], 
        status: str, 
        message: str
    ) -> None:
        """Update plan action status if plan context is provided."""
        if not plan_context:
            return
        
        plan = plan_context.get("plan")
        action_id = plan_context.get("action_id")
        plan_manager = plan_context.get("plan_manager")
        context_logger = plan_context.get("logger", self.logger)
        
        if plan and action_id:
            # Update action status
            plan.update_action_status(action_id, status)
            
            # Send update via plan manager if available
            if plan_manager:
                try:
                    await plan_manager.update_plan(plan)
                    context_logger.info(f"📋 Updated action {action_id} to {status}: {message}")
                except Exception as e:
                    context_logger.warning(f"Failed to send plan update: {e}")
            else:
                context_logger.info(f"📋 Updated action {action_id} to {status}: {message}")
    
    async def get_tool_server(self, tool_name: str) -> Optional[str]:
        """Dynamically determine which MCP server should handle a specific tool."""
        # Use dynamic discovery instead of hardcoded mappings
        tool_mapping = await self.discover_tool_server_mapping()
        
        if tool_name in tool_mapping:
            return tool_mapping[tool_name]
        
        # If not found in discovery, tool doesn't exist or server is down
        self.logger.info(f"🔍 Tool {tool_name} not found in current discovery - server may be down")
        
        # No server found for this tool
        self.logger.warning(f"❌ Unknown tool {tool_name} - no server provides this tool")
        return None
    
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
    
    # Dynamic Discovery Methods
    
    async def discover_tool_server_mapping(self, force_refresh: bool = False) -> Dict[str, str]:
        """Dynamically discover which server provides which tool."""
        import time
        
        # Check cache validity (default 5 minutes)
        cache_duration = 300  # 5 minutes
        current_time = time.time()
        
        if (not force_refresh and 
            self.discovery_timestamp and 
            (current_time - self.discovery_timestamp) < cache_duration and
            self.tool_to_server_cache):
            self.logger.debug("Using cached tool-to-server mapping")
            return self.tool_to_server_cache
        
        self.logger.info("🔍 Discovering tool-to-server mappings dynamically...")
        tool_to_server = {}
        server_tools = {}
        
        # Discover from connected servers
        for server_name in self.connections.keys():
            try:
                if server_name not in self.clients:
                    continue
                    
                client = self.clients[server_name]
                tools = await client.list_tools()
                
                server_tools[server_name] = []
                for tool in tools:
                    tool_name = tool.name
                    tool_to_server[tool_name] = server_name
                    
                    # Extract metadata from tool tags and meta
                    tool_meta = getattr(tool, 'meta', {}) or {}
                    tool_tags = getattr(tool, 'tags', set()) or set()
                    
                    # Parse capability and domain from tags
                    capability = tool_meta.get('capability')
                    domain = tool_meta.get('domain')
                    requires_auth = tool_meta.get('requires_auth', False)
                    
                    # Also check tags for capability:xxx format
                    if not capability:
                        for tag in tool_tags:
                            if tag.startswith('capability:'):
                                capability = tag.split(':', 1)[1]
                                break
                    
                    if not domain:
                        for tag in tool_tags:
                            if tag.startswith('domain:'):
                                domain = tag.split(':', 1)[1]
                                break
                    
                    server_tools[server_name].append({
                        "name": tool_name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                        "capability": capability,
                        "domain": domain,
                        "requires_auth": requires_auth,
                        "tags": list(tool_tags) if tool_tags else [],
                        "meta": tool_meta
                    })
                
                self.logger.info(f"📋 Discovered {len(server_tools[server_name])} tools from {server_name}")
                
            except Exception as e:
                self.logger.warning(f"Failed to discover tools from {server_name}: {e}")
                
                # Log the failure but continue - no fallback needed with metadata-driven approach
                self.logger.warning(f"Server {server_name} discovery failed, skipping")
        
        # Update cache
        self.tool_to_server_cache = tool_to_server
        self.server_tools_cache = server_tools
        self.discovery_timestamp = current_time
        
        total_tools = len(tool_to_server)
        total_servers = len([s for s in server_tools.values() if s])
        self.logger.info(f"✅ Discovery complete: {total_tools} tools across {total_servers} servers")
        
        # Log discovery details
        for server_name, tools in server_tools.items():
            if tools:
                tool_names = [t["name"] for t in tools]
                capabilities = set(t.get("capability") for t in tools if t.get("capability"))
                self.logger.info(f"📋 {server_name}: {tool_names} (capabilities: {list(capabilities)})")
        
        return tool_to_server
    
    async def get_servers_for_capability(self, capability: str) -> List[str]:
        """Get servers that provide a specific capability based on tool metadata."""
        await self.discover_tool_server_mapping()  # Ensure cache is fresh
        servers = set()
        
        for server_name, tools in self.server_tools_cache.items():
            for tool in tools:
                if tool.get("capability") == capability:
                    servers.add(server_name)
                    break
        
        return list(servers)
    
    async def get_servers_for_domain(self, domain: str) -> List[str]:
        """Get servers that operate in a specific domain based on tool metadata."""
        await self.discover_tool_server_mapping()  # Ensure cache is fresh
        servers = set()
        
        for server_name, tools in self.server_tools_cache.items():
            for tool in tools:
                if tool.get("domain") == domain:
                    servers.add(server_name)
                    break
        
        return list(servers)
    
    async def get_tools_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Get all tools that provide a specific capability."""
        await self.discover_tool_server_mapping()  # Ensure cache is fresh
        matching_tools = []
        
        for server_name, tools in self.server_tools_cache.items():
            for tool in tools:
                if tool.get("capability") == capability:
                    matching_tools.append(tool)
        
        return matching_tools
    
    async def get_auth_providers(self) -> List[str]:
        """Get servers that provide authentication."""
        return await self.get_servers_for_capability("authentication")
    
    async def get_required_servers_for_tools(self, tool_names: List[str]) -> List[str]:
        """Dynamically determine which servers are needed for a list of tools."""
        tool_mapping = await self.discover_tool_server_mapping()
        required_servers = set()
        
        for tool_name in tool_names:
            if tool_name in tool_mapping:
                required_servers.add(tool_mapping[tool_name])
            else:
                self.logger.warning(f"Unknown tool {tool_name} - cannot determine required server")
        
        return list(required_servers)
    
    async def get_dynamic_tool_list(self, server_filter: Optional[str] = None) -> Dict[str, Any]:
        """Get a comprehensive, dynamic tool list organized by server."""
        await self.discover_tool_server_mapping()  # Refresh cache
        
        tools_by_server = {}
        all_tools = []
        
        for server_name, tools in self.server_tools_cache.items():
            if server_filter and server_name != server_filter:
                continue
                
            server_config = self.servers.get(server_name)
            server_info = {
                "name": server_name,
                "description": server_config.description if server_config else "No description",
                "capabilities": server_config.capabilities if server_config else [],
                "domains": server_config.domains if server_config else [],
                "tools": []
            }
            
            for tool in tools:
                tool_info = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "server": server_name
                }
                server_info["tools"].append(tool_info)
                all_tools.append(tool_info)
            
            if server_info["tools"]:  # Only include servers with tools
                tools_by_server[server_name] = server_info
        
        return {
            "tools_by_server": tools_by_server,
            "all_tools": all_tools,
            "total_tools": len(all_tools),
            "server_count": len(tools_by_server),
            "discovery_timestamp": self.discovery_timestamp
        }
