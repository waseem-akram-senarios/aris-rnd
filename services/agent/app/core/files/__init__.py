"""File processing and document handling core library."""

from .processor import FileProcessor
from .models import FileContent
from .s3_utils import get_document_content_from_s3, DocumentContent
from .factory import FileHandlerFactory
from .handlers import (
    BaseFileHandler,
    TextHandler,
    CSVHandler,
    JSONHandler,
    XMLHandler,
    HTMLHandler,
    MarkdownHandler,
    PDFHandler,
    WordHandler,
    ExcelHandler,
    PowerPointHandler,
    RTFHandler,
)

__all__ = [
    "FileProcessor",
    "FileContent",
    "DocumentContent",
    "get_document_content_from_s3",
    "FileHandlerFactory",
    "BaseFileHandler",
    "TextHandler",
    "CSVHandler",
    "JSONHandler",
    "XMLHandler",
    "HTMLHandler",
    "MarkdownHandler",
    "PDFHandler",
    "WordHandler",
    "ExcelHandler",
    "PowerPointHandler",
    "RTFHandler",
]
