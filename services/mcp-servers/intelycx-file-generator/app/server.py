"""FastMCP File Generator Server for Intelycx."""

import os
import logging
import asyncio
from typing import Any, Dict, Optional
from io import BytesIO
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# AWS S3 imports
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Filter to exclude health check requests from uvicorn access logs
class HealthCheckAccessLogFilter(logging.Filter):
    """Filter to exclude health check requests from access logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Filter out health check paths from uvicorn access logs
        # Format: "172.31.23.238:51492 - \"GET /health HTTP/1.1\" 200 OK"
        if hasattr(record, 'msg'):
            msg = str(record.msg)
            # Exclude /health paths from uvicorn access logs
            if 'GET /health' in msg or '"GET /health' in msg:
                return False
        return True

# Apply filter to uvicorn access logger
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(HealthCheckAccessLogFilter())

# Create FastMCP server
mcp = FastMCP(
    "Intelycx File Generator",
    on_duplicate_tools="warn"
)

# Initialize S3 client
try:
    s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "us-east-2"))
    bucket_name = os.getenv("S3_BUCKET_NAME", "iris-batch-001-data-975049910508")
    logger.info(f"🪣 S3 initialized: bucket={bucket_name}")
except Exception as e:
    logger.error(f"❌ Failed to initialize S3: {str(e)}")
    s3_client = None
    bucket_name = None


# Response model
class FileCreationResponse(BaseModel):
    """Response from file creation operations."""
    success: bool = Field(description="Whether the operation was successful")
    file_url: Optional[str] = Field(None, description="S3 URL to access the created file")
    file_path: Optional[str] = Field(None, description="Storage path of the file")
    file_size: Optional[int] = Field(None, description="Size of the created file in bytes")
    filename: Optional[str] = Field(None, description="Name of the created file")
    error_message: Optional[str] = Field(None, description="Error message if operation failed")


def _construct_file_path(chat_id: str, filename: str) -> str:
    """Construct the standard file path: chats/{chat_id}/{filename}"""
    return f"chats/{chat_id}/{filename}"


def _generate_pdf(title: str, content: str, author: Optional[str] = None) -> bytes:
    """Generate PDF content using ReportLab."""
    buffer = BytesIO()
    
    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Set document metadata
    if author:
        doc.author = author
    doc.title = title
    doc.creator = "Intelycx File Generator"
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom title style
    title_style = ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2E3B4E')
    )
    
    # Create custom body style
    body_style = ParagraphStyle(
        name='CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        spaceAfter=12,
        leading=14
    )
    
    # Build document content
    story = []
    
    # Add title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 20))
    
    # Add timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph(f"Generated: {timestamp}", styles['Normal']))
    story.append(Spacer(1, 30))
    
    # Add content paragraphs
    paragraphs = content.split('\n\n')
    for paragraph in paragraphs:
        if paragraph.strip():
            story.append(Paragraph(paragraph.strip(), body_style))
            story.append(Spacer(1, 12))
    
    # Build PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


async def _upload_to_s3(file_content: bytes, file_path: str) -> Dict[str, Any]:
    """Upload file to S3."""
    if not s3_client or not bucket_name:
        return {
            "success": False,
            "error_message": "S3 client not initialized"
        }
    
    try:
        # Upload to S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_path,
            Body=file_content,
            ContentType="application/pdf",
            ServerSideEncryption='AES256'
        )
        
        # Generate presigned download URL (expires in 1 hour) - run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            signed_url = await loop.run_in_executor(
                executor,
                lambda: s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': file_path},
                    ExpiresIn=3600  # 1 hour
                )
            )
        
        file_size = len(file_content)
        s3_path = f"s3://{bucket_name}/{file_path}"
        
        logger.info(f"✅ File uploaded: {s3_path} ({file_size} bytes)")
        logger.info(f"🔗 Generated download URL (expires in 1 hour): {signed_url}")
        
        return {
            "success": True,
            "file_url": signed_url,  # Now returns HTTPS download URL
            "file_path": file_path,
            "file_size": file_size,
            "s3_path": s3_path  # Keep S3 path for reference
        }
        
    except Exception as e:
        error_message = f"S3 upload failed: {str(e)}"
        logger.error(f"❌ {error_message}")
        return {
            "success": False,
            "error_message": error_message
        }


@mcp.tool()
async def create_pdf(
    title: str,
    content: str,
    chat_id: str,
    filename: Optional[str] = None,
    author: Optional[str] = None,
    ctx: Context = None
) -> FileCreationResponse:
    """
    Create a PDF document with title and content.
    
    Args:
        title: The main title of the PDF document
        content: The main text content of the document
        chat_id: Chat ID for organizing the file in storage
        filename: Custom filename (optional, will generate if not provided)
        author: Document author (optional)
    
    Returns:
        FileCreationResponse with file details or error information
    """
    if ctx:
        ctx.info(
            "📄 Starting PDF creation...",
            extra={
                "stage": "pdf_start",
                "title_length": len(title),
                "content_length": len(content),
                "chat_id": chat_id,
                "has_filename": bool(filename),
                "has_author": bool(author),
                "tool_version": "1.0"
            }
        )
    
    try:
        # Generate filename if not provided
        if not filename:
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_')[:50]
            filename = f"{safe_title}.pdf"
        
        # Ensure .pdf extension
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        if ctx:
            ctx.info(
                f"📝 Generating PDF: {filename}",
                extra={
                    "stage": "pdf_generation",
                    "filename": filename,
                    "safe_title": safe_title if 'safe_title' in locals() else title
                }
            )
        
        # Generate PDF content
        pdf_bytes = _generate_pdf(title=title, content=content, author=author)
        
        if ctx:
            ctx.info(
                f"📤 Uploading to S3...",
                extra={
                    "stage": "s3_upload",
                    "pdf_size": len(pdf_bytes),
                    "bucket": bucket_name
                }
            )
        
        # Construct file path
        file_path = _construct_file_path(chat_id, filename)
        
        # Upload to S3
        upload_result = await _upload_to_s3(pdf_bytes, file_path)
        
        if upload_result["success"]:
            if ctx:
                ctx.info(
                    f"✅ PDF created successfully: {filename}",
                    extra={
                        "stage": "pdf_complete",
                        "filename": filename,
                        "file_size": upload_result['file_size'],
                        "file_url": upload_result["file_url"],
                        "file_path": upload_result["file_path"]
                    }
                )
            
            logger.info(f"✅ PDF created: {filename} ({upload_result['file_size']} bytes)")
            
            return FileCreationResponse(
                success=True,
                file_url=upload_result["file_url"],
                file_path=upload_result["file_path"],
                file_size=upload_result["file_size"],
                filename=filename
            )
        else:
            error_msg = upload_result["error_message"]
            logger.error(f"❌ {error_msg}")
            
            if ctx:
                ctx.info(
                    f"❌ Upload failed: {error_msg}",
                    extra={
                        "stage": "upload_failed",
                        "error": error_msg
                    }
                )
            
            return FileCreationResponse(
                success=False,
                error_message=error_msg
            )
            
    except Exception as e:
        error_msg = f"PDF creation failed: {str(e)}"
        logger.error(f"❌ {error_msg}")
        
        if ctx:
            ctx.info(
                f"❌ Error: {error_msg}",
                extra={
                    "stage": "pdf_error",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
        
        return FileCreationResponse(
            success=False,
            error_message=error_msg
        )


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    return JSONResponse({"status": "healthy", "service": "Intelycx File Generator"})


def main():
    """Main entry point."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    
    logger.info(f"🚀 Starting Intelycx File Generator MCP Server on {host}:{port}")
    logger.info(f"🪣 S3 Bucket: {bucket_name}")
    
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
