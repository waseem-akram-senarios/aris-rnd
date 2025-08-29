"""Data models for file processing."""

import logging
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
    
    @property
    def is_error(self) -> bool:
        """Check if this represents an error state."""
        return self.error is not None
    
    @property
    def size_bytes(self) -> int:
        """Get the size of the text content in bytes."""
        return len(self.text_content.encode('utf-8')) if self.text_content else 0
    
    def get_preview(self, max_length: int = 500) -> str:
        """Get a preview of the content."""
        if self.error:
            return f"Error: {self.error}"
        if not self.text_content:
            return "No content"
        
        if len(self.text_content) <= max_length:
            return self.text_content
        
        return self.text_content[:max_length] + "..."
