"""Handler for PDF files."""

import logging
import io
from typing import Dict, Any

from .base import BaseFileHandler
from ..models import FileContent

logger = logging.getLogger(__name__)


class PDFHandler(BaseFileHandler):
    """Handler for PDF files."""
    
    SUPPORTED_EXTENSIONS = {'.pdf'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from PDF file."""
        file_info = self.get_file_info(file_path)
        
        if not self.validate_file_size(file_bytes):
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=f"File size exceeds {self.MAX_FILE_SIZE} bytes limit"
            )
        
        try:
            import fitz  # PyMuPDF
            
            # Open PDF from bytes
            pdf_stream = io.BytesIO(file_bytes)
            pdf = fitz.open(stream=pdf_stream, filetype="pdf")
            
            if len(pdf) == 0:
                return FileContent(
                    filename=file_info["filename"],
                    extension=file_info["extension"],
                    content_type="text",
                    text_content="[Empty PDF document]",
                    metadata={"pages": 0}
                )
            
            text_parts = []
            total_pages = len(pdf)
            
            for page_num, page in enumerate(pdf):
                page_text = page.get_text().strip()
                
                if page_text:
                    # Add page header
                    text_parts.append(f"--- Page {page_num + 1} of {total_pages} ---")
                    text_parts.append(page_text)
                    text_parts.append("")  # Add blank line between pages
            
            pdf.close()
            
            if not text_parts:
                return FileContent(
                    filename=file_info["filename"],
                    extension=file_info["extension"],
                    content_type="text",
                    text_content="[PDF contains no extractable text - may contain only images]",
                    metadata={"pages": total_pages, "has_text": False}
                )
            
            text_content = "\n".join(text_parts)
            
            # Check if content might be truncated due to size
            if len(text_content) > 100000:  # Arbitrary large text threshold
                self.logger.info(f"Large PDF text content: {len(text_content)} characters")
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text_content,
                metadata={
                    "pages": total_pages,
                    "has_text": True,
                    "text_length": len(text_content)
                }
            )
            
        except ImportError as e:
            self.logger.error(f"Missing required library for PDF processing: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error="PDF processing library (PyMuPDF) not installed"
            )
        except Exception as e:
            self.logger.error(f"Error extracting PDF content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )

