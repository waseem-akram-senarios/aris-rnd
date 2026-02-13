"""Handlers for text-based file formats."""

import csv
import io
import logging
from typing import List, Dict, Any

from .base import BaseFileHandler
from ..models import FileContent

logger = logging.getLogger(__name__)


class TextHandler(BaseFileHandler):
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


class CSVHandler(BaseFileHandler):
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




class JSONHandler(BaseFileHandler):
    """Handler for JSON files."""
    
    SUPPORTED_EXTENSIONS = {'.json', '.jsonl'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from JSON file."""
        import json
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
            text = file_bytes.decode('utf-8', errors='ignore')
            
            # Try to parse and pretty-print JSON
            if file_info["extension"] == '.jsonl':
                # Handle JSON Lines format
                lines = text.strip().split('\n')
                parsed_lines = []
                for line in lines:
                    if line.strip():
                        parsed_lines.append(json.loads(line))
                content = json.dumps(parsed_lines, indent=2, ensure_ascii=False)
            else:
                # Regular JSON
                parsed = json.loads(text)
                content = json.dumps(parsed, indent=2, ensure_ascii=False)
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="structured",
                text_content=content,
                metadata={"format": "json"}
            )
            
        except json.JSONDecodeError:
            # If JSON is invalid, return raw text
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text,
                metadata={"format": "json", "valid": False}
            )
        except Exception as e:
            self.logger.error(f"Error extracting JSON content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )


class XMLHandler(BaseFileHandler):
    """Handler for XML files."""
    
    SUPPORTED_EXTENSIONS = {'.xml', '.xhtml', '.svg'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from XML file."""
        import xml.etree.ElementTree as ET
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
            text = file_bytes.decode('utf-8', errors='ignore')
            
            # Try to parse XML for validation
            root = ET.fromstring(text)
            
            # Return the raw XML text (already formatted)
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="structured",
                text_content=text,
                metadata={"format": "xml", "root_tag": root.tag}
            )
            
        except ET.ParseError:
            # If XML is invalid, return raw text
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text,
                metadata={"format": "xml", "valid": False}
            )
        except Exception as e:
            self.logger.error(f"Error extracting XML content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )


class HTMLHandler(BaseFileHandler):
    """Handler for HTML files."""
    
    SUPPORTED_EXTENSIONS = {'.html', '.htm'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from HTML file."""
        from html.parser import HTMLParser
        import re
        
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
            html_text = file_bytes.decode('utf-8', errors='ignore')
            
            # Simple HTML to text extraction
            # Remove script and style elements
            html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
            html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
            
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', ' ', html_text)
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text,
                metadata={"format": "html", "original_length": len(html_text)}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting HTML content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )


class MarkdownHandler(BaseFileHandler):
    """Handler for Markdown files."""
    
    SUPPORTED_EXTENSIONS = {'.md', '.markdown', '.mkd', '.mdx'}
    
    def can_handle(self, file_extension: str) -> bool:
        return file_extension.lower() in self.SUPPORTED_EXTENSIONS
    
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from Markdown file."""
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
            # Markdown is plain text, just decode it
            text_content = file_bytes.decode('utf-8', errors='ignore')
            
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="text",
                text_content=text_content,
                metadata={"format": "markdown"}
            )
            
        except Exception as e:
            self.logger.error(f"Error extracting Markdown content: {str(e)}")
            return FileContent(
                filename=file_info["filename"],
                extension=file_info["extension"],
                content_type="error",
                text_content="",
                metadata={},
                error=str(e)
            )

