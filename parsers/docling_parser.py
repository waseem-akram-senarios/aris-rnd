"""
Docling parser using the simple quickstart pattern from documentation.
Uses ThreadPoolExecutor to prevent UI blocking during long processing.
"""
import os
import logging
from typing import Optional
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
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None) -> ParsedDocument:
        """
        Parse PDF using Docling - simple quickstart pattern.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
        
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
            logger.info(f"Docling: Starting conversion of {os.path.basename(actual_path)} ({file_size/1024/1024:.2f} MB)")
            
            # Run Docling conversion in a separate thread to prevent UI blocking
            # Docling can take 5-10 minutes for large PDFs
            def run_docling_conversion():
                """Run Docling conversion in thread."""
                try:
                    logger.info("Docling: Initializing DocumentConverter...")
                    converter = self.DocumentConverter()
                    logger.info("Docling: Starting document conversion (this may take 5-10 minutes)...")
                    logger.info(f"Docling: Converting file: {os.path.basename(actual_path)}")
                    result = converter.convert(actual_path, raises_on_error=False)
                    logger.info("Docling: Conversion completed, accessing document...")
                    doc = result.document
                    logger.info(f"Docling: Document accessed successfully, pages: {len(doc.pages) if hasattr(doc, 'pages') else 'unknown'}")
                    return doc
                except Exception as e:
                    logger.error(f"Docling: Error in conversion thread: {str(e)}")
                    raise
            
            # Use ThreadPoolExecutor with a very long timeout (20 minutes) for Docling
            # Docling processes all pages which can take a long time, especially for scanned PDFs with OCR
            timeout_seconds = 1200  # 20 minutes timeout (increased for OCR processing)
            try:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(run_docling_conversion)
                    logger.info(f"Docling: Processing in background thread (timeout: {timeout_seconds}s)...")
                    logger.info(f"Docling: This may take 5-20 minutes for scanned PDFs with OCR...")
                    
                    # Wait for result with periodic progress logging
                    import time as time_module
                    import threading
                    
                    start_time = time_module.time()
                    progress_logging_active = threading.Event()
                    progress_logging_active.set()
                    
                    def log_progress():
                        """Log progress every minute while processing."""
                        check_interval = 60  # Log every minute
                        last_log_time = start_time
                        while progress_logging_active.is_set():
                            time_module.sleep(check_interval)
                            if not progress_logging_active.is_set():
                                break
                            elapsed = time_module.time() - start_time
                            if elapsed >= timeout_seconds:
                                break
                            minutes = int(elapsed // 60)
                            seconds = int(elapsed % 60)
                            logger.info(f"Docling: Still processing... ({minutes}m {seconds}s elapsed, max {timeout_seconds//60}m)")
                            last_log_time = elapsed
                    
                    # Start progress logging thread
                    progress_thread = threading.Thread(target=log_progress, daemon=True)
                    progress_thread.start()
                    
                    try:
                        # Wait for result with timeout
                        logger.info(f"Docling: Waiting for conversion result (max {timeout_seconds//60} minutes)...")
                        doc = future.result(timeout=timeout_seconds)
                        progress_logging_active.clear()
                        logger.info("Docling: Document conversion successful - result received")
                        if doc is None:
                            raise ValueError("Docling conversion returned None - conversion may have failed")
                        logger.info(f"Docling: Document object received, type: {type(doc)}")
                    except Exception as e:
                        progress_logging_active.clear()
                        logger.error(f"Docling: Error waiting for result: {str(e)}")
                        raise
                    finally:
                        progress_logging_active.clear()
            except FutureTimeoutError:
                logger.error(f"Docling: Conversion timed out after {timeout_seconds} seconds")
                raise ValueError(
                    f"Docling conversion timed out after {timeout_seconds} seconds. "
                    f"The document may be too large or complex. "
                    f"Try using PyMuPDF parser for faster processing."
                )
            except Exception as e:
                logger.error(f"Docling: Conversion failed: {str(e)}")
                raise
            
            # Export to markdown (as shown in quickstart)
            logger.info("Docling: Exporting document to markdown...")
            try:
                text = doc.export_to_markdown()
                logger.info(f"Docling: Markdown export completed ({len(text):,} characters)")
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
            
            # Get page count
            pages = 0
            if hasattr(doc, 'pages'):
                pages_dict = doc.pages
                if isinstance(pages_dict, dict):
                    pages = len(pages_dict)
                elif isinstance(pages_dict, list):
                    pages = len(pages_dict)
            
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
                "file_size": len(file_content) if file_content else os.path.getsize(file_path)
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
            # Clean up temp file on error
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
            raise ValueError(f"Failed to parse PDF with Docling: {str(e)}")
