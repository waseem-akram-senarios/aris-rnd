"""
Token-aware text splitter using TikToken.
"""
import tiktoken
import time
import logging
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
    
    def split_text(self, text: str, progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Split text into chunks based on token count, preserving sentence boundaries.
        
        Args:
            text: Text to split
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of text chunks
        """
        logger = logging.getLogger(__name__)
        
        if not text.strip():
            return []
        
        # Encode text to tokens
        logger.debug(f"TokenTextSplitter: Encoding text ({len(text):,} chars)...")
        tokens = self.encoding.encode(text)
        total_tokens = len(tokens)
        logger.debug(f"TokenTextSplitter: Encoded to {total_tokens:,} tokens")
        
        if len(tokens) <= self.chunk_size:
            return [text]
        
        # Estimate number of chunks for progress tracking
        estimated_chunks = (total_tokens + self.chunk_size - 1) // self.chunk_size
        logger.info(f"TokenTextSplitter: Splitting {total_tokens:,} tokens into ~{estimated_chunks} chunks (chunk_size={self.chunk_size})")
        
        chunks = []
        start_idx = 0
        chunk_count = 0
        last_progress_log = time.time()
        chunking_start_time = time.time()
        
        # Try to split on sentence boundaries for better accuracy
        # For very large documents (>100K chars), use simpler/faster chunking
        use_sentence_boundaries = len(text) < 100000
        if use_sentence_boundaries:
            import re
            # Common sentence endings
            sentence_endings = re.compile(r'([.!?]\s+|\.\n|\n\n)')
        else:
            logger.info(f"TokenTextSplitter: Large document detected ({len(text):,} chars) - using fast chunking (no sentence boundary detection)")
        
        while start_idx < len(tokens):
            # Log progress every 10 chunks or every 5 seconds for large documents
            chunk_count += 1
            current_time = time.time()
            
            # Determine logging frequency based on document size
            if total_tokens > 500000:  # Very large document - log every 2 chunks or 3 seconds
                log_interval_chunks = 2
                log_interval_seconds = 3.0
            elif total_tokens > 100000:  # Large document - log every 5 chunks or 3 seconds
                log_interval_chunks = 5
                log_interval_seconds = 3.0
            else:  # Smaller document - log every 10 chunks or 5 seconds
                log_interval_chunks = 10
                log_interval_seconds = 5.0
            
            if chunk_count % log_interval_chunks == 0 or (current_time - last_progress_log) >= log_interval_seconds:
                progress_pct = (start_idx / total_tokens * 100) if total_tokens > 0 else 0
                elapsed_time = current_time - chunking_start_time
                tokens_remaining = total_tokens - start_idx
                
                # Calculate processing speed and estimated time remaining
                if elapsed_time > 0 and start_idx > 0:
                    chunks_per_sec = chunk_count / elapsed_time
                    tokens_per_sec = start_idx / elapsed_time
                    if tokens_per_sec > 0:
                        estimated_remaining = tokens_remaining / tokens_per_sec
                        remaining_min = int(estimated_remaining // 60)
                        remaining_sec = int(estimated_remaining % 60)
                        time_remaining_str = f"~{remaining_min}m {remaining_sec}s remaining"
                    else:
                        time_remaining_str = "calculating..."
                else:
                    chunks_per_sec = 0
                    time_remaining_str = "calculating..."
                
                logger.info(
                    f"TokenTextSplitter: Progress - {chunk_count} chunks created, "
                    f"{start_idx:,}/{total_tokens:,} tokens ({progress_pct:.1f}%) | "
                    f"Speed: {chunks_per_sec:.2f} chunks/sec | {time_remaining_str}"
                )
                if progress_callback:
                    progress_callback('chunking', progress_pct / 100, 
                                    detailed_message=f"Creating chunks... {chunk_count} chunks, {progress_pct:.1f}% complete | {time_remaining_str}")
                last_progress_log = current_time
            
            # Get chunk
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode to check for sentence boundaries
            chunk_text = self.encoding.decode(chunk_tokens)
            
            # For large documents without sentence boundaries, skip complex validation
            # Only perform simple token count check
            if not use_sentence_boundaries:
                # Simple chunking for large documents - just verify token count
                if len(chunk_tokens) > self.chunk_size:
                    chunk_tokens = chunk_tokens[:self.chunk_size]
                    chunk_text = self.encoding.decode(chunk_tokens)
            # If not at end of text, try to extend to sentence boundary (only for smaller docs)
            elif end_idx < len(tokens) and use_sentence_boundaries:
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
            # For large documents, use simpler validation to avoid multiple encode/decode cycles
            if use_sentence_boundaries:
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
            else:
                # For large documents, just verify token count (already done above)
                # No need for multiple re-encodings
                pass
            
            # Only add non-empty chunks (with final safety check)
            if chunk_text.strip():
                # Final safety check before adding to chunks list (only for smaller docs)
                if use_sentence_boundaries:
                    try:
                        safety_check = len(self.encoding.encode(chunk_text))
                        if safety_check > self.chunk_size:
                            # Force truncate one more time
                            encoded = self.encoding.encode(chunk_text)
                            encoded = encoded[:self.chunk_size]
                            chunk_text = self.encoding.decode(encoded)
                    except Exception:
                        pass  # If check fails, proceed with chunk as-is
                # For large documents, skip this check to avoid extra encoding
                
                chunks.append(chunk_text)
            
            # Log completion for large documents
            if total_tokens > 100000 and chunk_count % 50 == 0:
                logger.info(f"TokenTextSplitter: Created {chunk_count} chunks so far, {len(tokens) - start_idx:,} tokens remaining")
            
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
        
        # Calculate completion metrics
        chunking_end_time = time.time()
        total_time = chunking_end_time - chunking_start_time
        chunks_per_sec = len(chunks) / total_time if total_time > 0 else 0
        tokens_per_sec = total_tokens / total_time if total_time > 0 else 0
        
        logger.info(
            f"TokenTextSplitter: Chunking completed - {len(chunks)} chunks created from {total_tokens:,} tokens | "
            f"Time: {total_time:.2f}s | Speed: {chunks_per_sec:.2f} chunks/sec, {tokens_per_sec:.0f} tokens/sec"
        )
        if progress_callback:
            progress_callback('chunking', 1.0, detailed_message=f"Chunking complete: {len(chunks)} chunks created in {total_time:.1f}s")
        
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
            
            # Extract page_blocks metadata for citation support
            page_blocks = None
            if hasattr(doc, 'metadata') and isinstance(doc.metadata, dict):
                page_blocks = doc.metadata.get('page_blocks', None)
            
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
                
                text_chunks = self.split_text(page_content, progress_callback=progress_callback)
                
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
            
            # Track character positions in original text for citation support
            text_start_pos = 0
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
                
                # Calculate character offsets for citation support
                chunk_start_char = text_start_pos
                chunk_end_char = text_start_pos + len(chunk_text)
                text_start_pos = chunk_end_char  # Update for next chunk (accounting for overlap)
                
                # Determine page number for this chunk and check for image references
                chunk_page = None
                chunk_image_ref = None
                if page_blocks:
                    # Find which page this chunk belongs to based on character position
                    # Account for "--- Page X ---" markers in the text
                    cumulative_pos = 0
                    for page_block in page_blocks:
                        page_text = page_block.get('text', '')
                        page_num = page_block.get('page', None)
                        block_type = page_block.get('type', 'text')
                        
                        # Check if this is an image block on the same page
                        if block_type == 'image' and page_num:
                            # If chunk is on this page, associate with image
                            if chunk_page == page_num or (chunk_page is None and page_num):
                                chunk_image_ref = {
                                    'page': page_num,
                                    'image_index': page_block.get('image_index'),
                                    'bbox': page_block.get('bbox'),
                                    'xref': page_block.get('xref'),
                                    'type': 'image'
                                }
                        
                        if page_text and page_num:
                            # Account for page marker in original text (if present)
                            page_marker = f"--- Page {page_num} ---\n"
                            page_start = cumulative_pos
                            # Page end includes marker if text has markers
                            page_end = cumulative_pos + len(page_text)
                            
                            # Check if chunk starts within this page
                            if chunk_start_char >= page_start and chunk_start_char < page_end:
                                chunk_page = page_num
                                # Check for images on this page
                                if not chunk_image_ref:
                                    for img_block in page_blocks:
                                        if (isinstance(img_block, dict) and 
                                            img_block.get('type') == 'image' and 
                                            img_block.get('page') == page_num):
                                            chunk_image_ref = {
                                                'page': page_num,
                                                'image_index': img_block.get('image_index'),
                                                'bbox': img_block.get('bbox'),
                                                'xref': img_block.get('xref'),
                                                'type': 'image'
                                            }
                                            break
                            # Also check if chunk overlaps with this page
                            elif chunk_start_char < page_end and chunk_end_char > page_start:
                                chunk_page = page_num
                                # Check for images on this page
                                if not chunk_image_ref:
                                    for img_block in page_blocks:
                                        if (isinstance(img_block, dict) and 
                                            img_block.get('type') == 'image' and 
                                            img_block.get('page') == page_num):
                                            chunk_image_ref = {
                                                'page': page_num,
                                                'image_index': img_block.get('image_index'),
                                                'bbox': img_block.get('bbox'),
                                                'xref': img_block.get('xref'),
                                                'type': 'image'
                                            }
                                            break
                            
                            cumulative_pos = page_end
                
                # If page not found from page_blocks, try to extract from text markers
                if chunk_page is None:
                    import re
                    # Look for "--- Page X ---" markers in chunk
                    page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                    if page_match:
                        chunk_page = int(page_match.group(1))
                
                # Create new document with metadata
                chunk_metadata_copy = chunk_metadata.copy()
                chunk_metadata_copy.update({
                    'chunk_index': chunk_idx,
                    'total_chunks': len(text_chunks),
                    'source_chunk': doc_idx,
                    'token_count': token_count,
                    'start_char': chunk_start_char,  # Character offset in original document
                    'end_char': chunk_end_char  # Character offset in original document
                })
                
                # Add page number for citation support
                if chunk_page:
                    chunk_metadata_copy['page'] = chunk_page
                    chunk_metadata_copy['source_page'] = chunk_page
                elif 'page' in chunk_metadata_copy:
                    chunk_metadata_copy['source_page'] = chunk_metadata_copy['page']
                
                # Add image reference if found
                if chunk_image_ref:
                    chunk_metadata_copy['image_ref'] = chunk_image_ref
                    chunk_metadata_copy['has_image'] = True
                    chunk_metadata_copy['image_index'] = chunk_image_ref.get('image_index')
                    chunk_metadata_copy['image_bbox'] = chunk_image_ref.get('bbox')
                
                # Preserve page_blocks metadata if available (for citation support)
                if 'page_blocks' in chunk_metadata_copy:
                    # Keep page_blocks reference for citation lookup
                    pass  # Already in metadata
                elif page_blocks:
                    chunk_metadata_copy['page_blocks'] = page_blocks
                
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

