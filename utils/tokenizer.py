"""
Token-aware text splitter using TikToken.
"""
import tiktoken
from typing import List, Optional, Callable
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
        Count tokens in text using the same encoding as split_text.
        
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
            # Use the exact same encoding method as split_text for consistency
            encoded = self.encoding.encode(text)
            return len(encoded)
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
                                new_end_idx = start_idx + len(chunk_tokens)
                                # CRITICAL: Ensure chunk never exceeds chunk_size
                                max_end_idx = start_idx + self.chunk_size
                                end_idx = min(new_end_idx, max_end_idx, len(tokens))
                                
                                # If we exceeded the limit, truncate to exact limit
                                if end_idx > start_idx + self.chunk_size:
                                    end_idx = start_idx + self.chunk_size
                                
                                # Re-encode to ensure we don't exceed limit
                                chunk_tokens = tokens[start_idx:end_idx]
                                chunk_text = self.encoding.decode(chunk_tokens)
                                
                                # Final verification: re-encode and check
                                final_tokens = self.encoding.encode(chunk_text)
                                if len(final_tokens) > self.chunk_size:
                                    # If still too large, truncate more aggressively
                                    chunk_tokens = tokens[start_idx:start_idx + self.chunk_size]
                                    chunk_text = self.encoding.decode(chunk_tokens)
                                    end_idx = start_idx + self.chunk_size
                            except Exception:
                                # If encoding fails, use original chunk with strict limit
                                end_idx = min(start_idx + self.chunk_size, len(tokens))
                                chunk_tokens = tokens[start_idx:end_idx]
                                chunk_text = self.encoding.decode(chunk_tokens)
                except (IndexError, ValueError, Exception) as e:
                    # If anything goes wrong with sentence boundary detection, use original chunk
                    # This is a safety fallback
                    pass
            
            # Final verification: ensure chunk doesn't exceed limit (CRITICAL CHECK)
            try:
                final_encoded = self.encoding.encode(chunk_text)
                final_token_count = len(final_encoded)
                
                if final_token_count > self.chunk_size:
                    # Force truncate to exact limit
                    final_encoded = final_encoded[:self.chunk_size]
                    chunk_text = self.encoding.decode(final_encoded)
                    end_idx = start_idx + self.chunk_size
                    
                    # Verify one more time after truncation
                    verify_encoded = self.encoding.encode(chunk_text)
                    if len(verify_encoded) > self.chunk_size:
                        # Last resort: take exact token slice from original
                        chunk_tokens = tokens[start_idx:start_idx + self.chunk_size]
                        chunk_text = self.encoding.decode(chunk_tokens)
                        end_idx = start_idx + self.chunk_size
            except Exception:
                # If encoding fails, use safe truncation
                chunk_tokens = tokens[start_idx:min(start_idx + self.chunk_size, len(tokens))]
                chunk_text = self.encoding.decode(chunk_tokens)
                end_idx = start_idx + len(chunk_tokens)
            
            # Only add non-empty chunks (with final safety check)
            if chunk_text.strip():
                # Final safety check before adding to chunks list
                try:
                    safety_check = len(self.encoding.encode(chunk_text))
                    if safety_check > self.chunk_size:
                        # Force truncate one more time
                        encoded = self.encoding.encode(chunk_text)
                        encoded = encoded[:self.chunk_size]
                        chunk_text = self.encoding.decode(encoded)
                except Exception:
                    pass  # If check fails, proceed with chunk as-is
                
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
    
    def split_documents(self, documents: List[Document], progress_callback: Optional[Callable] = None) -> List[Document]:
        """
        Split documents into chunks based on token count.
        
        Args:
            documents: List of Document objects to split
            progress_callback: Optional callback function(status, progress, **kwargs) for progress updates
        
        Returns:
            List of Document chunks with token count metadata
        """
        all_chunks = []
        
        if not documents:
            return all_chunks
        
        total_docs = len(documents)
        for doc_idx, doc in enumerate(documents):
            # Update progress for each document
            if progress_callback and total_docs > 0:
                doc_progress = doc_idx / total_docs  # 0.0 to 1.0
                progress_callback('chunking', 0.1 + (doc_progress * 0.2), 
                                detailed_message=f"Splitting document {doc_idx + 1}/{total_docs} into chunks...")
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
                # Estimate text length for progress
                text_length = len(page_content) if page_content else 0
                if progress_callback:
                    if text_length > 100000:  # Large document
                        progress_callback('chunking', 0.1 + ((doc_idx + 0.3) / total_docs) * 0.2,
                                        detailed_message=f"Processing large document {doc_idx + 1}/{total_docs} ({text_length:,} chars)...")
                    else:
                        progress_callback('chunking', 0.1 + ((doc_idx + 0.5) / total_docs) * 0.2,
                                        detailed_message=f"Splitting document {doc_idx + 1}/{total_docs} into chunks...")
                
                text_chunks = self.split_text(page_content)
                
                # Update progress after splitting
                if progress_callback:
                    progress_callback('chunking', 0.1 + ((doc_idx + 1) / total_docs) * 0.2,
                                    detailed_message=f"Document {doc_idx + 1}/{total_docs} split into {len(text_chunks)} chunks")
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
                # Count tokens in chunk (use actual encoding for accuracy)
                try:
                    # Use the same encoding method as split_text for consistency
                    token_count = len(self.encoding.encode(chunk_text))
                    # Verify it doesn't exceed chunk_size (safety check)
                    if token_count > self.chunk_size:
                        # This shouldn't happen, but if it does, log and truncate
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Chunk token count ({token_count}) exceeds chunk_size ({self.chunk_size}). Truncating.")
                        # Re-encode and truncate
                        encoded = self.encoding.encode(chunk_text)
                        if len(encoded) > self.chunk_size:
                            encoded = encoded[:self.chunk_size]
                            chunk_text = self.encoding.decode(encoded)
                            token_count = len(encoded)
                except Exception:
                    # Fallback to count_tokens method
                    token_count = self.count_tokens(chunk_text)
                    if token_count > self.chunk_size:
                        token_count = self.chunk_size  # Cap at chunk_size
                
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

