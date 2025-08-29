"""File handlers for various document formats."""

from .base import BaseFileHandler
from .text import TextHandler, CSVHandler, JSONHandler, XMLHandler, HTMLHandler, MarkdownHandler
from .pdf import PDFHandler
from .office import WordHandler, ExcelHandler, PowerPointHandler, RTFHandler

__all__ = [
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
