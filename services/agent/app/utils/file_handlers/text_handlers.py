"""Handlers for text-based file formats."""

import csv
import io
import logging
from typing import List, Dict, Any

from .base import BaseFileHandler, FileContent

logger = logging.getLogger(__name__)


class TextFileHandler(BaseFileHandler):
    """Handler for plain text files."""
    
    SUPPORTED_EXTENSIONS = {'.txt', '.text', '.log', '.md', '.markdown'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from text file."""
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
            # Try UTF-8 first, then fallback to other encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            text_content = None
            
            for encoding in encodings:
                try:
                    text_content = file_bytes.decode(encoding)
                    self.logger.debug(f"Successfully decoded {file_info['filename']} with {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            
            if text_content is None:
                # Last resort: decode with errors ignored
                text_content = file_bytes.decode('utf-8', errors='ignore')
                self.logger.warning(f"Decoded {file_info['filename']} with errors ignored")
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text_content,
                metadata={"encoding": encoding if text_content else "utf-8-ignore"}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting text content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )


class CSVFileHandler(BaseFileHandler):
    """Handler for CSV files."""
    
    SUPPORTED_EXTENSIONS = {'.csv', '.tsv'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from CSV file."""
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
            # Decode bytes to string
            text = file_bytes.decode('utf-8', errors='ignore')
            
            # Detect delimiter
            delimiter = '\t' if file_info["extension"] == '.tsv' else ','
            
            # Parse CSV
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
            
            if not rows:
                return FileContent(
                    filename=file_info["filename"],
                    extension=file_info["extension"],
                    content_type="table",
                    text_content="[Empty CSV file]",
                    metadata={"rows": 0, "columns": 0}
                )
            
            # Format as readable table
            formatted_lines = []
            
            # Add header if present
            if rows:
                header = rows[0]
                formatted_lines.append("| " + " | ".join(str(cell) for cell in header) + " |")
                formatted_lines.append("|" + "---|" * len(header))
                
                # Add data rows (limit to prevent overwhelming context)
                max_rows = 100  # Configurable limit
                for row in rows[1:max_rows+1]:
                    formatted_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                
                if len(rows) > max_rows + 1:
                    formatted_lines.append(f"\n... ({len(rows) - max_rows - 1} more rows)")
            
            text_content = "\n".join(formatted_lines)
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="table",
                text_content=text_content,
                metadata={
                    "rows": len(rows),
                    "columns": len(rows[0]) if rows else 0,
                    "delimiter": delimiter
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting CSV content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )


class RTFFileHandler(BaseFileHandler):
    """Handler for RTF (Rich Text Format) files."""
    
    SUPPORTED_EXTENSIONS = {'.rtf'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from RTF file."""
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
            # Import striprtf only when needed
            try:
                from striprtf.striprtf import rtf_to_text
            except ImportError:
                # Fallback: basic RTF stripping if striprtf not available
                text = file_bytes.decode('utf-8', errors='ignore')
                # Very basic RTF stripping - not perfect but better than nothing
                import re
                text = re.sub(r'\\[a-z]+\d*\s?', '', text)
                text = re.sub(r'[{}]', '', text)
                text = text.strip()
                
                return FileContent(
                    filename=file_info["filename"],
                    extension=file_info["extension"],
                    content_type="text",
                    text_content=text,
                    metadata={"rtf_parser": "basic"}
                )
            
            # Use striprtf for proper RTF parsing
            rtf_content = file_bytes.decode('utf-8', errors='ignore')
            text_content = rtf_to_text(rtf_content)
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text_content,
                metadata={"rtf_parser": "striprtf"}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting RTF content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )

