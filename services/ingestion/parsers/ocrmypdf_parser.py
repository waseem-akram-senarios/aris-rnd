"""
OCRmyPDF Parser with Tesseract OCR integration.
High-accuracy OCR for scanned PDFs and image-based documents.
Supports multilingual OCR with script-specific optimizations.
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
logger = logging.getLogger(__name__)

class OCRmyPDFParser(BaseParser):
    """
    Parser using OCRmyPDF + Tesseract for high-accuracy OCR.
    
    Features:
    - Automatic deskew and rotation correction
    - Noise removal for better accuracy
    - Text layer embedding in PDFs
    - Support for multiple languages including CJK and Cyrillic
    - Optimized settings for different script types
    - Script-specific DPI and preprocessing
    """
    
    def __init__(self, languages: str = "eng", dpi: Optional[int] = None, auto_optimize: bool = True):
        """
        Initialize OCRmyPDF parser.
        
        Args:
            languages: Tesseract language codes (e.g., 'eng', 'eng+spa', 'chi_sim+eng')
            dpi: DPI for OCR processing (auto-optimized by default based on script type)
            auto_optimize: If True, automatically optimize DPI for script type
        """
        super().__init__("ocrmypdf")
        self.auto_optimize = auto_optimize
        
        # Get optimized OCR parameters based on language
        self._optimize_for_language(languages, dpi)
        self._check_dependencies()
        
        # Log the final language configuration
        logger.info(f"[OCRmyPDF] Initialized with languages={self.languages}, dpi={self.dpi}")
    
    def _optimize_for_language(self, languages: str, dpi: Optional[int] = None):
        """
        Optimize OCR parameters based on language/script type.
        
        Args:
            languages: Tesseract language codes
            dpi: Optional explicit DPI override
        """
        try:
            from services.language.detector import get_detector, get_ocr_params
            detector = get_detector()
            
            # Get the primary language from the languages string
            primary_lang = languages.split('+')[0] if '+' in languages else languages
            
            # Get optimized parameters for this language
            ocr_params = detector.get_ocr_params(primary_lang)
            
            # Set DPI (use provided or optimized)
            self.dpi = dpi if dpi is not None else ocr_params.get("dpi", 300)
            
            # Store script info for later use
            self.script_type = detector.get_script_type(primary_lang)
            self.is_cjk = detector.is_cjk_language(primary_lang)
            self.is_rtl = detector.is_rtl_language(primary_lang)
            self.preprocessing = ocr_params.get("preprocessing", "standard")
            
            # Convert language code to Tesseract format if needed
            self.languages = self._normalize_tesseract_languages(languages, detector)
            
            logger.info(
                f"[OCRmyPDF] Optimized for language={self.languages}, "
                f"script={self.script_type}, dpi={self.dpi}, is_cjk={self.is_cjk}"
            )
            
        except ImportError:
            # Fallback if language detector not available
            self.languages = languages
            self.dpi = dpi if dpi is not None else 300
            self.script_type = "latin"
            self.is_cjk = False
            self.is_rtl = False
            self.preprocessing = "standard"
            logger.warning("[OCRmyPDF] Language detector not available, using defaults")
    
    def _normalize_tesseract_languages(self, languages: str, detector) -> str:
        """
        Normalize language codes to Tesseract format.
        
        Args:
            languages: Input language string (e.g., 'eng', 'es', 'zh-cn')
            detector: LanguageDetector instance
            
        Returns:
            Tesseract-compatible language string (e.g., 'eng', 'spa', 'chi_sim')
        """
        if '+' in languages:
            # Multiple languages
            parts = languages.split('+')
            tesseract_parts = [detector.get_ocr_language(p.strip()) for p in parts]
            return '+'.join(tesseract_parts)
        else:
            return detector.get_ocr_language(languages)
    
    def _check_dependencies(self):
        """Check if OCRmyPDF and Tesseract are installed."""
        # Check Tesseract
        tesseract_available = self._has_tesseract()
        if not tesseract_available:
            logger.warning(
                "Tesseract OCR not found. Install with: sudo apt-get install tesseract-ocr tesseract-ocr-eng"
            )
        else:
            # Check if required language packs are installed
            self._check_tesseract_languages()
        
        # Check OCRmyPDF
        try:
            import ocrmypdf
            self.ocrmypdf_available = True
        except ImportError:
            logger.warning("OCRmyPDF not found. Install with: pip install ocrmypdf")
            self.ocrmypdf_available = False
        except Exception as e:
            logger.warning(f"OCRmyPDF import failed (missing system dependencies?): {e}")
            self.ocrmypdf_available = False
    
    def _check_tesseract_languages(self):
        """Check if required Tesseract language packs are installed."""
        try:
            import subprocess
            # Get list of installed Tesseract languages
            result = subprocess.run(
                ['tesseract', '--list-langs'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                installed_langs = set(result.stdout.strip().split('\n')[1:])  # Skip first line "List of available languages"
                logger.info(f"Tesseract installed languages: {sorted(installed_langs)}")
                
                # Check if required languages are installed
                required_langs = set()
                if hasattr(self, 'languages'):
                    # Parse language string (e.g., "spa+eng" -> ["spa", "eng"])
                    for lang in self.languages.split('+'):
                        required_langs.add(lang.strip())
                
                missing_langs = required_langs - installed_langs
                if missing_langs:
                    logger.warning(
                        f"⚠️ Tesseract language packs missing: {missing_langs}. "
                        f"Install with: sudo apt-get install {' '.join([f'tesseract-ocr-{lang}' for lang in missing_langs])}"
                    )
                    # For Spanish, provide specific installation command
                    if 'spa' in missing_langs:
                        logger.warning(
                            "⚠️ Spanish language pack not installed. "
                            "Install with: sudo apt-get install tesseract-ocr-spa"
                        )
                else:
                    logger.info(f"✅ All required Tesseract language packs installed: {required_langs}")
            else:
                logger.warning("Could not check Tesseract language packs (tesseract --list-langs failed)")
        except FileNotFoundError:
            logger.warning("Tesseract not found in PATH, cannot check language packs")
        except subprocess.TimeoutExpired:
            logger.warning("Tesseract language check timed out")
        except Exception as e:
            logger.warning(f"Could not check Tesseract language packs: {e}")

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
                
                logger.info(
                    f"[OCRmyPDF] Processing with languages={self.languages}, "
                    f"dpi={self.dpi}, script={getattr(self, 'script_type', 'unknown')}"
                )
                
                # Validate language string format for Tesseract
                # Tesseract expects format like "eng", "spa", "eng+spa", etc.
                validated_languages = self.languages
                if not validated_languages or validated_languages.strip() == "":
                    logger.warning("[OCRmyPDF] Empty language string, defaulting to 'eng'")
                    validated_languages = "eng"
                
                # Log language configuration for debugging
                logger.info(f"[OCRmyPDF] Using Tesseract languages: {validated_languages}")
                
                # Build OCR options based on script type
                # OPTIMIZED FOR MAXIMUM ACCURACY
                ocr_kwargs = {
                    "input_file": input_path,
                    "output_file": output_path,
                    "deskew": True,              # Correct skewed pages for better OCR
                    "clean": True,               # Remove noise/artifacts
                    "rotate_pages": True,        # Auto-correct page rotation
                    "rotate_pages_threshold": 2.0,  # Lower threshold = more sensitive rotation detection
                    "skip_text": False,          # DON'T skip - process ALL pages for max accuracy
                    "language": validated_languages,  # Language support (validated)
                    "output_type": "pdf",        # Output as searchable PDF
                    "optimize": 0,               # No optimization - preserve quality
                    "force_ocr": True,           # Force OCR on ALL pages for maximum accuracy
                    # Note: redo_ocr is incompatible with deskew, so we use force_ocr instead
                    "progress_bar": False,       # Disable progress bar (we have our own)
                    "tesseract_timeout": 300.0,  # 5 minute timeout per page (increased for accuracy)
                }
                
                # Add image-dpi for better quality with CJK/complex scripts
                if hasattr(self, 'dpi') and self.dpi:
                    ocr_kwargs["image_dpi"] = self.dpi
                
                # CJK-specific optimizations
                if getattr(self, 'is_cjk', False):
                    logger.info("[OCRmyPDF] Applying CJK-specific optimizations (higher quality)")
                    # Higher quality for complex characters
                    ocr_kwargs["oversample"] = 2  # 2x oversampling for better stroke detection
                    ocr_kwargs["remove_background"] = True  # Better contrast for CJK
                
                # RTL-specific handling
                if getattr(self, 'is_rtl', False):
                    logger.info("[OCRmyPDF] RTL document detected")
                    # RTL languages don't need special OCRmyPDF flags, but we log it
                
                # Run OCRmyPDF with optimized settings
                try:
                    ocrmypdf.ocr(**ocr_kwargs)
                except ocrmypdf.exceptions.TesseractConfigError as e:
                    # Handle missing language pack error
                    error_msg = str(e)
                    if "language" in error_msg.lower() or "spa" in error_msg.lower() or "eng" in error_msg.lower():
                        logger.error(f"[OCRmyPDF] Tesseract language pack error: {error_msg}")
                        logger.error(f"[OCRmyPDF] Attempted to use languages: {validated_languages}")
                        logger.error(f"[OCRmyPDF] Install missing language packs with: sudo apt-get install tesseract-ocr-{validated_languages.split('+')[0]}")
                        raise ValueError(
                            f"Tesseract language pack not installed for '{validated_languages}'. "
                            f"Install with: sudo apt-get install {' '.join([f'tesseract-ocr-{lang}' for lang in validated_languages.split('+')])}"
                        )
                    else:
                        raise
                
                if progress_callback:
                    progress_callback("parsing", 0.6, detailed_message="OCR complete, extracting text...")
                
                logger.info(f"[OCRmyPDF] OCR processing complete, extracting text from: {output_path}")
                
                # Extract text from OCR'd PDF using PyMuPDF for better extraction
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(output_path)
                    
                    text_parts = []
                    page_blocks = []  # Store page-level blocks for citation support
                    extracted_images = []  # Store extracted images for OpenSearch
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
                        cumulative_pos = page_end + 1  # +1 for \n separator (consistent with PyMuPDF)
                        
                        # Check for images
                        image_list = page.get_images()
                        if image_list:
                            images_detected = True
                            image_count += len(image_list)
                            
                            # Add to extracted_images list with OCR extraction
                            for img_idx, img_info in enumerate(image_list):
                                try:
                                    xref = img_info[0]
                                    
                                    # Extract image and perform OCR on it
                                    ocr_text = ""
                                    try:
                                        # Extract image bytes from PDF
                                        base_image = doc.extract_image(xref)
                                        if base_image:
                                            image_bytes = base_image.get("image")
                                            if image_bytes:
                                                # Save to temp file and run Tesseract OCR
                                                import io
                                                from PIL import Image
                                                import pytesseract
                                                
                                                # Convert to PIL Image
                                                img = Image.open(io.BytesIO(image_bytes))
                                                # Run OCR with Tesseract
                                                ocr_text = pytesseract.image_to_string(
                                                    img,
                                                    lang=self.languages.replace('+', '+') if hasattr(self, 'languages') else 'eng'
                                                ).strip()
                                                logger.debug(f"OCR extracted {len(ocr_text)} chars from image {img_idx + 1} on page {actual_page_num}")
                                    except Exception as ocr_err:
                                        logger.debug(f"Could not OCR image {img_idx + 1} on page {actual_page_num}: {ocr_err}")
                                        ocr_text = f"Image {img_idx + 1} on page {actual_page_num}"
                                    
                                    # Use page text as fallback if no OCR text extracted
                                    if not ocr_text or len(ocr_text) < 10:
                                        # Try to use surrounding page text as context
                                        ocr_text = f"Image {img_idx + 1} on page {actual_page_num}"
                                    
                                    extracted_images.append({
                                        "source": os.path.basename(file_path),
                                        "page": actual_page_num,
                                        "image_number": len(extracted_images) + 1,
                                        "image_index": img_idx,
                                        "ocr_text": ocr_text,
                                        "ocr_text_length": len(ocr_text)
                                    })
                                    
                                    # Add to page_blocks (CRITICAL for RAG Citation)
                                    # Get image bounding box if available
                                    img_rects = page.get_image_rects(xref)
                                    if img_rects:
                                        for rect in img_rects:
                                            page_blocks.append({
                                                'type': 'image',
                                                'page': actual_page_num,
                                                'image_index': img_idx,
                                                'bbox': [rect.x0, rect.y0, rect.x1, rect.y1],
                                                'xref': xref
                                            })
                                except Exception as e:
                                    logger.debug(f"operation: {type(e).__name__}: {e}")
                                    pass
                        
                        if progress_callback and pages > 0:
                            progress = 0.6 + (0.3 * (page_num + 1) / pages)
                            progress_callback("parsing", progress, 
                                            detailed_message=f"Extracting text from page {page_num + 1}/{pages}...")
                    
                    doc.close()
                    extracted_text = "\n".join(text_parts)
                    
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
                        cumulative_pos = page_end + 1  # +1 for \n separator
                        
                        if progress_callback and pages > 0:
                            progress = 0.6 + (0.3 * (page_num + 1) / pages)
                            progress_callback("parsing", progress,
                                            detailed_message=f"Extracting text from page {page_num + 1}/{pages}...")
                    
                    extracted_text = "\n".join(text_parts)
                
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
                        "page_blocks": page_blocks,  # Store page-level blocks for citation support
                        "extracted_images": extracted_images  # Store extracted images list for OpenSearch storage
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
