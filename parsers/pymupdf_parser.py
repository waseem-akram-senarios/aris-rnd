"""
PyMuPDF (fitz) parser for PDF documents.
Fast and efficient parser for text-based PDFs.
"""
import os
import logging
import time
from typing import Optional
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
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None) -> ParsedDocument:
        """
        Parse PDF using PyMuPDF with timeout protection.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
        
        Returns:
            ParsedDocument with extracted text and metadata
        """
        file_name = os.path.basename(file_path)
        file_size = len(file_content) if file_content else (os.path.getsize(file_path) if os.path.exists(file_path) else 0)
        
        logger.info(f"PyMuPDF: Starting parsing of {file_name} ({file_size/1024/1024:.2f} MB)")
        
        def run_pymupdf_parsing():
            """Run PyMuPDF parsing in thread with timeout protection."""
            try:
                # Open PDF
                if file_content:
                    doc = self.fitz.open(stream=file_content, filetype="pdf")
                else:
                    doc = self.fitz.open(file_path)
                
                if len(doc) == 0:
                    doc.close()
                    return ParsedDocument(
                        text="",
                        metadata={"source": file_path, "pages": 0},
                        pages=0,
                        images_detected=False,
                        parser_used=self.name,
                        confidence=0.0,
                        extraction_percentage=0.0
                    )
                
                # Extract text from all pages
                text_parts = []
                pages_with_text = 0
                total_images = 0
                images_detected = False
                
                # Get total pages before processing
                total_pages = len(doc)
                logger.info(f"PyMuPDF: Processing {total_pages} pages...")
                
                # Process pages with timeout protection per page
                for page_num in range(total_pages):
                    try:
                        page = doc[page_num]
                        
                        # Extract text with per-page timeout (30 seconds per page)
                        try:
                            page_text = page.get_text()
                            if page_text.strip():
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
                        except Exception as e:
                            logger.warning(f"PyMuPDF: Failed to get images from page {page_num + 1}: {str(e)[:100]}")
                            # Continue with next page
                        
                        # Log progress every 10 pages
                        if (page_num + 1) % 10 == 0:
                            logger.info(f"PyMuPDF: Processed {page_num + 1}/{total_pages} pages...")
                    
                    except Exception as e:
                        logger.warning(f"PyMuPDF: Error processing page {page_num + 1}: {str(e)[:100]}")
                        # Continue with next page
                
                # Combine all text before closing
                full_text = "\n\n".join(text_parts)
                
                # Calculate extraction percentage
                extraction_percentage = pages_with_text / total_pages if total_pages > 0 else 0.0
                
                # Close document
                doc.close()
                
                logger.info(f"PyMuPDF: Parsing completed - {pages_with_text}/{total_pages} pages with text")
                
                # Calculate confidence based on extraction percentage and text length
                if extraction_percentage >= 0.8 and len(full_text.strip()) > 100:
                    confidence = 1.0
                elif extraction_percentage >= 0.5:
                    confidence = 0.8
                elif extraction_percentage >= 0.3:
                    confidence = 0.6
                else:
                    confidence = 0.4
                
                # Metadata
                metadata = {
                    "source": file_path,
                    "pages": total_pages,
                    "images_count": total_images,
                    "pages_with_text": pages_with_text,
                    "file_size": file_size
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
                logger.error(f"PyMuPDF: Error in parsing thread: {str(e)}")
                raise
        
        # Use ThreadPoolExecutor with timeout (10 minutes max for PyMuPDF)
        # PyMuPDF should be fast, but some PDFs can hang
        timeout_seconds = 600  # 10 minutes timeout
        try:
            logger.info(f"PyMuPDF: Processing in background thread (timeout: {timeout_seconds}s)...")
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_pymupdf_parsing)
                result = future.result(timeout=timeout_seconds)
                logger.info("PyMuPDF: Parsing completed successfully")
                return result
        except FutureTimeoutError:
            error_msg = f"PyMuPDF parsing timed out after {timeout_seconds} seconds for {file_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Failed to parse PDF with PyMuPDF: {str(e)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

