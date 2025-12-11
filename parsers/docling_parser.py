"""
Docling parser using the simple quickstart pattern from documentation.
Uses ThreadPoolExecutor to prevent UI blocking during long processing.
"""
import os
import logging
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .base_parser import BaseParser, ParsedDocument

# Set up logging
logger = logging.getLogger(__name__)


class DoclingParser(BaseParser):
    """Parser using Docling library - following the official quickstart pattern."""
    
    def __init__(self):
        super().__init__("docling")
        try:
            from docling.document_converter import DocumentConverter
            self.DocumentConverter = DocumentConverter
        except ImportError:
            raise ImportError(
                "Docling is not installed. "
                "Install it with: pip install docling"
            )
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle PDF files."""
        _, ext = os.path.splitext(file_path.lower())
        return ext == '.pdf'
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None, progress_callback: Optional[Callable[[str, float], None]] = None, _retry_without_callback: bool = False) -> ParsedDocument:
        """
        Parse PDF using Docling - simple quickstart pattern.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
            progress_callback: Optional callback(status_message, progress) for UI updates
        
        Returns:
            ParsedDocument with extracted text and metadata
        """
        try:
            # Handle file_content by saving to temp file if needed
            actual_path = file_path
            temp_file = None
            if file_content:
                import tempfile
                # Create temp file in system temp directory
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', mode='wb')
                temp_file.write(file_content)
                temp_file.flush()
                os.fsync(temp_file.fileno())  # Ensure data is written to disk
                temp_file.close()
                actual_path = temp_file.name
                # Verify temp file was created and has content
                if not os.path.exists(actual_path):
                    raise ValueError(f"Temp file was not created: {actual_path}")
                if os.path.getsize(actual_path) == 0:
                    raise ValueError(f"Temp file is empty: {actual_path}")
            
            # Use absolute path
            actual_path = os.path.abspath(actual_path)
            if not os.path.exists(actual_path):
                raise ValueError(f"File not found: {actual_path}")
            
            # Log start of processing
            file_size = os.path.getsize(actual_path)
            file_size_mb = file_size / 1024 / 1024
            # Estimate pages based on file size (1-2 MB per page for scanned PDFs, less for text-based)
            estimated_pages = max(1, int(file_size_mb / 1.5)) if file_size_mb > 0 else 0
            # Estimate processing time (5-20 minutes for scanned PDFs with OCR)
            if file_size_mb > 10:
                estimated_time = "15-30 minutes"
            elif file_size_mb > 5:
                estimated_time = "10-20 minutes"
            else:
                estimated_time = "5-15 minutes"
            
            logger.info(f"Docling: Starting conversion of {os.path.basename(actual_path)} ({file_size_mb:.2f} MB)")
            logger.info(f"Docling: File size: {file_size_mb:.2f} MB | Estimated pages: {estimated_pages} | Estimated time: {estimated_time}")
            logger.info(f"Docling: Progress updates every 15 seconds")
            
            # Run Docling conversion in a separate thread to prevent UI blocking
            # Docling can take 5-10 minutes for large PDFs
            def run_docling_conversion():
                """Run Docling conversion in thread."""
                try:
                    logger.info("Docling: [Phase 1/4] Initializing DocumentConverter with OCR enabled...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 1/4] Initializing DocumentConverter with OCR enabled...", 0.1)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    
                    # Enable OCR for image-based PDFs
                    try:
                        from docling.datamodel.pipeline_options import PipelineOptions
                        from docling.datamodel.document_converter_config import DocumentConverterConfig
                        
                        pipeline_options = PipelineOptions()
                        pipeline_options.do_ocr = True  # Enable OCR to extract text from images
                        pipeline_options.do_table_structure = True  # Keep table extraction enabled
                        pipeline_options.do_vision = True  # Enable vision model for better image understanding
                        
                        config = DocumentConverterConfig()
                        config.pipeline_options = pipeline_options
                        
                        converter = self.DocumentConverter(config=config)
                        logger.info("Docling: OCR enabled for image text extraction")
                    except (ImportError, AttributeError) as e:
                        # Fallback to default if configuration fails
                        logger.warning(f"Docling: Could not enable OCR configuration: {e}. Using default converter.")
                        converter = self.DocumentConverter()
                    
                    logger.info("Docling: [Phase 2/4] DocumentConverter initialized with OCR, starting conversion...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 2/4] Starting document conversion with OCR...", 0.2)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    logger.info(f"Docling: [Phase 2/4] Converting file: {os.path.basename(actual_path)}")
                    result = converter.convert(actual_path, raises_on_error=False)
                    logger.info("Docling: [Phase 3/4] Conversion completed, accessing document...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 3/4] Conversion completed, accessing document...", 0.8)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    doc = result.document
                    page_count = len(doc.pages) if hasattr(doc, 'pages') else 'unknown'
                    logger.info(f"Docling: [Phase 4/4] Document accessed successfully, pages: {page_count}")
                    if progress_callback:
                        try:
                            progress_callback(f"Docling: [Phase 4/4] Document accessed, {page_count} pages", 0.9)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    return doc
                except Exception as e:
                    logger.error(f"Docling: Error in conversion thread: {str(e)}")
                    raise
            
            # Use ThreadPoolExecutor without file-level timeout
            # Files will process completely regardless of size
            # Docling processes all pages which can take a long time, especially for scanned PDFs with OCR
            # No timeout - will process completely
            try:
                # Wait for result with periodic progress logging
                import time as time_module
                import threading
                
                start_time = time_module.time()
                progress_logging_active = threading.Event()
                progress_logging_active.set()
                
                # Get max timeout from env or use default (30 minutes)
                max_timeout = int(os.getenv('DOCLING_MAX_TIMEOUT', '1800'))  # 30 minutes default
                
                # Track progress for stuck detection
                last_progress_value = 0.0
                last_progress_change_time = start_time
                stuck_threshold = 10 * 60  # 10 minutes without progress change
                stuck_warning_logged = False
                
                # Future will be set by executor
                future_ref = [None]  # Use list to allow modification in nested scope
                
                def log_progress():
                    """Log detailed progress every 15 seconds while processing."""
                    nonlocal last_progress_value, last_progress_change_time, stuck_warning_logged
                    check_interval = 15  # Log every 15 seconds (more frequent)
                    last_log_time = start_time
                    
                    while progress_logging_active.is_set():
                        time_module.sleep(check_interval)
                        if not progress_logging_active.is_set():
                            break
                        
                        elapsed = time_module.time() - start_time
                        
                        # Check if maximum processing time exceeded
                        if elapsed > max_timeout + 60:  # Slightly longer than timeout
                            logger.warning(f"Docling: Maximum processing time exceeded. Stopping progress logging.")
                            progress_logging_active.clear()
                            return
                        
                        # Check if future is actually done (conversion completed)
                        # Don't show 100% until conversion is actually complete
                        future_done = False
                        if future_ref[0] is not None:
                            future_done = future_ref[0].done()
                        
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        
                        # Calculate estimated progress based on elapsed time and file size
                        # Docling typically processes at 0.5-2 pages per minute for scanned PDFs with OCR
                        # For text-based PDFs, it's much faster (10-50 pages per minute)
                        # IMPORTANT: Cap at 95% until future is actually done to avoid showing 100% while still processing
                        if file_size_mb > 10:
                            # Large scanned PDF - estimate 0.5-1 page per minute
                            processing_rate = 0.75
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                # For unknown pages, use time-based with cap at 0.95 until done
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        elif file_size_mb > 5:
                            # Medium scanned PDF - estimate 1-2 pages per minute
                            processing_rate = 1.5
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        else:
                            # Small PDF - estimate 2-5 pages per minute
                            processing_rate = 3.0
                            estimated_pages_processed = min(estimated_pages, elapsed / 60 * processing_rate)
                            if estimated_pages > 0:
                                raw_progress = min(1.0, estimated_pages_processed / estimated_pages)
                                # Cap at 95% until conversion is actually done
                                estimated_progress = raw_progress if future_done else min(0.95, raw_progress)
                            else:
                                estimated_progress = 0.95 if not future_done else min(0.98, elapsed / max_timeout)
                        
                        # If future is done, show 95-99% (finalizing)
                        if future_done:
                            estimated_progress = min(0.99, estimated_progress + 0.04)  # Show 95-99% when done but not yet retrieved
                        
                        # Stuck processing detection
                        if estimated_progress >= 0.90:
                            if abs(estimated_progress - last_progress_value) < 0.01:
                                # Progress hasn't changed significantly
                                if elapsed - last_progress_change_time > stuck_threshold and not stuck_warning_logged:
                                    logger.warning(f"Docling: Processing appears stuck at ~{int(estimated_progress*100)}% for {stuck_threshold//60} minutes")
                                    logger.warning(f"Docling: Document may have unprocessable pages. Consider using PyMuPDF parser.")
                                    stuck_warning_logged = True
                            else:
                                # Progress has changed, reset tracking
                                last_progress_value = estimated_progress
                                last_progress_change_time = elapsed
                                stuck_warning_logged = False
                        else:
                            # Progress is still low, update tracking
                            last_progress_value = estimated_progress
                            last_progress_change_time = elapsed
                        
                        # Estimate remaining time based on current progress
                        if estimated_progress > 0.05:  # Only estimate if we have meaningful progress
                            estimated_total_time = elapsed / estimated_progress
                            estimated_remaining = max(0, estimated_total_time - elapsed)
                            remaining_minutes = int(estimated_remaining // 60)
                            remaining_seconds = int(estimated_remaining % 60)
                            remaining_str = f"~{remaining_minutes}m {remaining_seconds}s remaining"
                        else:
                            remaining_str = "calculating..."
                        
                        # Determine current phase based on elapsed time
                        if elapsed < 30:
                            phase = "Initializing DocumentConverter"
                        elif elapsed < 120:
                            phase = "Analyzing document structure"
                        elif elapsed < 300:
                            phase = "Processing pages (OCR if needed)"
                        else:
                            phase = "Processing remaining pages (OCR if needed)"
                        
                        # Log detailed progress
                        progress_pct = int(estimated_progress * 100)
                        
                        # Add status indicator if future is done
                        status_indicator = ""
                        if future_done:
                            status_indicator = " (conversion complete, finalizing...)"
                        elif estimated_progress >= 0.95:
                            status_indicator = " (processing final pages...)"
                        
                        log_msg = (
                            f"Docling: [{phase}] "
                            f"Progress: ~{progress_pct}%{status_indicator} | "
                            f"Elapsed: {minutes}m {seconds}s | "
                            f"{remaining_str} | "
                            f"File: {file_size_mb:.1f}MB | "
                            f"Estimated pages: {estimated_pages}"
                        )
                        logger.info(log_msg)
                        
                        # Call progress callback if available (safely handle Streamlit NoSessionContext)
                        if progress_callback:
                            try:
                                # Map progress to 0.1-0.9 range (leaving 0.9-1.0 for final steps)
                                callback_progress = 0.1 + (estimated_progress * 0.8)
                                progress_callback(log_msg, callback_progress)
                            except Exception as callback_error:
                                # Handle NoSessionContext and other threading issues
                                if "NoSessionContext" in str(callback_error) or "NoSessionContext" in type(callback_error).__name__:
                                    # Don't call callback from background thread - just log
                                    logger.debug(f"Docling: Skipping progress callback (NoSessionContext in background thread)")
                                else:
                                    # Log other callback errors but don't fail
                                    logger.warning(f"Docling: Progress callback error: {str(callback_error)}")
                        
                        last_log_time = elapsed
                
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_docling_conversion)
                    future_ref[0] = future  # Store reference for log_progress to access
                    
                    logger.info(f"Docling: Processing in background thread (no timeout - will process completely)...")
                    logger.info(f"Docling: File size: {file_size_mb:.2f} MB | Estimated time: {estimated_time} | Estimated pages: {estimated_pages}")
                    
                    # Start progress logging thread
                    progress_thread = threading.Thread(target=log_progress, daemon=True)
                    progress_thread.start()
                    
                    try:
                        # Wait for result with maximum timeout to prevent infinite hangs
                        # Docling can get stuck on pages with no text, so we need a safety timeout
                        logger.info(f"Docling: Waiting for conversion result (max timeout: {max_timeout//60} minutes)...")
                        
                        # Check periodically if future is done and log final progress
                        import time as time_check
                        last_check = time_check.time()
                        while not future.done() and (time_check.time() - start_time) < max_timeout:
                            time_check.sleep(1)  # Check every second
                            elapsed_check = time_check.time() - start_time
                            if elapsed_check - last_check >= 15:  # Log every 15 seconds
                                logger.info(f"Docling: Still waiting for conversion to complete... ({int(elapsed_check//60)}m {int(elapsed_check%60)}s elapsed)")
                                last_check = elapsed_check
                        
                        # Now get the result (should be done or will timeout)
                        doc = future.result(timeout=max_timeout)  # Add timeout to prevent infinite hangs
                        progress_logging_active.clear()
                        logger.info("Docling: Document conversion successful - result received")
                        if doc is None:
                            raise ValueError("Docling conversion returned None - conversion may have failed")
                        logger.info(f"Docling: Document object received, type: {type(doc)}")
                        logger.info("Docling: ✅ Conversion 100% complete - processing finished")
                    except FutureTimeoutError:
                        progress_logging_active.clear()
                        logger.error(f"Docling: Processing timed out after {max_timeout//60} minutes")
                        logger.error(f"Docling: Document may have unprocessable pages or is too complex")
                        logger.error(f"Docling: Try using PyMuPDF parser instead, or check document for corrupted pages")
                        raise ValueError(
                            f"Docling processing timed out after {max_timeout//60} minutes. "
                            f"The document may have pages that cannot be processed or is too complex. "
                            f"Try using PyMuPDF parser instead."
                        )
                    except Exception as e:
                        progress_logging_active.clear()
                        error_str = str(e) if str(e) else type(e).__name__
                        logger.error(f"Docling: Error waiting for result: {error_str}")
                        if "timeout" in error_str.lower() or "TimeoutError" in str(type(e)):
                            logger.error(f"Docling: Processing timed out. Try using PyMuPDF parser instead.")
                        raise
                    finally:
                        progress_logging_active.clear()
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_str = str(e) if str(e) else type(e).__name__
                if not error_str or error_str.strip() == "":
                    error_str = f"Unknown error ({type(e).__name__})"
                
                logger.error(f"Docling: Conversion failed: {error_str}")
                logger.error(f"Docling: Full traceback:\n{error_details}")
                
                # Create user-friendly error message
                if "not valid" in error_str.lower():
                    error_msg = f"Docling cannot process this PDF - the file format is not valid. Error: {error_str}. Try using PyMuPDF parser instead."
                elif "timeout" in error_str.lower():
                    error_msg = f"Docling conversion timed out. The PDF may be very large or complex. Error: {error_str}. Try using PyMuPDF parser for faster processing."
                else:
                    error_msg = f"Docling conversion failed: {error_str}. The PDF may be corrupted or in an unsupported format. Try using PyMuPDF parser instead."
                
                raise ValueError(error_msg)
            
            # Export to markdown (as shown in quickstart)
            logger.info("Docling: Exporting document to markdown...")
            page_blocks = []  # Store page-level blocks for citation support
            
            # Get actual page count from document for validation
            total_pages = len(doc.pages) if hasattr(doc, 'pages') else 0
            logger.info(f"Docling: Document has {total_pages} pages")
            
            try:
                text = doc.export_to_markdown()
                logger.info(f"Docling: Markdown export completed ({len(text):,} characters)")
                
                # Extract page-level structure if available
                if hasattr(doc, 'pages'):
                    pages_dict = doc.pages
                    if isinstance(pages_dict, dict):
                        for page_key, page_content in pages_dict.items():
                            try:
                                # Try to extract page number from key
                                if isinstance(page_key, int):
                                    page_idx = page_key
                                elif isinstance(page_key, str) and page_key.isdigit():
                                    page_idx = int(page_key)
                                else:
                                    continue
                                
                                # Docling may use 0-based indexing, convert to 1-based for display
                                if page_idx == 0 and total_pages > 0:
                                    page_idx = 1  # First page should be 1
                                elif page_idx < 0:
                                    page_idx = abs(page_idx)  # Handle negative indices
                                
                                # Validate page is within document range
                                if page_idx < 1 or (total_pages > 0 and page_idx > total_pages):
                                    logger.warning(f"Docling: Page {page_idx} out of range [1, {total_pages}], skipping")
                                    continue
                                
                                page_text = str(page_content) if hasattr(page_content, '__str__') else ""
                                if page_text:
                                    page_blocks.append({
                                        'page': page_idx,
                                        'text': page_text,
                                        'blocks': [{'text': page_text, 'page': page_idx}]  # Simplified for Docling
                                    })
                            except Exception as e:
                                logger.warning(f"Docling: Error processing page {page_key}: {e}")
                    elif isinstance(pages_dict, list):
                        for idx, page_content in enumerate(pages_dict):
                            try:
                                # Docling list indices are 0-based, convert to 1-based
                                page_idx = idx + 1
                                
                                # Validate page is within document range
                                if total_pages > 0 and page_idx > total_pages:
                                    logger.warning(f"Docling: Page {page_idx} exceeds document pages {total_pages}")
                                    break
                                
                                page_text = str(page_content) if hasattr(page_content, '__str__') else ""
                                if page_text:
                                    page_blocks.append({
                                        'page': page_idx,
                                        'text': page_text,
                                        'blocks': [{'text': page_text, 'page': page_idx}]
                                    })
                            except Exception as e:
                                logger.warning(f"Docling: Error processing page {idx}: {e}")
            except Exception as e:
                logger.error(f"Docling: Error exporting to markdown: {str(e)}")
                # Try alternative export methods
                text = None
                if hasattr(doc, 'export_to_text'):
                    try:
                        logger.info("Docling: Trying export_to_text as fallback...")
                        text = doc.export_to_text()
                        logger.info(f"Docling: Text export completed ({len(text) if text else 0:,} characters)")
                    except Exception as e2:
                        logger.error(f"Docling: Error exporting to text: {str(e2)}")
                
                if not text or not text.strip():
                    raise ValueError(f"Docling: Could not export document text. Markdown export failed: {str(e)}")
            
            # Validate text extraction - try alternative methods if markdown is empty
            if not text or not text.strip():
                # Try export_to_text as fallback
                if hasattr(doc, 'export_to_text'):
                    try:
                        text = doc.export_to_text()
                    except:
                        pass
                
                # If still empty, try get_text
                if not text or not text.strip():
                    if hasattr(doc, 'get_text'):
                        try:
                            text = doc.get_text()
                        except:
                            pass
                
                # If still empty, try accessing text attribute directly
                if not text or not text.strip():
                    if hasattr(doc, 'text'):
                        try:
                            text = str(doc.text) if doc.text else ""
                        except:
                            pass
            
            # Clean up temp file if created (after text extraction)
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            
            # Final validation - raise error if no text extracted
            if not text or not text.strip():
                raise ValueError(
                    f"Docling processed the PDF but extracted no text content. "
                    f"This may indicate the PDF format is not compatible with Docling's layout model. "
                    f"Try using PyMuPDF parser instead."
                )
            
            # Get page count - ensure it matches actual document page count
            pages = 0
            if hasattr(doc, 'pages'):
                pages_dict = doc.pages
                if isinstance(pages_dict, dict):
                    pages = len(pages_dict)
                elif isinstance(pages_dict, list):
                    pages = len(pages_dict)
                else:
                    pages = total_pages  # Use calculated total_pages
            else:
                pages = total_pages
            
            # Validate pages count
            if pages <= 0:
                logger.warning(f"Docling: Invalid page count {pages}, using 1 as fallback")
                pages = 1
            elif total_pages > 0 and pages != total_pages:
                logger.warning(f"Docling: Page count mismatch - calculated {total_pages} but got {pages} from pages structure")
                # Use the higher value to be safe
                pages = max(pages, total_pages)
            
            # Calculate metrics
            text_length = len(text.strip())
            words = text.split()
            word_count = len(words)
            
            logger.info(f"Docling: Extracted {pages} pages, {len(text):,} characters, {word_count:,} words")
            
            # Estimate extraction percentage
            if pages > 0:
                estimated_chars_per_page = 2000  # Conservative estimate
                expected_text_length = pages * estimated_chars_per_page
                extraction_percentage = min(1.0, text_length / expected_text_length) if expected_text_length > 0 else 0.0
            else:
                extraction_percentage = 1.0 if text_length > 500 else (text_length / 500.0) if text_length > 0 else 0.0
            
            # Confidence based on text extraction
            if text_length > 2000:
                confidence = 0.95
            elif text_length > 1000:
                confidence = 0.85
            elif text_length > 500:
                confidence = 0.75
            elif text_length > 100:
                confidence = 0.65
            else:
                confidence = 0.5
            
            # Check for images
            images_detected = False
            if hasattr(doc, 'pictures') and len(doc.pictures) > 0:
                images_detected = True
            
            metadata = {
                "source": file_path,
                "pages": pages,
                "text_length": text_length,
                "word_count": word_count,
                "file_size": len(file_content) if file_content else os.path.getsize(file_path),
                "page_blocks": page_blocks  # Store page-level blocks for citation support
            }
            
            return ParsedDocument(
                text=text,
                metadata=metadata,
                pages=pages,
                images_detected=images_detected,
                parser_used=self.name,
                confidence=confidence,
                extraction_percentage=extraction_percentage
            )
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            # Get error message - handle empty messages
            error_str = str(e) if str(e) else type(e).__name__
            if not error_str or error_str.strip() == "":
                error_str = f"Unknown error ({type(e).__name__})"
            
            # Log full error details
            logger.error(f"Docling: Failed to parse PDF: {error_str}")
            logger.error(f"Docling: Full traceback:\n{error_details}")
            
            # Clean up temp file on error
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            
            # Create user-friendly error message
            if "NoSessionContext" in error_str or "NoSessionContext" in type(e).__name__:
                # This is a Streamlit threading issue - try direct parsing without callbacks (only once)
                if not _retry_without_callback:
                    logger.warning(f"Docling: NoSessionContext error detected - this is a Streamlit threading issue, not a PDF problem")
                    logger.info(f"Docling: Attempting direct parsing without progress callbacks...")
                    try:
                        # Retry without progress callback (set flag to prevent infinite recursion)
                        return self.parse(file_path, file_content, progress_callback=None, _retry_without_callback=True)
                    except Exception as retry_error:
                        error_msg = (
                            f"Docling parser failed due to Streamlit session context issues (NoSessionContext). "
                            f"This is a threading limitation, not a PDF problem. "
                            f"Try using PyMuPDF parser instead, which handles this better."
                        )
                else:
                    # Already retried once, don't retry again
                    error_msg = (
                        f"Docling parser failed due to Streamlit session context issues (NoSessionContext). "
                        f"This is a threading limitation, not a PDF problem. "
                        f"Try using PyMuPDF parser instead, which handles this better."
                    )
            elif "not valid" in error_str.lower() or "cannot process" in error_str.lower():
                error_msg = f"Docling cannot process this PDF. The file may be corrupted, encrypted, or in an unsupported format. Error: {error_str}. Try using PyMuPDF parser instead."
            elif "timeout" in error_str.lower() or "timed out" in error_str.lower():
                error_msg = f"Docling parsing timed out. The PDF may be very large or complex. Error: {error_str}. Try using PyMuPDF parser for faster processing."
            elif "too large" in error_str.lower():
                error_msg = f"PDF is too large for Docling to process. Error: {error_str}. Try using PyMuPDF or Textract parser instead."
            elif "memory" in error_str.lower() or "out of memory" in error_str.lower():
                error_msg = f"Docling ran out of memory processing this PDF. The document may be too large. Error: {error_str}. Try using PyMuPDF parser instead."
            else:
                error_msg = f"Failed to parse PDF with Docling: {error_str}. The PDF may be corrupted, encrypted, or in an unsupported format. Try using PyMuPDF parser for better compatibility."
            
            raise ValueError(error_msg)
