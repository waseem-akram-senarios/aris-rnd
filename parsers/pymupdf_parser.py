"""
PyMuPDF (fitz) parser for PDF documents.
Fast and efficient parser for text-based PDFs.
"""
import os
import logging
import time
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from .base_parser import BaseParser, ParsedDocument

logger = logging.getLogger(__name__)


class PyMuPDFParser(BaseParser):
    """Parser using PyMuPDF (fitz) library."""
    
    def __init__(self):
        super().__init__("pymupdf")
        try:
            import fitz  # PyMuPDF
            self.fitz = fitz
        except ImportError:
            raise ImportError(
                "PyMuPDF (pymupdf) is not installed. "
                "Install it with: pip install pymupdf"
            )
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle PDF files."""
        _, ext = os.path.splitext(file_path.lower())
        return ext == '.pdf'
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None, progress_callback: Optional[Callable[[str, float], None]] = None) -> ParsedDocument:
        """
        Parse PDF using PyMuPDF with timeout protection and progress updates.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
            progress_callback: Optional callback(status_message, progress) for UI updates
        
        Returns:
            ParsedDocument with extracted text and metadata
        """
        file_name = os.path.basename(file_path)
        file_size = len(file_content) if file_content else (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        
        logger.info(f"PyMuPDF: Starting parsing of {file_name} ({file_size/1024/1024:.2f} MB)")
        
        if progress_callback:
            progress_callback("🔍 Opening PDF document...", 0.0)
        
        def run_pymupdf_parsing():
            """Run PyMuPDF parsing in thread with timeout protection and progress updates."""
            try:
                # Open PDF
                if progress_callback:
                    progress_callback("📄 Opening PDF file...", 0.05)
                
                try:
                    if file_content:
                        doc = self.fitz.open(stream=file_content, filetype="pdf")
                    else:
                        doc = self.fitz.open(file_path)
                except Exception as open_error:
                    error_str = str(open_error) if str(open_error) else type(open_error).__name__
                    logger.error(f"PyMuPDF: Failed to open PDF: {error_str}")
                    if progress_callback:
                        progress_callback(f"❌ Cannot open PDF: {error_str[:50]}...", 1.0)
                    raise ValueError(f"Cannot open PDF file: {error_str}. The file may be corrupted, encrypted, or in an unsupported format.")
                
                if len(doc) == 0:
                    doc.close()
                    if progress_callback:
                        progress_callback("⚠️ PDF is empty", 1.0)
                    return ParsedDocument(
                        text="",
                        metadata={"source": file_path, "pages": 0},
                        pages=0,
                        images_detected=False,
                        parser_used=self.name,
                        confidence=0.0,
                        extraction_percentage=0.0
                    )
                
                # Extract text from all pages with page-level metadata
                text_parts = []
                pages_with_text = 0
                total_images = 0
                images_detected = False
                page_blocks = []  # Store page-level text blocks with metadata
                
                # Get total pages before processing
                total_pages = len(doc)
                logger.info(f"PyMuPDF: Processing {total_pages} pages...")
                
                if progress_callback:
                    progress_callback(f"📖 Found {total_pages} pages. Starting extraction...", 0.1)
                
                # Process pages with timeout protection per page
                start_time = time.time()
                last_progress_update = 0
                
                for page_num in range(total_pages):
                    # Check for timeout every page
                    elapsed = time.time() - start_time
                    if elapsed > 580:  # Warn at 9m 40s (20s before timeout)
                        error_msg = f"PyMuPDF parsing is taking too long ({elapsed:.0f}s). This may indicate a problematic PDF."
                        logger.warning(error_msg)
                        if progress_callback:
                            progress_callback(f"⚠️ Processing is slow ({elapsed:.0f}s elapsed)...", page_num / total_pages)
                    
                    # Update progress every page or every 5 seconds
                    current_time = time.time()
                    if progress_callback and (page_num == 0 or (page_num + 1) % 5 == 0 or (current_time - last_progress_update) >= 2.0):
                        progress = 0.1 + (page_num / total_pages) * 0.85  # 10% to 95%
                        status_msg = f"📄 Processing page {page_num + 1}/{total_pages}..."
                        progress_callback(status_msg, progress)
                        last_progress_update = current_time
                        logger.info(f"PyMuPDF: Processing page {page_num + 1}/{total_pages}...")
                    
                    try:
                        page = doc[page_num]
                        
                        # Extract text blocks with bounding boxes for citation support
                        try:
                            # Get text blocks with positions
                            text_dict = page.get_text("dict")
                            page_text = page.get_text()
                            
                            if page_text.strip():
                                # Store page-level blocks with metadata
                                page_blocks_data = {
                                    'page': page_num + 1,
                                    'text': page_text,
                                    'blocks': []
                                }
                                
                                # Extract text blocks with bounding boxes
                                if 'blocks' in text_dict:
                                    for block in text_dict['blocks']:
                                        if 'lines' in block:
                                            block_text_parts = []
                                            block_bbox = None
                                            for line in block['lines']:
                                                if 'spans' in line:
                                                    line_text_parts = []
                                                    for span in line['spans']:
                                                        if 'text' in span:
                                                            line_text_parts.append(span['text'])
                                                        if 'bbox' in span and block_bbox is None:
                                                            block_bbox = span['bbox']
                                                    if line_text_parts:
                                                        block_text_parts.append(' '.join(line_text_parts))
                                                
                                                # Use line bbox if block bbox not available
                                                if 'bbox' in line and block_bbox is None:
                                                    block_bbox = line['bbox']
                                            
                                            if block_text_parts:
                                                block_text = ' '.join(block_text_parts)
                                                page_blocks_data['blocks'].append({
                                                    'text': block_text,
                                                    'bbox': block_bbox,
                                                    'page': page_num + 1
                                                })
                                
                                page_blocks.append(page_blocks_data)
                                text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                                pages_with_text += 1
                        except Exception as e:
                            logger.warning(f"PyMuPDF: Failed to extract text from page {page_num + 1}: {str(e)[:100]}")
                            # Continue with next page
                        
                        # Check for images (with timeout protection)
                        try:
                            image_list = page.get_images()
                            if image_list:
                                total_images += len(image_list)
                                images_detected = True
                                # Store image metadata for citation
                                for img_idx, img_info in enumerate(image_list):
                                    try:
                                        # Get image bounding box if available
                                        img_rects = page.get_image_rects(img_info[7])  # xref number
                                        if img_rects:
                                            for rect in img_rects:
                                                page_blocks.append({
                                                    'page': page_num + 1,
                                                    'type': 'image',
                                                    'image_index': img_idx,
                                                    'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                                                    'xref': img_info[7]
                                                })
                                    except Exception:
                                        pass  # Skip if image metadata extraction fails
                        except Exception as e:
                            logger.warning(f"PyMuPDF: Failed to get images from page {page_num + 1}: {str(e)[:100]}")
                            # Continue with next page
                    
                    except Exception as e:
                        logger.warning(f"PyMuPDF: Error processing page {page_num + 1}: {str(e)[:100]}")
                        # Continue with next page
                
                # Combine all text before closing
                if progress_callback:
                    progress_callback("📝 Combining extracted text...", 0.95)
                
                full_text = "\n\n".join(text_parts)
                
                # Calculate extraction percentage
                extraction_percentage = pages_with_text / total_pages if total_pages > 0 else 0.0
                
                # Close document
                doc.close()
                
                logger.info(f"PyMuPDF: Parsing completed - {pages_with_text}/{total_pages} pages with text")
                
                if progress_callback:
                    progress_callback(f"✅ Completed! Extracted {pages_with_text}/{total_pages} pages", 1.0)
                
                # Calculate confidence based on extraction percentage and text length
                if extraction_percentage >= 0.8 and len(full_text.strip()) > 100:
                    confidence = 1.0
                elif extraction_percentage >= 0.5:
                    confidence = 0.8
                elif extraction_percentage >= 0.3:
                    confidence = 0.6
                else:
                    confidence = 0.4
                
                # Metadata with page-level blocks for citation support
                metadata = {
                    "source": file_path,
                    "pages": total_pages,
                    "images_count": total_images,
                    "pages_with_text": pages_with_text,
                    "file_size": file_size,
                    "page_blocks": page_blocks  # Store page-level text blocks with bboxes
                }
                
                return ParsedDocument(
                    text=full_text,
                    metadata=metadata,
                    pages=total_pages,
                    images_detected=images_detected,
                    parser_used=self.name,
                    confidence=confidence,
                    extraction_percentage=extraction_percentage
                )
                
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                error_msg = str(e) if str(e) else type(e).__name__
                logger.error(f"PyMuPDF: Error in parsing thread: {error_msg}")
                logger.error(f"PyMuPDF: Traceback:\n{error_details}")
                raise
        
        # Use ThreadPoolExecutor with timeout (5 minutes max for PyMuPDF)
        # PyMuPDF should be fast, but some PDFs can hang
        # Some PDFs may cause NoSessionContext errors in threads, so we'll try threaded first, then fallback to direct
        timeout_seconds = 300  # 5 minutes timeout (reduced from 10 minutes)
        try:
            if progress_callback:
                progress_callback(f"⏳ Starting PyMuPDF parsing (max {timeout_seconds//60} minutes)...", 0.0)
            
            logger.info(f"PyMuPDF: Processing in background thread (timeout: {timeout_seconds}s)...")
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_pymupdf_parsing)
                
                # Monitor progress and update UI periodically
                while not future.done():
                    elapsed = time.time() - start_time
                    if elapsed >= timeout_seconds:
                        future.cancel()
                        error_msg = f"PyMuPDF parsing timed out after {timeout_seconds} seconds for {file_name}"
                        logger.error(error_msg)
                        if progress_callback:
                            progress_callback(f"❌ Timeout after {timeout_seconds//60} minutes", 1.0)
                        raise ValueError(error_msg)
                    
                    # Update progress every 5 seconds
                    if progress_callback and int(elapsed) % 5 == 0 and elapsed > 0:
                        minutes, seconds = divmod(int(elapsed), 60)
                        progress = min(0.9, elapsed / timeout_seconds * 0.8)  # 0-80% based on elapsed time
                        progress_callback(f"⏳ Processing... ({minutes}m {seconds}s elapsed)", progress)
                    
                    time.sleep(0.5)  # Check every 0.5 seconds
                
                result = future.result(timeout=1)  # Should be immediate since future is done
                logger.info(f"PyMuPDF: Parsing completed successfully in {time.time() - start_time:.2f}s")
                return result
                
        except FutureTimeoutError:
            error_msg = f"PyMuPDF parsing timed out after {timeout_seconds} seconds for {file_name}"
            logger.error(error_msg)
            if progress_callback:
                progress_callback(f"❌ Timeout after {timeout_seconds//60} minutes", 1.0)
            raise ValueError(
                f"PyMuPDF parsing timed out after {timeout_seconds} seconds. "
                f"The PDF may be very complex or corrupted. "
                f"Try using Docling parser for better handling of complex PDFs."
            )
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            
            # Get error message - handle empty messages
            error_str = str(e) if str(e) else type(e).__name__
            if not error_str or error_str.strip() == "":
                error_str = f"Unknown error ({type(e).__name__})"
            
            # Check for NoSessionContext error - this is a threading issue with PyMuPDF
            if "NoSessionContext" in error_str or "NoSessionContext" in type(e).__name__:
                logger.warning(f"PyMuPDF: NoSessionContext error detected - trying direct (non-threaded) parsing as fallback...")
                if progress_callback:
                    progress_callback("🔄 Retrying with direct parsing (no threading)...", 0.1)
                
                # Try parsing directly without threading (fallback)
                try:
                    logger.info(f"PyMuPDF: Attempting direct parsing (no threading) for {file_name}")
                    result = run_pymupdf_parsing()  # Call directly without thread
                    logger.info(f"PyMuPDF: Direct parsing succeeded!")
                    return result
                except Exception as direct_error:
                    direct_error_str = str(direct_error) if str(direct_error) else type(direct_error).__name__
                    logger.error(f"PyMuPDF: Direct parsing also failed: {direct_error_str}")
                    error_msg = (
                        f"PyMuPDF cannot process this PDF due to threading context issues (NoSessionContext). "
                        f"This PDF may have a structure that PyMuPDF cannot handle in a threaded environment. "
                        f"Please try using the Docling parser instead - it handles complex PDFs better."
                    )
                    if progress_callback:
                        progress_callback("❌ PyMuPDF cannot process this PDF - try Docling parser", 1.0)
                    raise ValueError(error_msg)
            
            # Log full error details
            logger.error(f"PyMuPDF: Failed to parse PDF: {error_str}")
            logger.error(f"PyMuPDF: Full traceback:\n{error_details}")
            
            # Create user-friendly error message
            if "cannot open" in error_str.lower() or ("file" in error_str.lower() and "not found" in error_str.lower()):
                error_msg = f"PyMuPDF cannot open the PDF file. The file may be corrupted, encrypted, or in an unsupported format. Error: {error_str}"
            elif "password" in error_str.lower() or "encrypted" in error_str.lower():
                error_msg = f"PDF is password-protected or encrypted. PyMuPDF cannot process encrypted PDFs. Error: {error_str}"
            elif "timeout" in error_str.lower():
                error_msg = f"PyMuPDF parsing timed out. The PDF may be very complex or corrupted. Error: {error_str}"
            else:
                error_msg = f"Failed to parse PDF with PyMuPDF: {error_str}. The PDF may be corrupted, encrypted, or in an unsupported format. Try using Docling parser for better compatibility."
            
            if progress_callback:
                progress_callback(f"❌ Error: {error_str[:50]}...", 1.0)
            
            raise ValueError(error_msg)

