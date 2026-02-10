"""
Base parser interface for all document parsers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ParsedDocument:
    """Data class representing a parsed document."""
    text: str
    metadata: Dict
    pages: int
    images_detected: bool
    parser_used: str
    confidence: float = 1.0
    extraction_percentage: float = 0.0  # Percentage of pages with text extracted
    image_count: int = 0  # Number of images detected in the document
    
    def __post_init__(self):
        """Validate parsed document data."""
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if self.pages < 0:
            raise ValueError("pages must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


class BaseParser(ABC):
    """Abstract base class for all document parsers."""
    
    def __init__(self, name: str):
        """
        Initialize the parser.
        
        Args:
            name: Name of the parser (e.g., 'pymupdf', 'docling', 'textract')
        """
        self.name = name
    
    @abstractmethod
    def parse(self, file_path: str, file_content: Optional[bytes] = None) -> ParsedDocument:
        """
        Parse a document and extract text.
        
        Args:
            file_path: Path to the document file
            file_content: Optional file content as bytes (for in-memory processing)
        
        Returns:
            ParsedDocument containing extracted text and metadata
        
        Raises:
            ValueError: If file cannot be parsed
            FileNotFoundError: If file_path doesn't exist and file_content is None
        """
        pass
    
    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """
        Check if this parser can handle the given file.
        
        Args:
            file_path: Path to the file to check
        
        Returns:
            True if parser can handle this file type, False otherwise
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the required dependencies or services for this parser are available.
        
        Returns:
            True if available, False otherwise
        """
        pass
    
    def get_name(self) -> str:
        """Get the name of this parser."""
        return self.name

