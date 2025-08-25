"""Base file handler abstraction for processing various document formats."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileContent:
    """Structured representation of extracted file content."""
    
    filename: str
    extension: str
    content_type: str  # 'text', 'table', 'structured', 'error'
    text_content: str
    metadata: Dict[str, Any]
    error: Optional[str] = None
    
    def to_context_string(self) -> str:
        """Convert file content to string suitable for LLM context."""
        if self.error:
            return f"[Error processing {self.filename}: {self.error}]"
        
        header = f"--- Document: {self.filename} ---\n"
        content = self.text_content
        footer = f"\n--- End of {self.filename} ---"
        
        return header + content + footer


class BaseFileHandler(ABC):
    """Abstract base class for file handlers."""
    
    MAX_FILE_SIZE = 4 * 1024 * 1024  # 4 MB
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def can_handle(self, file_extension: str) -> bool:
        """Check if this handler can process the given file extension."""
        pass
    
    @abstractmethod
    def extract_content(self, file_path: str, file_bytes: bytes) -> FileContent:
        """Extract content from the file."""
        pass
    
    def validate_file_size(self, file_bytes: bytes) -> bool:
        """Validate that file size is within limits."""
        size = len(file_bytes)
        if size > self.MAX_FILE_SIZE:
            self.logger.warning(f"File size {size} exceeds limit of {self.MAX_FILE_SIZE}")
            return False
        return True
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Extract basic file information."""
        path = Path(file_path)
        return {
            "filename": path.name,
            "extension": path.suffix.lower(),
            "stem": path.stem
        }

