"""Recursive text chunking with hierarchical separators (LangChain-style)."""

import logging
from typing import List, Dict, Any, Optional

from .base import ChunkingStrategy, Chunk

logger = logging.getLogger(__name__)


class RecursiveChunker(ChunkingStrategy):
    """
    Recursive chunking strategy using hierarchical separators.
    
    Tries to split text using a hierarchy of separators, falling back to
    the next separator if chunks are still too large.
    
    Default separator hierarchy:
    1. Double newline (paragraphs)
    2. Single newline (lines)
    3. Space (words)
    4. Empty string (characters)
    
    This is inspired by LangChain's RecursiveCharacterTextSplitter.
    Good balance between semantic coherence and simplicity.
    """
    
    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize recursive chunker.
        
        Additional config:
            separators: List of separators in priority order
        """
        super().__init__(config)
        self.separators = config.get("separators", self.DEFAULT_SEPARATORS)
    
    async def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Chunk text using recursive splitting."""
        self._validate_text(text)
        
        # Recursively split text
        split_texts = self._split_text_recursive(text)
        
        # Convert to Chunk objects
        chunks = []
        current_pos = 0
        
        for i, chunk_text in enumerate(split_texts):
            chunk = self._create_chunk(
                document_id=document_id,
                chunk_index=i,
                content=chunk_text,
                start_char=current_pos,
                end_char=current_pos + len(chunk_text),
                base_metadata={
                    **(metadata or {}),
                    "chunking_strategy": "recursive"
                }
            )
            chunks.append(chunk)
            current_pos += len(chunk_text)
        
        self.logger.info(
            f"Recursive chunking complete: {len(chunks)} chunks from {len(text)} chars"
        )
        
        return chunks
    
    def _split_text_recursive(
        self,
        text: str,
        separators: Optional[List[str]] = None
    ) -> List[str]:
        """Recursively split text using hierarchy of separators."""
        if separators is None:
            separators = self.separators.copy()
        
        # Base case: no more separators or text is small enough
        if not separators or len(text) <= self.chunk_size:
            return [text] if len(text) >= self.min_chunk_size else []
        
        # Try current separator
        separator = separators[0]
        remaining_separators = separators[1:]
        
        # Split by current separator
        if separator == "":
            # Character-level split
            splits = list(text)
        else:
            splits = text.split(separator)
        
        # Merge splits into chunks
        chunks = []
        current_chunk = []
        current_length = 0
        
        for split in splits:
            split_length = len(split)
            
            # Check if adding this split exceeds chunk size
            if current_length + split_length > self.chunk_size and current_chunk:
                # Join current chunk
                chunk_text = separator.join(current_chunk)
                
                # If chunk is too large, split it recursively
                if len(chunk_text) > self.max_chunk_size and remaining_separators:
                    sub_chunks = self._split_text_recursive(
                        chunk_text,
                        remaining_separators
                    )
                    chunks.extend(sub_chunks)
                elif len(chunk_text) >= self.min_chunk_size:
                    chunks.append(chunk_text)
                
                # Start new chunk with overlap
                # For overlap, keep last item
                if self.chunk_overlap > 0 and current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_length = len(current_chunk[0])
                else:
                    current_chunk = []
                    current_length = 0
            
            # Add split to current chunk
            current_chunk.append(split)
            current_length += split_length + len(separator)
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = separator.join(current_chunk)
            if len(chunk_text) > self.max_chunk_size and remaining_separators:
                sub_chunks = self._split_text_recursive(
                    chunk_text,
                    remaining_separators
                )
                chunks.extend(sub_chunks)
            elif len(chunk_text) >= self.min_chunk_size:
                chunks.append(chunk_text)
        
        return chunks

