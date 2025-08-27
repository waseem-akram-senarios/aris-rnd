"""HTTP-based MCP Server for Intelycx Core API."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .clients.intelycx_core_client import IntelycxCoreClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security
security = HTTPBearer()

# Valid API keys (in production, load from secure storage)
VALID_API_KEYS = {
    os.environ.get("MCP_API_KEY", "mcp-dev-key-12345"): "aris-agent"
}

app = FastAPI(
    title="Intelycx Core MCP Server",
    description="MCP Server for Intelycx Core manufacturing data API",
    version="0.1.0"
)


class MCPRequest(BaseModel):
    """MCP protocol request model."""
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class MCPResponse(BaseModel):
    """MCP protocol response model."""
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    id: Optional[str] = None


class IntelycxCoreMCPServer:
    """HTTP-based MCP Server for Intelycx Core API."""
    
    def __init__(self):
        self.client = IntelycxCoreClient(
            base_url=os.environ.get("INTELYCX_CORE_BASE_URL", "https://api.intelycx.com"),
            api_key=os.environ.get("INTELYCX_CORE_API_KEY")
        )
        self.logger = logger
        
        # MCP protocol state
        self.initialized = False
        self.tools = [
            {
                "name": "intelycx_login",
                "description": "Authenticate with Intelycx Core API to obtain a JWT token for accessing manufacturing data. This must be called first before using any other Intelycx tools.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "username": {
                            "type": "string",
                            "description": "Intelycx Core API username"
                        },
                        "password": {
                            "type": "string",
                            "description": "Intelycx Core API password"
                        }
                    },
                    "required": ["username", "password"]
                }
            },

            {
                "name": "get_machine",
                "description": "Get detailed information about a specific machine including status, location, maintenance schedule, and performance metrics. Requires authentication via intelycx_login first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "machine_id": {
                            "type": "string",
                            "description": "The unique identifier of the machine"
                        },
                        "jwt_token": {
                            "type": "string",
                            "description": "JWT token obtained from intelycx_login tool"
                        }
                    },
                    "required": ["machine_id", "jwt_token"]
                }
            },
            {
                "name": "get_machine_group",
                "description": "Get comprehensive information about a machine group including all machines, performance metrics, shift schedules, and capacity information. Requires authentication via intelycx_login first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "group_id": {
                            "type": "string",
                            "description": "The unique identifier of the machine group"
                        },
                        "jwt_token": {
                            "type": "string",
                            "description": "JWT token obtained from intelycx_login tool"
                        }
                    },
                    "required": ["group_id", "jwt_token"]
                }
            },
            {
                "name": "get_production_summary",
                "description": "Get production summary data and metrics for analysis and reporting. Requires authentication via intelycx_login first.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "params": {
                            "type": "object",
                            "description": "Parameters for filtering production data",
                            "properties": {
                                "date_from": {
                                    "type": "string",
                                    "description": "Start date for data range (YYYY-MM-DD)"
                                },
                                "date_to": {
                                    "type": "string",
                                    "description": "End date for data range (YYYY-MM-DD)"
                                },
                                "machine_ids": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of machine IDs to filter by"
                                }
                            }
                        },
                        "jwt_token": {
                            "type": "string",
                            "description": "JWT token obtained from intelycx_login tool"
                        }
                    },
                    "required": ["params", "jwt_token"]
                }
            }
        ]
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """Handle incoming MCP requests."""
        method = request.method
        request_id = request.id
        
        try:
            if method == "initialize":
                return await self._handle_initialize(request)
            elif method == "tools/list":
                return await self._handle_tools_list(request)
            elif method == "tools/call":
                return await self._handle_tools_call(request)
            elif method == "ping":
                return MCPResponse(result="pong", id=request_id)
            else:
                return MCPResponse(
                    error={"code": -32601, "message": f"Method not found: {method}"},
                    id=request_id
                )
        except Exception as e:
            self.logger.error(f"Request handling failed: {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": f"Internal error: {str(e)}"},
                id=request_id
            )
    
    async def _handle_initialize(self, request: MCPRequest) -> MCPResponse:
        """Handle MCP initialize request."""
        self.initialized = True
        self.logger.info("MCP server initialized")
        
        return MCPResponse(
            result={
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "intelycx-core-mcp-server",
                    "version": "0.1.0"
                }
            },
            id=request.id
        )
    
    async def _handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request."""
        if not self.initialized:
            return MCPResponse(
                error={"code": -32002, "message": "Server not initialized"},
                id=request.id
            )
        
        return MCPResponse(
            result={"tools": self.tools},
            id=request.id
        )
    
    async def _handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request."""
        if not self.initialized:
            return MCPResponse(
                error={"code": -32002, "message": "Server not initialized"},
                id=request.id
            )
        
        params = request.params or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        self.logger.info(f"🔧 TOOL CALL: {tool_name}")
        self.logger.info(f"📥 TOOL INPUT: {json.dumps(arguments, indent=2)}")
        
        try:
            if tool_name == "intelycx_login":
                username = arguments.get("username")
                password = arguments.get("password")
                if not username or not password:
                    raise ValueError("username and password are required")
                
                result = await self.client.login(username, password)
                self.logger.info(f"✅ TOOL SUCCESS: {tool_name}")
                # Don't log the full result as it contains sensitive token info
                self.logger.info(f"📤 TOOL OUTPUT: Login {'successful' if result.get('success') else 'failed'}")
                
                return MCPResponse(result=result, id=request.id)
                
            elif tool_name == "get_machine":
                machine_id = arguments.get("machine_id")
                jwt_token = arguments.get("jwt_token")
                if not machine_id:
                    raise ValueError("machine_id is required")
                if not jwt_token:
                    raise ValueError("jwt_token is required - please authenticate first using intelycx_login")
                
                result = await self.client.get_machine(jwt_token, machine_id)
                self.logger.info(f"✅ TOOL SUCCESS: {tool_name}")
                self.logger.info(f"📤 TOOL OUTPUT: {json.dumps(result, indent=2)}")
                
                return MCPResponse(result=result, id=request.id)
                
            elif tool_name == "get_machine_group":
                group_id = arguments.get("group_id")
                jwt_token = arguments.get("jwt_token")
                if not group_id:
                    raise ValueError("group_id is required")
                if not jwt_token:
                    raise ValueError("jwt_token is required - please authenticate first using intelycx_login")
                
                result = await self.client.get_machine_group(jwt_token, group_id)
                self.logger.info(f"✅ TOOL SUCCESS: {tool_name}")
                self.logger.info(f"📤 TOOL OUTPUT: {json.dumps(result, indent=2)}")
                
                return MCPResponse(result=result, id=request.id)
                
            elif tool_name == "get_production_summary":
                params_arg = arguments.get("params", {})
                jwt_token = arguments.get("jwt_token")
                if not jwt_token:
                    raise ValueError("jwt_token is required - please authenticate first using intelycx_login")
                
                result = await self.client.get_production_summary(jwt_token, params_arg)
                self.logger.info(f"✅ TOOL SUCCESS: {tool_name}")
                self.logger.info(f"📤 TOOL OUTPUT: {json.dumps(result, indent=2)}")
                
                return MCPResponse(result=result, id=request.id)
                
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            self.logger.error(f"❌ TOOL ERROR: {tool_name} - {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": f"Tool execution failed: {str(e)}"},
                id=request.id
            )


# Global server instance
mcp_server = IntelycxCoreMCPServer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key authentication."""
    if credentials.credentials not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return VALID_API_KEYS[credentials.credentials]


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "intelycx-core-mcp-server"}


@app.post("/mcp", response_model=MCPResponse)
async def handle_mcp_request(
    request: MCPRequest, 
    client: str = Depends(verify_api_key)
) -> MCPResponse:
    """Handle MCP protocol requests over HTTP."""
    logger.info(f"MCP request from {client}: {request.method}")
    return await mcp_server.handle_request(request)


@app.get("/tools")
async def list_tools(client: str = Depends(verify_api_key)):
    """List available tools (convenience endpoint)."""
    return {"tools": mcp_server.tools}
