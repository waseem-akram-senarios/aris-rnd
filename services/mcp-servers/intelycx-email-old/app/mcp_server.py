"""HTTP-based MCP Server for Intelycx Email Service."""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from .clients.email_client import EmailClient, EmailMessage, EmailRecipient, EmailAttachment

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
    title="Intelycx Email MCP Server",
    description="MCP Server for Intelycx Email communication service",
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


class IntelycxEmailMCPServer:
    """HTTP-based MCP Server for Intelycx Email Service."""
    
    def __init__(self):
        self.client = EmailClient(
            smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(os.environ.get("SMTP_PORT", "587")),
            username=os.environ.get("SMTP_USER"),
            password=os.environ.get("SMTP_PASSWORD"),
            use_tls=os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
        )
        self.logger = logger
        
        # MCP protocol state
        self.initialized = False
        self.tools = [
            {
                "name": "send_email",
                "description": "Send an email with full control over recipients, subject, body, and attachments. Supports HTML content and multiple recipients.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string", "description": "Recipient email address"},
                                    "name": {"type": "string", "description": "Recipient name (optional)"}
                                },
                                "required": ["email"]
                            },
                            "description": "List of email recipients"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content"
                        },
                        "cc": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "name": {"type": "string"}
                                },
                                "required": ["email"]
                            },
                            "description": "CC recipients (optional)"
                        },
                        "bcc": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "name": {"type": "string"}
                                },
                                "required": ["email"]
                            },
                            "description": "BCC recipients (optional)"
                        },
                        "is_html": {
                            "type": "boolean",
                            "description": "Whether the body content is HTML format",
                            "default": False
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "send_simple_email",
                "description": "Send a simple email to a single recipient with basic parameters. Ideal for quick notifications and alerts.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to_email": {
                            "type": "string",
                            "description": "Recipient email address"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Email subject line"
                        },
                        "body": {
                            "type": "string",
                            "description": "Email body content"
                        },
                        "to_name": {
                            "type": "string",
                            "description": "Recipient name (optional)"
                        },
                        "is_html": {
                            "type": "boolean",
                            "description": "Whether the body content is HTML format",
                            "default": False
                        }
                    },
                    "required": ["to_email", "subject", "body"]
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
        self.logger.info("Email MCP server initialized")
        
        return MCPResponse(
            result={
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "intelycx-email-mcp-server",
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
        
        self.logger.info(f"🔧 EMAIL TOOL CALL: {tool_name}")
        self.logger.info(f"📥 TOOL INPUT: {json.dumps(arguments, indent=2)}")
        
        try:
            if tool_name == "send_email":
                # Parse recipients
                to_recipients = [
                    EmailRecipient(email=r["email"], name=r.get("name"))
                    for r in arguments.get("to", [])
                ]
                
                cc_recipients = None
                if arguments.get("cc"):
                    cc_recipients = [
                        EmailRecipient(email=r["email"], name=r.get("name"))
                        for r in arguments["cc"]
                    ]
                
                bcc_recipients = None
                if arguments.get("bcc"):
                    bcc_recipients = [
                        EmailRecipient(email=r["email"], name=r.get("name"))
                        for r in arguments["bcc"]
                    ]
                
                # Create email message
                message = EmailMessage(
                    to=to_recipients,
                    subject=arguments.get("subject", ""),
                    body=arguments.get("body", ""),
                    cc=cc_recipients,
                    bcc=bcc_recipients,
                    is_html=arguments.get("is_html", False)
                )
                
                result = await self.client.send_email(message)
                self.logger.info(f"✅ EMAIL TOOL SUCCESS: {tool_name}")
                self.logger.info(f"📤 TOOL OUTPUT: {json.dumps(result, indent=2)}")
                
                return MCPResponse(result=result, id=request.id)
                
            elif tool_name == "send_simple_email":
                to_email = arguments.get("to_email")
                subject = arguments.get("subject")
                body = arguments.get("body")
                
                if not all([to_email, subject, body]):
                    raise ValueError("to_email, subject, and body are required")
                
                result = await self.client.send_simple_email(
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    to_name=arguments.get("to_name"),
                    is_html=arguments.get("is_html", False)
                )
                
                self.logger.info(f"✅ EMAIL TOOL SUCCESS: {tool_name}")
                self.logger.info(f"📤 TOOL OUTPUT: {json.dumps(result, indent=2)}")
                
                return MCPResponse(result=result, id=request.id)
                
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
                
        except Exception as e:
            self.logger.error(f"❌ EMAIL TOOL ERROR: {tool_name} - {str(e)}")
            return MCPResponse(
                error={"code": -32603, "message": f"Tool execution failed: {str(e)}"},
                id=request.id
            )


# Global server instance
mcp_server = IntelycxEmailMCPServer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key authentication."""
    if credentials.credentials not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return VALID_API_KEYS[credentials.credentials]


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "intelycx-email-mcp-server"}


@app.post("/mcp", response_model=MCPResponse)
async def handle_mcp_request(
    request: MCPRequest, 
    client: str = Depends(verify_api_key)
) -> MCPResponse:
    """Handle MCP protocol requests over HTTP."""
    logger.info(f"Email MCP request from {client}: {request.method}")
    return await mcp_server.handle_request(request)


@app.get("/tools")
async def list_tools(client: str = Depends(verify_api_key)):
    """List available tools (convenience endpoint)."""
    return {"tools": mcp_server.tools}
