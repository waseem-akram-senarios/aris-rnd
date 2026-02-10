"""
Document processor for real-time ingestion with progress tracking.
"""
import os
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any, Any
from shared.schemas import ProcessingResult
from .parsers.parser_factory import ParserFactory
from .engine import IngestionEngine
from shared.config.settings import ARISConfig

# Set up enhanced logging
from scripts.setup_logging import setup_logging
logger = setup_logging(
    name="aris_rag.document_processor",
    level=logging.INFO,
    log_file="logs/document_processor.log"
)




class DocumentProcessor:
    """Processes documents with real-time progress tracking."""
    
    def __init__(self, rag_system: IngestionEngine):
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
        document_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        index_name: Optional[str] = None,
        language: str = "eng",
        is_update: bool = False,
        old_index_name: Optional[str] = None
    ) -> ProcessingResult:
        """
        Process a single document.
        
        Args:
            file_path: Path to the file (or identifier)
            file_content: Optional file content as bytes
            file_name: Optional file name for display
            parser_preference: Preferred parser ('auto', 'pymupdf', 'docling', 'textract')
            document_id: Optional document ID for strict indexing and registry persistence
            progress_callback: Optional callback function(status, progress) for updates
            index_name: Optional explicit OpenSearch index name
            language: Language code for OCR (default: 'eng'). Use '+' for multiple (e.g. 'eng+spa')
            is_update: Whether this is an update to an existing document
            old_index_name: Old index name to clean up if updating
        
        Returns:
            ProcessingResult with processing statistics
        """
        start_time = time.time()
        doc_name = file_name or os.path.basename(file_path)
        doc_id = document_id or file_path
        s3_url = None
        
        logger.info("=" * 60)
        if is_update:
            logger.info(f"[STEP 1] DocumentProcessor: UPDATING existing document: {doc_name}")
        else:
            logger.info(f"[STEP 1] DocumentProcessor: Starting processing for: {doc_name}")
        logger.info(f"   Document ID: {doc_id}")
        if is_update and old_index_name:
            logger.info(f"   Updating index: {old_index_name}")
        logger.info("=" * 60)
        
        # If updating, clean up old index data first
        if is_update and old_index_name:
            self._cleanup_old_index_data(doc_id, old_index_name, doc_name)
        
        # Handle OpenSearch index name generation from document name (for non-UI cases like API)
        # Only generate if index is not explicitly set or is the default
        if (hasattr(self.rag_system, 'vector_store_type') and 
            self.rag_system.vector_store_type.lower() == 'opensearch'):
            current_index = getattr(self.rag_system, 'opensearch_index', None)
            default_index = 'aris-rag-index'
            
            # Priority 1: Explicitly provided index name
            if index_name:
                self.rag_system.opensearch_index = index_name
                current_index = index_name
                logger.info(f"📇 Using explicitly provided OpenSearch index: '{index_name}'")
            # Priority 2: document_id based index for document isolation
            elif document_id:
                self.rag_system.opensearch_index = f"aris-doc-{document_id}"
                current_index = self.rag_system.opensearch_index
                logger.info(f"📇 Using document-specific OpenSearch index: '{current_index}'")
            
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
            'document_name': doc_name,
            'detailed_message': 'Starting...'
        }
        
        # Immediate registry persistence for status tracking
        if doc_id:
            try:
                from storage.document_registry import DocumentRegistry
                registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                registry.add_document(doc_id, {
                    'document_id': doc_id,
                    'document_name': doc_name,
                    'status': 'processing',
                    'progress': 0.0,
                    'created_at': datetime.fromtimestamp(os.path.getctime(file_path)).isoformat() if os.path.exists(file_path) else datetime.now().isoformat()
                })
                logger.info(f"Registered document {doc_id} in registry with 'processing' status")
            except Exception as e:
                logger.warning(f"Could not register document {doc_id} on startup: {e}")
        
        def update_status(status, progress, detailed_message=None):
            """Internal helper to update state and call callback"""
            self.processing_state[doc_id].update({
                'status': status,
                'progress': progress
            })
            if detailed_message:
                self.processing_state[doc_id]['detailed_message'] = detailed_message
            
            if progress_callback:
                try:
                    import inspect
                    sig = inspect.signature(progress_callback)
                    if len(sig.parameters) > 2:
                        progress_callback(status, progress, detailed_message=detailed_message)
                    else:
                        progress_callback(status, progress)
                except Exception as e:
                    logger.warning(f"Error in external progress callback: {e}")

        update_status('processing', 0.0, "Starting document processing...")
        
        try:
            # Initialize images_stored_count at higher scope for registry access
            images_stored_count = 0
            
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
            
            # [NEW] Upload to S3 if enabled
            if hasattr(self.rag_system, 's3_service') and self.rag_system.s3_service.enabled:
                try:
                    s3_start = time.time()
                    update_status('processing', 0.1, f"Backing up {doc_name} to S3...")
                    # Use a clean folder structure: documents/doc_id/filename
                    s3_key = f"documents/{doc_id}/{doc_name}"
                    
                    upload_success = False
                    if file_content:
                        upload_success = self.rag_system.s3_service.upload_bytes(file_content, s3_key)
                    else:
                        upload_success = self.rag_system.s3_service.upload_file(file_path, s3_key)
                        
                    s3_time = time.time() - s3_start
                    if upload_success:
                        s3_url = f"s3://{self.rag_system.s3_service.bucket_name}/{s3_key}"
                        logger.info(f"✅ [STEP 1.2] Document backed up to S3 in {s3_time:.2f}s: {s3_url}")
                    else:
                        logger.warning(f"⚠️ [STEP 1.2] S3 backup failed for {doc_name} after {s3_time:.2f}s, continuing with local processing")
                except Exception as e:
                    logger.warning(f"⚠️ [STEP 1.2] S3 upload error (non-critical): {e}")
            
            # Step 2: Parse document (25% progress)
            logger.info("[STEP 2] DocumentProcessor: Starting document parsing...")
            update_status('parsing', 0.25, "Starting document parsing...")
            
            parse_start = time.time()
            try:
                # Get parser from factory with language preference
                # Note: get_parser requires file_path as first argument, then preferred_parser
                parser = ParserFactory.get_parser(
                    file_path,
                    parser_preference or 'auto',
                    language=language
                )
                
                # Guard against None parser - provide clear error message
                if parser is None:
                    if parser_preference and parser_preference.lower() in ['llamascan', 'llama-scan']:
                        raise ValueError(
                            "Llama-Scan parser selected but Ollama server is not reachable or vision model is missing. "
                            "Please ensure Ollama is running (default: http://localhost:11434 or host.docker.internal) "
                            "and the vision model (default: qwen2.5vl:latest) is pulled."
                        )
                    elif parser_preference and parser_preference.lower() == 'ocrmypdf':
                        raise ValueError(
                            "OCRmyPDF selected but not available. "
                            "Ensure ocrmypdf and tesseract-ocr are installed: "
                            "sudo apt-get install tesseract-ocr && pip install ocrmypdf"
                        )
                    else:
                        file_ext = os.path.splitext(file_path)[1].lower().lstrip('.')
                        raise ValueError(f"No parser available for file extension: {file_ext}")
                
                logger.info(f"[STEP 2.1] Parser selected: {parser.get_name()} (Language: {language})")
                if parser_preference:
                    logger.info(f"[STEP 2.1] Explicit parser selected: {parser_preference} (will NOT fall back)")
                
                # Special handling for Docling - show progress updates
                if parser_preference and parser_preference.lower() == 'docling':
                    update_status('parsing', 0.3, f"Docling parsing {doc_name}...")
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
                def parser_progress_callback(status_msg, progress, detailed_message=None):
                    # Map parser progress (0.0-1.0) to parsing phase (0.25-0.45)
                    # Parsing phase is 25% to 45% of total progress
                    mapped_progress = 0.25 + (progress * 0.20)  # 0.25 to 0.45
                    # Use detailed_message if provided, otherwise use status_msg
                    msg = detailed_message if detailed_message else status_msg
                    update_status('parsing', mapped_progress, msg)
                
                parsed_doc = ParserFactory.parse_with_fallback(
                    file_path,
                    file_content,
                    preferred_parser=parser_preference,
                    progress_callback=parser_progress_callback if progress_callback else None,
                    language=language
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
                    
                    # Store images in OpenSearch if available
                    extracted_images_list = None
                    if (hasattr(parsed_doc, 'metadata') and 
                        isinstance(parsed_doc.metadata, dict)):
                        extracted_images_list = parsed_doc.metadata.get('extracted_images', [])
                        logger.info(f"[STEP 2.4] Checking for extracted_images: found {len(extracted_images_list) if extracted_images_list else 0} images")
                    
                    if extracted_images_list and len(extracted_images_list) > 0:
                        logger.info(f"[STEP 2.4] Storing {len(extracted_images_list)} images in OpenSearch...")
                        img_store_start = time.time()
                        try:
                            images_stored_count = self._store_images_in_opensearch(
                                extracted_images_list,
                                doc_name,
                                parsed_doc.parser_used
                            )
                            img_store_time = time.time() - img_store_start
                            logger.info(f"✅ [STEP 2.4] Successfully stored {images_stored_count} images in OpenSearch in {img_store_time:.2f}s")
                        except Exception as e:
                            img_store_time = time.time() - img_store_start
                            logger.warning(f"⚠️ [STEP 2.4] Failed to store images in OpenSearch after {img_store_time:.2f}s: {str(e)}")
                            import traceback
                            logger.debug(f"[STEP 2.4] Storage error details: {traceback.format_exc()}")
                            # Don't fail processing if image storage fails
                    elif extracted_images_list is not None and len(extracted_images_list) == 0:
                        logger.warning(f"⚠️ [STEP 2.4] extracted_images list is empty - no images to store")
                    else:
                        logger.info(f"[STEP 2.4] No extracted_images in metadata - images may not have been extracted")
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
            
            # Step 3.5: Enhanced Language Detection and Optional Translation
            detected_language = language  # Use provided language as default
            secondary_language = None
            script_type = "latin"
            english_translation = None
            
            try:
                # Auto-detect language if enabled and not explicitly set
                multilingual_config = ARISConfig.get_multilingual_config()
                
                if multilingual_config.get('auto_detect_language', True) and language == "eng" and len(doc_text) > 50:
                    try:
                        from services.language.detector import get_detector
                        detector = get_detector()
                        
                        # Detect primary and secondary languages for mixed-language documents
                        sample_text = doc_text[:5000]  # Use first 5000 chars for detection
                        detected_iso2 = detector.detect(sample_text)
                        detected_language = detector.detect_to_iso639_3(sample_text)
                        
                        # Detect primary and secondary languages
                        primary_iso2, secondary_iso2 = detector.detect_primary_and_secondary(sample_text)
                        if secondary_iso2:
                            from services.language.detector import ISO_639_1_TO_639_3
                            secondary_language = ISO_639_1_TO_639_3.get(secondary_iso2, secondary_iso2)
                        
                        # Get script type for metadata
                        script_type = detector.get_script_type(detected_iso2)
                        
                        lang_name = detector.get_language_name(detected_iso2)
                        if detected_language != "eng":
                            logger.info(
                                f"🌐 [STEP 3.5] Auto-detected document language: {lang_name} ({detected_language}), "
                                f"script={script_type}, secondary={secondary_language}"
                            )
                            update_status('processing', 0.45, f"Detected language: {lang_name} ({script_type} script)")
                        else:
                            logger.info(f"🌐 [STEP 3.5] Document language: English")
                            
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 3.5] Language detection failed: {e}")
                        detected_language = language
                
                # Optional: Translate to English for better embeddings (if enabled)
                if (multilingual_config.get('translate_on_ingestion', False) and 
                    detected_language != "eng" and 
                    len(doc_text) > 0):
                    try:
                        from services.language.translator import get_translator
                        update_status('processing', 0.47, f"Translating document to English...")
                        
                        translator = get_translator(provider=multilingual_config.get('translation_provider', 'openai'))
                        
                        # Store original text BEFORE translation for dual-language storage
                        original_text = doc_text
                        
                        # Translate in chunks to handle large documents
                        max_chunk_size = 4000  # OpenAI limit consideration
                        if len(doc_text) > max_chunk_size:
                            # Translate in chunks
                            translated_chunks = []
                            for i in range(0, len(doc_text), max_chunk_size):
                                chunk = doc_text[i:i+max_chunk_size]
                                translated_chunk = translator.translate(chunk, target_lang="en")
                                translated_chunks.append(translated_chunk)
                            english_translation = " ".join(translated_chunks)
                        else:
                            english_translation = translator.translate(doc_text, target_lang="en")
                        
                        logger.info(f"✅ [STEP 3.5] Document translated to English ({len(english_translation):,} chars)")
                        
                        # Use Native Language Embeddings (don't replace doc_text)
                        # Store translation in metadata for cross-lingual search
                        
                    except Exception as e:
                        logger.warning(f"⚠️ [STEP 3.5] Translation failed, using original: {e}")
                        original_text = doc_text
                        english_translation = None
                else:
                    # No translation needed - document is already English or translation disabled
                    original_text = doc_text
                    english_translation = doc_text if detected_language == "eng" else None
                        
            except ImportError as e:
                logger.debug(f"Language services not available: {e}")
                original_text = doc_text
                english_translation = None
            
            # Store language in metadata (MANDATORY for language-isolated search)
            language = detected_language

            
            # Step 4: Process with RAG system (chunking and embedding)
            logger.info("[STEP 4] DocumentProcessor: Starting chunking and embedding process...")
            update_status('chunking', 0.5, "Starting chunking phase...")
            
            chunk_start = time.time()
            # Add to RAG system incrementally
            try:
                # Ensure text is valid string
                if not isinstance(doc_text, str):
                    doc_text = str(doc_text)
                
                # Create a wrapper callback that maps internal progress to our progress range
                def chunking_progress_callback(status, progress, **kwargs):
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
                    update_status(status, mapped_progress, detailed_message)
                
                # Estimate chunks and tokens
                estimated_chunks = max(1, len(doc_text) // (self.rag_system.chunk_size * 4))  # Rough estimate: 4 chars per token
                estimated_tokens = len(doc_text) // 4  # Rough estimate: 4 chars per token
                logger.info(f"[STEP 4.1] DocumentProcessor: Starting chunking and embedding for {doc_name}")
                logger.info(f"[STEP 4.1] Text length: {len(doc_text):,} characters | Estimated chunks: ~{estimated_chunks} | Estimated tokens: ~{estimated_tokens:,}")
                
                # Build metadata with page_blocks for citation support
                # MANDATORY: language field for language-isolated indexing/filtering
                base_metadata = {
                    'source': doc_name,
                    'document_id': document_id,
                    # MANDATORY language metadata for isolated indexing
                    'language': language,  # ISO 639-3 code (e.g., 'eng', 'spa')
                    'language_detected': detected_language,  # What was auto-detected
                    'primary_language': detected_language,
                    'secondary_language': secondary_language,  # For mixed-language docs
                    'script_type': script_type,  # 'latin', 'cyrillic', 'cjk', etc.
                    # Parser and extraction info
                    'parser_used': getattr(parsed_doc, 'parser_used', 'unknown'),
                    'pages': getattr(parsed_doc, 'pages', 0),
                    'images_detected': getattr(parsed_doc, 'images_detected', False),
                    'image_count': getattr(parsed_doc, 'image_count', 0),  # Store image count for queries
                    'extraction_percentage': getattr(parsed_doc, 'extraction_percentage', 0.0),
                    's3_url': s3_url,
                    # Dual-language storage for cross-lingual search
                    'text_original': original_text[:5000] if len(original_text) > 5000 else original_text,  # Truncate to prevent metadata bloat
                    'text_english': english_translation[:5000] if english_translation and len(english_translation) > 5000 else english_translation
                }
                
                # NEW LOGIC: Use page_blocks if available for accurate citations
                texts_to_process = []
                metadatas_to_process = []

                if (hasattr(parsed_doc, 'metadata') and 
                    isinstance(parsed_doc.metadata, dict) and 
                    'page_blocks' in parsed_doc.metadata and 
                    parsed_doc.metadata['page_blocks']):
                    
                    page_blocks = parsed_doc.metadata['page_blocks']
                    num_raw_blocks = len(page_blocks)
                    logger.info(f"[STEP 4.2] Processing page_blocks for accurate citation chunking ({num_raw_blocks} blocks detected)...")
                    
                    # Group blocks by page to avoid overhead of 100,000+ individual items
                    # This is Fix #11 for ingestion performance
                    grouped_by_page = {}
                    for block in page_blocks:
                        page_num = block.get('page', 0)
                        if page_num not in grouped_by_page:
                            grouped_by_page[page_num] = {
                                'text_parts': [],
                                'start_char': block.get('start_char', 0),
                                'end_char': block.get('end_char', 0)
                            }
                        
                        if block.get('text') and block['text'].strip():
                            grouped_by_page[page_num]['text_parts'].append(block['text'])
                            # Update page boundaries
                            grouped_by_page[page_num]['start_char'] = min(grouped_by_page[page_num]['start_char'], block.get('start_char', 0))
                            grouped_by_page[page_num]['end_char'] = max(grouped_by_page[page_num]['end_char'], block.get('end_char', 0))
                    
                    # Convert grouped pages back to lists for processing
                    sorted_page_nums = sorted(grouped_by_page.keys())
                    
                    # Limit the number of blocks stored in metadata if it's too large to prevent OpenSearch failures
                    max_meta_blocks = getattr(ARISConfig, 'MAX_PAGE_BLOCKS_PER_DOC', 2000)
                    if len(page_blocks) > max_meta_blocks:
                        logger.warning(f"⚠️ Document has too many blocks ({len(page_blocks)}). Reducing to {max_meta_blocks} for metadata storage.")
                        # We still process everyone, but we only store a sample/summary in metadata if it's huge
                        base_metadata['page_blocks'] = page_blocks[:max_meta_blocks]
                        base_metadata['total_blocks_count'] = len(page_blocks)
                    else:
                        base_metadata['page_blocks'] = page_blocks

                    for page_num in sorted_page_nums:
                        page_data = grouped_by_page[page_num]
                        if page_data['text_parts']:
                            page_text = "\n".join(page_data['text_parts'])
                            
                            page_meta = base_metadata.copy()
                            page_meta.update({
                                'page': page_num,
                                'start_char': page_data['start_char'],
                                'end_char': page_data['end_char']
                            })
                            
                            texts_to_process.append(page_text)
                            metadatas_to_process.append(page_meta)
                    
                    logger.info(f"✅ [STEP 4.2] Consolidated {num_raw_blocks} blocks into {len(texts_to_process)} page-level entries.")
                
                # Fallback if no page blocks or empty blocks
                if not texts_to_process:
                    logger.info(f"[STEP 4.2] No page_blocks found, using full document text...")
                    texts_to_process = [doc_text]
                    # Include original page_blocks in metadata if they exist but were not used (e.g. malformed)
                    if hasattr(parsed_doc, 'metadata') and isinstance(parsed_doc.metadata, dict):
                        if 'page_blocks' in parsed_doc.metadata:
                            base_metadata['page_blocks'] = parsed_doc.metadata['page_blocks']
                    metadatas_to_process = [base_metadata]
                
                logger.info(f"[STEP 4.2] DocumentProcessor: Calling RAGSystem.add_documents_incremental with {len(texts_to_process)} text items...")
                stats = self.rag_system.add_documents_incremental(
                    texts=texts_to_process,
                    metadatas=metadatas_to_process,
                    progress_callback=chunking_progress_callback,
                    index_name=index_name
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
            update_status('complete', 1.0, "Processing complete!")
            
            processing_time = time.time() - start_time
            logger.info(f"✅ [STEP 5] Processing finalized - Total time: {processing_time:.2f}s")
            
            result = ProcessingResult(
                document_id=document_id,  # Pass through the authoritative document_id
                status='success',
                document_name=doc_name,
                language=language,
                chunks_created=stats['chunks_created'],
                tokens_extracted=stats['tokens_added'],
                parser_used=parsed_doc.parser_used,
                processing_time=processing_time,
                extraction_percentage=parsed_doc.extraction_percentage,
                confidence=getattr(parsed_doc, 'confidence', 0.0),
                images_detected=parsed_doc.images_detected,
                image_count=getattr(parsed_doc, 'image_count', 0),
                pages=getattr(parsed_doc, 'pages', 0),
                file_size=file_size,
                file_type=file_type,
                is_update=is_update
            )
            
            # Ensure document is ALWAYS saved to registry for long-term storage
            logger.info("[STEP 6] DocumentProcessor: Ensuring document is saved to registry for long-term storage...")
            try:
                # Import here to avoid circular dependency
                from storage.document_registry import DocumentRegistry
                # Save result to registry for persistence
                import hashlib
                from datetime import datetime
                
                # Get or create registry
                registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
                registry = DocumentRegistry(registry_path)
                
                # Use authoritative document_id if provided (FastAPI path). Otherwise fall back to stable ID.
                if document_id:
                    doc_id = document_id
                else:
                    content_hash = hashlib.md5(
                        (doc_name + str(file_size)).encode()
                    ).hexdigest()[:16]
                    doc_id = f"{doc_name}_{content_hash}"
                
                # Get image count from parsed document or extracted images
                actual_image_count = getattr(parsed_doc, 'image_count', 0)
                if hasattr(parsed_doc, 'metadata') and isinstance(parsed_doc.metadata, dict):
                    extracted_images = parsed_doc.metadata.get('extracted_images', [])
                    if extracted_images:
                        actual_image_count = max(actual_image_count, len(extracted_images))
                
                # Use images_stored_count from image storage phase
                images_stored = images_stored_count
                
                # Save comprehensive metadata to registry
                doc_metadata = {
                    'document_id': doc_id,
                    'document_name': doc_name,
                    'status': 'success',
                    'language': language,
                    'chunks_created': stats['chunks_created'],
                    'tokens_extracted': stats['tokens_added'],
                    'parser_used': parsed_doc.parser_used,
                    'processing_time': processing_time,
                    'extraction_percentage': parsed_doc.extraction_percentage,
                    'images_detected': parsed_doc.images_detected,
                    'image_count': actual_image_count,
                    'images_stored': images_stored,
                    'pages': parsed_doc.pages,
                    'file_size': file_size,
                    'file_type': file_type,
                    's3_url': s3_url,
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
                            doc_metadata['text_index'] = self.rag_system.opensearch_index
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
    
    def _cleanup_old_index_data(self, doc_id: str, old_index_name: str, doc_name: str) -> bool:
        """
        Clean up old index data when updating a document.
        
        Args:
            doc_id: Document ID
            old_index_name: Name of the old index to clean up
            doc_name: Document name for source filtering
        
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            logger.info(f"[CLEANUP] Starting cleanup of old index data for document: {doc_name}")
            
            # Check if RAG system has OpenSearch
            if not hasattr(self.rag_system, 'vector_store_type'):
                logger.warning("[CLEANUP] No vector store type configured, skipping cleanup")
                return False
            
            if self.rag_system.vector_store_type.lower() != 'opensearch':
                logger.info("[CLEANUP] Not using OpenSearch, skipping index cleanup")
                return False
            
            # Get OpenSearch client
            from vectorstores.opensearch_store import OpenSearchStore
            
            # Delete chunks from the old index that belong to this document
            if hasattr(self.rag_system, 'vectorstore') and self.rag_system.vectorstore:
                try:
                    store = self.rag_system.vectorstore
                    if hasattr(store, 'vectorstore') and hasattr(store.vectorstore, 'client'):
                        client = store.vectorstore.client
                        
                        # Delete by source field (document name)
                        delete_query = {
                            "query": {
                                "bool": {
                                    "should": [
                                        {"match": {"source": doc_name}},
                                        {"match": {"metadata.source": doc_name}}
                                    ]
                                }
                            }
                        }
                        
                        response = client.delete_by_query(
                            index=old_index_name,
                            body=delete_query,
                            conflicts='proceed'
                        )
                        
                        deleted_count = response.get('deleted', 0)
                        logger.info(f"[CLEANUP] Deleted {deleted_count} chunks from index '{old_index_name}' for document '{doc_name}'")
                        
                        # Also clean up from images index
                        try:
                            images_index = "aris-rag-images-index"
                            images_delete_query = {
                                "query": {
                                    "bool": {
                                        "should": [
                                            {"match": {"source": doc_name}},
                                            {"match": {"document_name": doc_name}}
                                        ]
                                    }
                                }
                            }
                            
                            images_response = client.delete_by_query(
                                index=images_index,
                                body=images_delete_query,
                                conflicts='proceed'
                            )
                            
                            images_deleted = images_response.get('deleted', 0)
                            if images_deleted > 0:
                                logger.info(f"[CLEANUP] Deleted {images_deleted} images from '{images_index}' for document '{doc_name}'")
                        except Exception as img_e:
                            logger.debug(f"[CLEANUP] Could not clean images index (may not exist): {img_e}")
                        
                        return True
                except Exception as client_e:
                    logger.warning(f"[CLEANUP] Failed to delete old chunks: {client_e}")
                    return False
            
            logger.warning("[CLEANUP] No vectorstore available for cleanup")
            return False
            
        except Exception as e:
            logger.error(f"[CLEANUP] Error during cleanup: {e}")
            return False
    
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
    
    def _store_images_in_opensearch(
        self,
        extracted_images: List[Dict[str, Any]],
        doc_name: str,
        parser_used: str
    ) -> int:
        """
        Store extracted images in OpenSearch images index.
        
        Args:
            extracted_images: List of image dictionaries from parser
            doc_name: Document name
            parser_used: Parser that extracted the images
            
        Returns:
            Number of images successfully stored
        """
        if not extracted_images:
            logger.info(f"_store_images_in_opensearch: No images to store (list is empty or None)")
            return 0
        
        logger.info(f"_store_images_in_opensearch: Attempting to store {len(extracted_images)} images for document: {doc_name}")
        # Log first image format for debugging
        if extracted_images and len(extracted_images) > 0:
            first_img = extracted_images[0]
            logger.info(f"_store_images_in_opensearch: First image keys: {list(first_img.keys())}")
            logger.info(f"_store_images_in_opensearch: First image source: {first_img.get('source', 'MISSING')}")
            logger.info(f"_store_images_in_opensearch: First image number: {first_img.get('image_number', 'MISSING')}")
            logger.info(f"_store_images_in_opensearch: First image page: {first_img.get('page', 'MISSING')}")
            logger.info(f"_store_images_in_opensearch: First image OCR length: {len(first_img.get('ocr_text', ''))}")
        
        # Normalize and clean image payloads to ensure consistent retrieval
        normalized_source = os.path.basename(doc_name) if doc_name else doc_name
        cleaned_images: List[Dict[str, Any]] = []
        for idx, img in enumerate(extracted_images):
            if not isinstance(img, dict):
                continue
            cleaned = dict(img)
            # Force a canonical source so downstream retrieval can query by document name
            cleaned['source'] = normalized_source
            # Ensure image_number is set and valid (1-based)
            cleaned['image_number'] = cleaned.get('image_number') or (idx + 1)
            if cleaned['image_number'] == 0:
                cleaned['image_number'] = idx + 1
            # Ensure page is set and valid (1-based)
            original_page = cleaned.get('page')
            if original_page is None or original_page == 0:
                cleaned['page'] = 1  # Default to page 1 if not specified
            else:
                cleaned['page'] = original_page
            cleaned['ocr_text'] = cleaned.get('ocr_text') or ""
            # Log for debugging
            logger.debug(f"_store_images_in_opensearch: Image {idx+1}: page={cleaned['page']}, image_number={cleaned['image_number']}")
            cleaned_images.append(cleaned)

        if not cleaned_images:
            logger.warning("_store_images_in_opensearch: Image list was empty after normalization - skipping storage")
            return 0

        opensearch_domain = getattr(self.rag_system, 'opensearch_domain', None)
        if not opensearch_domain:
            # Check if OpenSearch is configured via environment variables
            opensearch_domain = os.getenv('OPENSEARCH_DOMAIN') or os.getenv('AWS_OPENSEARCH_DOMAIN')
        
        if not opensearch_domain:
            logger.debug("OpenSearch domain not configured - skipping image storage")
            logger.debug("To enable image storage, set OPENSEARCH_DOMAIN or AWS_OPENSEARCH_DOMAIN environment variable")
            return 0
        
        stored_count = 0
        try:
            from vectorstores.opensearch_images_store import OpenSearchImagesStore
            from langchain_openai import OpenAIEmbeddings
            from shared.utils.image_extraction_logger import image_logger
            
            # Log storage start
            if image_logger:
                image_logger.log_storage_start(
                    source=doc_name,
                    image_count=len(extracted_images),
                    storage_method="opensearch"
                )
            
            # Initialize images store
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model=self.rag_system.embedding_model
            )
            
            # Use OpenSearch domain from rag_system or environment
            opensearch_domain = getattr(self.rag_system, 'opensearch_domain', None) or os.getenv('AWS_OPENSEARCH_DOMAIN') or os.getenv('OPENSEARCH_DOMAIN')
            opensearch_region = getattr(self.rag_system, 'region', None) or os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
            
            if not opensearch_domain:
                logger.warning("OpenSearch domain not found - cannot store images")
                return 0
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=opensearch_domain,
                region=opensearch_region
            )
            
            # Store images in batch
            logger.info(f"_store_images_in_opensearch: Calling store_images_batch with {len(cleaned_images)} images")
            try:
                image_ids = images_store.store_images_batch(cleaned_images)
                stored_count = len(image_ids) if image_ids else 0
                logger.info(f"_store_images_in_opensearch: store_images_batch returned {stored_count} image IDs")
                if image_ids:
                    logger.info(f"_store_images_in_opensearch: ✅ Successfully stored images: {image_ids[:5]}...")
                else:
                    logger.warning(f"_store_images_in_opensearch: ⚠️  store_images_batch returned empty list")
            except Exception as e:
                logger.error(f"_store_images_in_opensearch: ❌ Error in store_images_batch: {str(e)}")
                import traceback
                logger.error(f"_store_images_in_opensearch: Error details: {traceback.format_exc()}")
                raise
            
            # Log storage success
            if image_logger:
                image_logger.log_storage_success(
                    source=doc_name,
                    images_stored=stored_count,
                    image_ids=image_ids
                )
            
            logger.info(f"✅ Stored {stored_count} images in OpenSearch for document: {doc_name}")
            return stored_count
        except ImportError as e:
            logger.warning(f"OpenSearch images store not available: {str(e)}")
            return 0
        except Exception as e:
            # Log storage failure
            try:
                from shared.utils.image_extraction_logger import image_logger
                if image_logger:
                    image_logger.log_storage_failure(
                        source=doc_name,
                        error=str(e),
                        images_attempted=len(extracted_images)
                    )
            except:
                pass
            raise

