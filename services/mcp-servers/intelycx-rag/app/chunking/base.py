"""Base classes for document chunking strategies."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """
    Document chunk representation.
    
    Attributes:
        chunk_id: Unique identifier for the chunk
        document_id: Parent document ID
        chunk_index: Sequential index within document (0-based)
        content: Chunk text content
        metadata: Additional metadata (start_char, end_char, etc.)
        created_at: Timestamp when chunk was created
    """
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: Dict[str, Any]
    created_at: datetime


class ChunkingStrategy(ABC):
    """
    Abstract base class for chunking strategies.
    
    Different strategies optimize for different use cases:
    - Semantic: Preserves meaning by splitting at natural boundaries
    - Fixed-size: Simple, predictable chunks (fast but may break context)
    - Recursive: Hierarchical splitting with multiple separators
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize chunking strategy.
        
        Args:
            config: Configuration dictionary
                - chunk_size: Target chunk size in characters
                - chunk_overlap: Overlap between chunks in characters
                - min_chunk_size: Minimum viable chunk size
                - max_chunk_size: Maximum allowed chunk size
        """
        self.config = config
        self.chunk_size = config.get("chunk_size", 1000)
        self.chunk_overlap = config.get("chunk_overlap", 200)
        self.min_chunk_size = config.get("min_chunk_size", 100)
        self.max_chunk_size = config.get("max_chunk_size", 2000)
        self.logger = logger
        
        # Validate configuration
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("Chunk overlap must be less than chunk size")
        if self.min_chunk_size > self.chunk_size:
            raise ValueError("Minimum chunk size cannot exceed target chunk size")
    
    @abstractmethod
    async def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Split text into chunks.
        
        Args:
            text: Text to chunk
            document_id: Document identifier
            metadata: Optional metadata to include in chunks
            
        Returns:
            List of Chunk objects
            
        Raises:
            ValueError: If text is empty or invalid
        """
        pass
    
    def _generate_chunk_id(self, document_id: str, chunk_index: int) -> str:
        """Generate a unique chunk ID."""
        return f"{document_id}:chunk:{chunk_index}"
    
    def _validate_text(self, text: str) -> None:
        """Validate input text."""
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
    
    def _create_chunk(
        self,
        document_id: str,
        chunk_index: int,
        content: str,
        start_char: int,
        end_char: int,
        base_metadata: Optional[Dict[str, Any]] = None
    ) -> Chunk:
        """
        Create a Chunk object with metadata.
        
        Args:
            document_id: Document identifier
            chunk_index: Sequential chunk index
            content: Chunk content
            start_char: Start position in original text
            end_char: End position in original text
            base_metadata: Additional metadata from document
            
        Returns:
            Chunk object
        """
        metadata = {
            "start_char": start_char,
            "end_char": end_char,
            "char_count": len(content),
            "word_count": len(content.split()),
            **(base_metadata or {})
        }
        
        return Chunk(
            chunk_id=self._generate_chunk_id(document_id, chunk_index),
            document_id=document_id,
            chunk_index=chunk_index,
            content=content.strip(),
            metadata=metadata,
            created_at=datetime.utcnow()
        )
    
    def get_strategy_name(self) -> str:
        """Get the name of this chunking strategy."""
        return self.__class__.__name__.replace("Chunker", "").lower()

