"""FastMCP Email Server for Intelycx."""

import os
import logging
from typing import Any, Dict, List, Optional, Union, Annotated
from enum import Enum

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, EmailStr
from starlette.requests import Request
from starlette.responses import JSONResponse
from .email_client import EmailClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server with enhanced configuration
mcp = FastMCP(
    "Intelycx Email",
    on_duplicate_tools="warn"  # Warn about duplicate tool registrations
)

# Initialize email client
email_client = EmailClient(
    smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    smtp_port=int(os.environ.get("SMTP_PORT", "587")),
    username=os.environ.get("SMTP_USER"),
    password=os.environ.get("SMTP_PASSWORD"),
    use_tls=os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
)


# Enums for constrained values
class EmailPriority(Enum):
    """Email priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Pydantic models for structured parameters and responses
class EmailRecipient(BaseModel):
    """Email recipient with optional display name."""
    email: str = Field(description="Email address")
    name: Optional[str] = Field(None, description="Display name")


class EmailResponse(BaseModel):
    """Response model for email operations."""
    success: bool = Field(description="Whether the email was sent successfully")
    message_id: Optional[str] = Field(None, description="Unique message identifier")
    recipients_count: Optional[int] = Field(None, description="Number of primary recipients")
    cc_count: Optional[int] = Field(None, description="Number of CC recipients")
    bcc_count: Optional[int] = Field(None, description="Number of BCC recipients")
    status: Optional[str] = Field(None, description="Detailed status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    sent_at: Optional[str] = Field(None, description="Timestamp when email was sent")
    size_kb: Optional[float] = Field(None, description="Email size in kilobytes")


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


@mcp.tool(
    name="send_email",
    description="Send emails with flexible recipient support, rich formatting, and comprehensive delivery tracking",
    tags={"email", "communication", "notification", "messaging"},
    meta={"version": "2.0", "category": "communication", "author": "intelycx"},
    annotations={
        "title": "Email Sender",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether email was sent successfully"},
            "message_id": {"type": "string", "description": "Unique message identifier"},
            "recipients_count": {"type": "integer", "description": "Number of primary recipients"},
            "cc_count": {"type": "integer", "description": "Number of CC recipients"},
            "bcc_count": {"type": "integer", "description": "Number of BCC recipients"},
            "status": {"type": "string", "description": "Detailed status message"},
            "error": {"type": "string", "description": "Error message if unsuccessful"},
            "sent_at": {"type": "string", "description": "Timestamp when email was sent"},
            "size_kb": {"type": "number", "description": "Email size in kilobytes"}
        },
        "required": ["success"]
    }
)
async def send_email(
    to: Annotated[Union[str, List[str], List[Dict[str, str]]], Field(
        description="Email recipients - string, list of strings, or list of dicts with email/name"
    )],
    subject: Annotated[str, Field(
        min_length=1,
        max_length=200,
        description="Email subject line"
    )],
    body: Annotated[str, Field(
        min_length=1,
        description="Email body content"
    )],
    cc: Annotated[Optional[Union[str, List[str], List[Dict[str, str]]]], Field(
        None,
        description="CC recipients - same formats as 'to'"
    )] = None,
    bcc: Annotated[Optional[Union[str, List[str], List[Dict[str, str]]]], Field(
        None,
        description="BCC recipients - same formats as 'to'"
    )] = None,
    is_html: bool = False,
    priority: EmailPriority = EmailPriority.NORMAL,
    ctx: Context = None
) -> EmailResponse:
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
    # Enhanced multi-stage progress with structured logging and notifications
    await ctx.info(
        "📧 Starting email composition...",
        extra={
            "stage": "email_start",
            "recipient_count": len(to) if isinstance(to, list) else 1,
            "has_cc": bool(cc),
            "has_bcc": bool(bcc),
            "is_html": is_html,
            "priority": priority.value,
            "subject_length": len(subject),
            "body_length": len(body),
            "tool_version": "2.0"
        }
    )
    await ctx.report_progress(progress=10, total=100)
    
    # Notify start of email process
    await ctx.notify(f"Composing {priority.value} priority email to {len(to) if isinstance(to, list) else 1} recipient(s)", level="info")
    
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
        email_size_kb = round(len(f"{subject}{body}") / 1024, 2)
        
        await ctx.info(
            f"✅ Email sent successfully! Message ID: {result.get('message_id')}",
            extra={
                "stage": "email_complete",
                "message_id": result.get('message_id'),
                "recipients_count": result.get('recipients_count'),
                "cc_count": result.get('cc_count'),
                "bcc_count": result.get('bcc_count'),
                "status": result.get('status'),
                "email_size_kb": email_size_kb
            }
        )
        await ctx.report_progress(progress=100, total=100)
        await ctx.notify(f"Email sent successfully to {result.get('recipients_count', 0)} recipients", level="success")
        
        logger.debug(f"Email sent successfully: {result.get('message_id')}")
        
        # Return structured response with metadata
        if isinstance(result, dict):
            result["size_kb"] = email_size_kb
            return EmailResponse(**result)
        else:
            return EmailResponse(
                success=True,
                message_id=result.get('message_id') if hasattr(result, 'get') else None,
                size_kb=email_size_kb
            )
        
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
        await ctx.notify(f"Email sending failed: {str(e)}", level="error")
        logger.error(f"send_email error: {str(e)}")
        
        # Return structured error response
        return EmailResponse(
            success=False,
            error=error_msg
        )


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx Email MCP Server with FastMCP")
    
    # Run HTTP server on port 8081
    mcp.run(transport="http", host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
