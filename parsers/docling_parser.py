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
    
    def _verify_ocr_models(self):
        """Verify OCR models are available for Docling."""
        try:
            # Try to check if OCR models exist
            from pathlib import Path
            import os
            
            # Docling stores models in user home directory
            home_dir = Path.home()
            models_path = home_dir / ".cache" / "docling" / "models"
            
            # Check if models directory exists and has content
            if models_path.exists():
                # Check for model files (common OCR model patterns)
                model_files = list(models_path.rglob("*.onnx"))  # ONNX models used by RapidOCR
                model_files.extend(list(models_path.rglob("*.pt")))  # PyTorch models
                model_files.extend(list(models_path.rglob("*.pth")))  # PyTorch models
                model_files.extend(list(models_path.rglob("*.bin")))  # Binary model files
                
                if model_files:
                    logger.info(f"Docling: ✅ OCR models found ({len(model_files)} model files)")
                    return True
                elif any(models_path.iterdir()):
                    # Directory exists with some content, assume models might be there
                    logger.info("Docling: ✅ OCR models directory found (models may be available)")
                    return True
                else:
                    logger.warning("Docling: ⚠️  OCR models directory exists but is empty")
                    logger.warning("Docling: Install models with: docling download-models")
                    return False
            else:
                logger.warning("Docling: ⚠️  OCR models directory not found")
                logger.warning("Docling: Install models with: docling download-models")
                logger.warning("Docling: OCR may still work if models are installed elsewhere or auto-downloaded")
                # Don't return False here - models might be auto-downloaded or in different location
                # Return True to allow processing to continue (Docling will handle missing models)
                return True
        except Exception as e:
            logger.warning(f"Docling: Could not verify OCR models: {e}")
            logger.warning("Docling: OCR may still work if models are available")
            # Return True to allow processing - Docling will handle missing models gracefully
            return True
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle PDF files."""
        _, ext = os.path.splitext(file_path.lower())
        return ext == '.pdf'
    
    def test_ocr_configuration(self) -> dict:
        """
        Test OCR configuration and return diagnostic information.
        
        Returns:
            dict with status, models_available, config_status, etc.
        """
        result = {
            'ocr_available': False,
            'models_available': False,
            'config_success': False,
            'warnings': [],
            'errors': []
        }
        
        # Check models
        result['models_available'] = self._verify_ocr_models()
        
        # Test OCR configuration - default DocumentConverter has OCR enabled by default
        try:
            # The default DocumentConverter has OCR enabled by default
            test_converter = self.DocumentConverter()
            result['config_success'] = True
            result['ocr_available'] = True
            result['warnings'].append("Using default converter (OCR enabled by default in Docling)")
        except Exception as e:
            result['errors'].append(f"OCR configuration test failed: {e}")
        
        return result
    
    def _insert_image_markers(self, text: str, image_positions: list = None) -> str:
        """
        Insert <!-- image --> markers into text at specified positions or before image-related content.
        
        Args:
            text: Text content
            image_positions: Optional list of character positions where images should be marked
        
        Returns:
            Text with image markers inserted
        """
        if not text or not text.strip():
            return text
        
        # If image positions provided, insert markers at those positions
        if image_positions:
            # Sort positions in reverse order to maintain indices when inserting
            sorted_positions = sorted(image_positions, reverse=True)
            result_text = text
            for pos in sorted_positions:
                if 0 <= pos <= len(result_text):
                    result_text = result_text[:pos] + "<!-- image -->\n" + result_text[pos:]
            return result_text
        
        # Otherwise, return text as-is (markers should be inserted by parser logic)
        return text
    
    def _extract_text_per_page(self, doc, total_pages: int, progress_callback: Optional[Callable[[str, float], None]] = None):
        """
        Extract text per page from Docling document structure.
        
        Args:
            doc: Docling document object
            total_pages: Total number of pages in document
            progress_callback: Optional progress callback
        
        Returns:
            Tuple of (full_text_with_markers, page_blocks, success_flag)
            success_flag: True if per-page extraction succeeded, False if fallback needed
        """
        text_parts = []
        page_blocks = []
        cumulative_pos = 0
        per_page_extraction_success = False
        
        try:
            # Try to access pages structure
            if not hasattr(doc, 'pages') or not doc.pages:
                logger.warning("Docling: No pages structure available, will use fallback")
                return "", [], False
            
            pages_dict = doc.pages
            pages_iterable = None
            
            # Handle both dict and list formats
            if isinstance(pages_dict, dict):
                # Dict format: keys might be page numbers or indices
                # Try to get pages in order
                try:
                    # Try numeric keys first (1, 2, 3...)
                    sorted_keys = sorted([k for k in pages_dict.keys() if isinstance(k, (int, str))], 
                                        key=lambda x: int(x) if str(x).isdigit() else 0)
                    if sorted_keys:
                        pages_iterable = [(int(k) if str(k).isdigit() else 0, pages_dict[k]) for k in sorted_keys]
                    else:
                        # Fallback: use values directly
                        pages_iterable = enumerate(pages_dict.values(), 1)
                except Exception:
                    # Fallback: use values directly
                    pages_iterable = enumerate(pages_dict.values(), 1)
            elif isinstance(pages_dict, list):
                pages_iterable = enumerate(pages_dict, 1)
            else:
                logger.warning("Docling: Pages structure format not recognized, will use fallback")
                return "", [], False
            
            # Try to extract text from each page
            pages_with_text = 0
            for page_idx, page_obj in pages_iterable:
                page_num = page_idx if isinstance(page_idx, int) else page_idx[0] if isinstance(page_idx, tuple) else 1
                page_content = page_obj if not isinstance(page_idx, tuple) else page_idx[1]
                
                page_text = ""
                
                # Try multiple methods to extract text from page
                # Method 1: page.export_to_text()
                if hasattr(page_content, 'export_to_text'):
                    try:
                        page_text = page_content.export_to_text()
                        if page_text and page_text.strip():
                            per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} export_to_text() failed: {e}")
                
                # Method 2: page.get_text()
                if not page_text and hasattr(page_content, 'get_text'):
                    try:
                        page_text = page_content.get_text()
                        if page_text and page_text.strip():
                            per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} get_text() failed: {e}")
                
                # Method 3: Extract from page.blocks
                if not page_text and hasattr(page_content, 'blocks'):
                    try:
                        block_texts = []
                        image_blocks_found = []
                        for block_idx, block in enumerate(page_content.blocks):
                            # Check if this is an image block
                            is_image_block = False
                            if hasattr(block, 'type') and block.type in ['image', 'figure', 'picture', 'illustration']:
                                is_image_block = True
                                image_blocks_found.append(block_idx)
                            
                            # Extract text from block
                            block_text = ""
                            if hasattr(block, 'text') and block.text:
                                block_text = block.text
                            elif hasattr(block, 'get_text'):
                                try:
                                    block_text = block.get_text()
                                except:
                                    pass
                            
                            if block_text:
                                # If this is an image block, insert marker before its text
                                if is_image_block:
                                    block_texts.append("<!-- image -->\n" + block_text)
                                else:
                                    block_texts.append(block_text)
                        
                        if block_texts:
                            page_text = '\n'.join(block_texts)
                            if page_text.strip():
                                per_page_extraction_success = True
                    except Exception as e:
                        logger.debug(f"Docling: Page {page_num} blocks extraction failed: {e}")
                
                # Check for images on this page (pictures attribute)
                page_has_images = False
                if hasattr(page_content, 'pictures') and len(page_content.pictures) > 0:
                    page_has_images = True
                    # If we have text but no image markers yet, insert them
                    # Insert marker at the start if this page has images and text was extracted
                    if page_text and '<!-- image -->' not in page_text:
                        # Check if text looks like OCR content (short lines, structured)
                        # Insert marker before text if images are present
                        page_text = "<!-- image -->\n" + page_text
                
                # If we got text from this page, add it with marker
                if page_text and page_text.strip():
                    pages_with_text += 1
                    
                    # Add page marker (matching PyMuPDF format)
                    page_marker = f"--- Page {page_num} ---\n"
                    page_text_with_marker = page_marker + page_text
                    
                    # Track character positions for accurate page boundaries
                    page_start = cumulative_pos
                    page_end = cumulative_pos + len(page_text_with_marker)
                    
                    # Create page block with accurate boundaries
                    page_blocks.append({
                        'page': page_num,
                        'text': page_text,
                        'start_char': page_start,
                        'end_char': page_end,
                        'blocks': [{'text': page_text, 'page': page_num}]
                    })
                    
                    # Add to full text with marker
                    text_parts.append(page_text_with_marker)
                    cumulative_pos = page_end
                    
                    # Update progress
                    if progress_callback and total_pages > 0:
                        try:
                            progress = 0.9 + (page_num / total_pages) * 0.05  # 90-95% range
                            progress_callback(f"Docling: Extracted page {page_num}/{total_pages}...", progress)
                        except:
                            pass
            
            if per_page_extraction_success and pages_with_text > 0:
                full_text = "\n\n".join(text_parts)
                logger.info(f"Docling: ✅ Per-page extraction successful - {pages_with_text}/{total_pages} pages extracted")
                return full_text, page_blocks, True
            else:
                logger.warning(f"Docling: Per-page extraction failed or extracted 0 pages, will use fallback")
                return "", [], False
                
        except Exception as e:
            logger.warning(f"Docling: Error in per-page extraction: {e}, will use fallback")
            import traceback
            logger.debug(f"Docling: Per-page extraction traceback: {traceback.format_exc()}")
            return "", [], False
    
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
                    # Verify OCR models are available first
                    ocr_models_available = self._verify_ocr_models()
                    if not ocr_models_available:
                        logger.warning("Docling: OCR models may not be available - OCR may fail")
                        logger.warning("Docling: Run 'docling download-models' to install OCR models")
                    
                    # IMPORTANT: The default DocumentConverter in Docling has OCR enabled by default
                    # We don't need to configure it - just use the default converter
                    # Docling automatically uses OCR when processing documents with images
                    converter = self.DocumentConverter()
                    logger.info("Docling: ✅ Using default DocumentConverter (OCR enabled by default)")
                    logger.info("Docling: OCR will automatically process images in the document")
                    
                    logger.info("Docling: [Phase 2/4] DocumentConverter initialized with OCR, starting conversion...")
                    logger.info("Docling: OCR will process images in the document (this may take time)...")
                    if progress_callback:
                        try:
                            progress_callback("Docling: [Phase 2/4] Starting document conversion with OCR...", 0.2)
                        except Exception as e:
                            if "NoSessionContext" not in str(e):
                                logger.warning(f"Docling: Progress callback error: {str(e)}")
                    logger.info(f"Docling: [Phase 2/4] Converting file: {os.path.basename(actual_path)}")
                    result = converter.convert(actual_path, raises_on_error=False)
                    logger.info("Docling: [Phase 3/4] Conversion completed, accessing document...")
                    logger.info("Docling: OCR processing complete - extracting text from converted document...")
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
            
            # PRIMARY METHOD: Extract text per page for accurate page numbers
            # This ensures page markers and accurate page_blocks for citation support
            logger.info("Docling: Extracting text per page for accurate page numbers...")
            
            page_blocks = []  # Store page-level blocks for citation support
            text = ""
            total_pages = 0
            
            try:
                # Get page count first
                if hasattr(doc, 'pages') and doc.pages:
                    pages_dict = doc.pages
                    if isinstance(pages_dict, dict):
                        total_pages = len(pages_dict)
                    elif isinstance(pages_dict, list):
                        total_pages = len(pages_dict)
                    else:
                        total_pages = 1
                else:
                    total_pages = 1
                
                logger.info(f"Docling: Document has {total_pages} pages")
                
                # PRIMARY: Try per-page extraction first for accurate page numbers
                text, page_blocks, per_page_success = self._extract_text_per_page(doc, total_pages, progress_callback)
                
                if per_page_success and text:
                    logger.info(f"Docling: ✅ Per-page text extraction completed ({len(text):,} characters with page markers)")
                else:
                    # FALLBACK: Use export_to_text() if per-page extraction failed
                    logger.info("Docling: Per-page extraction not available, using export_to_text() with fallback page markers...")
                    try:
                        text = doc.export_to_text()
                        logger.info(f"Docling: ✅ Text export completed ({len(text):,} characters)")
                        
                        # Add page markers to text and create page_blocks as fallback
                        if total_pages > 1 and text:
                            # Split text into approximate pages and add markers
                            text_lines = text.split('\n')
                            lines_per_page = max(1, len(text_lines) // total_pages)
                            text_parts = []
                            cumulative_pos = 0
                            
                            for page_idx in range(1, total_pages + 1):
                                start_line = (page_idx - 1) * lines_per_page
                                end_line = page_idx * lines_per_page if page_idx < total_pages else len(text_lines)
                                page_text = '\n'.join(text_lines[start_line:end_line])
                                
                                if page_text.strip():
                                    # Add page marker (matching PyMuPDF format)
                                    page_marker = f"--- Page {page_idx} ---\n"
                                    page_text_with_marker = page_marker + page_text
                                    
                                    # Track character positions
                                    page_start = cumulative_pos
                                    page_end = cumulative_pos + len(page_text_with_marker)
                                    
                                    # Create page block with boundaries
                                    page_blocks.append({
                                        'page': page_idx,
                                        'text': page_text.strip(),
                                        'start_char': page_start,
                                        'end_char': page_end,
                                        'blocks': [{'text': page_text.strip(), 'page': page_idx}]
                                    })
                                    
                                    text_parts.append(page_text_with_marker)
                                    cumulative_pos = page_end
                            
                            # Rebuild text with page markers
                            text = "\n\n".join(text_parts)
                            logger.info(f"Docling: ✅ Added page markers to text ({len(text):,} characters)")
                    
                    except Exception as e1:
                        logger.warning(f"Docling: export_to_text() failed: {e1}, trying export_to_markdown()...")
                        # FALLBACK: Use export_to_markdown() if export_to_text() fails
                        try:
                            text = doc.export_to_markdown()
                            logger.info(f"Docling: ✅ Markdown export completed ({len(text):,} characters)")
                            
                            # Add page markers to markdown and create page_blocks
                            if total_pages > 1 and text:
                                text_lines = text.split('\n')
                                lines_per_page = max(1, len(text_lines) // total_pages)
                                text_parts = []
                                cumulative_pos = 0
                                
                                for page_idx in range(1, total_pages + 1):
                                    start_line = (page_idx - 1) * lines_per_page
                                    end_line = page_idx * lines_per_page if page_idx < total_pages else len(text_lines)
                                    page_text = '\n'.join(text_lines[start_line:end_line])
                                    
                                    if page_text.strip():
                                        # Add page marker
                                        page_marker = f"--- Page {page_idx} ---\n"
                                        page_text_with_marker = page_marker + page_text
                                        
                                        # Track character positions
                                        page_start = cumulative_pos
                                        page_end = cumulative_pos + len(page_text_with_marker)
                                        
                                        page_blocks.append({
                                            'page': page_idx,
                                            'text': page_text.strip(),
                                            'start_char': page_start,
                                            'end_char': page_end,
                                            'blocks': [{'text': page_text.strip(), 'page': page_idx}]
                                        })
                                        
                                        text_parts.append(page_text_with_marker)
                                        cumulative_pos = page_end
                                
                                # Rebuild text with page markers
                                text = "\n\n".join(text_parts)
                                logger.info(f"Docling: ✅ Added page markers to markdown text ({len(text):,} characters)")
                        except Exception as e2:
                            logger.error(f"Docling: Both export methods failed: export_to_text()={e1}, export_to_markdown()={e2}")
                            raise ValueError(f"Docling: Could not export document text. Both methods failed.")
            except Exception as e:
                logger.error(f"Docling: Error during text extraction: {str(e)}")
                # Try alternative export methods (prefer export_to_text first)
                text = None
                if hasattr(doc, 'export_to_text'):
                    try:
                        logger.info("Docling: Trying export_to_text as primary method...")
                        text = doc.export_to_text()
                        logger.info(f"Docling: Text export completed ({len(text) if text else 0:,} characters)")
                    except Exception as e2:
                        logger.error(f"Docling: Error exporting to text: {str(e2)}")
                        # Try markdown as fallback
                        if hasattr(doc, 'export_to_markdown'):
                            try:
                                logger.info("Docling: Trying export_to_markdown as fallback...")
                                text = doc.export_to_markdown()
                                logger.info(f"Docling: Markdown export completed ({len(text) if text else 0:,} characters)")
                            except Exception as e3:
                                logger.error(f"Docling: Error exporting to markdown: {str(e3)}")
                
                if not text or not text.strip():
                    raise ValueError(f"Docling: Could not export document text. Both export methods failed: {str(e)}")
            
            # Validate text extraction - try alternative methods if text is empty
            if not text or not text.strip():
                # Try export_to_text as primary fallback
                if hasattr(doc, 'export_to_text'):
                    try:
                        text = doc.export_to_text()
                        logger.info(f"Docling: Text validation: export_to_text() extracted {len(text):,} characters")
                    except:
                        pass
                
                # Try markdown as secondary fallback
                if (not text or not text.strip()) and hasattr(doc, 'export_to_markdown'):
                    try:
                        text = doc.export_to_markdown()
                        logger.info(f"Docling: Text validation: export_to_markdown() extracted {len(text):,} characters")
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
            pages = total_pages  # Use total_pages from extraction above
            if hasattr(doc, 'pages'):
                pages_dict = doc.pages
                if isinstance(pages_dict, dict):
                    pages = len(pages_dict)
                elif isinstance(pages_dict, list):
                    pages = len(pages_dict)
                # If total_pages was set during extraction, use it
                if total_pages > 0:
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
            
            # Verify OCR extracted text from images if images were detected
            # Note: images_detected will be set later, but we'll check it after detection
            
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
            
            # Check for images - use multiple detection methods
            images_detected = False
            image_count = 0
            detection_methods = []
            
            try:
                # Method 1: Check doc.pictures (existing method)
                if hasattr(doc, 'pictures') and len(doc.pictures) > 0:
                    images_detected = True
                    image_count = len(doc.pictures)
                    detection_methods.append(f"doc.pictures ({image_count} pictures)")
                    logger.info(f"Docling: Found {image_count} pictures in document")
                
                # Method 2: Check pages for image content
                if hasattr(doc, 'pages'):
                    pages_dict = doc.pages
                    if isinstance(pages_dict, (dict, list)):
                        page_images = 0
                        for page_content in (pages_dict.values() if isinstance(pages_dict, dict) else pages_dict):
                            # Check if page has image content
                            if hasattr(page_content, 'pictures') and len(page_content.pictures) > 0:
                                page_images += len(page_content.pictures)
                                images_detected = True
                            
                            # Check for image blocks in page structure
                            if hasattr(page_content, 'blocks'):
                                for block in page_content.blocks:
                                    if hasattr(block, 'type') and block.type in ['image', 'figure', 'picture', 'illustration']:
                                        page_images += 1
                                        images_detected = True
                                        break
                        
                        if page_images > 0:
                            image_count = max(image_count, page_images)
                            detection_methods.append(f"page content ({page_images} images)")
                
                # Method 3: Heuristic - if text is very low but file is large, likely image-based
                file_size_mb = os.path.getsize(actual_path) / 1024 / 1024 if os.path.exists(actual_path) else 0
                if not images_detected and text_length < 100 and file_size_mb > 0.5:
                    images_detected = True
                    detection_methods.append("heuristic (low text, large file)")
                    logger.info("Docling: Low text content suggests image-based PDF")
                
                if images_detected:
                    logger.info(f"Docling: ✅ Images detected via: {', '.join(detection_methods)}")
                else:
                    logger.info("Docling: No images detected in document")
                    
            except Exception as e:
                logger.warning(f"Docling: Error detecting images: {e}")
                # If we have very little text, assume images might be present
                if text_length < 100:
                    images_detected = True
                    logger.info("Docling: Assuming image-based PDF due to low text content")
            
            # Verify OCR extracted text from images if images were detected
            if images_detected:
                if text_length < 100:
                    logger.error("Docling: ❌ Images detected but very little text extracted - OCR may have failed!")
                    logger.error("Docling: Possible reasons:")
                    logger.error("   1. OCR models not downloaded (run: docling download-models)")
                    logger.error("   2. Images are too low quality for OCR")
                    logger.error("   3. OCR processing failed silently")
                    logger.error("   4. Document format not supported by OCR")
                    logger.error("Docling: 💡 Suggestion: Try using Textract parser for better OCR results")
                    logger.error("Docling: 💡 Or pre-process PDF with external OCR software")
                elif text_length < 500:
                    logger.warning("Docling: ⚠️  Images detected but limited text extracted")
                    logger.warning("Docling: OCR may have partially failed or images have low-quality text")
                else:
                    logger.info(f"Docling: ✅ OCR appears successful - extracted {text_length:,} characters from images")
            
            metadata = {
                "source": file_path,
                "pages": pages,
                "text_length": text_length,
                "word_count": word_count,
                "file_size": len(file_content) if file_content else os.path.getsize(file_path),
                "page_blocks": page_blocks,  # Store page-level blocks for citation support
                "image_count": image_count,  # Store image count for queries
                "images_detected": images_detected  # Store boolean flag
            }
            
            return ParsedDocument(
                text=text,
                metadata=metadata,
                pages=pages,
                images_detected=images_detected,
                parser_used=self.name,
                confidence=confidence,
                extraction_percentage=extraction_percentage,
                image_count=image_count
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
