"""Fixed-size chunking strategy - simple and fast."""

import logging
from typing import List, Dict, Any, Optional

from .base import ChunkingStrategy, Chunk

logger = logging.getLogger(__name__)


class FixedSizeChunker(ChunkingStrategy):
    """
    Fixed-size chunking strategy - splits text at fixed character intervals.
    
    Pros:
    - Very fast
    - Predictable chunk sizes
    - Simple implementation
    
    Cons:
    - May split in middle of words/sentences
    - Less semantic coherence
    - Context can be broken
    
    Best for: Quick prototyping, uniform chunk sizes, non-critical applications
    """
    
    async def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """Chunk text at fixed character intervals with overlap."""
        self._validate_text(text)
        
        chunks = []
        text_length = len(text)
        start = 0
        chunk_index = 0
        
        while start < text_length:
            # Calculate end position
            end = min(start + self.chunk_size, text_length)
            
            # Try to break at word boundary if possible
            if end < text_length:
                # Look for space within last 50 chars
                search_start = max(end - 50, start)
                last_space = text.rfind(' ', search_start, end)
                if last_space > start:
                    end = last_space + 1
            
            # Extract chunk content
            content = text[start:end]
            
            # Skip if too small (unless it's the last chunk)
            if len(content) < self.min_chunk_size and end < text_length:
                start = end - self.chunk_overlap
                continue
            
            # Create chunk
            chunk = self._create_chunk(
                document_id=document_id,
                chunk_index=chunk_index,
                content=content,
                start_char=start,
                end_char=end,
                base_metadata={
                    **(metadata or {}),
                    "chunking_strategy": "fixed_size"
                }
            )
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start = end - self.chunk_overlap
            chunk_index += 1
            
            # Prevent infinite loop
            if start >= text_length:
                break
        
        self.logger.info(
            f"Fixed-size chunking complete: {len(chunks)} chunks from {len(text)} chars"
        )
        
        return chunks

