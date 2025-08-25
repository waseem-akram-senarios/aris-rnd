"""File handlers module for processing various document formats."""

from .base import BaseFileHandler, FileContent
from .factory import FileHandlerFactory
from .processor import FileProcessor

# Export main components
__all__ = [
    'BaseFileHandler',
    'FileContent',
    'FileHandlerFactory',
    'FileProcessor',
]

