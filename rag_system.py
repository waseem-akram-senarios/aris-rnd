"""
RAG System for document processing and querying
"""
import os
import time as time_module
import math
import logging
import traceback
from typing import List, Dict, Optional, Callable
import numpy as np
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document
import requests
from utils.tokenizer import TokenTextSplitter
from vectorstores.vector_store_factory import VectorStoreFactory
from config.settings import ARISConfig

load_dotenv()

class RAGSystem:
    def __init__(self, use_cerebras=False, metrics_collector=None, 
                 embedding_model=None,
                 openai_model=None,
                 cerebras_model=None,
                 vector_store_type="faiss",
                 opensearch_domain=None,
                 opensearch_index=None,
                 chunk_size=None,
                 chunk_overlap=None):
        self.use_cerebras = use_cerebras
        
        # Store model selections - use ARISConfig defaults if not provided
        if embedding_model is None:
            embedding_model = ARISConfig.EMBEDDING_MODEL
        if openai_model is None:
            openai_model = ARISConfig.OPENAI_MODEL
        if cerebras_model is None:
            cerebras_model = ARISConfig.CEREBRAS_MODEL
        
        self.embedding_model = embedding_model
        self.openai_model = openai_model
        self.cerebras_model = cerebras_model
        
        # Vector store configuration
        self.vector_store_type = vector_store_type.lower()
        self.opensearch_domain = opensearch_domain
        self.opensearch_index = opensearch_index

        # Active document filter (set by UI to restrict queries to selected docs)
        self.active_sources: Optional[List[str]] = None
        
        # Chunking configuration - use defaults optimized for large documents if not provided
        if chunk_size is None:
            chunk_size = ARISConfig.DEFAULT_CHUNK_SIZE
        if chunk_overlap is None:
            chunk_overlap = ARISConfig.DEFAULT_CHUNK_OVERLAP
        
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        
        # Use selected embedding model (use instance variable after defaults applied)
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=self.embedding_model
        )
        self.vectorstore = None
        # Use token-aware text splitter with configurable chunking
        self.text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=embedding_model
        )
        
        # Document tracking for incremental updates
        self.document_index: Dict[str, List[int]] = {}  # {doc_id: [chunk_indices]}
        self.total_tokens = 0
        
        # Metrics collector for R&D analytics
        self.metrics_collector = metrics_collector
        
        # Initialize LLM
        if use_cerebras:
            self.llm = None  # Will use Cerebras API directly
            self.cerebras_api_key = os.getenv('CEREBRAS_API_KEY')
        else:
            self.llm = None  # Will use OpenAI API directly
            self.openai_api_key = os.getenv('OPENAI_API_KEY')
    
    def process_documents(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None):
        """Process and chunk documents, then create vector store"""
        from scripts.setup_logging import get_logger
        logger = get_logger("aris_rag.rag_system")
        
        # Validate inputs
        if not texts:
            return 0
        
        # Create Document objects
        # IMPORTANT: Convert all text to plain strings BEFORE threading to avoid PyMuPDF NoSessionContext errors
        documents = []
        for i, text in enumerate(texts):
            # Safely get metadata - handle case where metadatas list is shorter than texts
            if metadatas and i < len(metadatas):
                metadata = metadatas[i] if isinstance(metadatas[i], dict) else {}
            else:
                metadata = {}
            
            # Ensure text is a string and not None
            # Convert to string BEFORE threading to avoid PyMuPDF NoSessionContext errors
            if text is None:
                text = ""
            elif not isinstance(text, str):
                try:
                    # Try to convert to string - this might fail with NoSessionContext if text is a PyMuPDF object
                    text = str(text)
                except Exception as e:
                    error_str = str(e) if str(e) else type(e).__name__
                    if "NoSessionContext" in error_str or "NoSessionContext" in type(e).__name__:
                        logger.warning(f"Text conversion failed with NoSessionContext. Attempting safe extraction...")
                        # Try to get text content safely without accessing PyMuPDF internals
                        try:
                            # If it's a ParsedDocument or similar, try to get text attribute
                            if hasattr(text, 'text'):
                                text = str(text.text) if text.text else ""
                            elif hasattr(text, 'page_content'):
                                text = str(text.page_content) if text.page_content else ""
                            else:
                                # Last resort: try repr and extract if possible
                                text = repr(text)
                                # If repr contains quotes, try to extract the content
                                if text.startswith("'") and text.endswith("'"):
                                    text = text[1:-1]
                                elif text.startswith('"') and text.endswith('"'):
                                    text = text[1:-1]
                        except Exception as e2:
                            logger.error(f"Failed to safely extract text: {str(e2)}")
                            text = ""  # Fallback to empty string
                    else:
                        # Re-raise if it's not a NoSessionContext error
                        raise
            
            # Skip empty documents
            if not text.strip():
                continue
            
            documents.append(Document(page_content=text, metadata=metadata))
        
        # Validate we have documents to process
        if not documents:
            return 0
        
        # Split documents into chunks using token-aware splitter
        # IMPORTANT: Extract all text content BEFORE threading to avoid PyMuPDF NoSessionContext errors
        total_text_length = sum(len(doc.page_content) if hasattr(doc, 'page_content') and isinstance(doc.page_content, str) else 0 for doc in documents)
        logger.info(f"[STEP 3.1] RAGSystem: Starting chunking for {len(documents)} document(s), total text length: {total_text_length:,} chars")
        if progress_callback:
            progress_callback('chunking', 0.1, detailed_message="Starting chunking process...")
        
        # Ensure all document text is extracted as plain strings before chunking
        # This prevents downstream components from interacting with parser-specific objects
        safe_documents = []
        for doc in documents:
            try:
                # Extract text content as plain string
                text_content = doc.page_content if hasattr(doc, 'page_content') else ""
                if not isinstance(text_content, str):
                    text_content = str(text_content)
                
                # Create a new Document with plain string content
                safe_doc = Document(page_content=text_content, metadata=doc.metadata if hasattr(doc, 'metadata') else {})
                safe_documents.append(safe_doc)
            except Exception as e:
                error_str = str(e) if str(e) else type(e).__name__
                if "NoSessionContext" in error_str:
                    logger.warning(f"Skipping document due to NoSessionContext error during text extraction: {error_str}")
                    continue
                else:
                    # For other errors, try to continue with empty text
                    safe_doc = Document(page_content="", metadata=doc.metadata if hasattr(doc, 'metadata') else {})
                    safe_documents.append(safe_doc)
        
        if not safe_documents:
            raise ValueError("No valid documents to chunk after text extraction. This may be due to parser session context issues.")
        
        # Adaptive chunking: upscale chunk size for very large documents when user selected small chunks
        splitter_to_use = self.text_splitter
        adaptive_chunk_size = None
        adaptive_chunk_overlap = None
        estimated_tokens = 0
        try:
            estimated_tokens = sum(self.count_tokens(doc.page_content) for doc in safe_documents)
        except Exception:
            # Fallback estimate using character count
            estimated_tokens = total_text_length // 4
        
        estimated_chunks = math.ceil(estimated_tokens / max(self.chunk_size, 1))
        logger.info(
            f"[STEP 3.1.1] RAGSystem: Chunking configuration - requested chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}, estimated tokens≈{estimated_tokens:,}, "
            f"estimated chunks≈{estimated_chunks}"
        )
        
        MAX_CHUNKS_BEFORE_ADAPT = 200
        MIN_ADAPTIVE_CHUNK_SIZE = 512
        MAX_ADAPTIVE_CHUNK_SIZE = 1536
        
        if (
            estimated_chunks > MAX_CHUNKS_BEFORE_ADAPT
            and self.chunk_size <= MIN_ADAPTIVE_CHUNK_SIZE
        ):
            target_chunk_size = math.ceil(estimated_tokens / MAX_CHUNKS_BEFORE_ADAPT)
            adaptive_chunk_size = min(
                max(target_chunk_size, MIN_ADAPTIVE_CHUNK_SIZE, self.chunk_size),
                MAX_ADAPTIVE_CHUNK_SIZE
            )
            
            if adaptive_chunk_size > self.chunk_size:
                overlap_ratio = self.chunk_overlap / max(self.chunk_size, 1)
                adaptive_chunk_overlap = int(adaptive_chunk_size * overlap_ratio)
                adaptive_chunk_overlap = min(adaptive_chunk_overlap, adaptive_chunk_size // 2)
                
                splitter_to_use = TokenTextSplitter(
                    chunk_size=adaptive_chunk_size,
                    chunk_overlap=adaptive_chunk_overlap,
                    model_name=self.embedding_model
                )
                
                logger.info(
                    f"[STEP 3.1.2] RAGSystem: Adaptive chunking enabled for large document - "
                    f"chunk_size {self.chunk_size} -> {adaptive_chunk_size}, "
                    f"overlap {self.chunk_overlap} -> {adaptive_chunk_overlap}, "
                    f"document tokens≈{estimated_tokens:,}"
                )
                if progress_callback:
                    progress_callback(
                        'chunking',
                        0.12,
                        detailed_message=(
                            f"Large document detected (~{estimated_tokens:,} tokens). "
                            f"Auto-adjusted chunk size to {adaptive_chunk_size} tokens "
                            f"for better performance."
                        )
                    )
        
        # Perform chunking synchronously (avoids Streamlit NoSessionContext errors)
        def splitter_progress_callback(status, progress, **kwargs):
            if progress_callback:
                progress_callback(status, progress, **kwargs)
        
        # Track chunking performance
        chunking_start_time = time_module.time()
        chunking_timeout_warning = 600  # 10 minutes in seconds
        
        try:
            logger.info(f"[STEP 3.1.3] RAGSystem: Starting chunking operation (timeout warning at {chunking_timeout_warning}s)...")
            chunks = splitter_to_use.split_documents(
                safe_documents,
                progress_callback=splitter_progress_callback
            )
            if chunks is None:
                chunks = []
            
            # Log chunking performance
            chunking_end_time = time_module.time()
            chunking_duration = chunking_end_time - chunking_start_time
            
            if chunking_duration > chunking_timeout_warning:
                logger.warning(
                    f"⚠️ [STEP 3.1] RAGSystem: Chunking took {chunking_duration:.1f}s ({chunking_duration/60:.1f} minutes) - "
                    f"this is longer than expected. Consider using larger chunk sizes for very large documents."
                )
            else:
                logger.info(
                    f"[STEP 3.1] RAGSystem: Chunking completed in {chunking_duration:.1f}s ({chunking_duration/60:.1f} minutes)"
                )
            
            # Log performance metrics
            if len(chunks) > 0:
                chunks_per_sec = len(chunks) / chunking_duration if chunking_duration > 0 else 0
                logger.info(
                    f"[STEP 3.1] RAGSystem: Chunking performance - {chunks_per_sec:.2f} chunks/sec, "
                    f"{estimated_tokens/chunking_duration:.0f} tokens/sec"
                )
        except Exception as e:
            error_details = traceback.format_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            if not error_msg or error_msg.strip() == "":
                error_msg = f"Unknown error ({type(e).__name__})"
            if "NoSessionContext" in error_msg:
                error_msg = (
                    "Streamlit session context was lost while updating progress. "
                    "This typically happens when attempting to update the UI from a background thread. "
                    "Please retry the operation."
                )
            logger.error(f"❌ [STEP 3.1] RAGSystem: Chunking failed: {error_msg}\n{error_details}")
            raise ValueError(f"Failed to split documents into chunks: {error_msg}")
        
        chunk_size_used = adaptive_chunk_size or self.chunk_size
        overlap_used = adaptive_chunk_overlap if adaptive_chunk_overlap is not None else self.chunk_overlap
        logger.info(
            f"✅ [STEP 3.1] RAGSystem: Chunking completed - {len(chunks)} chunks created "
            f"(effective chunk_size={chunk_size_used}, overlap={overlap_used})"
        )
        
        # Validate chunks
        if not chunks:
            raise ValueError("No chunks created from documents. The documents may be empty or too small.")
        
        if progress_callback:
            progress_callback(
                'chunking',
                0.3,
                detailed_message=(
                    f"Chunking completed: {len(chunks)} chunks created "
                    f"(effective chunk size ≈ {chunk_size_used} tokens)"
                )
            )
        
        # Filter out invalid chunks
        valid_chunks = []
        total_chunks = len(chunks)
        for idx, chunk in enumerate(chunks):
            if chunk is None:
                continue
            if not hasattr(chunk, 'page_content'):
                continue
            if not chunk.page_content or not chunk.page_content.strip():
                continue
            valid_chunks.append(chunk)
            
            # Update progress every 10 chunks or at the end
            if progress_callback and (idx % 10 == 0 or idx == total_chunks - 1):
                progress = 0.3 + (idx / total_chunks) * 0.2  # 0.3 to 0.5
                progress_callback('chunking', progress, detailed_message=f"Validating chunks... {idx + 1}/{total_chunks} processed")
        
        if not valid_chunks:
            raise ValueError("No valid chunks created. All chunks are empty or invalid.")
        
        logger.info(f"Valid chunks: {len(valid_chunks)}/{len(chunks)}")
        
        if progress_callback:
            progress_callback(
                'chunking',
                0.5,
                detailed_message=(
                    f"Chunking complete: {len(valid_chunks)} valid chunks ready for embedding "
                    f"(chunk size ≈ {chunk_size_used} tokens)"
                )
            )
        
        # Track tokens
        for chunk in valid_chunks:
            token_count = chunk.metadata.get('token_count', 0)
            self.total_tokens += token_count
        
        logger.info(f"Total tokens: {self.total_tokens:,}")
        
        if progress_callback:
            progress_callback('embedding', 0.6)
        
        # Create or update vector store incrementally
        logger.info(f"Creating/updating {self.vector_store_type.upper()} vector store with {len(valid_chunks)} chunks...")
        try:
            if self.vectorstore is None:
                # Validate chunks before creating vectorstore
                if len(valid_chunks) == 0:
                    raise ValueError("Cannot create vectorstore: no valid chunks")
                
                # Create vector store using factory
                logger.info(f"[STEP 3.2.1] RAGSystem: Creating new {self.vector_store_type.upper()} vectorstore with {len(valid_chunks)} chunks (this may take a few minutes for large documents)...")
                if progress_callback:
                    progress_callback('embedding', 0.65)
                
                self.vectorstore = VectorStoreFactory.create_vector_store(
                    store_type=self.vector_store_type,
                    embeddings=self.embeddings,
                    opensearch_domain=self.opensearch_domain,
                    opensearch_index=self.opensearch_index
                )
                
                # Process in batches for large documents to show progress
                # Use smaller batches (50) for better progress visibility
                batch_size = 50  # Process 50 chunks at a time for better progress updates
                total_batches = (len(valid_chunks) + batch_size - 1) // batch_size
                
                if len(valid_chunks) > batch_size:
                    logger.info(f"[STEP 3.2.2] RAGSystem: Processing {len(valid_chunks)} chunks in {total_batches} batches of {batch_size} (this may take several minutes)...")
                    # Process first batch to create vectorstore
                    first_batch = valid_chunks[:batch_size]
                    logger.info(f"[STEP 3.2.2.1] RAGSystem: Processing batch 1/{total_batches} ({len(first_batch)} chunks) - creating embeddings...")
                    if progress_callback:
                        progress_callback('embedding', 0.65, detailed_message=f"Initializing vector store... Batch 1/{total_batches} ({len(first_batch)} chunks)")
                    
                    import time
                    batch_start = time_module.time()
                    self.vectorstore.from_documents(first_batch)
                    batch_time = time_module.time() - batch_start
                    logger.info(f"✅ [STEP 3.2.2.1] RAGSystem: Batch 1/{total_batches} completed in {batch_time:.1f}s ({len(first_batch)} chunks embedded)")
                    
                    if progress_callback:
                        progress_callback('embedding', 0.7, detailed_message=f"Batch 1/{total_batches} complete ({len(first_batch)} chunks embedded in {batch_time:.1f}s)")
                    
                    # Process remaining batches
                    embedding_start_time = time_module.time()
                    for batch_num in range(1, total_batches):
                        start_idx = batch_num * batch_size
                        end_idx = min(start_idx + batch_size, len(valid_chunks))
                        batch = valid_chunks[start_idx:end_idx]
                        
                        if batch:
                            batch_pct = int((batch_num + 1) / total_batches * 100)
                            elapsed_embedding = time_module.time() - embedding_start_time
                            
                            # Calculate speed and remaining time
                            chunks_processed_so_far = (batch_num * batch_size) + len(first_batch)
                            if elapsed_embedding > 0:
                                chunks_per_sec = chunks_processed_so_far / elapsed_embedding
                                remaining_chunks = len(valid_chunks) - chunks_processed_so_far
                                estimated_remaining = remaining_chunks / chunks_per_sec if chunks_per_sec > 0 else 0
                                remaining_minutes = int(estimated_remaining // 60)
                                remaining_seconds = int(estimated_remaining % 60)
                                remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining" if estimated_remaining > 0 else "calculating..."
                            else:
                                remaining_str = "calculating..."
                                chunks_per_sec = 0
                            
                            logger.info(f"[STEP 3.2.2.{batch_num + 1}] RAGSystem: Processing batch {batch_num + 1}/{total_batches} ({batch_pct}%) - {len(batch)} chunks | {remaining_str}")
                            if progress_callback:
                                # Update progress: 0.7 to 0.9 based on batches
                                batch_progress = 0.7 + ((batch_num + 1) / total_batches) * 0.2
                                detailed_msg = f"Batch {batch_num + 1}/{total_batches} ({batch_pct}%) | {len(batch)} chunks | {remaining_str}"
                                progress_callback('embedding', batch_progress, detailed_message=detailed_msg)
                            
                            batch_start = time_module.time()
                            self.vectorstore.add_documents(batch, auto_recreate_on_mismatch=True)
                            batch_time = time_module.time() - batch_start
                            chunks_per_sec_batch = len(batch) / batch_time if batch_time > 0 else 0
                            logger.info(f"✅ [STEP 3.2.2.{batch_num + 1}] RAGSystem: Batch {batch_num + 1}/{total_batches} completed in {batch_time:.1f}s | Speed: {chunks_per_sec_batch:.2f} chunks/sec | {len(batch)} chunks embedded")
                            
                            if progress_callback:
                                # Update progress: 0.7 to 0.9 based on batches
                                batch_progress = 0.7 + ((batch_num + 1) / total_batches) * 0.2
                                progress_callback('embedding', batch_progress, detailed_message=f"Batch {batch_num + 1}/{total_batches} complete ({len(batch)} chunks embedded in {batch_time:.1f}s, {chunks_per_sec_batch:.2f} chunks/sec)")
                else:
                    # Small document - process all at once
                    logger.info(f"[STEP 3.2.2] RAGSystem: Processing {len(valid_chunks)} chunks - creating embeddings (this may take a minute)...")
                    if progress_callback:
                        progress_callback('embedding', 0.7, detailed_message=f"Creating embeddings for {len(valid_chunks)} chunks... This may take a minute")
                    import time
                    embed_start = time_module.time()
                    self.vectorstore.from_documents(valid_chunks)
                    embed_time = time_module.time() - embed_start
                    logger.info(f"✅ [STEP 3.2.2] RAGSystem: Embedding completed in {embed_time:.1f}s ({len(valid_chunks)} chunks)")
                    if progress_callback:
                        progress_callback('embedding', 0.85, detailed_message=f"Embeddings complete! {len(valid_chunks)} chunks embedded in {embed_time:.1f}s")
                
                logger.info(f"✅ [STEP 3.2] RAGSystem: {self.vector_store_type.upper()} vectorstore created successfully")
            else:
                # Add to existing vector store (incremental update)
                if len(valid_chunks) > 0:
                    logger.info(f"[STEP 3.2.3] RAGSystem: Adding {len(valid_chunks)} chunks to existing {self.vector_store_type.upper()} vectorstore (this may take a few minutes for large documents)...")
                    
                    # Process in batches for large documents
                    batch_size = 50  # Use smaller batches for better progress visibility
                    total_batches = (len(valid_chunks) + batch_size - 1) // batch_size
                    
                    if len(valid_chunks) > batch_size:
                        logger.info(f"[STEP 3.2.3.1] RAGSystem: Processing {len(valid_chunks)} chunks in {total_batches} batches of {batch_size} (this may take several minutes)...")
                        embedding_start_time = time_module.time()
                        for batch_num in range(total_batches):
                            start_idx = batch_num * batch_size
                            end_idx = min(start_idx + batch_size, len(valid_chunks))
                            batch = valid_chunks[start_idx:end_idx]
                            
                            if batch:
                                batch_pct = int((batch_num + 1) / total_batches * 100)
                                elapsed_embedding = time_module.time() - embedding_start_time
                                
                                # Calculate speed and remaining time
                                chunks_processed_so_far = (batch_num + 1) * batch_size if (batch_num + 1) * batch_size <= len(valid_chunks) else len(valid_chunks)
                                if elapsed_embedding > 0:
                                    chunks_per_sec = chunks_processed_so_far / elapsed_embedding
                                    remaining_chunks = len(valid_chunks) - chunks_processed_so_far
                                    estimated_remaining = remaining_chunks / chunks_per_sec if chunks_per_sec > 0 else 0
                                    remaining_minutes = int(estimated_remaining // 60)
                                    remaining_seconds = int(estimated_remaining % 60)
                                    remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining" if estimated_remaining > 0 else "calculating..."
                                else:
                                    remaining_str = "calculating..."
                                    chunks_per_sec = 0
                                
                                logger.info(f"[STEP 3.2.3.{batch_num + 1}] RAGSystem: Processing batch {batch_num + 1}/{total_batches} ({batch_pct}%) - {len(batch)} chunks | {remaining_str}")
                                batch_start = time_module.time()
                                self.vectorstore.add_documents(batch, auto_recreate_on_mismatch=True)
                                batch_time = time_module.time() - batch_start
                                chunks_per_sec_batch = len(batch) / batch_time if batch_time > 0 else 0
                                logger.info(f"✅ [STEP 3.2.3.{batch_num + 1}] RAGSystem: Batch {batch_num + 1}/{total_batches} completed in {batch_time:.1f}s | Speed: {chunks_per_sec_batch:.2f} chunks/sec | {len(batch)} chunks embedded")
                                
                                if progress_callback:
                                    # Update progress: 0.6 to 0.9 based on batches
                                    batch_progress = 0.6 + ((batch_num + 1) / total_batches) * 0.3
                                    detailed_msg = f"Batch {batch_num + 1}/{total_batches} ({batch_pct}%) | {len(batch)} chunks | {remaining_str}"
                                    progress_callback('embedding', batch_progress, detailed_message=detailed_msg)
                    else:
                        # Small update - process all at once
                        logger.info(f"[STEP 3.2.3.1] RAGSystem: Processing {len(valid_chunks)} chunks - creating embeddings (this may take a minute)...")
                        if progress_callback:
                            progress_callback('embedding', 0.7)
                        embed_start = time_module.time()
                        self.vectorstore.add_documents(valid_chunks, auto_recreate_on_mismatch=True)
                        embed_time = time_module.time() - embed_start
                        logger.info(f"✅ [STEP 3.2.3.1] RAGSystem: Embedding completed in {embed_time:.1f}s ({len(valid_chunks)} chunks)")
                        if progress_callback:
                            progress_callback('embedding', 0.85)
                    
                    logger.info(f"✅ [STEP 3.2.3] RAGSystem: Chunks added to {self.vector_store_type.upper()} vectorstore successfully")
        except Exception as e:
            # Capture full error details including traceback
            error_details = traceback.format_exc()
            error_msg = str(e) if str(e) else type(e).__name__
            if not error_msg or error_msg.strip() == "":
                error_msg = f"Unknown error ({type(e).__name__})"
            
            logger.error(f"❌ [STEP 3.2] RAGSystem: Vectorstore creation/update failed: {error_msg}")
            logger.error(f"❌ [STEP 3.2] RAGSystem: Full traceback:\n{error_details}")
            
            # Check for specific error types
            if "OpenSearch" in error_msg or "opensearch" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update OpenSearch vectorstore: {error_msg}. "
                    f"Please check your OpenSearch credentials and domain configuration. "
                    f"You may want to use FAISS instead for local storage."
                )
            elif "dimension" in error_msg.lower() or "shape" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to dimension mismatch in embeddings. "
                    f"Try removing existing vectorstore and reprocessing documents."
                )
            elif "empty" in error_msg.lower() or "no documents" in error_msg.lower():
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to empty chunks. Please check your document content."
                )
            else:
                raise ValueError(
                    f"Failed to create/update vectorstore: {error_msg}. "
                    f"This may be due to empty chunks or embedding issues. "
                    f"Full error: {error_details[-500:]}"  # Last 500 chars of traceback
                )
        
        if progress_callback:
            progress_callback('embedding', 0.9)
        
        # Track document chunks
        # Calculate chunk_start based on total existing chunks
        chunk_start = sum(len(chunk_list) for chunk_list in self.document_index.values())
        for i, chunk in enumerate(valid_chunks):
            doc_id = chunk.metadata.get('source', f'doc_{len(documents)}')
            if doc_id not in self.document_index:
                self.document_index[doc_id] = []
            self.document_index[doc_id].append(chunk_start + i)
        
        logger.info(f"✅ [STEP 3.3] RAGSystem: Document indexing completed - {len(valid_chunks)} chunks indexed")
        
        return len(valid_chunks)
    
    def add_documents_incremental(self, texts: List[str], metadatas: List[Dict] = None, progress_callback: Optional[Callable] = None) -> Dict:
        """
        Add documents incrementally to the vector store.
        Returns processing statistics.
        
        Args:
            texts: List of text content
            metadatas: List of metadata dictionaries
            progress_callback: Optional callback function(status, progress) for updates
        
        Returns:
            Dict with processing stats: chunks_created, tokens_added, documents_added
        """
        chunks_before = sum(len(chunks) for chunks in self.document_index.values())
        tokens_before = self.total_tokens
        
        chunks_created = self.process_documents(texts, metadatas, progress_callback=progress_callback)
        
        chunks_after = sum(len(chunks) for chunks in self.document_index.values())
        tokens_after = self.total_tokens
        
        return {
            'chunks_created': chunks_created,
            'tokens_added': tokens_after - tokens_before,
            'documents_added': len(texts),
            'total_chunks': chunks_after,
            'total_tokens': tokens_after
        }

    def load_selected_documents(self, document_names: List[str], path: str = "vectorstore") -> Dict:
        """
        Load only the selected documents into a fresh vectorstore (FAISS) or
        configure OpenSearch to filter by those documents.

        Args:
            document_names: List of document names (metadata 'source') to load.
            path: Base path for FAISS vectorstore storage.

        Returns:
            Dict with keys:
                loaded: bool
                docs_loaded: int
                chunks_loaded: int
                message: str
        """
        from scripts.setup_logging import get_logger
        from langchain_community.docstore.in_memory import InMemoryDocstore
        from config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")

        if not document_names:
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": "No documents selected."
            }

        self.active_sources = document_names

        if self.vector_store_type == "opensearch":
            # For OpenSearch, we don't load locally; rely on filtered retrieval
            msg = f"OpenSearch filter applied for {len(document_names)} document(s)."
            logger.info(f"✅ {msg}")
            return {
                "loaded": True,
                "docs_loaded": len(document_names),
                "chunks_loaded": 0,
                "message": msg
            }

        # FAISS: build a fresh in-memory index containing only selected docs
        # Load the full store once to extract vectors, then rebuild subset
        model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
        base_path = path
        if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
            model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))

        if not os.path.exists(model_specific_path):
            msg = f"Vectorstore path does not exist: {model_specific_path}. Reprocess documents first."
            logger.warning(f"⚠️ {msg}")
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }

        try:
            logger.info(f"[STEP 1] Loading full FAISS store to extract selected docs: {model_specific_path}")
            full_vs = VectorStoreFactory.load_vector_store(
                store_type="faiss",
                embeddings=self.embeddings,
                path=model_specific_path
            )
        except Exception as e:
            msg = f"Failed to load base vectorstore: {e}"
            logger.error(f"❌ {msg}", exc_info=True)
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }

        # Extract matching docs and vectors
        docs = []
        vectors = []
        
        # Try multiple ways to access docstore and mapping
        mapping = None
        ds = None
        actual_faiss = None  # The actual FAISS object we'll use
        
        # Method 1: Check if it's a wrapped FAISSVectorStore (from VectorStoreFactory)
        if hasattr(full_vs, "vectorstore"):
            actual_faiss = full_vs.vectorstore
            logger.info("Detected FAISSVectorStore wrapper, accessing inner vectorstore")
        # Method 2: Direct FAISS object
        elif hasattr(full_vs, "docstore"):
            actual_faiss = full_vs
        else:
            actual_faiss = full_vs
        
        # Now try to access docstore and mapping from the actual FAISS object
        if actual_faiss and hasattr(actual_faiss, "docstore"):
            ds = actual_faiss.docstore
            # Try to get index_to_docstore_id
            if hasattr(actual_faiss, "index_to_docstore_id"):
                mapping = actual_faiss.index_to_docstore_id
            # Some versions might store it differently
            elif hasattr(actual_faiss, "_index_to_docstore_id"):
                mapping = actual_faiss._index_to_docstore_id
        
        # Check if documents are stored as strings (metadata lost) by sampling first document
        use_fallback = False
        if mapping is not None and ds is not None:
            # Sample first document to check if it's a string
            try:
                if len(mapping) > 0:
                    first_doc_id = mapping[0]
                    if hasattr(ds, "_dict") and first_doc_id in ds._dict:
                        first_doc = ds._dict[first_doc_id]
                        if isinstance(first_doc, str):
                            logger.info("Documents in docstore are strings (metadata lost), using similarity_search fallback")
                            use_fallback = True
            except Exception:
                pass
        
        if mapping is not None and ds is not None and not use_fallback:
            # Extract documents and vectors using mapping
            logger.info(f"Using index_to_docstore_id mapping with {len(mapping)} entries")
            all_sources_in_mapping = []
            for i, doc_id in enumerate(mapping):
                try:
                    # Try different ways to get document from docstore
                    # Prefer _dict access as it's more direct
                    doc = None
                    if hasattr(ds, "_dict") and doc_id in ds._dict:
                        doc = ds._dict[doc_id]
                    elif hasattr(ds, "search"):
                        doc = ds.search(doc_id)
                    elif hasattr(ds, "get") and callable(ds.get):
                        doc = ds.get(doc_id)
                    
                    if doc and hasattr(doc, "metadata"):
                        metadata = doc.metadata
                        source = metadata.get("source", "") if isinstance(metadata, dict) else ""
                        all_sources_in_mapping.append(source)
                        if i < 3:  # Log first 3 for debugging
                            logger.info(f"Document {i} (id={doc_id}) source: '{source}'")
                        if source in document_names:
                            docs.append(doc)
                            logger.info(f"✅ Found matching document via mapping: {source}")
                            try:
                                # Try to reconstruct vector from index (use actual_faiss if available)
                                index_obj = actual_faiss.index if actual_faiss and hasattr(actual_faiss, "index") else (full_vs.index if hasattr(full_vs, "index") else None)
                                if index_obj and hasattr(index_obj, "reconstruct"):
                                    vec = index_obj.reconstruct(i)
                                    vectors.append(vec)
                            except Exception as e:
                                logger.debug(f"Could not reconstruct vector for index {i}: {e}")
                                # Continue without vector - we'll re-embed if needed
                except Exception as e:
                    logger.debug(f"Error accessing document {doc_id}: {e}")
                    continue
            
            if not docs and all_sources_in_mapping:
                logger.warning(f"Looking for: {document_names}, but found sources in mapping: {set(all_sources_in_mapping)}")
        
        if use_fallback or mapping is None or not docs:
            # Fallback: Try to access docstore directly or use similarity_search
            logger.info("Using fallback method: attempting direct docstore access or similarity_search")
            try:
                # Determine which vectorstore to use for searching
                search_vs = actual_faiss if actual_faiss else full_vs
                
                # Try to access docstore directly if available
                if hasattr(search_vs, "docstore"):
                    ds = search_vs.docstore
                    # Try to iterate through all documents in docstore
                    if hasattr(ds, "_dict"):
                        logger.info(f"Accessing docstore._dict with {len(ds._dict)} entries")
                        all_sources_found = []
                        for doc_id, doc in ds._dict.items():
                            try:
                                if hasattr(doc, "metadata"):
                                    source = doc.metadata.get("source", "")
                                    all_sources_found.append(source)
                                    logger.debug(f"Document {doc_id} has source: {source}")
                                    if source in document_names:
                                        docs.append(doc)
                                        logger.info(f"✅ Found matching document: {source}")
                            except Exception as e:
                                logger.debug(f"Error checking document {doc_id}: {e}")
                                continue
                        
                        if not docs and all_sources_found:
                            logger.warning(f"Looking for: {document_names}, but found sources: {set(all_sources_found)}")
                    elif hasattr(ds, "search"):
                        # Try to search for documents - this is tricky without knowing IDs
                        # We'll use similarity_search as fallback
                        pass
                
                # If we still don't have docs, use similarity_search with multiple queries
                if not docs:
                    logger.info("Using similarity_search to extract documents...")
                    # Try multiple generic queries to get all documents
                    queries = ["document", "text", "content", "information", "data"]
                    all_docs_set = set()  # Use set to avoid duplicates
                    
                    for query in queries:
                        try:
                            found_docs = search_vs.similarity_search(query, k=1000)
                            for doc in found_docs:
                                # Use a unique identifier for each doc (content + metadata)
                                doc_key = (doc.page_content[:100] if hasattr(doc, "page_content") else str(doc),
                                          str(doc.metadata.get("source", "")) if hasattr(doc, "metadata") else "")
                                if doc_key not in all_docs_set:
                                    all_docs_set.add(doc_key)
                                    if hasattr(doc, "metadata") and doc.metadata.get("source") in document_names:
                                        docs.append(doc)
                        except Exception:
                            continue
                    
                    # If still no docs, try one more time with empty query and very large k
                    if not docs:
                        try:
                            all_docs = search_vs.similarity_search("the", k=10000)
                            seen = set()
                            for doc in all_docs:
                                doc_key = (doc.page_content[:100] if hasattr(doc, "page_content") else str(doc),
                                          str(doc.metadata.get("source", "")) if hasattr(doc, "metadata") else "")
                                if doc_key not in seen:
                                    seen.add(doc_key)
                                    if hasattr(doc, "metadata") and doc.metadata.get("source") in document_names:
                                        docs.append(doc)
                        except Exception:
                            pass
                
                if not docs:
                    msg = f"Selected documents ({document_names}) not found in vectorstore. Available sources may differ."
                    logger.warning(f"⚠️ {msg}")
                    # Try to list available sources for debugging
                    try:
                        debug_vs = actual_faiss if actual_faiss else full_vs
                        if hasattr(debug_vs, "docstore") and hasattr(debug_vs.docstore, "_dict"):
                            available_sources = set()
                            for doc in debug_vs.docstore._dict.values():
                                if hasattr(doc, "metadata") and "source" in doc.metadata:
                                    available_sources.add(doc.metadata["source"])
                            if available_sources:
                                logger.info(f"Available document sources in vectorstore: {list(available_sources)[:10]}")
                    except Exception:
                        pass
                    return {
                        "loaded": False,
                        "docs_loaded": 0,
                        "chunks_loaded": 0,
                        "message": msg
                    }
                
                # Re-embed the filtered documents to get vectors
                logger.info(f"Re-embedding {len(docs)} filtered documents...")
                doc_texts = [doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in docs]
                vectors = self.embeddings.embed_documents(doc_texts)
                
            except Exception as e:
                msg = f"Failed to extract documents from vectorstore: {e}"
                logger.error(f"❌ {msg}", exc_info=True)
                return {
                    "loaded": False,
                    "docs_loaded": 0,
                    "chunks_loaded": 0,
                    "message": msg
                }

        if not docs:
            msg = "Selected documents not found in vectorstore."
            logger.warning(f"⚠️ {msg}")
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }
        
        # If we don't have vectors (fallback method), re-embed the documents
        if not vectors or len(vectors) != len(docs):
            logger.info(f"Re-embedding {len(docs)} documents to get vectors...")
            doc_texts = [doc.page_content if hasattr(doc, "page_content") else str(doc) for doc in docs]
            vectors = self.embeddings.embed_documents(doc_texts)

        # Build a fresh FAISS index with selected vectors
        try:
            # Get dimension from vectors or existing index
            if vectors and len(vectors) > 0:
                dim = len(vectors[0])
            else:
                # Try to get dimension from the actual FAISS index
                index_obj = None
                if actual_faiss and hasattr(actual_faiss, "index"):
                    index_obj = actual_faiss.index
                elif hasattr(full_vs, "index"):
                    index_obj = full_vs.index
                elif hasattr(full_vs, "vectorstore") and hasattr(full_vs.vectorstore, "index"):
                    index_obj = full_vs.vectorstore.index
                
                if index_obj and hasattr(index_obj, "d"):
                    dim = index_obj.d
                else:
                    # Fallback: get dimension from embeddings
                    test_embedding = self.embeddings.embed_query("test")
                    dim = len(test_embedding)
            
            import faiss
            new_index = faiss.IndexFlatL2(dim)
            new_docstore = InMemoryDocstore()
            new_index_to_docstore_id = []

            for vec, doc in zip(vectors, docs):
                doc_id = str(len(new_index_to_docstore_id))
                new_docstore._dict[doc_id] = doc
                new_index_to_docstore_id.append(doc_id)
                new_index.add(np.array([vec], dtype="float32"))

            from langchain_community.vectorstores.faiss import FAISS as LCFAISS
            subset_vs = LCFAISS(
                embedding_function=self.embeddings,
                index=new_index,
                docstore=new_docstore,
                index_to_docstore_id=new_index_to_docstore_id
            )

            # Replace active vectorstore with subset
            self.vectorstore = subset_vs

            # Rebuild document_index for the subset
            self.document_index = {}
            for idx, doc in enumerate(docs):
                src = doc.metadata.get("source", f"doc_{idx}")
                if src not in self.document_index:
                    self.document_index[src] = []
                self.document_index[src].append(idx)

            msg = f"Loaded {len(docs)} document(s) into subset vectorstore ({len(vectors)} chunks)."
            logger.info(f"✅ {msg}")
            return {
                "loaded": True,
                "docs_loaded": len(docs),
                "chunks_loaded": len(vectors),
                "message": msg
            }
        except Exception as e:
            msg = f"Failed to build subset vectorstore: {e}"
            logger.error(f"❌ {msg}", exc_info=True)
            return {
                "loaded": False,
                "docs_loaded": 0,
                "chunks_loaded": 0,
                "message": msg
            }
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the tokenizer."""
        return self.text_splitter.count_tokens(text)
    
    def _clean_answer(self, answer: str) -> str:
        """
        Clean answer to remove repetitive text, greetings, and unwanted endings.
        
        Args:
            answer: Raw answer from LLM
        
        Returns:
            Cleaned answer
        """
        if not answer:
            return answer
        
        # Remove common unwanted endings
        unwanted_endings = [
            "Best regards",
            "Thank you",
            "Please let me know",
            "If you have any other questions",
            "I will be happy to help",
            "I will do my best to help",
            "[Your Name]",
            "Best regards, [Your Name]",
            "Thank you, [Your Name]"
        ]
        
        # Find and remove unwanted endings
        lines = answer.split('\n')
        cleaned_lines = []
        found_unwanted = False
        
        for line in lines:
            line_stripped = line.strip()
            # Check if this line contains unwanted text
            if any(unwanted in line_stripped for unwanted in unwanted_endings):
                found_unwanted = True
                break  # Stop at first unwanted ending
            cleaned_lines.append(line)
        
        cleaned = '\n'.join(cleaned_lines).strip()
        
        # Remove repetitive "Best regards" patterns
        import re
        # Remove multiple occurrences of "Best regards" patterns
        cleaned = re.sub(r'(Best regards[,\s]*\[Your Name\]\s*)+', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'(Best regards\s*)+', '', cleaned, flags=re.IGNORECASE)
        
        # Remove trailing repetitive phrases
        cleaned = re.sub(r'(\s*Best regards[,\s]*\[Your Name\]\s*)+$', '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
        
        return cleaned.strip()
    
    def query_with_rag(self, question: str, k: int = None, use_mmr: bool = None) -> Dict:
        """
        Query the RAG system with maximum accuracy settings.
        
        Args:
            question: The question to answer
            k: Number of chunks to retrieve (default from config for maximum accuracy)
            use_mmr: Use Maximum Marginal Relevance (default True for best accuracy)
        
        Returns:
            Dict with answer, sources, and context chunks
        """
        from config.settings import ARISConfig
        
        # Use accuracy-optimized defaults if not specified
        if k is None:
            k = ARISConfig.DEFAULT_RETRIEVAL_K
        if use_mmr is None:
            use_mmr = ARISConfig.DEFAULT_USE_MMR
        query_start_time = time_module.time()
        
        if self.vectorstore is None:
            return {
                "answer": "No documents have been uploaded yet. Please upload documents first.",
                "sources": []
            }
        
        # Prepare filter for OpenSearch (different syntax than FAISS)
        opensearch_filter = None
        if self.active_sources and self.vector_store_type.lower() == "opensearch":
            # Filter out None/empty values and construct OpenSearch filter
            valid_sources = [s for s in self.active_sources if s and s.strip()]
            if valid_sources:
                if len(valid_sources) == 1:
                    # Single source: use term filter
                    opensearch_filter = {"term": {"metadata.source.keyword": valid_sources[0]}}
                else:
                    # Multiple sources: use terms filter
                    opensearch_filter = {"terms": {"metadata.source.keyword": valid_sources}}
        
        # Retrieve relevant documents with MMR optimized for maximum accuracy
        if use_mmr:
            # Use MMR with accuracy-optimized parameters
            from config.settings import ARISConfig
            fetch_k = ARISConfig.DEFAULT_MMR_FETCH_K
            lambda_mult = ARISConfig.DEFAULT_MMR_LAMBDA
            
            # Build search_kwargs with appropriate filter
            search_kwargs = {
                "k": k,
                "fetch_k": fetch_k,  # Large candidate pool for best selection
                "lambda_mult": lambda_mult,  # Prioritize relevance (lower = more relevant)
            }
            
            # Add filter only if we have valid sources and it's OpenSearch
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            elif self.active_sources and self.vector_store_type.lower() != "opensearch":
                # For FAISS, use MongoDB-style filter (if supported)
                valid_sources = [s for s in self.active_sources if s and s.strip()]
                if valid_sources:
                    search_kwargs["filter"] = {"source": {"$in": valid_sources}}
            
            retriever = self.vectorstore.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs
            )
        else:
            # Standard similarity search
            search_kwargs = {"k": k}
            
            # Add filter only if we have valid sources
            if opensearch_filter:
                search_kwargs["filter"] = opensearch_filter
            elif self.active_sources and self.vector_store_type.lower() != "opensearch":
                # For FAISS, use MongoDB-style filter (if supported)
                valid_sources = [s for s in self.active_sources if s and s.strip()]
                if valid_sources:
                    search_kwargs["filter"] = {"source": {"$in": valid_sources}}
            
            retriever = self.vectorstore.as_retriever(
                search_kwargs=search_kwargs
            )
        
        # Use invoke for newer LangChain versions, fallback to get_relevant_documents
        try:
            relevant_docs = retriever.invoke(question)
        except AttributeError:
            # Fallback for older versions
            relevant_docs = retriever.get_relevant_documents(question)

        # If UI selected specific documents, filter results to those sources
        if self.active_sources:
            allowed_sources = set(self.active_sources)
            filtered_docs = [doc for doc in relevant_docs if doc.metadata.get('source') in allowed_sources]

            # If none found, retry with a broader pull and then filter
            if not filtered_docs:
                try:
                    alt_docs = self.vectorstore.similarity_search(question, k=max(k * 4, 20))
                    filtered_docs = [doc for doc in alt_docs if doc.metadata.get('source') in allowed_sources]
                except Exception:
                    filtered_docs = []

            if not filtered_docs:
                return {
                    "answer": (
                        "No chunks were found for the selected document(s). "
                        "Try selecting a different document or load all documents."
                    ),
                    "sources": [],
                    "citations": [],
                    "context_chunks": []
                }

            relevant_docs = filtered_docs
        
        # Build context with metadata for better accuracy and collect citations
        context_parts = []
        citations = []  # Store citation information for each source
        
        for i, doc in enumerate(relevant_docs, 1):
            import re
            
            # Extract citation metadata
            source = doc.metadata.get('source', 'Unknown')
            chunk_text = doc.page_content
            
            # Try multiple ways to get page number
            page = doc.metadata.get('source_page', doc.metadata.get('page', None))
            
            # If page not in metadata, try to extract from text markers
            if page is None:
                # Look for "--- Page X ---" markers in chunk text
                page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                if page_match:
                    page = int(page_match.group(1))
                else:
                    # Try other patterns
                    page_match = re.search(r'Page\s+(\d+)', chunk_text, re.IGNORECASE)
                    if page_match:
                        page = int(page_match.group(1))
            
            start_char = doc.metadata.get('start_char', None)
            end_char = doc.metadata.get('end_char', None)
            
            # Check for image references in metadata
            image_ref = None
            image_info = None
            page_blocks = doc.metadata.get('page_blocks', [])
            
            # Check if this chunk is associated with an image
            if page_blocks:
                for block in page_blocks:
                    if isinstance(block, dict) and block.get('type') == 'image':
                        if page and block.get('page') == page:
                            image_ref = {
                                'page': block.get('page'),
                                'image_index': block.get('image_index'),
                                'bbox': block.get('bbox'),
                                'xref': block.get('xref')
                            }
                            image_info = f"Image {block.get('image_index', '?')} on Page {page}"
                            break
            
            # Also check if chunk metadata has image reference
            if not image_ref:
                if doc.metadata.get('has_image') or doc.metadata.get('image_index') is not None:
                    image_ref = {
                        'page': page,
                        'image_index': doc.metadata.get('image_index'),
                        'bbox': doc.metadata.get('image_bbox')
                    }
                    image_info = f"Image {doc.metadata.get('image_index', '?')} on Page {page}" if page else "Image reference"
            
            # Create snippet - show more context (up to 500 chars for better display)
            snippet = chunk_text[:500] + "..." if len(chunk_text) > 500 else chunk_text
            # Clean snippet - remove page markers for cleaner display
            snippet_clean = re.sub(r'---\s*Page\s+\d+\s*---\s*\n?', '', snippet).strip()
            if not snippet_clean:
                snippet_clean = snippet  # Fallback to original if cleaning removes everything
            
            # Build source location description (certification field)
            source_location_parts = []
            if page:
                source_location_parts.append(f"Page {page}")
            if image_ref:
                source_location_parts.append(f"Image {image_ref.get('image_index', '?')}")
            elif doc.metadata.get('images_detected'):
                source_location_parts.append("Image-based content")
            
            source_location = " | ".join(source_location_parts) if source_location_parts else "Text content"
            
            # Build citation entry with enhanced metadata
            citation = {
                'id': i,
                'source': source,
                'page': page,
                'snippet': snippet_clean,
                'full_text': chunk_text,
                'start_char': start_char,
                'end_char': end_char,
                'chunk_index': doc.metadata.get('chunk_index', None),
                'image_ref': image_ref,  # Image reference if available
                'image_info': image_info,  # Human-readable image info
                'source_location': source_location,  # Certification field: exact location
                'content_type': 'image' if image_ref else 'text'  # Type of content
            }
            citations.append(citation)
            
            # Add source and page info to context
            page_info = f" (Page {page})" if page else ""
            context_parts.append(f"[Source {i}: {source}{page_info}]\n{chunk_text}")
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Count tokens in context (question + context)
        context_tokens = self.count_tokens(question + "\n\n" + context)
        
        # Generate answer using LLM with improved prompt
        if self.use_cerebras:
            answer, response_tokens = self._query_cerebras(question, context, relevant_docs)
        else:
            answer, response_tokens = self._query_openai(question, context, relevant_docs)
        
        response_time = time_module.time() - query_start_time
        total_tokens = context_tokens + response_tokens
        
        # Record query metrics
        if self.metrics_collector:
            self.metrics_collector.record_query(
                question=question,
                answer_length=len(answer),
                response_time=response_time,
                chunks_used=len(relevant_docs),
                sources_count=len(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
                api_used="cerebras" if self.use_cerebras else "openai",
                success=True,
                context_tokens=context_tokens,
                response_tokens=response_tokens,
                total_tokens=total_tokens
            )
        
        return {
            "answer": answer,
            "sources": list(set([doc.metadata.get('source', 'Unknown') for doc in relevant_docs])),
            "context_chunks": [doc.page_content for doc in relevant_docs],  # Full chunk text for citation display
            "citations": citations,  # Detailed citation information with page numbers and snippets
            "num_chunks_used": len(relevant_docs),
            "response_time": response_time,
            "context_tokens": context_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens
        }
    
    def _query_openai(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        """
        Query OpenAI with maximum accuracy settings.
        
        Args:
            question: The question to answer
            context: Retrieved context from documents
            relevant_docs: List of relevant documents (for metadata)
        """
        from openai import OpenAI
        from config.settings import ARISConfig
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        # Improved prompt for accuracy - prevents hallucinations and repetitive text
        system_prompt = """You are a precise technical assistant that provides accurate, detailed answers based strictly on the provided context. 

CRITICAL RULES:
- Answer ONLY using information from the provided context
- DO NOT add greetings, signatures, or closing statements
- DO NOT repeat phrases or sentences
- DO NOT include "Best regards", "Thank you", or similar endings
- DO NOT make up information not in the context
- Be specific and cite exact values, measurements, and specifications when available
- If information is not in the context, explicitly state "The provided context does not contain this information"
- Include relevant details like dimensions, materials, standards, and procedures
- Maintain technical accuracy and precision
- If multiple sources provide information, synthesize them clearly
- End your answer when you have provided the information - do not add unnecessary text"""
        
        user_prompt = f"""Context from documents:
{context}

Question: {question}

Instructions:
1. Read the context carefully
2. Identify the most relevant information for the question
3. Provide a comprehensive, accurate answer using ONLY information from the context
4. Include specific details, numbers, and specifications when available
5. If the answer is not in the context, state so clearly
6. DO NOT add greetings, signatures, or closing statements
7. DO NOT repeat information or phrases
8. Stop immediately after providing the answer

Answer:"""
        
        try:
            response = client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=ARISConfig.DEFAULT_TEMPERATURE,  # Maximum determinism (0.0 = most accurate)
                max_tokens=ARISConfig.DEFAULT_MAX_TOKENS,  # More tokens for comprehensive answers
                stop=["Best regards", "Thank you", "Please let me know", "If you have any other questions"]  # Stop at common endings
            )
            # Check if response has choices
            if not response.choices or len(response.choices) == 0:
                raise ValueError("OpenAI API returned no choices in response")
            answer = response.choices[0].message.content
            if answer is None:
                raise ValueError("OpenAI API returned empty content in response")
            
            # Get token usage from response
            response_tokens = response.usage.completion_tokens if hasattr(response, 'usage') and response.usage else 0
            if response_tokens == 0:
                # Fallback: estimate tokens in answer
                response_tokens = self.count_tokens(answer)
            
            # Clean up any repetitive or unwanted endings
            answer = self._clean_answer(answer)
            return answer, response_tokens
        except Exception as e:
            error_msg = str(e)
            # Provide user-friendly error messages
            if "model_not_found" in error_msg or "404" in error_msg:
                if "gpt-5" in error_msg.lower():
                    error_answer = f"Error: GPT-5 requires organization verification and is not publicly available. Please use a different model like gpt-4o or gpt-4."
                elif "verify" in error_msg.lower():
                    error_answer = f"Error: This model requires organization verification. Please use a different model or verify your organization at https://platform.openai.com/settings/organization/general"
                else:
                    error_answer = f"Error: Model '{self.openai_model}' is not available. Please check if the model name is correct or try a different model."
            elif "401" in error_msg or "unauthorized" in error_msg.lower():
                error_answer = "Error: Invalid API key. Please check your OpenAI API key in the .env file."
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                error_answer = "Error: Rate limit exceeded. Please wait a moment and try again."
            else:
                error_answer = f"Error querying OpenAI: {error_msg}"
            return error_answer, self.count_tokens(error_answer)
    
    def _query_cerebras(self, question: str, context: str, relevant_docs: List = None) -> tuple:
        """Query Cerebras API with maximum accuracy settings"""
        from config.settings import ARISConfig
        # Improved prompt for Cerebras
        prompt = f"""You are a precise technical assistant. Answer the question using ONLY information from the provided context. Be specific and accurate.

CRITICAL: DO NOT add greetings, signatures, or closing statements. DO NOT repeat phrases. End your answer when you have provided the information.

Context:
{context}

Question: {question}

Instructions:
- Use ONLY information from the context above
- Be specific with numbers, measurements, and technical details
- If information is not in the context, state "The context does not contain this information"
- Provide comprehensive and accurate answers
- DO NOT add "Best regards", "Thank you", or similar endings
- Stop immediately after providing the answer

Answer:"""
        
        headers = {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type": "application/json"
        }
        
        # Use selected Cerebras model
        try:
            data = {
                "model": self.cerebras_model,
                "prompt": prompt,
                "max_tokens": ARISConfig.DEFAULT_MAX_TOKENS,
                "temperature": ARISConfig.DEFAULT_TEMPERATURE
            }
            
            response = requests.post(
                "https://api.cerebras.ai/v1/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                choices = result.get('choices', [])
                if not choices or len(choices) == 0:
                    raise ValueError("Cerebras API returned no choices in response")
                answer = choices[0].get('text', 'No response generated')
                if not answer:
                    answer = 'No response generated'
                
                # Get token usage from response if available
                response_tokens = result.get('usage', {}).get('completion_tokens', 0)
                if response_tokens == 0:
                    # Fallback: estimate tokens in answer
                    response_tokens = self.count_tokens(answer)
                
                # Clean answer to remove unwanted text
                answer = self._clean_answer(answer)
                return answer, response_tokens
            else:
                error_msg = f"Error: Cerebras API returned status {response.status_code}"
                return error_msg, self.count_tokens(error_msg)
        except Exception as e:
            error_msg = f"Error: Could not get response from Cerebras API: {str(e)}"
            return error_msg, self.count_tokens(error_msg)
    
    def save_vectorstore(self, path: str = "vectorstore"):
        """Save vector store to disk (FAISS only) or cloud (OpenSearch)"""
        from scripts.setup_logging import get_logger
        from config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vectorstore:
            if self.vector_store_type == "faiss":
                # Use model-specific path to support multiple embedding models
                base_path = path
                model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
                if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                    # If get_vectorstore_path returns relative path, join with base_path
                    model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
                else:
                    # Use the model-specific path directly
                    model_specific_path = model_specific_path
                
                logger.info(f"[STEP 1] RAGSystem: Saving FAISS vectorstore to: {model_specific_path}")
                # Create directory if it doesn't exist
                os.makedirs(model_specific_path, exist_ok=True)
                
                try:
                    self.vectorstore.save_local(model_specific_path)
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore saved to {model_specific_path}")
                    
                    # Also save document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 2] RAGSystem: Saving document index to: {index_path}")
                    with open(index_path, 'wb') as f:
                        pickle.dump({
                            'document_index': self.document_index,
                            'total_tokens': self.total_tokens,
                            'embedding_model': self.embedding_model
                        }, f)
                    logger.info(f"✅ [STEP 2] RAGSystem: Document index saved to {index_path}")
                except Exception as e:
                    logger.error(f"❌ [STEP 1] RAGSystem: Failed to save vectorstore: {e}", exc_info=True)
            else:
                # OpenSearch stores data in cloud, no local save needed
                logger.info("ℹ️ [STEP 1] RAGSystem: OpenSearch stores data in the cloud. No local save needed.")
    
    def load_vectorstore(self, path: str = "vectorstore"):
        """Load vector store from disk (FAISS) or cloud (OpenSearch) with model-specific path"""
        from scripts.setup_logging import get_logger
        from config.settings import ARISConfig
        logger = get_logger("aris_rag.rag_system")
        
        if self.vector_store_type == "faiss":
            # Use model-specific path
            base_path = path
            model_specific_path = ARISConfig.get_vectorstore_path(self.embedding_model)
            if not model_specific_path.startswith(os.path.abspath(base_path)) and not os.path.isabs(model_specific_path):
                # If get_vectorstore_path returns relative path, join with base_path
                model_specific_path = os.path.join(base_path, self.embedding_model.replace("/", "_"))
            else:
                # Use the model-specific path directly
                model_specific_path = model_specific_path
            
            logger.info(f"[STEP 1] RAGSystem: Loading FAISS vectorstore from: {model_specific_path}")
            if os.path.exists(model_specific_path):
                logger.info(f"[STEP 1.1] RAGSystem: Vectorstore path exists, loading...")
                try:
                    self.vectorstore = VectorStoreFactory.load_vector_store(
                        store_type="faiss",
                        embeddings=self.embeddings,
                        path=model_specific_path
                    )
                    # Also load document index
                    import pickle
                    index_path = os.path.join(model_specific_path, "document_index.pkl")
                    logger.info(f"[STEP 1.2] RAGSystem: Loading document index from: {index_path}")
                    if os.path.exists(index_path):
                        with open(index_path, 'rb') as f:
                            data = pickle.load(f)
                            self.document_index = data.get('document_index', {})
                            self.total_tokens = data.get('total_tokens', 0)
                            saved_model = data.get('embedding_model', 'unknown')
                            if saved_model != self.embedding_model:
                                logger.warning(
                                    f"⚠️ [STEP 1.2] RAGSystem: Vectorstore was created with '{saved_model}' "
                                    f"but current model is '{self.embedding_model}'. "
                                    f"Dimension mismatch may occur."
                                )
                        logger.info(f"✅ [STEP 1.2] RAGSystem: Document index loaded - {len(self.document_index)} documents, {self.total_tokens:,} tokens")
                    logger.info(f"✅ [STEP 1] RAGSystem: Vectorstore loaded successfully")
                    return True
                except Exception as e:
                    error_msg = str(e)
                    if "dimension" in error_msg.lower():
                        logger.warning(
                            f"⚠️ [STEP 1] RAGSystem: Dimension mismatch when loading vectorstore.\n"
                            f"   This vectorstore was created with a different embedding model.\n"
                            f"   It will be recreated automatically when you add new documents."
                        )
                        return False
                    else:
                        raise
            else:
                # Check if old path exists (backward compatibility)
                if os.path.exists(path) and os.path.isdir(path) and not os.path.basename(path).startswith("text-embedding"):
                    logger.info(f"[STEP 1.1] RAGSystem: Found old vectorstore at {path}, migrating to model-specific path...")
                    try:
                        # Try to load from old path
                        self.vectorstore = VectorStoreFactory.load_vector_store(
                            store_type="faiss",
                            embeddings=self.embeddings,
                            path=path
                        )
                        # If successful, save to new model-specific path
                        self.save_vectorstore(path)
                        logger.info(f"✅ [STEP 1.1] RAGSystem: Migrated to model-specific path: {model_specific_path}")
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 1.1] RAGSystem: Could not migrate old vectorstore: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ [STEP 1] RAGSystem: Vectorstore path does not exist: {model_specific_path}")
                    return False
        else:
            # OpenSearch loads from cloud index automatically
            logger.info("[STEP 1] RAGSystem: OpenSearch loads data from the cloud index automatically.")
            try:
                logger.info(f"[STEP 1.1] RAGSystem: Connecting to OpenSearch domain: {self.opensearch_domain}, index: {self.opensearch_index}")
                self.vectorstore = VectorStoreFactory.load_vector_store(
                    store_type="opensearch",
                    embeddings=self.embeddings,
                    path=self.opensearch_index or "aris-rag-index",
                    opensearch_domain=self.opensearch_domain,
                    opensearch_index=self.opensearch_index
                )
                logger.info(f"✅ [STEP 1.1] RAGSystem: OpenSearch vectorstore connected successfully")
                return True
            except Exception as e:
                logger.error(f"❌ [STEP 1.1] RAGSystem: Failed to load OpenSearch vectorstore: {str(e)}")
                return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the RAG system."""
        total_documents = len(self.document_index)
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        
        # Estimate embedding cost (text-embedding-3-small: $0.02 per 1M tokens)
        estimated_cost = (self.total_tokens / 1_000_000) * 0.02
        
        return {
            'total_documents': total_documents,
            'total_chunks': total_chunks,
            'total_tokens': self.total_tokens,
            'estimated_embedding_cost_usd': estimated_cost
        }
    
    def get_chunk_token_stats(self) -> Dict:
        """
        Get token statistics for all chunks in the vectorstore.
        Uses metrics collector data if available, otherwise estimates from vectorstore.
        
        Returns:
            Dict with token distribution statistics
        """
        if self.vectorstore is None:
            return {
                'chunk_token_counts': [],
                'avg_tokens_per_chunk': 0,
                'min_tokens_per_chunk': 0,
                'max_tokens_per_chunk': 0,
                'total_chunks': 0,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Try to get actual chunk token counts from vectorstore first (most accurate)
        chunk_token_counts = []
        try:
            # Access the underlying documents from vectorstore
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'page_content'):
                        # Always recalculate from actual content for accuracy
                        # This ensures we get the real token count, not potentially stale metadata
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                    elif hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        # Fallback to metadata if page_content not available
                        chunk_token_counts.append(doc.metadata['token_count'])
        except Exception:
            pass
        
        # Fallback: Try to get from metrics collector
        if not chunk_token_counts and self.metrics_collector and hasattr(self.metrics_collector, 'processing_metrics'):
            for metric in self.metrics_collector.processing_metrics:
                if metric.success and metric.chunks_created > 0:
                    # Estimate tokens per chunk (total tokens / chunks)
                    tokens_per_chunk = metric.tokens_extracted / metric.chunks_created if metric.chunks_created > 0 else 0
                    # Add tokens for each chunk (approximate)
                    for _ in range(metric.chunks_created):
                        chunk_token_counts.append(int(tokens_per_chunk))
        
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # If we got actual counts from vectorstore, return them
        if chunk_token_counts:
            return {
                'chunk_token_counts': chunk_token_counts,
                'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                'total_chunks': len(chunk_token_counts),
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Fallback: try to get from vectorstore directly (if not already done)
        try:
            # Access the underlying documents
            if hasattr(self.vectorstore, 'docstore') and hasattr(self.vectorstore.docstore, '_dict'):
                all_docs = self.vectorstore.docstore._dict
                chunk_token_counts = []
                
                # Extract token counts from document metadata or count from content
                for doc_id, doc in all_docs.items():
                    if hasattr(doc, 'metadata') and 'token_count' in doc.metadata:
                        chunk_token_counts.append(doc.metadata['token_count'])
                    elif hasattr(doc, 'page_content'):
                        # Count tokens from actual content
                        token_count = self.count_tokens(doc.page_content)
                        chunk_token_counts.append(token_count)
                
                if chunk_token_counts:
                    return {
                        'chunk_token_counts': chunk_token_counts,
                        'avg_tokens_per_chunk': sum(chunk_token_counts) / len(chunk_token_counts) if chunk_token_counts else 0,
                        'min_tokens_per_chunk': min(chunk_token_counts) if chunk_token_counts else 0,
                        'max_tokens_per_chunk': max(chunk_token_counts) if chunk_token_counts else 0,
                        'total_chunks': len(chunk_token_counts),
                        'configured_chunk_size': self.chunk_size,
                        'configured_chunk_overlap': self.chunk_overlap
                    }
        except Exception:
            pass
        
        # Final fallback: estimate from total tokens and chunks
        total_chunks = sum(len(chunks) for chunks in self.document_index.values())
        if total_chunks > 0 and self.total_tokens > 0:
            avg_tokens = self.total_tokens / total_chunks
            # Create a distribution estimate
            estimated_counts = [int(avg_tokens)] * total_chunks
            return {
                'chunk_token_counts': estimated_counts,
                'avg_tokens_per_chunk': avg_tokens,
                'min_tokens_per_chunk': int(avg_tokens * 0.8),  # Estimate
                'max_tokens_per_chunk': int(avg_tokens * 1.2),  # Estimate
                'total_chunks': total_chunks,
                'configured_chunk_size': self.chunk_size,
                'configured_chunk_overlap': self.chunk_overlap
            }
        
        # Return empty stats if nothing works
        return {
            'chunk_token_counts': [],
            'avg_tokens_per_chunk': 0,
            'min_tokens_per_chunk': 0,
            'max_tokens_per_chunk': 0,
            'total_chunks': 0,
            'configured_chunk_size': self.chunk_size,
            'configured_chunk_overlap': self.chunk_overlap
        }

