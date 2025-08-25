"""Factory for creating appropriate file handlers based on file type."""

import logging
from typing import Optional, List
from pathlib import Path

from .base import BaseFileHandler, FileContent
from .text_handlers import TextFileHandler, CSVFileHandler, RTFFileHandler
from .office_handlers import WordDocumentHandler, ExcelFileHandler, PowerPointHandler
from .pdf_handler import PDFFileHandler

logger = logging.getLogger(__name__)


class FileHandlerFactory:
    """Factory for creating appropriate file handlers."""
    
    # Define supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.txt', '.text', '.log', '.md', '.markdown',  # Text files
        '.csv', '.tsv',  # CSV files
        '.rtf',  # RTF files
        '.pdf',  # PDF files
        '.doc', '.docx',  # Word documents
        '.xls', '.xlsx',  # Excel files
        '.ppt', '.pptx',  # PowerPoint presentations
    }
    
    def __init__(self):
        # Initialize all handlers
        self.handlers: List[BaseFileHandler] = [
            TextFileHandler(),
            CSVFileHandler(),
            RTFFileHandler(),
            PDFFileHandler(),
            WordDocumentHandler(),
            ExcelFileHandler(),
            PowerPointHandler(),
        ]
        logger.info(f"FileHandlerFactory initialized with {len(self.handlers)} handlers")
    
    def get_handler(self, file_extension: str) -> Optional[BaseFileHandler]:
        """Get appropriate handler for the given file extension."""
        ext_lower = file_extension.lower()
        
        # Check if extension is supported
        if ext_lower not in self.SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported file extension: {ext_lower}")
            return None
        
        # Find the appropriate handler
        for handler in self.handlers:
            if handler.can_handle(ext_lower):
                logger.debug(f"Using {handler.__class__.__name__} for {ext_lower}")
                return handler
        
        logger.warning(f"No handler found for extension: {ext_lower}")
        return None
    
    def is_supported(self, file_path: str) -> bool:
        """Check if the file type is supported."""
        ext = Path(file_path).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS
    
    def process_file(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Process a file and extract its content."""
        ext = Path(file_path).suffix.lower()
        
        handler = self.get_handler(ext)
        if not handler:
            return FileContent(
                filename=Path(file_path).name,
                extension=ext,
                content_type="error",
                text_content="",
                metadata={},
                error=f"Unsupported file type: {ext}"
            )
        
        try:
            return handler.extract_content(file_path, file_bytes)
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            return FileContent(
                filename=Path(file_path).name,
                extension=ext,
                content_type="error",
                text_content="",
                metadata={},
                error=f"Failed to process file: {str(e)}"
            )

