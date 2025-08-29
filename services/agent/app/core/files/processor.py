"""Main file processor that handles S3 integration and file processing orchestration."""

import logging
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

from .factory import FileHandlerFactory
from .models import FileContent

logger = logging.getLogger(__name__)


class FileProcessor:
    """Main file processor that orchestrates file handling from S3."""
    
    MAX_FILE_SIZE = 4 * 1024 * 1024  # 4 MB
    
    def __init__(self, aws_region: Optional[str] = None):
        """Initialize file processor with S3 client and handler factory."""
        self.s3_client = boto3.client('s3', region_name=aws_region) if aws_region else boto3.client('s3')
        self.handler_factory = FileHandlerFactory()
        self.logger = logger
    
    def validate_file_size_from_s3(self, bucket: str, key: str) -> Tuple[bool, int]:
        """Check file size in S3 before downloading."""
        try:
            response = self.s3_client.head_object(Bucket=bucket, Key=key)
            file_size = response['ContentLength']
            
            if file_size > self.MAX_FILE_SIZE:
                self.logger.warning(f"File {key} size ({file_size} bytes) exceeds limit ({self.MAX_FILE_SIZE} bytes)")
                return False, file_size
            
            return True, file_size
        except ClientError as e:
            self.logger.error(f"Error checking file size in S3: {str(e)}")
            raise
    
    def download_from_s3(self, bucket: str, key: str) -> bytes:
        """Download file from S3 and return as bytes."""
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            file_bytes = response['Body'].read()
            self.logger.info(f"Successfully downloaded {key} from {bucket} ({len(file_bytes)} bytes)")
            return file_bytes
        except ClientError as e:
            self.logger.error(f"Error downloading file from S3: {str(e)}")
            raise
    
    def process_s3_file(self, bucket: str, key: str) -> FileContent:
        """Process a file from S3 and extract its content."""
        filename = Path(key).name
        extension = Path(key).suffix.lower()
        
        try:
            # Validate file size first
            is_valid_size, file_size = self.validate_file_size_from_s3(bucket, key)
            if not is_valid_size:
                return FileContent(
                    filename=filename,
                    extension=extension,
                    content_type="error",
                    text_content="",
                    metadata={"size": file_size},
                    error=f"File size ({file_size} bytes) exceeds maximum allowed size ({self.MAX_FILE_SIZE} bytes)"
                )
            
            # Check if file type is supported
            if not self.handler_factory.is_supported(key):
                return FileContent(
                    filename=filename,
                    extension=extension,
                    content_type="error",
                    text_content="",
                    metadata={},
                    error=f"Unsupported file type: {extension}. Supported types: txt, csv, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx"
                )
            
            # Download file
            file_bytes = self.download_from_s3(bucket, key)
            
            # Process file with appropriate handler
            file_content = self.handler_factory.process_file(key, file_bytes)
            
            # Add S3 metadata
            file_content.metadata["s3_bucket"] = bucket
            file_content.metadata["s3_key"] = key
            file_content.metadata["file_size"] = len(file_bytes)
            
            return file_content
            
        except Exception as e:
            self.logger.error(f"Error processing S3 file {bucket}/{key}: {str(e)}")
            return FileContent(
                filename=filename,
                extension=extension,
                content_type="error",
                text_content="",
                metadata={"s3_bucket": bucket, "s3_key": key},
                error=f"Failed to process file: {str(e)}"
            )
    
    def inject_file_content_into_message(self, message: str, file_content: FileContent) -> str:
        """Inject file content into user's message as context."""
        if file_content.error:
            # Include error in context
            context = f"\n\n{file_content.to_context_string()}\n\n"
            return message + context
        
        # Build context string
        context_parts = [
            "\n\n--- Attached Document ---",
            f"Filename: {file_content.filename}",
            f"Type: {file_content.extension}",
        ]
        
        # Add metadata if relevant
        if "pages" in file_content.metadata:
            context_parts.append(f"Pages: {file_content.metadata['pages']}")
        elif "sheets" in file_content.metadata:
            context_parts.append(f"Sheets: {file_content.metadata['sheets']}")
        elif "slides" in file_content.metadata:
            context_parts.append(f"Slides: {file_content.metadata['slides']}")
        elif "rows" in file_content.metadata:
            context_parts.append(f"Rows: {file_content.metadata['rows']}")
        
        # Add content
        context_parts.append("\n--- Content ---")
        context_parts.append(file_content.text_content)
        context_parts.append("--- End of Document ---\n")
        
        context = "\n".join(context_parts)
        
        # Combine message with file context
        enhanced_message = f"{message}\n{context}"
        
        return enhanced_message
    
    def process_document_for_response(self, bucket: str, key: str) -> Dict[str, Any]:
        """Process document and return structured response for WebSocket."""
        file_content = self.process_s3_file(bucket, key)
        
        if file_content.error:
            return {
                "document": {
                    "name": file_content.filename,
                    "format": "error",
                    "error": file_content.error
                }
            }
        
        return {
            "document": {
                "name": file_content.filename,
                "format": file_content.extension[1:] if file_content.extension else "unknown",
                "type": file_content.content_type,
                "metadata": file_content.metadata,
                "source": {
                    "text": file_content.text_content[:5000],  # Limit preview
                    "full_length": len(file_content.text_content)
                }
            }
        }

