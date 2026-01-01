"""
Simple text parser for .txt files.
"""
import logging
import os
from typing import Optional, Dict
from .base_parser import BaseParser, ParsedDocument

logger = logging.getLogger("aris_rag.text_parser")

class TextParser(BaseParser):
    """Parser for plain text files."""
    
    def __init__(self):
        super().__init__(name="text_parser")
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None, **kwargs) -> ParsedDocument:
        """Parse plain text file."""
        try:
            if file_content:
                text = file_content.decode('utf-8', errors='ignore')
            else:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            
            return ParsedDocument(
                text=text,
                metadata={"source": file_path, "type": "txt"},
                pages=1,
                images_detected=False,
                parser_used="text_parser",
                confidence=1.0,
                extraction_percentage=1.0,
                image_count=0
            )
        except Exception as e:
            logger.error(f"Error parsing text file: {e}")
            raise ValueError(f"Failed to parse text file: {e}")

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.lower().endswith('.txt')

    def is_available(self) -> bool:
        return True
