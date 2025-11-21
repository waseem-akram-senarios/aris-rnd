"""
Token-aware text splitter using TikToken.
"""
import tiktoken
from typing import List, Optional
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document


class TokenTextSplitter:
    """
    Text splitter that chunks text based on token count rather than character count.
    Uses TikToken for accurate token counting.
    """
    
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        model_name: str = "text-embedding-3-small"
    ):
        """
        Initialize token-aware text splitter.
        
        Args:
            chunk_size: Maximum number of tokens per chunk
            chunk_overlap: Number of tokens to overlap between chunks
            model_name: Model name for tokenizer encoding
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.model_name = model_name
        
        # Get encoding for the model
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding (used by GPT-3.5/GPT-4)
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
        
        Returns:
            Number of tokens
        """
        if text is None:
            return 0
        if not isinstance(text, str):
            text = str(text)
        if not text.strip():
            return 0
        try:
            return len(self.encoding.encode(text))
        except Exception:
            # Fallback: estimate based on character count (rough approximation)
            return len(text) // 4
    
    def split_text(self, text: str) -> List[str]:
        """
        Split text into chunks based on token count, preserving sentence boundaries.
        
        Args:
            text: Text to split
        
        Returns:
            List of text chunks
        """
        if not text.strip():
            return []
        
        # Encode text to tokens
        tokens = self.encoding.encode(text)
        
        if len(tokens) <= self.chunk_size:
            return [text]
        
        chunks = []
        start_idx = 0
        
        # Try to split on sentence boundaries for better accuracy
        import re
        # Common sentence endings
        sentence_endings = re.compile(r'([.!?]\s+|\.\n|\n\n)')
        
        while start_idx < len(tokens):
            # Get chunk
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode to check for sentence boundaries
            chunk_text = self.encoding.decode(chunk_tokens)
            
            # If not at end of text, try to extend to sentence boundary
            if end_idx < len(tokens):
                try:
                    # Look ahead a bit to find sentence boundary
                    lookahead = min(50, len(tokens) - end_idx)  # Look ahead up to 50 tokens
                    extended_tokens = tokens[start_idx:end_idx + lookahead]
                    extended_text = self.encoding.decode(extended_tokens)
                    
                    # Find last sentence boundary in extended text
                    sentences = sentence_endings.split(extended_text)
                    if len(sentences) > 1:
                        # Reconstruct up to last complete sentence
                        # Note: split() with capturing group returns: [text, delimiter, text, delimiter, ...]
                        # So we need to pair them correctly
                        complete_sentences = []
                        i = 0
                        while i < len(sentences) - 1:
                            # Pair text with its delimiter
                            if i + 1 < len(sentences):
                                complete_sentences.append(sentences[i] + sentences[i + 1])
                                i += 2
                            else:
                                # Last item without delimiter - only add if it has content
                                if i < len(sentences) and sentences[i].strip():
                                    complete_sentences.append(sentences[i])
                                break
                        
                        if complete_sentences:
                            chunk_text = ''.join(complete_sentences)
                            # Re-encode to get actual end index
                            try:
                                chunk_tokens = self.encoding.encode(chunk_text)
                                end_idx = start_idx + len(chunk_tokens)
                                # Ensure end_idx doesn't exceed token bounds
                                if end_idx > len(tokens):
                                    end_idx = len(tokens)
                            except Exception:
                                # If encoding fails, use original chunk
                                end_idx = min(start_idx + self.chunk_size, len(tokens))
                except (IndexError, ValueError, Exception) as e:
                    # If anything goes wrong with sentence boundary detection, use original chunk
                    # This is a safety fallback
                    pass
            
            # Only add non-empty chunks
            if chunk_text.strip():
                chunks.append(chunk_text)
            
            # Move start index with overlap
            start_idx = end_idx - self.chunk_overlap
            
            # Ensure start_idx doesn't go negative or exceed bounds
            if start_idx < 0:
                start_idx = 0
            if start_idx >= len(tokens):
                break
            
            # Prevent infinite loop
            if start_idx >= len(tokens) - self.chunk_overlap:
                # Add remaining text
                if start_idx < len(tokens):
                    remaining_tokens = tokens[start_idx:]
                    remaining_text = self.encoding.decode(remaining_tokens)
                    if remaining_text.strip():
                        chunks.append(remaining_text)
                break
        
        return chunks
    
    def split_documents(self, documents: List[Document]) -> List[Document]:
        """
        Split documents into chunks based on token count.
        
        Args:
            documents: List of Document objects to split
        
        Returns:
            List of Document chunks with token count metadata
        """
        all_chunks = []
        
        if not documents:
            return all_chunks
        
        for doc_idx, doc in enumerate(documents):
            # Validate document
            if doc is None:
                continue
            if not hasattr(doc, 'page_content'):
                continue
            
            # Ensure page_content is a string
            page_content = doc.page_content if doc.page_content else ""
            if not isinstance(page_content, str):
                page_content = str(page_content)
            
            # Split text
            try:
                text_chunks = self.split_text(page_content)
            except Exception as e:
                # If splitting fails, create a single chunk with the original text
                text_chunks = [page_content] if page_content else []
            
            if not text_chunks:
                continue
            
            # Safely get metadata
            try:
                chunk_metadata = doc.metadata.copy() if hasattr(doc, 'metadata') and doc.metadata else {}
            except Exception:
                chunk_metadata = {}
            
            for chunk_idx, chunk_text in enumerate(text_chunks):
                # Count tokens in chunk
                try:
                    token_count = self.count_tokens(chunk_text)
                except Exception:
                    token_count = 0
                
                # Create new document with metadata
                chunk_metadata_copy = chunk_metadata.copy()
                chunk_metadata_copy.update({
                    'chunk_index': chunk_idx,
                    'total_chunks': len(text_chunks),
                    'source_chunk': doc_idx,
                    'token_count': token_count
                })
                
                # Add source page if available
                if 'page' in chunk_metadata_copy:
                    chunk_metadata_copy['source_page'] = chunk_metadata_copy['page']
                
                try:
                    chunk_doc = Document(
                        page_content=chunk_text,
                        metadata=chunk_metadata_copy
                    )
                    all_chunks.append(chunk_doc)
                except Exception as e:
                    # Skip chunks that can't be created
                    continue
        
        return all_chunks
    
    def split_text_with_metadata(
        self,
        text: str,
        metadata: Optional[dict] = None
    ) -> List[Document]:
        """
        Split text into Document chunks with metadata.
        
        Args:
            text: Text to split
            metadata: Optional metadata to add to each chunk
        
        Returns:
            List of Document chunks
        """
        text_chunks = self.split_text(text)
        documents = []
        
        for idx, chunk_text in enumerate(text_chunks):
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update({
                'chunk_index': idx,
                'total_chunks': len(text_chunks),
                'token_count': self.count_tokens(chunk_text)
            })
            
            doc = Document(
                page_content=chunk_text,
                metadata=chunk_metadata
            )
            documents.append(doc)
        
        return documents

