"""
OCRmyPDF Parser with Tesseract OCR integration.
High-accuracy OCR for scanned PDFs and image-based documents.
"""
import os
import tempfile
import logging
from typing import Optional, Dict
from pathlib import Path
import subprocess
import shutil

from .base_parser import BaseParser, ParsedDocument
from scripts.setup_logging import get_logger

logger = get_logger("aris_rag.ocrmypdf_parser")


class OCRmyPDFParser(BaseParser):
    """
    Parser using OCRmyPDF + Tesseract for high-accuracy OCR.
    
    Features:
    - Automatic deskew and rotation correction
    - Noise removal for better accuracy
    - Text layer embedding in PDFs
    - Support for multiple languages
    - Optimized for scanned documents
    """
    
    def __init__(self, languages: str = "eng", dpi: int = 300):
        """
        Initialize OCRmyPDF parser.
        
        Args:
            languages: Tesseract language codes (e.g., 'eng', 'eng+spa', 'eng+fra')
            dpi: DPI for OCR processing (300+ recommended for best accuracy)
        """
        super().__init__("ocrmypdf")
        self.languages = languages
        self.dpi = dpi
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check if OCRmyPDF and Tesseract are installed."""
        # Check Tesseract
        tesseract_available = self._has_tesseract()
        if not tesseract_available:
            logger.warning(
                "Tesseract OCR not found. Install with: sudo apt-get install tesseract-ocr tesseract-ocr-eng"
            )
        
        # Check OCRmyPDF
        try:
            import ocrmypdf
            self.ocrmypdf_available = True
        except ImportError:
            logger.warning(
                "OCRmyPDF not found. Install with: pip install ocrmypdf"
            )
            self.ocrmypdf_available = False

    @staticmethod
    def _has_tesseract() -> bool:
        """Return True if tesseract is available, even if PATH is overridden."""
        if shutil.which("tesseract") is not None:
            return True
        return any(os.path.exists(p) and os.access(p, os.X_OK) for p in ("/usr/bin/tesseract", "/usr/local/bin/tesseract", "/bin/tesseract"))
    
    def is_available(self) -> bool:
        """Check if OCRmyPDF is available for use."""
        return self.ocrmypdf_available and self._has_tesseract()
    
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.lower().endswith('.pdf') and self.is_available()
    
    def parse(self, file_path: str, file_content: Optional[bytes] = None, 
              progress_callback: Optional[callable] = None) -> ParsedDocument:
        """
        Parse PDF using OCRmyPDF + Tesseract OCR.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
            progress_callback: Optional callback for progress updates
        
        Returns:
            ParsedDocument with OCR-extracted text
        
        Raises:
            ValueError: If OCR processing fails
        """
        if not self.is_available():
            raise ValueError(
                "OCRmyPDF or Tesseract not available. "
                "Install with: sudo apt-get install tesseract-ocr && pip install ocrmypdf"
            )
        
        if progress_callback:
            progress_callback("parsing", 0.0, detailed_message="Initializing OCRmyPDF + Tesseract...")
        
        logger.info(f"[OCRmyPDF] Starting OCR processing for: {file_path}")
        
        try:
            import ocrmypdf
            from PyPDF2 import PdfReader
            
            # Create temporary file for OCR output
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_output:
                output_path = temp_output.name
            
            try:
                # Prepare input file
                input_path = file_path
                if file_content:
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_input:
                        temp_input.write(file_content)
                        input_path = temp_input.name
                
                if progress_callback:
                    progress_callback("parsing", 0.1, detailed_message="Running OCR with deskew, clean, and rotate...")
                
                logger.info(f"[OCRmyPDF] Processing with languages={self.languages}, dpi={self.dpi}")
                
                # Run OCRmyPDF with optimal settings
                ocrmypdf.ocr(
                    input_file=input_path,
                    output_file=output_path,
                    deskew=True,              # Correct skewed pages
                    clean=True,               # Remove noise
                    rotate_pages=True,        # Fix rotated pages
                    skip_text=True,           # Skip pages with existing text (faster)
                    language=self.languages,  # Language support
                    output_type='pdf',        # Output as searchable PDF
                    optimize=1,               # Light optimization
                    force_ocr=False,          # Only OCR pages without text
                    progress_bar=False,       # Disable progress bar (we have our own)
                    tesseract_timeout=180.0,  # 3 minute timeout per page
                )
                
                if progress_callback:
                    progress_callback("parsing", 0.6, detailed_message="OCR complete, extracting text...")
                
                logger.info(f"[OCRmyPDF] OCR processing complete, extracting text from: {output_path}")
                
                # Extract text from OCR'd PDF using PyMuPDF for better extraction
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(output_path)
                    
                    text_parts = []
                    page_blocks = []  # Store page-level blocks for citation support
                    pages = len(doc)
                    images_detected = False
                    image_count = 0
                    cumulative_pos = 0
                    
                    for page_num in range(pages):
                        page = doc[page_num]
                        page_text = page.get_text()
                        actual_page_num = page_num + 1  # 1-indexed page number
                        
                        # Add page marker for consistency with other parsers
                        page_marker = f"--- Page {actual_page_num} ---\n"
                        page_text_with_marker = page_marker + page_text
                        page_start = cumulative_pos
                        page_end = cumulative_pos + len(page_text_with_marker)
                        
                        # Store page block metadata
                        page_blocks.append({
                            'type': 'page',
                            'page': actual_page_num,
                            'text': page_text,
                            'start_char': page_start,
                            'end_char': page_end,
                            'blocks': [{'text': page_text, 'page': actual_page_num}]
                        })
                        
                        text_parts.append(page_text_with_marker)
                        cumulative_pos = page_end + 2  # +2 for \n\n separator
                        
                        # Check for images
                        image_list = page.get_images()
                        if image_list:
                            images_detected = True
                            image_count += len(image_list)
                        
                        if progress_callback and pages > 0:
                            progress = 0.6 + (0.3 * (page_num + 1) / pages)
                            progress_callback("parsing", progress, 
                                            detailed_message=f"Extracting text from page {page_num + 1}/{pages}...")
                    
                    doc.close()
                    extracted_text = "\n\n".join(text_parts)
                    
                except ImportError:
                    # Fallback to PyPDF2 if PyMuPDF not available
                    logger.warning("[OCRmyPDF] PyMuPDF not available, using PyPDF2 (less accurate)")
                    reader = PdfReader(output_path)
                    pages = len(reader.pages)
                    
                    text_parts = []
                    page_blocks = []  # Store page-level blocks for citation support
                    images_detected = False
                    cumulative_pos = 0
                    
                    for page_num, page in enumerate(reader.pages):
                        page_text = page.extract_text()
                        actual_page_num = page_num + 1  # 1-indexed page number
                        
                        # Add page marker for consistency with other parsers
                        page_marker = f"--- Page {actual_page_num} ---\n"
                        page_text_with_marker = page_marker + page_text
                        page_start = cumulative_pos
                        page_end = cumulative_pos + len(page_text_with_marker)
                        
                        # Store page block metadata
                        page_blocks.append({
                            'type': 'page',
                            'page': actual_page_num,
                            'text': page_text,
                            'start_char': page_start,
                            'end_char': page_end,
                            'blocks': [{'text': page_text, 'page': actual_page_num}]
                        })
                        
                        text_parts.append(page_text_with_marker)
                        cumulative_pos = page_end + 2  # +2 for \n\n separator
                        
                        if progress_callback and pages > 0:
                            progress = 0.6 + (0.3 * (page_num + 1) / pages)
                            progress_callback("parsing", progress,
                                            detailed_message=f"Extracting text from page {page_num + 1}/{pages}...")
                    
                    extracted_text = "\n\n".join(text_parts)
                
                if progress_callback:
                    progress_callback("parsing", 0.95, detailed_message="Finalizing OCR results...")
                
                # Calculate extraction metrics
                char_count = len(extracted_text.strip())
                extraction_percentage = min(1.0, char_count / (pages * 500)) if pages > 0 else 0.0
                confidence = 0.95 if char_count > 100 else 0.7
                
                logger.info(
                    f"[OCRmyPDF] Extraction complete: {pages} pages, "
                    f"{char_count:,} characters, {image_count} images"
                )
                
                if progress_callback:
                    progress_callback("parsing", 1.0, detailed_message="OCR processing complete!")
                
                return ParsedDocument(
                    text=extracted_text,
                    metadata={
                        "source": os.path.basename(file_path),
                        "parser": "ocrmypdf",
                        "ocr_languages": self.languages,
                        "ocr_dpi": self.dpi,
                        "pages": pages,  # Use 'pages' for consistency
                        "total_pages": pages,
                        "character_count": char_count,
                        "image_count": image_count,
                        "page_blocks": page_blocks  # Store page-level blocks for citation support
                    },
                    pages=pages,
                    images_detected=images_detected,
                    parser_used="ocrmypdf",
                    confidence=confidence,
                    extraction_percentage=extraction_percentage,
                    image_count=image_count
                )
            
            finally:
                # Cleanup temporary files
                if os.path.exists(output_path):
                    os.unlink(output_path)
                if file_content and os.path.exists(input_path) and input_path != file_path:
                    os.unlink(input_path)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[OCRmyPDF] OCR processing failed: {error_msg}", exc_info=True)
            
            if progress_callback:
                progress_callback("failed", 0.0, detailed_message=f"OCR failed: {error_msg}")
            
            raise ValueError(f"OCRmyPDF processing failed: {error_msg}")
    
    def preprocess_pdf(self, input_path: str, output_path: str, 
                       force_ocr: bool = False) -> str:
        """
        Preprocess a PDF with OCR and return path to processed file.
        
        This can be used as a preprocessing step before other parsers.
        
        Args:
            input_path: Path to input PDF
            output_path: Path for output OCR'd PDF
            force_ocr: Force OCR on all pages (even those with text)
        
        Returns:
            Path to OCR'd PDF
        
        Raises:
            ValueError: If preprocessing fails
        """
        if not self.is_available():
            raise ValueError("OCRmyPDF not available")
        
        try:
            import ocrmypdf
            
            logger.info(f"[OCRmyPDF] Preprocessing PDF: {input_path} -> {output_path}")
            
            ocrmypdf.ocr(
                input_file=input_path,
                output_file=output_path,
                deskew=True,
                clean=True,
                rotate_pages=True,
                skip_text=not force_ocr,
                language=self.languages,
                output_type='pdf',
                optimize=1,
                force_ocr=force_ocr,
                progress_bar=False,
                tesseract_timeout=180.0
            )
            
            logger.info(f"[OCRmyPDF] Preprocessing complete: {output_path}")
            return output_path
        
        except Exception as e:
            logger.error(f"[OCRmyPDF] Preprocessing failed: {e}", exc_info=True)
            raise ValueError(f"OCRmyPDF preprocessing failed: {str(e)}")
