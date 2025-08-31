"""FastMCP Email Server for Intelycx."""

import os
import logging
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP, Context
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
    # Don't log routine health checks to reduce noise
    # Only log on startup or if there are issues
    
    # Perform basic health checks
    health_status = {
        "status": "healthy",
        "service": "intelycx-email-mcp-server",
        "version": "0.1.0",
        "transport": "http",
        "smtp_configured": bool(email_client.username),
        "timestamp": "2024-08-26T00:00:00Z"  # Would be actual timestamp in real implementation
    }
    
    return JSONResponse(content=health_status, status_code=200)


@mcp.tool
async def send_email(
    ctx: Context,
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
    # Enhanced multi-stage progress with structured logging
    await ctx.info(
        "📧 Starting email composition...",
        extra={
            "stage": "email_start",
            "recipient_count": len(to) if isinstance(to, list) else 1,
            "has_cc": bool(cc),
            "has_bcc": bool(bcc),
            "is_html": is_html,
            "subject_length": len(subject),
            "body_length": len(body)
        }
    )
    await ctx.report_progress(progress=10, total=100)
    
    # Infrastructure logging only
    logger.debug(f"send_email called: to={to}, subject='{subject}', cc={cc}, bcc={bcc}, is_html={is_html}")
    
    try:
        # Stage 1: Validate recipients (10-25%)
        await ctx.info(
            "📧 Validating email recipients...",
            extra={
                "stage": "recipient_validation",
                "primary_recipients": to,
                "cc_recipients": cc,
                "bcc_recipients": bcc
            }
        )
        await ctx.report_progress(progress=25, total=100)
        
        # Stage 2: Prepare content (25-45%)
        await ctx.info(
            "📝 Preparing email content...",
            extra={
                "stage": "content_preparation",
                "content_type": "html" if is_html else "text",
                "subject": subject
            }
        )
        await ctx.report_progress(progress=45, total=100)
        
        # Stage 3: Connect to SMTP (45-65%)
        await ctx.info(
            "🔗 Establishing email connection...",
            extra={
                "stage": "smtp_connection",
                "smtp_configured": bool(email_client.username)
            }
        )
        await ctx.report_progress(progress=65, total=100)
        
        # Stage 4: Send email (65-90%)
        await ctx.info(
            f"📬 Sending email to {to}...",
            extra={
                "stage": "email_sending",
                "recipients": to
            }
        )
        await ctx.report_progress(progress=90, total=100)
        
        result = await email_client.send_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            is_html=is_html
        )
        
        # Stage 5: Completion (90-100%)
        await ctx.info(
            f"✅ Email sent successfully! Message ID: {result.get('message_id')}",
            extra={
                "stage": "email_complete",
                "message_id": result.get('message_id'),
                "recipients_count": result.get('recipients_count'),
                "cc_count": result.get('cc_count'),
                "bcc_count": result.get('bcc_count'),
                "status": result.get('status')
            }
        )
        await ctx.report_progress(progress=100, total=100)
        
        logger.debug(f"Email sent successfully: {result.get('message_id')}")
        
        return result
        
    except Exception as e:
        error_msg = f"Email sending failed: {str(e)}"
        await ctx.error(
            f"❌ {error_msg}",
            extra={
                "stage": "email_exception",
                "error_type": "exception",
                "exception_class": type(e).__name__,
                "recipients": to
            }
        )
        logger.error(f"send_email error: {str(e)}")
        return {
            "error": error_msg
        }


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx Email MCP Server with FastMCP")
    
    # Run HTTP server on port 8081
    mcp.run(transport="http", host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
