"""Semantic chunking that preserves meaning by respecting sentence boundaries."""

import re
import logging
from typing import List, Dict, Any, Optional

from .base import ChunkingStrategy, Chunk

logger = logging.getLogger(__name__)


class SemanticChunker(ChunkingStrategy):
    """
    Semantic chunking strategy that respects natural language boundaries.
    
    Features:
    - Splits at sentence boundaries to preserve context
    - Maintains paragraphs when possible
    - Intelligent overlap using complete sentences
    - Respects markdown structure (headers, lists, code blocks)
    - Handles edge cases (abbreviations, decimals, etc.)
    
    This is the recommended strategy for manufacturing documents, manuals,
    and technical documentation where preserving context is critical.
    """
    
    # Sentence boundary patterns (handles common abbreviations)
    SENTENCE_ENDINGS = re.compile(
        r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s+(?=[A-Z])'
    )
    
    # Paragraph separators
    PARAGRAPH_SEP = re.compile(r'\n\s*\n+')
    
    # Markdown headers
    HEADER_PATTERN = re.compile(r'^#{1,6}\s+.+$', re.MULTILINE)
    
    # Code blocks
    CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```', re.MULTILINE)
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize semantic chunker.
        
        Additional config:
            respect_paragraphs: Keep paragraphs together when possible (default: True)
            respect_headers: Split at markdown headers (default: True)
            preserve_code_blocks: Keep code blocks intact (default: True)
        """
        super().__init__(config)
        self.respect_paragraphs = config.get("respect_paragraphs", True)
        self.respect_headers = config.get("respect_headers", True)
        self.preserve_code_blocks = config.get("preserve_code_blocks", True)
    
    async def chunk_text(
        self,
        text: str,
        document_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Chunk text using semantic boundaries.
        
        Process:
        1. Split into major sections (headers/paragraphs)
        2. Split sections into sentences
        3. Group sentences into chunks of target size
        4. Add intelligent overlap
        """
        self._validate_text(text)
        
        chunks = []
        current_position = 0
        
        # Extract and preserve code blocks if needed
        code_blocks = {}
        if self.preserve_code_blocks:
            text, code_blocks = self._extract_code_blocks(text)
        
        # Split into major sections
        sections = self._split_into_sections(text)
        
        for section_text in sections:
            # Split section into sentences
            sentences = self._split_into_sentences(section_text)
            
            if not sentences:
                continue
            
            # Group sentences into chunks
            section_chunks = self._group_sentences_into_chunks(
                sentences,
                document_id,
                current_position,
                metadata
            )
            
            chunks.extend(section_chunks)
            current_position = chunks[-1].metadata["end_char"] if chunks else 0
        
        # Restore code blocks
        if code_blocks:
            chunks = self._restore_code_blocks(chunks, code_blocks)
        
        # Re-index chunks sequentially
        for i, chunk in enumerate(chunks):
            chunk.chunk_index = i
            chunk.chunk_id = self._generate_chunk_id(document_id, i)
        
        self.logger.info(
            f"Semantic chunking complete: {len(chunks)} chunks from {len(text)} chars"
        )
        
        return chunks
    
    def _extract_code_blocks(self, text: str) -> tuple[str, Dict[str, str]]:
        """Extract code blocks and replace with placeholders."""
        code_blocks = {}
        counter = 0
        
        def replace_code_block(match):
            nonlocal counter
            placeholder = f"__CODE_BLOCK_{counter}__"
            code_blocks[placeholder] = match.group(0)
            counter += 1
            return placeholder
        
        text_with_placeholders = self.CODE_BLOCK_PATTERN.sub(replace_code_block, text)
        return text_with_placeholders, code_blocks
    
    def _restore_code_blocks(
        self,
        chunks: List[Chunk],
        code_blocks: Dict[str, str]
    ) -> List[Chunk]:
        """Restore code blocks in chunks."""
        for chunk in chunks:
            for placeholder, code_block in code_blocks.items():
                if placeholder in chunk.content:
                    chunk.content = chunk.content.replace(placeholder, code_block)
        return chunks
    
    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into major sections based on headers or paragraphs."""
        if self.respect_headers:
            # Split at markdown headers
            sections = []
            last_pos = 0
            
            for match in self.HEADER_PATTERN.finditer(text):
                if match.start() > last_pos:
                    sections.append(text[last_pos:match.start()].strip())
                last_pos = match.start()
            
            # Add remaining text
            if last_pos < len(text):
                sections.append(text[last_pos:].strip())
            
            # Filter out empty sections
            sections = [s for s in sections if s]
            
            if sections:
                return sections
        
        if self.respect_paragraphs:
            # Split by paragraphs
            sections = self.PARAGRAPH_SEP.split(text)
            return [s.strip() for s in sections if s.strip()]
        
        # Fallback: return entire text as one section
        return [text]
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences, handling common abbreviations.
        
        This is a simplified sentence splitter. For production use,
        consider using spaCy or nltk for better accuracy.
        """
        # Use regex to split at sentence boundaries
        sentences = self.SENTENCE_ENDINGS.split(text)
        
        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def _group_sentences_into_chunks(
        self,
        sentences: List[str],
        document_id: str,
        start_position: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Chunk]:
        """
        Group sentences into chunks of approximately target size.
        
        Strategy:
        - Add sentences until we reach target size
        - Include overlap by keeping last N sentences
        - Ensure chunks don't exceed max size
        """
        chunks = []
        current_sentences = []
        current_length = 0
        chunk_start_char = start_position
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # Check if adding this sentence would exceed max size
            if current_length + sentence_length > self.max_chunk_size and current_sentences:
                # Create chunk from current sentences
                chunk_text = ' '.join(current_sentences)
                chunk = self._create_chunk(
                    document_id=document_id,
                    chunk_index=len(chunks),
                    content=chunk_text,
                    start_char=chunk_start_char,
                    end_char=chunk_start_char + len(chunk_text),
                    base_metadata={
                        **(metadata or {}),
                        "sentence_count": len(current_sentences),
                        "chunking_strategy": "semantic"
                    }
                )
                chunks.append(chunk)
                
                # Calculate overlap (keep last N sentences)
                overlap_sentences = self._get_overlap_sentences(
                    current_sentences,
                    self.chunk_overlap
                )
                
                # Start new chunk with overlap
                current_sentences = overlap_sentences
                current_length = sum(len(s) for s in current_sentences)
                chunk_start_char = chunk_start_char + len(chunk_text) - current_length
            
            # Add sentence to current chunk
            current_sentences.append(sentence)
            current_length += sentence_length + 1  # +1 for space
            
            # Check if we've reached target size
            if current_length >= self.chunk_size and len(current_sentences) > 1:
                chunk_text = ' '.join(current_sentences)
                chunk = self._create_chunk(
                    document_id=document_id,
                    chunk_index=len(chunks),
                    content=chunk_text,
                    start_char=chunk_start_char,
                    end_char=chunk_start_char + len(chunk_text),
                    base_metadata={
                        **(metadata or {}),
                        "sentence_count": len(current_sentences),
                        "chunking_strategy": "semantic"
                    }
                )
                chunks.append(chunk)
                
                # Prepare overlap for next chunk
                overlap_sentences = self._get_overlap_sentences(
                    current_sentences,
                    self.chunk_overlap
                )
                current_sentences = overlap_sentences
                current_length = sum(len(s) for s in current_sentences)
                chunk_start_char = chunk_start_char + len(chunk_text) - current_length
        
        # Add remaining sentences as final chunk
        if current_sentences and current_length >= self.min_chunk_size:
            chunk_text = ' '.join(current_sentences)
            chunk = self._create_chunk(
                document_id=document_id,
                chunk_index=len(chunks),
                content=chunk_text,
                start_char=chunk_start_char,
                end_char=chunk_start_char + len(chunk_text),
                base_metadata={
                    **(metadata or {}),
                    "sentence_count": len(current_sentences),
                    "chunking_strategy": "semantic"
                }
            )
            chunks.append(chunk)
        
        return chunks
    
    def _get_overlap_sentences(
        self,
        sentences: List[str],
        target_overlap_chars: int
    ) -> List[str]:
        """
        Get last N sentences that approximately match target overlap size.
        
        Returns at least 1 sentence if available.
        """
        if not sentences:
            return []
        
        overlap_sentences = []
        overlap_length = 0
        
        # Work backwards from end of sentences
        for sentence in reversed(sentences):
            sentence_length = len(sentence)
            
            if overlap_length + sentence_length <= target_overlap_chars:
                overlap_sentences.insert(0, sentence)
                overlap_length += sentence_length
            else:
                # Stop if we've collected enough overlap
                if overlap_sentences:
                    break
                # Always include at least one sentence
                overlap_sentences.insert(0, sentence)
                break
        
        return overlap_sentences

