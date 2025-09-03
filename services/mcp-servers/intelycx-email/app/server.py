"""FastMCP Email Server for Intelycx."""

import os
import logging
from typing import Any, Dict, List, Optional, Union, Annotated
from enum import Enum
from datetime import datetime

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field, EmailStr
from starlette.requests import Request
from starlette.responses import JSONResponse
from .email_client import EmailClient
from .drivers import EmailPriority, EmailAttachment

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server with enhanced configuration
mcp = FastMCP(
    "Intelycx Email",
    on_duplicate_tools="warn"  # Warn about duplicate tool registrations
)

# Initialize enhanced email client with driver support
# Default to log driver if no credentials are configured
default_driver = "log"
if os.environ.get("SMTP_USER") and os.environ.get("SMTP_PASSWORD"):
    default_driver = "smtp"
elif os.environ.get("EMAIL_SENDER") and os.environ.get("EMAIL_REGION"):
    default_driver = "ses"

email_client = EmailClient(
    driver_name=os.environ.get("EMAIL_DRIVER", default_driver),
    # Legacy fallback for backward compatibility
    smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
    smtp_port=int(os.environ.get("SMTP_PORT", "587")),
    username=os.environ.get("SMTP_USER"),
    password=os.environ.get("SMTP_PASSWORD"),
    use_tls=os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
)


# Pydantic models for structured parameters and responses
class EmailRecipient(BaseModel):
    """Email recipient with optional display name."""
    email: str = Field(description="Email address")
    name: Optional[str] = Field(None, description="Display name")


class EmailResponse(BaseModel):
    """Response model for email operations."""
    success: bool = Field(description="Whether the email was sent successfully")
    message_id: Optional[str] = Field(None, description="Unique message identifier")
    recipients_count: int = Field(0, description="Number of primary recipients")
    cc_count: int = Field(0, description="Number of CC recipients") 
    bcc_count: int = Field(0, description="Number of BCC recipients")
    status: str = Field("unknown", description="Detailed status message")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    sent_at: Optional[str] = Field(None, description="Timestamp when email was sent")
    size_kb: float = Field(0.0, description="Email size in kilobytes")
    
    class Config:
        # Allow None values and provide defaults
        validate_assignment = True
        extra = "ignore"


class EmailDriverTestResponse(BaseModel):
    """Response model for email driver testing operations."""
    success: bool = Field(description="Whether the driver test passed")
    driver_info: Optional[Dict[str, Any]] = Field(None, description="Information about the current driver")
    connection_test: bool = Field(False, description="Result of connection test")
    configuration_status: str = Field("unknown", description="Status of driver configuration")
    error: Optional[str] = Field(None, description="Error message if test failed")
    test_timestamp: str = Field(description="Timestamp when test was performed")
    
    class Config:
        validate_assignment = True
        extra = "ignore"


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    # Don't log routine health checks to reduce noise
    # Only log on startup or if there are issues
    
    # Perform basic health checks
    driver_info = email_client.get_driver_info()
    
    health_status = {
        "status": "healthy",
        "service": "intelycx-email-mcp-server",
        "version": "0.1.0",
        "transport": "http",
        "email_driver": driver_info["driver_name"],
        "driver_configured": bool(email_client.driver.config),
        "timestamp": datetime.now().isoformat()
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
    reply_to: Annotated[Optional[str], Field(
        None,
        description="Reply-to email address"
    )] = None,
    attachment_urls: Annotated[Optional[List[str]], Field(
        None,
        description="List of URLs to download and attach to email"
    )] = None,
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
    
    # Log start of email process (notify not available in current FastMCP version)
    logger.info(f"Composing {priority.value} priority email to {len(to) if isinstance(to, list) else 1} recipient(s)")
    
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
                "stage": "email_connection",
                "driver_name": email_client.driver.driver_name,
                "driver_configured": bool(email_client.driver.config)
            }
        )
        await ctx.report_progress(progress=65, total=100)
        
        # Stage 4: Process attachments (65-75%)
        attachments = []
        if attachment_urls:
            await ctx.info(
                f"📎 Processing {len(attachment_urls)} attachments...",
                extra={
                    "stage": "attachment_processing",
                    "attachment_count": len(attachment_urls)
                }
            )
            await ctx.report_progress(progress=75, total=100)
            
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    for i, url in enumerate(attachment_urls):
                        try:
                            response = await client.get(url)
                            response.raise_for_status()
                            
                            # Extract filename from URL or use default
                            filename = url.split('/')[-1] or f"attachment_{i+1}"
                            content_type = response.headers.get('content-type', 'application/octet-stream')
                            
                            attachment = EmailAttachment(
                                filename=filename,
                                content=response.content,
                                content_type=content_type
                            )
                            attachments.append(attachment)
                            
                            await ctx.info(f"📎 Downloaded attachment: {filename}")
                            
                        except Exception as e:
                            await ctx.error(f"Failed to download attachment from {url}: {e}")
                            # Continue with other attachments
                            
            except ImportError:
                await ctx.error("httpx library not available for attachment downloads")
            except Exception as e:
                await ctx.error(f"Error processing attachments: {e}")
        
        # Stage 5: Send email (75-90%)
        await ctx.info(
            f"📬 Sending email to {to}...",
            extra={
                "stage": "email_sending",
                "recipients": to,
                "attachments_count": len(attachments)
            }
        )
        await ctx.report_progress(progress=90, total=100)
        
        result = await email_client.send_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            is_html=is_html,
            priority=priority,
            attachments=attachments if attachments else None,
            reply_to=reply_to
        )
        
        # Stage 6: Completion (90-100%)
        # Use size from result if available, otherwise calculate
        email_size_kb = result.get("size_kb", round(len(f"{subject}{body}") / 1024, 2))
        
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
        # Log success (notify not available in current FastMCP version)
        logger.info(f"Email sent successfully to {result.get('recipients_count', 0)} recipients")
        
        logger.debug(f"Email sent successfully: {result.get('message_id')}")
        
        # Return structured response using Pydantic model
        if isinstance(result, dict):
            return EmailResponse(
                success=result.get("success", True),
                message_id=result.get("message_id"),
                recipients_count=result.get("recipients_count", 0),
                cc_count=result.get("cc_count", 0),
                bcc_count=result.get("bcc_count", 0),
                status=result.get("status", "completed"),
                error=result.get("error"),
                sent_at=result.get("sent_at", datetime.now().isoformat()),
                size_kb=result.get("size_kb", email_size_kb)
            )
        else:
            return EmailResponse(
                success=True,
                message_id=result.get('message_id') if hasattr(result, 'get') else None,
                recipients_count=1,
                cc_count=0,
                bcc_count=0,
                status="completed",
                error=None,
                sent_at=datetime.now().isoformat(),
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
        # Log error (notify not available in current FastMCP version)
        logger.error(f"Email sending failed: {str(e)}")
        logger.error(f"send_email error: {str(e)}")
        
        # Return structured error response using Pydantic model
        return EmailResponse(
            success=False,
            message_id=None,
            recipients_count=0,
            cc_count=0,
            bcc_count=0,
            status="failed",
            error=error_msg,
            sent_at=datetime.now().isoformat(),
            size_kb=0.0
        )


@mcp.tool(
    name="test_email_driver",
    description="Test the current email driver configuration and connectivity",
    tags={"email", "testing", "diagnostics"},
    meta={"version": "1.0", "category": "diagnostics", "author": "intelycx"},
    annotations={
        "title": "Email Driver Tester",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def test_email_driver(ctx: Context = None) -> EmailDriverTestResponse:
    """
    Test the current email driver configuration and connectivity.
    
    This tool checks if the email driver is properly configured and can connect
    to the email service. It provides diagnostic information about the driver
    and its configuration without sending any actual emails.
    
    Returns:
        Dictionary containing:
        - success: Whether the driver test passed
        - driver_info: Information about the current driver
        - connection_test: Result of connection test
        - configuration_status: Status of driver configuration
        - error: Error message if test failed
    """
    await ctx.info("🔧 Testing email driver configuration...")
    await ctx.report_progress(progress=20, total=100)
    
    try:
        # Get driver information
        driver_info = email_client.get_driver_info()
        
        await ctx.info(
            f"📧 Testing {driver_info['driver_name']} driver...",
            extra={
                "driver_name": driver_info['driver_name'],
                "driver_class": driver_info['driver_class']
            }
        )
        await ctx.report_progress(progress=50, total=100)
        
        # Test connection
        connection_test = await email_client.test_connection()
        
        await ctx.info(
            f"🔗 Connection test: {'PASSED' if connection_test else 'FAILED'}",
            extra={"connection_test": connection_test}
        )
        await ctx.report_progress(progress=80, total=100)
        
        # Get configuration status
        config_status = "configured" if email_client.driver.config else "missing_config"
        
        await ctx.info(
            f"✅ Driver test completed",
            extra={
                "connection_test": connection_test,
                "config_status": config_status
            }
        )
        await ctx.report_progress(progress=100, total=100)
        
        # Log test results (notify not available in current FastMCP version)
        if connection_test:
            logger.info(f"Email driver ({driver_info['driver_name']}) test passed")
        else:
            logger.warning(f"Email driver ({driver_info['driver_name']}) test failed")
        
        return EmailDriverTestResponse(
            success=connection_test,
            driver_info=driver_info,
            connection_test=connection_test,
            configuration_status=config_status,
            test_timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        error_msg = f"Email driver test failed: {str(e)}"
        await ctx.error(error_msg)
        # Log error (notify not available in current FastMCP version)
        logger.error(f"Email driver test error: {str(e)}")
        
        return EmailDriverTestResponse(
            success=False,
            error=error_msg,
            test_timestamp=datetime.now().isoformat()
        )


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx Email MCP Server with FastMCP")
    
    # Run HTTP server on port 8081
    mcp.run(transport="http", host="0.0.0.0", port=8081)


if __name__ == "__main__":
    main()
