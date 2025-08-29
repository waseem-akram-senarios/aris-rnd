"""Base file handler abstraction for processing various document formats."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any
from pathlib import Path

from ..models import FileContent

logger = logging.getLogger(__name__)


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
