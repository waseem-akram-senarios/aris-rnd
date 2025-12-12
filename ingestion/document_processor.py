"""
Document processor for real-time ingestion with progress tracking.
"""
import os
import time
import logging
from dataclasses import dataclass
from typing import Optional, Dict, List
from parsers.parser_factory import ParserFactory
from rag_system import RAGSystem

# Set up enhanced logging
from scripts.setup_logging import setup_logging
logger = setup_logging(
    name="aris_rag.document_processor",
    level=logging.INFO,
    log_file="logs/document_processor.log"
)


@dataclass
class ProcessingResult:
    """Result of document processing."""
    status: str  # 'success', 'failed', 'processing'
    document_name: str
    chunks_created: int = 0
    tokens_extracted: int = 0
    parser_used: Optional[str] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    extraction_percentage: float = 0.0
    images_detected: bool = False


class DocumentProcessor:
    """Processes documents with real-time progress tracking."""
    
    def __init__(self, rag_system: RAGSystem):
        """
        Initialize document processor.
        
        Args:
            rag_system: RAGSystem instance to use for processing
        """
        self.rag_system = rag_system
        self.processing_state: Dict[str, Dict] = {}  # {doc_id: {status, progress, ...}}
    
    def process_document(
        self,
        file_path: str,
        file_content: Optional[bytes] = None,
        file_name: Optional[str] = None,
        parser_preference: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> ProcessingResult:
        """
        Process a single document.
        
        Args:
            file_path: Path to the file (or identifier)
            file_content: Optional file content as bytes
            file_name: Optional file name for display
            parser_preference: Preferred parser ('auto', 'pymupdf', 'docling', 'textract')
            progress_callback: Optional callback function(status, progress) for updates
        
        Returns:
            ProcessingResult with processing statistics
        """
        start_time = time.time()
        doc_name = file_name or os.path.basename(file_path)
        doc_id = file_path
        
        logger.info("=" * 60)
        logger.info(f"[STEP 1] DocumentProcessor: Starting processing for: {doc_name}")
        logger.info(f"   Document ID: {doc_id}")
        logger.info("=" * 60)
        
        # Handle OpenSearch index name generation from document name (for non-UI cases like API)
        # Only generate if index is not explicitly set or is the default
        if (hasattr(self.rag_system, 'vector_store_type') and 
            self.rag_system.vector_store_type.lower() == 'opensearch'):
            current_index = getattr(self.rag_system, 'opensearch_index', None)
            default_index = 'aris-rag-index'
            
            # Generate from document name if index is None or is the default
            if not current_index or current_index == default_index:
                try:
                    from vectorstores.opensearch_store import OpenSearchVectorStore
                    from langchain_openai import OpenAIEmbeddings
                    
                    # Generate index name from document name
                    base_index_name = OpenSearchVectorStore.sanitize_index_name(doc_name)
                    
                    # Check if index exists and auto-increment if needed
                    try:
                        # Create a temporary OpenSearchVectorStore to check index existence
                        temp_embeddings = OpenAIEmbeddings(
                            openai_api_key=os.getenv('OPENAI_API_KEY'),
                            model=self.rag_system.embedding_model
                        )
                        temp_store = OpenSearchVectorStore(
                            embeddings=temp_embeddings,
                            domain=self.rag_system.opensearch_domain,
                            index_name=base_index_name
                        )
                        
                        # Auto-increment if index exists
                        final_index_name = temp_store.get_index_name_for_document(doc_name, auto_increment=True)
                        self.rag_system.opensearch_index = final_index_name
                        logger.info(f"📇 Generated OpenSearch index name from document: '{final_index_name}'")
                    except Exception as e:
                        logger.warning(f"Could not generate index name from document name: {str(e)}. Using base name.")
                        # Use base name as fallback
                        self.rag_system.opensearch_index = base_index_name
                except Exception as e:
                    logger.warning(f"Could not set up document-based index name: {str(e)}")
                    # Continue with default index
        
        # Initialize state
        self.processing_state[doc_id] = {
            'status': 'processing',
            'progress': 0.0,
            'document_name': doc_name
        }
        
        if progress_callback:
            progress_callback('processing', 0.0)
        
        try:
            # Get file size
            logger.info("[STEP 1.1] DocumentProcessor: Validating and preparing document...")
            file_size = len(file_content) if file_content else 0
            if not file_size and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            
            # Get file type
            file_ext = os.path.splitext(doc_name)[1].lower().lstrip('.')
            file_type = file_ext if file_ext else 'unknown'
            file_size_mb = file_size / 1024 / 1024
            logger.info(f"✅ [STEP 1.1] Document validated: type={file_type}, size={file_size:,} bytes ({file_size_mb:.2f} MB)")
            
            # Step 2: Parse document (25% progress)
            logger.info("[STEP 2] DocumentProcessor: Starting document parsing...")
            if progress_callback:
                progress_callback('parsing', 0.25)
            
            parse_start = time.time()
            try:
                # Log parser selection
                parser_name = parser_preference or "auto"
                logger.info(f"[STEP 2.1] DocumentProcessor: Parser selection - preference: {parser_name}")
                if parser_preference:
                    logger.info(f"[STEP 2.1] Explicit parser selected: {parser_preference} (will NOT fall back)")
                
                # Special handling for Docling - show progress updates
                if parser_preference and parser_preference.lower() == 'docling':
                    if progress_callback:
                        progress_callback('parsing', 0.3)
                    # Estimate processing time based on file size
                    if file_size_mb > 10:
                        estimated_time = "15-30 minutes"
                    elif file_size_mb > 5:
                        estimated_time = "10-20 minutes"
                    else:
                        estimated_time = "5-15 minutes"
                        # Update status to show Docling is processing
                    logger.info(f"[STEP 2.2] Docling: Processing {doc_name} ({file_size_mb:.2f} MB) - Estimated time: {estimated_time}")
                
                # Parse document (this will block for Docling, but that's expected)
                logger.info(f"[STEP 2.2] DocumentProcessor: Calling parser with preference: {parser_preference}")
                if file_size_mb > 0:
                    logger.info(f"[STEP 2.2] File size: {file_size_mb:.2f} MB | Estimated processing time: {estimated_time if parser_preference and parser_preference.lower() == 'docling' else 'varies'}")
                
                # Create a wrapper callback that provides parser-specific progress updates
                def parser_progress_callback(status_msg, progress):
                    if progress_callback:
                        # Map parser progress (0.0-1.0) to parsing phase (0.25-0.45)
                        # Parsing phase is 25% to 45% of total progress
                        mapped_progress = 0.25 + (progress * 0.20)  # 0.25 to 0.45
                        # Pass detailed message to progress callback
                        import inspect
                        sig = inspect.signature(progress_callback)
                        if len(sig.parameters) > 2:  # Check if callback accepts kwargs
                            progress_callback('parsing', mapped_progress, detailed_message=status_msg)
                        else:
                            progress_callback('parsing', mapped_progress)
                
                parsed_doc = ParserFactory.parse_with_fallback(
                    file_path,
                    file_content,
                    preferred_parser=parser_preference,
                    progress_callback=parser_progress_callback if progress_callback else None
                )
                
                # Log successful parsing
                if parsed_doc:
                    logger.info(
                        f"✅ [STEP 2.3] DocumentProcessor: Parser '{parsed_doc.parser_used}' completed successfully: "
                        f"{parsed_doc.pages} pages, {len(parsed_doc.text):,} chars, "
                        f"{parsed_doc.extraction_percentage*100:.1f}% extraction"
                    )
                    text_preview = parsed_doc.text[:200] if parsed_doc.text else 'EMPTY'
                    logger.info(f"[STEP 2.3] Text preview (first 200 chars): {text_preview}...")
                else:
                    logger.error("❌ [STEP 2.3] DocumentProcessor: Parser returned None!")
                    raise ValueError("Parser returned None - document could not be parsed")
            except IndexError as e:
                logger.error(f"❌ [STEP 2] Parser error (list index out of range): {str(e)}")
                raise ValueError(f"Parser error (list index out of range): {str(e)}. The PDF may be corrupted or in an unsupported format.")
            except Exception as e:
                logger.error(f"❌ [STEP 2] Parser error: {str(e)}")
                raise ValueError(f"Parser error: {str(e)}")
            parsing_time = time.time() - parse_start
            logger.info(f"✅ [STEP 2] Parsing completed in {parsing_time:.2f} seconds")
            
            # Step 3: Validate parsed document
            logger.info("[STEP 3] DocumentProcessor: Validating parsed document...")
            if parsed_doc is None:
                logger.error("❌ [STEP 3] Parser returned None - document could not be parsed")
                raise ValueError("Parser returned None - document could not be parsed")
            if not hasattr(parsed_doc, 'text'):
                logger.error("❌ [STEP 3] Parsed document missing 'text' attribute")
                raise ValueError("Parsed document missing 'text' attribute")
            if not hasattr(parsed_doc, 'parser_used'):
                logger.error("❌ [STEP 3] Parsed document missing 'parser_used' attribute")
                raise ValueError("Parsed document missing 'parser_used' attribute")
            
            # Check if text is empty (common for scanned/image PDFs)
            doc_text = parsed_doc.text if parsed_doc.text else ""
            logger.info(f"[STEP 3.1] DocumentProcessor: Extracted text length: {len(doc_text):,} characters")
            if not doc_text or not doc_text.strip():
                logger.warning("⚠️ [STEP 3.1] Document text is empty - checking if image-based PDF...")
                # Check if this is an image-based PDF
                if parsed_doc.images_detected or parsed_doc.extraction_percentage < 0.1:
                    # Check if a specific parser was requested
                    requested_parser = parser_preference.lower() if parser_preference else None
                    actual_parser = parsed_doc.parser_used.lower() if hasattr(parsed_doc, 'parser_used') else 'unknown'
                    
                    # If a specific parser was requested but a different one was used, that's an error
                    if requested_parser and requested_parser != 'auto' and actual_parser != requested_parser:
                        logger.error(f"❌ [STEP 3.1] DocumentProcessor: ERROR - Requested {requested_parser} but got {actual_parser}")
                        raise ValueError(
                            f"Parser selection error: You selected '{parser_preference}' but '{parsed_doc.parser_used}' was used instead. "
                            f"This should not happen. Please report this issue."
                        )
                    
                    # Suggest Docling first (has OCR capabilities), then Textract
                    suggestions = []
                    if actual_parser != 'docling':
                        suggestions.append("1. Use Docling parser (has OCR capabilities for scanned PDFs) - Select 'Docling' in parser settings")
                    if actual_parser != 'textract':
                        suggestions.append("2. Use Textract parser (requires AWS credentials) - Select 'Textract' in parser settings")
                    suggestions.append("3. Use OCR software to convert the PDF to text first")
                    
                    error_msg = (
                        f"Document appears to be image-based (scanned PDF). "
                        f"No text could be extracted.\n"
                        f"Parser used: {parsed_doc.parser_used}\n"
                    )
                    
                    if requested_parser and requested_parser != 'auto':
                        error_msg += f"Parser requested: {parser_preference}\n"
                    
                    error_msg += (
                        f"Extraction: {parsed_doc.extraction_percentage * 100:.1f}%\n"
                        f"Pages: {parsed_doc.pages}\n"
                        f"Images detected: {parsed_doc.images_detected}\n\n"
                        f"Solutions:\n"
                        + "\n".join(suggestions)
                    )
                    
                    if actual_parser != 'textract':
                        error_msg += "\n4. Ensure AWS credentials are configured if using Textract"
                    
                    raise ValueError(error_msg)
                else:
                    logger.error("❌ [STEP 3.1] No text could be extracted from the document")
                    raise ValueError(
                        f"No text could be extracted from the document. "
                        f"The document may be corrupted or in an unsupported format."
                    )
            
            logger.info(f"✅ [STEP 3] Document validation completed - {len(doc_text):,} characters ready for processing")
            
            # Step 4: Process with RAG system (chunking and embedding)
            logger.info("[STEP 4] DocumentProcessor: Starting chunking and embedding process...")
            if progress_callback:
                progress_callback('chunking', 0.5)
            
            chunk_start = time.time()
            # Add to RAG system incrementally
            try:
                # Ensure text is valid string
                if not isinstance(doc_text, str):
                    doc_text = str(doc_text)
                
                # Create a wrapper callback that maps internal progress to our progress range
                def chunking_progress_callback(status, progress, **kwargs):
                    if progress_callback:
                        # Map internal progress (0.0-1.0) to our range (0.5-0.95)
                        # chunking: 0.5-0.7, embedding: 0.7-0.95
                        if status == 'chunking':
                            mapped_progress = 0.5 + (progress * 0.2)  # 0.5 to 0.7
                        elif status == 'embedding':
                            mapped_progress = 0.7 + (progress * 0.25)  # 0.7 to 0.95
                        else:
                            mapped_progress = 0.5 + (progress * 0.45)  # 0.5 to 0.95
                        
                        # Forward detailed_message if provided
                        detailed_message = kwargs.get('detailed_message', None)
                        if detailed_message:
                            progress_callback(status, mapped_progress, detailed_message=detailed_message)
                        else:
                            progress_callback(status, mapped_progress)
                
                # Estimate chunks and tokens
                estimated_chunks = max(1, len(doc_text) // (self.rag_system.chunk_size * 4))  # Rough estimate: 4 chars per token
                estimated_tokens = len(doc_text) // 4  # Rough estimate: 4 chars per token
                logger.info(f"[STEP 4.1] DocumentProcessor: Starting chunking and embedding for {doc_name}")
                logger.info(f"[STEP 4.1] Text length: {len(doc_text):,} characters | Estimated chunks: ~{estimated_chunks} | Estimated tokens: ~{estimated_tokens:,}")
                
                # Build metadata with page_blocks for citation support
                doc_metadata = {
                    'source': doc_name,
                    'parser_used': getattr(parsed_doc, 'parser_used', 'unknown'),
                    'pages': getattr(parsed_doc, 'pages', 0),
                    'images_detected': getattr(parsed_doc, 'images_detected', False),
                    'image_count': getattr(parsed_doc, 'image_count', 0),  # Store image count for queries
                    'extraction_percentage': getattr(parsed_doc, 'extraction_percentage', 0.0)
                }
                
                # Preserve page_blocks metadata if available (for citation support)
                if hasattr(parsed_doc, 'metadata') and isinstance(parsed_doc.metadata, dict):
                    if 'page_blocks' in parsed_doc.metadata:
                        doc_metadata['page_blocks'] = parsed_doc.metadata['page_blocks']
                
                logger.info(f"[STEP 4.2] DocumentProcessor: Calling RAGSystem.add_documents_incremental...")
                stats = self.rag_system.add_documents_incremental(
                    texts=[doc_text],
                    metadatas=[doc_metadata],
                    progress_callback=chunking_progress_callback
                )
                logger.info(f"✅ [STEP 4.2] Chunking and embedding completed: {stats['chunks_created']} chunks, {stats['tokens_added']:,} tokens")
            except IndexError as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"❌ [STEP 4] Chunking error (list index out of range): {str(e)}")
                raise ValueError(
                    f"Chunking error (list index out of range): {str(e)}\n"
                    f"The document may be too large or have formatting issues.\n"
                    f"Error details: {error_details[:500]}"
                )
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                logger.error(f"❌ [STEP 4] Chunking error: {str(e)}")
                raise ValueError(f"Chunking error: {str(e)}\nError details: {error_details[:500]}")
            chunking_time = time.time() - chunk_start
            logger.info(f"✅ [STEP 4] Chunking and embedding completed in {chunking_time:.2f} seconds")
            
            # Estimate embedding time (usually fast, but track it)
            embedding_time = 0.0  # Embedding happens in add_documents_incremental
            
            # Step 5: Complete (100% progress)
            logger.info("[STEP 5] DocumentProcessor: Finalizing processing...")
            if progress_callback:
                progress_callback('complete', 1.0)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ [STEP 5] Processing finalized - Total time: {processing_time:.2f}s")
            
            result = ProcessingResult(
                status='success',
                document_name=doc_name,
                chunks_created=stats['chunks_created'],
                tokens_extracted=stats['tokens_added'],
                parser_used=parsed_doc.parser_used,
                processing_time=processing_time,
                extraction_percentage=parsed_doc.extraction_percentage,
                images_detected=parsed_doc.images_detected
            )
            
            # Ensure document is ALWAYS saved to registry for long-term storage
            logger.info("[STEP 6] DocumentProcessor: Ensuring document is saved to registry for long-term storage...")
            try:
                # Import here to avoid circular dependency
                from storage.document_registry import DocumentRegistry
                from config.settings import ARISConfig
                import hashlib
                from datetime import datetime
                
                # Get or create registry
                registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
                registry = DocumentRegistry(registry_path)
                
                # Create stable document ID from file name and content hash
                content_hash = hashlib.md5(
                    (doc_name + str(file_size)).encode()
                ).hexdigest()[:16]
                doc_id = f"{doc_name}_{content_hash}"
                
                # Save comprehensive metadata to registry
                doc_metadata = {
                    'document_id': doc_id,
                    'document_name': doc_name,
                    'status': 'success',
                    'chunks_created': stats['chunks_created'],
                    'tokens_extracted': stats['tokens_added'],
                    'parser_used': parsed_doc.parser_used,
                    'processing_time': processing_time,
                    'extraction_percentage': parsed_doc.extraction_percentage,
                    'images_detected': parsed_doc.images_detected,
                    'pages': parsed_doc.pages,
                    'file_size': file_size,
                    'file_type': file_type,
                    'created_at': datetime.now().isoformat()
                }
                
                # Add vector store information for long-term tracking
                if hasattr(self.rag_system, 'vector_store_type'):
                    doc_metadata['vector_store_type'] = self.rag_system.vector_store_type
                    if self.rag_system.vector_store_type.lower() == 'opensearch':
                        # Add OpenSearch connection info for long-term reference
                        if hasattr(self.rag_system, 'opensearch_domain') and self.rag_system.opensearch_domain:
                            doc_metadata['opensearch_domain'] = self.rag_system.opensearch_domain
                        if hasattr(self.rag_system, 'opensearch_index') and self.rag_system.opensearch_index:
                            doc_metadata['opensearch_index'] = self.rag_system.opensearch_index
                        doc_metadata['storage_location'] = 'opensearch_cloud'
                    else:
                        doc_metadata['storage_location'] = 'local_faiss'
                
                registry.add_document(doc_id, doc_metadata)
                logger.info(f"✅ [STEP 6] Document saved to registry for long-term storage: {doc_id}")
            except Exception as e:
                logger.warning(f"⚠️ [STEP 6] Could not save to registry (non-critical): {e}")
                # Don't fail processing if registry save fails
            
            logger.info("=" * 60)
            logger.info(f"✅ ALL STEPS COMPLETE: Document processed successfully")
            logger.info(f"   Document: {doc_name}")
            logger.info(f"   Total time: {processing_time:.2f}s")
            logger.info(f"   Chunks: {stats['chunks_created']}")
            logger.info(f"   Tokens: {stats['tokens_added']:,}")
            logger.info(f"   Parser: {parsed_doc.parser_used}")
            logger.info("=" * 60)
            
            # Record metrics if collector is available
            logger.info("[STEP 6] DocumentProcessor: Recording metrics...")
            if hasattr(self.rag_system, 'metrics_collector') and self.rag_system.metrics_collector:
                self.rag_system.metrics_collector.record_processing(
                    document_name=doc_name,
                    file_size=file_size,
                    file_type=file_type,
                    parser_used=parsed_doc.parser_used,
                    pages=parsed_doc.pages,
                    chunks_created=stats['chunks_created'],
                    tokens_extracted=stats['tokens_added'],
                    extraction_percentage=parsed_doc.extraction_percentage,
                    confidence=parsed_doc.confidence if hasattr(parsed_doc, 'confidence') else 1.0,
                    processing_time=processing_time,
                    parsing_time=parsing_time,
                    chunking_time=chunking_time,
                    embedding_time=embedding_time,
                    success=True,
                    images_detected=parsed_doc.images_detected
                )
                logger.info("✅ [STEP 6] Metrics recorded")
            
            self.processing_state[doc_id] = {
                'status': 'success',
                'progress': 1.0,
                'document_name': doc_name,
                'result': result
            }
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)
            logger.error("=" * 60)
            logger.error(f"❌ ERROR: Document processing failed")
            logger.error(f"   Document: {doc_name}")
            logger.error(f"   Error: {error_msg}")
            logger.error(f"   Time elapsed: {processing_time:.2f}s")
            logger.error("=" * 60)
            
            # Get file size for metrics
            file_size = len(file_content) if file_content else 0
            if not file_size and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(doc_name)[1].lower().lstrip('.')
            file_type = file_ext if file_ext else 'unknown'
            
            result = ProcessingResult(
                status='failed',
                document_name=doc_name,
                error=error_msg,
                processing_time=processing_time
            )
            
            # Record failed metrics
            if hasattr(self.rag_system, 'metrics_collector') and self.rag_system.metrics_collector:
                self.rag_system.metrics_collector.record_processing(
                    document_name=doc_name,
                    file_size=file_size,
                    file_type=file_type,
                    parser_used=parser_preference or 'unknown',
                    pages=0,
                    chunks_created=0,
                    tokens_extracted=0,
                    extraction_percentage=0.0,
                    confidence=0.0,
                    processing_time=processing_time,
                    success=False,
                    error=error_msg
                )
            
            self.processing_state[doc_id] = {
                'status': 'failed',
                'progress': 1.0,
                'document_name': doc_name,
                'error': error_msg,
                'result': result
            }
            
            if progress_callback:
                progress_callback('failed', 1.0)
            
            return result
    
    def process_documents_batch(
        self,
        files: List[Dict],  # List of {path, content, name}
        parser_preference: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> List[ProcessingResult]:
        """
        Process multiple documents sequentially.
        
        Args:
            files: List of file dictionaries with 'path', 'content' (optional), 'name'
            parser_preference: Preferred parser
            progress_callback: Optional callback(doc_index, total_docs, status, progress)
        
        Returns:
            List of ProcessingResult objects
        """
        results = []
        total_files = len(files)
        
        for idx, file_info in enumerate(files):
            file_path = file_info.get('path', '')
            file_content = file_info.get('content')
            file_name = file_info.get('name', os.path.basename(file_path))
            
            # Create callback wrapper
            def doc_progress_callback(status, progress):
                if progress_callback:
                    overall_progress = (idx + progress) / total_files
                    progress_callback(idx, total_files, file_name, status, overall_progress)
            
            # Process document
            result = self.process_document(
                file_path=file_path,
                file_content=file_content,
                file_name=file_name,
                parser_preference=parser_preference,
                progress_callback=doc_progress_callback
            )
            
            results.append(result)
        
        return results
    
    def get_processing_state(self, doc_id: str) -> Optional[Dict]:
        """Get processing state for a document."""
        return self.processing_state.get(doc_id)
    
    def get_all_states(self) -> Dict[str, Dict]:
        """Get all processing states."""
        return self.processing_state.copy()
    
    def clear_state(self, doc_id: Optional[str] = None):
        """Clear processing state for a document or all documents."""
        if doc_id:
            self.processing_state.pop(doc_id, None)
        else:
            self.processing_state.clear()

