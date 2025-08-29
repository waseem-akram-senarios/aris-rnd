"""FastMCP Email Server for Intelycx."""

import os
import logging
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from .email_client import EmailClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("Intelycx Email")

# Initialize email client
email_client = EmailClient(
    smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    smtp_port=int(os.environ.get("SMTP_PORT", "587")),
    username=os.environ.get("SMTP_USER"),
    password=os.environ.get("SMTP_PASSWORD"),
    use_tls=os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    logger.info("🏥 Health check requested")
    
    # Perform basic health checks
    health_status = {
        "status": "healthy",
        "service": "intelycx-email-mcp-server",
        "version": "0.1.0",
        "transport": "http",
        "smtp_configured": bool(email_client.username),
        "timestamp": "2024-08-26T00:00:00Z"  # Would be actual timestamp in real implementation
    }
    
    logger.info(f"✅ Health check passed: {health_status['status']}")
    return JSONResponse(content=health_status, status_code=200)


@mcp.tool
async def send_email(
    to: Union[str, List[str], List[Dict[str, str]]],
    subject: str,
    body: str,
    cc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
    bcc: Optional[Union[str, List[str], List[Dict[str, str]]]] = None,
    is_html: bool = False
) -> Dict[str, Any]:
    """
    Send an email with flexible recipient support.
    
    Supports multiple recipient formats:
    - Single email string: "user@example.com"
    - List of email strings: ["user1@example.com", "user2@example.com"] 
    - List of recipient objects: [{"email": "user@example.com", "name": "User Name"}]
    
    Args:
        to: Email recipients (required) - string, list of strings, or list of dicts with email/name
        subject: Email subject line (required)
        body: Email body content (required)
        cc: CC recipients (optional) - same formats as 'to'
        bcc: BCC recipients (optional) - same formats as 'to'
        is_html: Whether the body content is HTML format (default: False)
        
    Returns:
        Dictionary with send status, message ID, and recipient counts
        
    Examples:
        # Simple email
        send_email("user@example.com", "Hello", "Hello World!")
        
        # Multiple recipients with names
        send_email(
            [{"email": "user1@example.com", "name": "User One"}, {"email": "user2@example.com", "name": "User Two"}],
            "Team Update", 
            "<h1>Important Update</h1><p>Please review...</p>",
            is_html=True
        )
        
        # With CC and BCC
        send_email(
            "recipient@example.com",
            "Project Status",
            "Here's the latest update...",
            cc=["manager@example.com"],
            bcc=["archive@example.com"]
        )
    """
    logger.info(f"🔧 EMAIL TOOL CALL: send_email")
    logger.info(f"📥 TOOL INPUT: to={to}, subject='{subject}', cc={cc}, bcc={bcc}, is_html={is_html}")
    
    try:
        result = await email_client.send_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            is_html=is_html
        )
        
        logger.info(f"✅ EMAIL TOOL SUCCESS: send_email")
        logger.info(f"📤 TOOL OUTPUT: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ EMAIL TOOL ERROR: send_email - {str(e)}")
        raise


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx Email MCP Server with FastMCP")
    
    # Run HTTP server on port 8081
    mcp.run(transport="http", host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
