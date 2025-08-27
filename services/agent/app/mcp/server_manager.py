"""MCP Server Manager for spawning and managing external MCP servers."""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp

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
    """Manages MCP servers as separate processes."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "mcp_servers.json"
        self.servers: Dict[str, MCPServerConfig] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
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
                        # Process-based server
                        self.servers[server_name] = MCPServerConfig(
                            name=server_name,
                            command=server_config["command"],
                            args=server_config.get("args", []),
                            env=server_config.get("env", {})
                        )
                
                self.logger.info(f"Loaded {len(self.servers)} MCP server configurations")
            else:
                self.logger.warning(f"MCP config file not found: {self.config_path}")
                
        except Exception as e:
            self.logger.error(f"Error loading MCP config: {str(e)}")
    
    async def start_server(self, server_name: str) -> bool:
        """Start an MCP server process."""
        if server_name not in self.servers:
            self.logger.error(f"Server {server_name} not configured")
            return False
        
        server_config = self.servers[server_name]
        
        try:
            if server_config.url:
                # HTTP-based server - test connection
                async with aiohttp.ClientSession() as session:
                    try:
                        # Test health endpoint first
                        health_url = server_config.url.replace('/mcp', '/health')
                        async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                # Initialize the HTTP MCP server
                                success = await self._initialize_http_server(server_name, server_config.url, session)
                                if success:
                                    self.connections[server_name] = {"type": "http", "url": server_config.url}
                                    self.logger.info(f"✅ Connected to HTTP MCP server: {server_name}")
                                    return True
                                else:
                                    self.logger.error(f"❌ Failed to initialize HTTP MCP server: {server_name}")
                                    return False
                            else:
                                self.logger.error(f"❌ HTTP MCP server {server_name} health check failed: {resp.status}")
                                return False
                    except Exception as e:
                        self.logger.error(f"❌ Failed to connect to HTTP MCP server {server_name}: {str(e)}")
                        return False
            
            # Process-based server
            cmd = [server_config.command]
            if server_config.args:
                cmd.extend(server_config.args)
            
            # Try to find the correct Python executable
            if server_config.command in ['python', 'python3']:
                python_exec = shutil.which('python3') or shutil.which('python')
                if python_exec:
                    cmd[0] = python_exec
                    self.logger.info(f"Using Python executable: {python_exec}")
                else:
                    self.logger.error(f"No Python executable found")
                    return False
            
            self.logger.info(f"Starting MCP server {server_name}: {' '.join(cmd)}")
            
            # Start the process
            self.logger.info(f"Executing command: {' '.join(cmd)}")
            self.logger.info(f"Environment: {server_config.env}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **(server_config.env or {})}
            )
            
            self.processes[server_name] = process
            self.logger.info(f"Started MCP server: {server_name} (PID: {process.pid})")
            
            # Initialize the server
            success = await self._initialize_server(server_name, process)
            if success:
                self.connections[server_name] = {"type": "process", "process": process}
                return True
            else:
                process.terminate()
                await process.wait()
                del self.processes[server_name]
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to start MCP server {server_name}: {str(e)}")
            return False
    
    async def _initialize_server(self, server_name: str, process: subprocess.Popen) -> bool:
        """Initialize MCP server with handshake."""
        try:
            # Send initialization request
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "0.1.0",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "intelycx-aris-agent",
                        "version": "0.1.0"
                    }
                },
                "id": 1
            }
            
            # Send request
            process.stdin.write(json.dumps(init_request).encode() + b'\n')
            await process.stdin.drain()
            
            # Read response
            response = await asyncio.wait_for(
                asyncio.create_task(process.stdout.readline()),
                timeout=10.0
            )
            
            if response:
                init_response = json.loads(response.decode())
                if "result" in init_response:
                    self.logger.info(f"MCP server {server_name} initialized successfully")
                    return True
            
            self.logger.error(f"MCP server {server_name} initialization failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error initializing MCP server {server_name}: {str(e)}")
            return False
    
    async def _initialize_http_server(self, server_name: str, url: str, session) -> bool:
        """Initialize an HTTP-based MCP server."""
        try:
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": "init-1"
            }
            
            headers = {
                "Authorization": f"Bearer {os.environ.get('MCP_API_KEY', 'mcp-dev-key-12345')}",
                "Content-Type": "application/json"
            }
            
            async with session.post(url, json=init_request, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    if "result" in response:
                        self.logger.info(f"HTTP MCP server {server_name} initialized successfully")
                        return True
                    else:
                        self.logger.error(f"HTTP MCP server {server_name} initialization failed: {response}")
                        return False
                else:
                    self.logger.error(f"HTTP MCP server {server_name} initialization failed: HTTP {resp.status}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Error initializing HTTP MCP server {server_name}: {str(e)}")
            return False
    
    async def start_all_servers(self) -> Dict[str, bool]:
        """Start all configured MCP servers."""
        results = {}
        for server_name in self.servers:
            results[server_name] = await self.start_server(server_name)
        return results
    
    async def stop_server(self, server_name: str):
        """Stop an MCP server."""
        if server_name in self.processes:
            process = self.processes[server_name]
            try:
                process.terminate()
                await process.wait()
                del self.processes[server_name]
                if server_name in self.connections:
                    del self.connections[server_name]
                self.logger.info(f"Stopped MCP server: {server_name}")
            except Exception as e:
                self.logger.error(f"Error stopping server {server_name}: {str(e)}")
    
    async def stop_all_servers(self):
        """Stop all MCP servers."""
        for server_name in list(self.processes.keys()):
            await self.stop_server(server_name)
    
    def get_server_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all MCP servers."""
        status = {}
        for server_name, server_config in self.servers.items():
            if server_name in self.connections:
                conn_info = self.connections[server_name]
                if conn_info["type"] == "process":
                    process = conn_info["process"]
                    status[server_name] = {
                        "status": "running" if process.poll() is None else "stopped",
                        "pid": process.pid,
                        "type": "process"
                    }
                else:
                    status[server_name] = {
                        "status": "connected",
                        "type": "http",
                        "url": conn_info["url"]
                    }
            else:
                status[server_name] = {
                    "status": "stopped",
                    "type": "unknown"
                }
        return status
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by routing to the appropriate MCP server."""
        try:
            # Route tools to appropriate servers
            server_name = self._get_server_for_tool(tool_name)
            
            if server_name not in self.connections:
                return {"error": f"MCP server {server_name} not connected"}
            
            connection = self.connections[server_name]
            
            if connection["type"] == "http":
                return await self._execute_http_tool(connection["url"], tool_name, arguments)
            else:
                # Fallback to process-based execution (legacy)
                return await self._execute_process_tool(server_name, tool_name, arguments)
                
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def _get_server_for_tool(self, tool_name: str) -> str:
        """Determine which MCP server should handle a specific tool."""
        # Tool routing logic
        email_tools = ["send_email", "send_simple_email"]
        core_tools = ["intelycx_login", "get_machine", "get_machine_group", "get_production_summary", "get_fake_data"]
        
        if tool_name in email_tools:
            return "intelycx-email"
        elif tool_name in core_tools:
            return "intelycx-core"
        else:
            # Default to core server for unknown tools
            self.logger.warning(f"Unknown tool {tool_name}, routing to intelycx-core")
            return "intelycx-core"
    
    async def _execute_http_tool(self, url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via HTTP MCP server."""
        
        mcp_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": "1"
        }
        
        headers = {
            "Authorization": f"Bearer {os.environ.get('MCP_API_KEY', 'mcp-dev-key-12345')}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=mcp_request, headers=headers) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    if "result" in response:
                        return response["result"]
                    elif "error" in response:
                        return {"error": response["error"]["message"]}
                    else:
                        return {"error": "Invalid MCP response"}
                else:
                    return {"error": f"HTTP error: {resp.status}"}
    
    async def _execute_process_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool via process-based MCP server (legacy fallback)."""
        # Legacy fallback - should not be used with HTTP-based servers
        self.logger.error(f"Process-based tool execution not supported for {server_name}")
        return {"error": "Process-based MCP servers are no longer supported"}
