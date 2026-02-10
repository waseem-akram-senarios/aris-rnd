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
        except KeyError as e:
            logger.debug(f"__init__: {type(e).__name__}: {e}")
            # Fallback to cl100k_base encoding (used by GPT-3.5/GPT-4)
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def _safe_encode(self, text: str):
        """
        Safely encode text handling special tokens that might be in the text.
        
        Args:
            text: Text to encode
        
        Returns:
            Encoded tokens as list
        """
        try:
            # Try encoding with special tokens allowed
            return self.encoding.encode(text, disallowed_special=())
        except Exception:
            try:
                # Fallback: allow all special tokens
                return self.encoding.encode(text, allowed_special="all")
            except Exception:
                # Last resort: encode without special token checks
                return self.encoding.encode(text, disallowed_special=())
    
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
            encoded = self._safe_encode(text)
            return len(encoded)
        except Exception as e:
            logger.debug(f"count_tokens: {type(e).__name__}: {e}")
            # Fallback: estimate based on character count (rough approximation)
            return len(text) // 4
    
    def _force_split_text(self, text: str) -> List[str]:
        """
        Force split text into chunks without sentence boundary detection.
        Used as fallback when normal splitting fails.
        
        Args:
            text: Text to split
        
        Returns:
            List of text chunks (guaranteed to be within chunk_size)
        """
        logger = logging.getLogger(__name__)
        
        if not text or not text.strip():
            return []
        
        try:
            # Encode to tokens (handle special tokens that might be in text)
            tokens = self._safe_encode(text)
            total_tokens = len(tokens)
            
            if total_tokens <= self.chunk_size:
                return [text]
            
            chunks = []
            start_idx = 0
            
            while start_idx < len(tokens):
                # Get chunk of exactly chunk_size tokens
                end_idx = min(start_idx + self.chunk_size, len(tokens))
                chunk_tokens = tokens[start_idx:end_idx]
                
                # Decode to text
                chunk_text = self.encoding.decode(chunk_tokens)
                
                if chunk_text.strip():
                    chunks.append(chunk_text)
                
                # Move to next chunk with overlap
                start_idx = end_idx - self.chunk_overlap
                
                # Prevent infinite loop
                if start_idx >= len(tokens):
                    break
                if start_idx < 0:
                    start_idx = 0
                # If we're at the end, add remaining tokens
                if start_idx >= len(tokens) - self.chunk_overlap:
                    if start_idx < len(tokens):
                        remaining_tokens = tokens[start_idx:]
                        remaining_text = self.encoding.decode(remaining_tokens)
                        if remaining_text.strip():
                            chunks.append(remaining_text)
                    break
            
            logger.info(f"TokenTextSplitter: Force split created {len(chunks)} chunks from {total_tokens:,} tokens")
            return chunks if chunks else [text]  # Fallback to single chunk if all else fails
            
        except Exception as e:
            logger.error(f"TokenTextSplitter: Force split failed: {e}")
            # Last resort: split by character count (rough approximation)
            # Estimate ~4 chars per token
            char_chunk_size = self.chunk_size * 4
            chunks = []
            for i in range(0, len(text), char_chunk_size - (self.chunk_overlap * 4)):
                chunk = text[i:i + char_chunk_size]
                if chunk.strip():
                    chunks.append(chunk)
            return chunks if chunks else [text]
    
    def split_text(self, text: str, progress_callback: Optional[Callable] = None) -> List[str]:
        """
        Split text into chunks based on token count, preserving sentence boundaries.
        
        Args:
            text: Text to split
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of text chunks
        """
        if not text.strip():
            return []
        
        # Encode text to tokens
        logger.debug(f"TokenTextSplitter: Encoding text ({len(text):,} chars)...")
        # Handle special tokens that might be in the text (like <|endoftext|>)
        tokens = self._safe_encode(text)
        total_tokens = len(tokens)
        logger.debug(f"TokenTextSplitter: Encoded to {total_tokens:,} tokens")
        
        if len(tokens) <= self.chunk_size:
            return [text]
        
        # Estimate number of chunks for progress tracking
        estimated_chunks = max(1, (total_tokens + self.chunk_size - 1) // self.chunk_size)
        logger.info(f"TokenTextSplitter: Splitting {total_tokens:,} tokens into ~{estimated_chunks} chunks (chunk_size={self.chunk_size})")
        
        # CRITICAL: For large documents, we MUST create multiple chunks
        # If estimated_chunks is 1 but tokens > chunk_size, something is wrong
        if total_tokens > self.chunk_size and estimated_chunks == 1:
            logger.error(f"TokenTextSplitter: ERROR - Document has {total_tokens:,} tokens (> {self.chunk_size}) but estimated_chunks=1!")
            logger.error(f"TokenTextSplitter: This indicates a calculation error. Forcing proper split...")
            # Recalculate correctly
            estimated_chunks = (total_tokens + self.chunk_size - 1) // self.chunk_size
            logger.info(f"TokenTextSplitter: Corrected estimated_chunks to {estimated_chunks}")
        
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
                                chunk_tokens = self._safe_encode(chunk_text)
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
                                final_tokens = self._safe_encode(chunk_text)
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
                    logger.debug("operation: exception suppressed")
                    # If anything goes wrong with sentence boundary detection, use original chunk
                    # This is a safety fallback
                    pass
            
            # Final verification: ensure chunk doesn't exceed limit (CRITICAL CHECK)
            # For large documents, use simpler validation to avoid multiple encode/decode cycles
            if use_sentence_boundaries:
                try:
                    final_encoded = self._safe_encode(chunk_text)
                    final_token_count = len(final_encoded)
                    
                    if final_token_count > self.chunk_size:
                        # Force truncate to exact limit
                        final_encoded = final_encoded[:self.chunk_size]
                        chunk_text = self.encoding.decode(final_encoded)
                        end_idx = start_idx + self.chunk_size
                        
                        # Verify one more time after truncation
                        verify_encoded = self._safe_encode(chunk_text)
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
                        safety_check = len(self._safe_encode(chunk_text))
                        if safety_check > self.chunk_size:
                            # Force truncate one more time
                            encoded = self._safe_encode(chunk_text)
                            encoded = encoded[:self.chunk_size]
                            chunk_text = self.encoding.decode(encoded)
                    except Exception as e:
                        logger.debug(f"operation: {type(e).__name__}: {e}")
                        pass  # If check fails, proceed with chunk as-is
                # For large documents, skip this check to avoid extra encoding
                
                chunks.append(chunk_text)
            
            # Log completion for large documents
            if total_tokens > 100000 and chunk_count % 50 == 0:
                logger.info(f"TokenTextSplitter: Created {chunk_count} chunks so far, {len(tokens) - start_idx:,} tokens remaining")
            
            # Move start index with overlap for next chunk
            # CRITICAL: Ensure we actually move forward, not backward
            new_start_idx = end_idx - self.chunk_overlap
            
            # Ensure start_idx doesn't go negative
            if new_start_idx < 0:
                new_start_idx = 0
            
            # CRITICAL: Ensure we're making progress (not stuck in same position)
            if new_start_idx <= start_idx:
                # If overlap calculation would keep us in same place, move forward by at least 1 token
                new_start_idx = start_idx + 1
                logger.warning(f"TokenTextSplitter: Overlap calculation would cause no progress, adjusting start_idx from {start_idx} to {new_start_idx}")
            
            start_idx = new_start_idx
            
            # Check if we've reached the end
            if start_idx >= len(tokens):
                break
            
            # Prevent infinite loop - if we're very close to the end, add remaining and exit
            if start_idx >= len(tokens) - self.chunk_overlap:
                # Add remaining text if there's any
                if start_idx < len(tokens):
                    remaining_tokens = tokens[start_idx:]
                    if remaining_tokens:
                        remaining_text = self.encoding.decode(remaining_tokens)
                        if remaining_text.strip():
                            chunks.append(remaining_text)
                break
            
            # Safety check: if we haven't made progress after many iterations, force exit
            if chunk_count > 10000:  # Prevent infinite loops
                logger.error(f"TokenTextSplitter: Safety limit reached (10000 chunks), forcing exit")
                if start_idx < len(tokens):
                    remaining_tokens = tokens[start_idx:]
                    if remaining_tokens:
                        remaining_text = self.encoding.decode(remaining_tokens)
                        if remaining_text.strip():
                            chunks.append(remaining_text)
                break
        
        # Calculate completion metrics
        chunking_end_time = time.time()
        total_time = chunking_end_time - chunking_start_time
        chunks_per_sec = len(chunks) / total_time if total_time > 0 else 0
        tokens_per_sec = total_tokens / total_time if total_time > 0 else 0
        
        # CRITICAL: Validate chunks are within size limits
        oversized_chunks = []
        for idx, chunk in enumerate(chunks):
            chunk_tokens = len(self._safe_encode(chunk))
            if chunk_tokens > self.chunk_size:
                oversized_chunks.append((idx, chunk_tokens))
        
        if oversized_chunks:
            logger.warning(f"TokenTextSplitter: Found {len(oversized_chunks)} oversized chunks after splitting!")
            for idx, token_count in oversized_chunks:
                logger.warning(f"TokenTextSplitter: Chunk {idx} has {token_count} tokens (exceeds {self.chunk_size})")
            # Fix oversized chunks
            fixed_chunks = []
            for idx, chunk in enumerate(chunks):
                if idx in [i for i, _ in oversized_chunks]:
                    # Re-split this chunk
                    tokens = self._safe_encode(chunk)
                    sub_chunks = []
                    sub_start = 0
                    while sub_start < len(tokens):
                        sub_end = min(sub_start + self.chunk_size, len(tokens))
                        sub_chunk_tokens = tokens[sub_start:sub_end]
                        sub_chunk_text = self.encoding.decode(sub_chunk_tokens)
                        if sub_chunk_text.strip():
                            fixed_chunks.append(sub_chunk_text)
                        sub_start = sub_end - self.chunk_overlap
                        if sub_start < 0:
                            sub_start = 0
                        if sub_start >= len(tokens):
                            break
                else:
                    fixed_chunks.append(chunk)
            chunks = fixed_chunks
            logger.info(f"TokenTextSplitter: Fixed oversized chunks, now have {len(chunks)} chunks")
        
        # CRITICAL: Verify we actually created multiple chunks for large documents
        if total_tokens > self.chunk_size and len(chunks) == 1:
            logger.error(f"TokenTextSplitter: ERROR - Large document ({total_tokens:,} tokens) resulted in only 1 chunk!")
            if chunks:
                single_chunk_tokens = len(self._safe_encode(chunks[0]))
                logger.error(f"TokenTextSplitter: Single chunk has {single_chunk_tokens} tokens (should be <= {self.chunk_size})")
                logger.error(f"TokenTextSplitter: This indicates the while loop exited too early or an exception occurred")
            # Force re-split
            logger.warning(f"TokenTextSplitter: Attempting force split as fallback...")
            try:
                chunks = self._force_split_text(text)
                logger.info(f"TokenTextSplitter: Force split resulted in {len(chunks)} chunks")
                if len(chunks) == 1:
                    logger.error(f"TokenTextSplitter: CRITICAL - Force split also resulted in 1 chunk! This is a serious bug.")
                    # Last resort: manual split by character count
                    logger.warning(f"TokenTextSplitter: Using character-based fallback split...")
                    char_chunk_size = self.chunk_size * 4  # Rough estimate: 4 chars per token
                    manual_chunks = []
                    for i in range(0, len(text), char_chunk_size - (self.chunk_overlap * 4)):
                        chunk = text[i:i + char_chunk_size]
                        if chunk.strip():
                            manual_chunks.append(chunk)
                    if len(manual_chunks) > 1:
                        chunks = manual_chunks
                        logger.info(f"TokenTextSplitter: Character-based split created {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"TokenTextSplitter: Force split failed: {e}")
                # Keep original chunks (even if wrong) to avoid complete failure
        
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
                
                # CRITICAL: Verify chunks were actually created and are within size limits
                if not text_chunks or len(text_chunks) == 0:
                    # If no chunks created, force split even if it failed
                    logger.warning(f"TokenTextSplitter: split_text returned no chunks, forcing split for document {doc_idx + 1}")
                    # Force split by manually chunking
                    text_chunks = self._force_split_text(page_content)
                
                # Verify chunk sizes - if any chunk exceeds limit, re-split
                oversized_chunks = []
                for idx, chunk in enumerate(text_chunks):
                    chunk_tokens = self.count_tokens(chunk)
                    if chunk_tokens > self.chunk_size:
                        logger.warning(f"TokenTextSplitter: Chunk {idx} has {chunk_tokens} tokens (exceeds {self.chunk_size}), will re-split")
                        oversized_chunks.append(idx)
                
                # Re-split oversized chunks
                if oversized_chunks:
                    logger.warning(f"TokenTextSplitter: Found {len(oversized_chunks)} oversized chunks, re-splitting...")
                    new_chunks = []
                    for idx, chunk in enumerate(text_chunks):
                        if idx in oversized_chunks:
                            # Re-split this chunk
                            sub_chunks = self._force_split_text(chunk)
                            new_chunks.extend(sub_chunks)
                        else:
                            new_chunks.append(chunk)
                    text_chunks = new_chunks
                    logger.info(f"TokenTextSplitter: Re-split resulted in {len(text_chunks)} chunks")
                
                # Update progress after splitting
                if progress_callback:
                    progress_callback('chunking', 0.1 + ((doc_idx + 1) / total_docs) * 0.2,
                                    detailed_message=f"Document {doc_idx + 1}/{total_docs} split into {len(text_chunks)} chunks")
            except Exception as e:
                # If splitting fails, try force split instead of single chunk
                logger.error(f"TokenTextSplitter: Error splitting document {doc_idx + 1}: {e}")
                import traceback
                logger.debug(f"TokenTextSplitter: Traceback: {traceback.format_exc()}")
                try:
                    # Try force split as fallback
                    text_chunks = self._force_split_text(page_content)
                    if not text_chunks:
                        # Last resort: create single chunk but warn
                        logger.warning(f"TokenTextSplitter: Force split also failed, creating single chunk (may exceed size limit)")
                        text_chunks = [page_content] if page_content else []
                except Exception as e2:
                    logger.error(f"TokenTextSplitter: Force split also failed: {e2}")
                text_chunks = [page_content] if page_content else []
            
            if not text_chunks:
                continue
            
            # Safely get metadata
            try:
                chunk_metadata = doc.metadata.copy() if hasattr(doc, 'metadata') and doc.metadata else {}
            except Exception as e:
                logger.debug(f"operation: {type(e).__name__}: {e}")
                chunk_metadata = {}
            
            # First pass: Check for oversized chunks and collect them for re-splitting
            oversized_indices = []
            for chunk_idx, chunk_text in enumerate(text_chunks):
                try:
                    token_count = len(self._safe_encode(chunk_text))
                    if token_count > self.chunk_size:
                        oversized_indices.append(chunk_idx)
                except:
                    # If encoding fails, check with count_tokens
                    token_count = self.count_tokens(chunk_text)
                    if token_count > self.chunk_size:
                        oversized_indices.append(chunk_idx)
            
            # Re-split oversized chunks
            if oversized_indices:
                logger.warning(f"TokenTextSplitter: Found {len(oversized_indices)} oversized chunks, re-splitting...")
                fixed_chunks = []
                for chunk_idx, chunk_text in enumerate(text_chunks):
                    if chunk_idx in oversized_indices:
                        # Re-split this chunk
                        sub_chunks = self._force_split_text(chunk_text)
                        if sub_chunks:
                            fixed_chunks.extend(sub_chunks)
                            logger.info(f"TokenTextSplitter: Chunk {chunk_idx} re-split into {len(sub_chunks)} sub-chunks")
                        else:
                            # If re-split failed, truncate as last resort
                            encoded = self._safe_encode(chunk_text)
                            if len(encoded) > self.chunk_size:
                                encoded = encoded[:self.chunk_size]
                                chunk_text = self.encoding.decode(encoded)
                            fixed_chunks.append(chunk_text)
                    else:
                        fixed_chunks.append(chunk_text)
                text_chunks = fixed_chunks
                logger.info(f"TokenTextSplitter: After re-splitting, document has {len(text_chunks)} chunks")
            
            # Track character positions in original text for citation support
            text_start_pos = 0
            for chunk_idx, chunk_text in enumerate(text_chunks):
                # Count tokens in chunk (use actual encoding for accuracy)
                try:
                    # Use the same encoding method as split_text for consistency
                    token_count = len(self._safe_encode(chunk_text))
                    # Final verification - should not exceed chunk_size after re-splitting
                    if token_count > self.chunk_size:
                        # This should not happen after re-splitting, but if it does, truncate
                        logger.error(f"Chunk {chunk_idx} still exceeds size after re-split ({token_count} > {self.chunk_size}). Truncating.")
                        encoded = self._safe_encode(chunk_text)
                        if len(encoded) > self.chunk_size:
                            encoded = encoded[:self.chunk_size]
                            chunk_text = self.encoding.decode(encoded)
                            token_count = len(encoded)
                except Exception:
                    # Fallback to count_tokens method
                    token_count = self.count_tokens(chunk_text)
                    if token_count > self.chunk_size:
                        # Last resort truncation
                        token_count = min(token_count, self.chunk_size)
                
                # Calculate character offsets for citation support
                # CRITICAL: Always set start_char and end_char for accurate page matching
                chunk_start_char = text_start_pos
                chunk_end_char = text_start_pos + len(chunk_text)
                
                # Ensure we have valid character positions
                if chunk_start_char is None:
                    chunk_start_char = 0
                if chunk_end_char is None or chunk_end_char < chunk_start_char:
                    chunk_end_char = chunk_start_char + len(chunk_text)
                
                text_start_pos = chunk_end_char  # Update for next chunk (accounting for overlap)
                
                # Determine page number for this chunk and check for image references
                chunk_page = None
                chunk_image_ref = None
                page_extraction_method = None  # Track how page was determined for debugging
                page_content_overlap = {}  # Track overlap with each page for dominant page calculation
                
                # Get document's total pages for validation
                doc_pages = chunk_metadata.get('pages', None)
                
                if page_blocks:
                    # ENHANCED: Find which page this chunk belongs to using dominant page calculation
                    # For chunks spanning multiple pages, select the page with most content
                    cumulative_pos = 0
                    
                    for page_block in page_blocks:
                        page_text = page_block.get('text', '')
                        page_num = page_block.get('page', None)
                        block_type = page_block.get('type', 'text')
                        
                        # Validate page number is within document range
                        if page_num and doc_pages and page_num > doc_pages:
                            logger.warning(f"Tokenizer: Page {page_num} in page_blocks exceeds document pages {doc_pages}")
                            continue
                        
                        # Check if this is an image block on the same page
                        if block_type == 'image' and page_num:
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
                            # Check if text actually contains the marker
                            if len(page_content) > cumulative_pos + len(page_marker):
                                text_ahead = page_content[cumulative_pos:cumulative_pos+len(page_marker)+10]
                                if page_marker.strip() in text_ahead:
                                    page_start += len(page_marker)
                            # Page end
                            page_end = cumulative_pos + len(page_text)
                            if len(page_content) > cumulative_pos:
                                check_text = page_content[cumulative_pos:cumulative_pos+50]
                                if f"--- Page {page_num} ---" in check_text:
                                    page_end += len(page_marker)
                            
                            # ENHANCED: Calculate overlap with this page for dominant page detection
                            overlap_start = max(chunk_start_char, page_start)
                            overlap_end = min(chunk_end_char, page_end)
                            
                            if overlap_start < overlap_end:
                                # Chunk overlaps with this page
                                overlap_chars = overlap_end - overlap_start
                                if doc_pages is None or page_num <= doc_pages:
                                    page_content_overlap[page_num] = overlap_chars
                                    
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
                    
                    # ENHANCED: Select dominant page (page with most content in chunk)
                    # Improved algorithm: consider both absolute overlap and percentage
                    if page_content_overlap:
                        # Calculate total chunk size for percentage calculation
                        chunk_size = chunk_end_char - chunk_start_char
                        
                        # Score each page: combine absolute overlap and percentage
                        page_scores = {}
                        for page_num, overlap_chars in page_content_overlap.items():
                            overlap_ratio = overlap_chars / chunk_size if chunk_size > 0 else 0.0
                            # Weighted score: 70% absolute overlap, 30% percentage
                            score = (overlap_chars * 0.7) + (overlap_ratio * chunk_size * 0.3)
                            page_scores[page_num] = {
                                'score': score,
                                'overlap_chars': overlap_chars,
                                'overlap_ratio': overlap_ratio
                            }
                        
                        # Select page with highest score
                        dominant_page = max(page_scores.keys(), key=lambda p: page_scores[p]['score'])
                        chunk_page = dominant_page
                        page_extraction_method = 'page_blocks_dominant'
                        
                        # Log if chunk spans multiple pages
                        if len(page_content_overlap) > 1:
                            dominant_info = page_scores[dominant_page]
                            total_overlap = sum(page_content_overlap.values())
                            dominant_ratio = dominant_info['overlap_ratio']
                            
                            if dominant_ratio < 0.7:  # Log warning if <70% content from dominant page
                                logger.debug(
                                    f"Tokenizer: Chunk {chunk_idx} spans pages {list(page_content_overlap.keys())}, "
                                    f"using dominant page {dominant_page} ({dominant_ratio:.1%} of content, "
                                    f"{dominant_info['overlap_chars']}/{chunk_size} chars)"
                                )
                            else:
                                logger.debug(
                                    f"Tokenizer: Chunk {chunk_idx} assigned to page {dominant_page} "
                                    f"({dominant_ratio:.1%} overlap, {dominant_info['overlap_chars']} chars)"
                                )
                
                # If page not found from page_blocks, try to extract from text markers
                if chunk_page is None:
                    import re
                    page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                    if page_match:
                        extracted_page = int(page_match.group(1))
                        # Validate against document pages
                        if doc_pages and extracted_page > doc_pages:
                            logger.warning(f"Tokenizer: Page {extracted_page} from text marker exceeds document pages {doc_pages}")
                        else:
                            chunk_page = extracted_page
                            page_extraction_method = 'text_marker'
                
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
                # Always ensure both 'page' and 'source_page' are set for accurate citations
                if chunk_page:
                    chunk_metadata_copy['page'] = chunk_page
                    chunk_metadata_copy['source_page'] = chunk_page
                    chunk_metadata_copy['page_extraction_method'] = page_extraction_method or 'page_blocks'
                elif 'page' in chunk_metadata_copy:
                    # Use existing page from metadata
                    chunk_metadata_copy['source_page'] = chunk_metadata_copy['page']
                    chunk_metadata_copy['page_extraction_method'] = 'existing_metadata'
                elif 'source_page' in chunk_metadata_copy:
                    # Use existing source_page if available
                    chunk_metadata_copy['page'] = chunk_metadata_copy['source_page']
                    chunk_metadata_copy['page_extraction_method'] = 'existing_metadata'
                else:
                    # Fallback: try to extract from text markers one more time
                    import re
                    page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                    if page_match:
                        extracted_page = int(page_match.group(1))
                        if not doc_pages or extracted_page <= doc_pages:
                            chunk_metadata_copy['page'] = extracted_page
                            chunk_metadata_copy['source_page'] = extracted_page
                            chunk_metadata_copy['page_extraction_method'] = 'text_marker_fallback'
                    # If still no page, default to 1 (ensures citations always have a page)
                    if 'page' not in chunk_metadata_copy:
                        chunk_metadata_copy['page'] = 1
                        chunk_metadata_copy['source_page'] = 1
                        chunk_metadata_copy['page_extraction_method'] = 'fallback_page_1'
                        # Log warning when falling back to page 1
                        source = chunk_metadata.get('source', 'Unknown')
                        logger.warning(
                            f"Tokenizer: No page found for chunk {chunk_idx}, using fallback page 1. "
                            f"Source: {source}, chunk chars: {chunk_start_char}-{chunk_end_char}"
                        )
                
                # Add image reference if found
                if chunk_image_ref:
                    chunk_metadata_copy['image_ref'] = chunk_image_ref
                    chunk_metadata_copy['has_image'] = True
                    chunk_metadata_copy['image_index'] = chunk_image_ref.get('image_index')
                    chunk_metadata_copy['image_bbox'] = chunk_image_ref.get('bbox')
                    
                    # CRITICAL: Ensure image page metadata is preserved
                    # Extract page from image_ref if available
                    img_page = chunk_image_ref.get('page') or chunk_image_ref.get('image_page')
                    if img_page:
                        # Override page metadata with image's page number
                        chunk_metadata_copy['page'] = img_page
                        chunk_metadata_copy['source_page'] = img_page
                        chunk_metadata_copy['image_page'] = img_page
                        chunk_metadata_copy['page_extraction_method'] = 'image_ref_tokenizer'
                        logger.debug(f"Tokenizer: Set page {img_page} from image_ref for chunk {chunk_idx}")
                
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
                    logger.debug(f"operation: {type(e).__name__}: {e}")
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

