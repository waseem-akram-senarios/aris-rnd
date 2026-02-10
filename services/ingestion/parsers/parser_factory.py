"""
Parser factory for selecting and managing document parsers.
"""
import os
import logging
from typing import Optional, Dict, Type
from .base_parser import BaseParser, ParsedDocument
from scripts.setup_logging import get_logger
logger = logging.getLogger(__name__)

class ParserFactory:
    """Factory class for creating and managing document parsers."""
    
    _parsers: Dict[str, Type[BaseParser]] = {}
    _registered = False
    
    @classmethod
    def register_parser(cls, file_extension: str, parser_class: Type[BaseParser]):
        """
        Register a parser for a specific file extension.
        
        Args:
            file_extension: File extension (e.g., 'pdf', 'docx') without the dot
            parser_class: Parser class that implements BaseParser
        """
        ext = file_extension.lower().lstrip('.')
        cls._parsers[ext] = parser_class
    
    @classmethod
    def _register_default_parsers(cls):
        """Register default parsers (lazy import to avoid circular dependencies)."""
        if cls._registered:
            return
        
        # Import parsers here to avoid circular dependencies
        try:
            from .pymupdf_parser import PyMuPDFParser
            cls.register_parser('pdf', PyMuPDFParser)
        except ImportError as e:
            logger.debug(f"_register_default_parsers: {type(e).__name__}: {e}")
            pass
        
        try:
            from .docling_parser import DoclingParser
            cls.register_parser('pdf', DoclingParser)  # Also for PDF
        except ImportError as e:
            logger.debug(f"_register_default_parsers: {type(e).__name__}: {e}")
            pass
        
        try:
            from .textract_parser import TextractParser
            # Textract is also for PDF, but we'll handle it in get_parser
        except ImportError as e:
            logger.debug(f"_register_default_parsers: {type(e).__name__}: {e}")
            pass
        
        try:
            from .ocrmypdf_parser import OCRmyPDFParser
            # OCRmyPDF is also for PDF, but we'll handle it in get_parser
        except ImportError as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass

        try:
            from .llama_scan_parser import LlamaScanParser
            cls.register_parser('llamascan', LlamaScanParser)
            # Llama-Scan is also for PDF, handled in get_parser
        except ImportError as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass

        try:
            from .text_parser import TextParser
            cls.register_parser('txt', TextParser)
        except ImportError as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass
        
        cls._registered = True
    
    @classmethod
    def get_parser(cls, file_path: str, preferred_parser: Optional[str] = None, language: str = "eng") -> Optional[BaseParser]:
        """
        Get an appropriate parser for the given file.
        
        Args:
            file_path: Path to the file
            preferred_parser: Optional preferred parser name ('pymupdf', 'docling', 'textract', 'ocrmypdf', 'llama-scan', 'auto')
            language: Language code for OCR (default: 'eng'). Use '+' for multiple.
        
        Returns:
            BaseParser instance or None if no suitable parser found
        """
        cls._register_default_parsers()
        
        # Get file extension
        _, ext = os.path.splitext(file_path.lower())
        ext = ext.lstrip('.')
        
        if not ext:
            return None
        
        # Handle preferred parser
        if preferred_parser and preferred_parser.lower() != 'auto':
            try:
                if preferred_parser.lower() == 'pymupdf':
                    from .pymupdf_parser import PyMuPDFParser
                    return PyMuPDFParser()
                elif preferred_parser.lower() == 'docling':
                    from .docling_parser import DoclingParser
                    if DoclingParser().is_available():
                        return DoclingParser()
                elif preferred_parser.lower() == 'textract':
                    from .textract_parser import TextractParser
                    if TextractParser().is_available():
                        return TextractParser()
                elif preferred_parser.lower() == 'ocrmypdf':
                    from .ocrmypdf_parser import OCRmyPDFParser
                    if OCRmyPDFParser().is_available():
                        return OCRmyPDFParser(languages=language)
                elif preferred_parser.lower() in ['llama-scan', 'llamascan']:
                    from .llama_scan_parser import LlamaScanParser
                    if LlamaScanParser().is_available():
                        return LlamaScanParser()
            except ImportError as e:
                logger.warning(f"Could not load preferred parser {preferred_parser}: {e}")
                # Fall back to auto selection
        
        # Default: return first registered parser for this extension
        if ext in cls._parsers:
            parser_class = cls._parsers[ext]
            return parser_class()
        
        return None
    
    @classmethod
    def parse_with_fallback(cls, file_path: str, file_content: Optional[bytes] = None, 
                           preferred_parser: Optional[str] = None,
                           progress_callback: Optional[callable] = None,
                           language: str = "eng") -> ParsedDocument:
        """
        Parse a document using fallback chain.
        
        For PDFs:
        1. Try PyMuPDF first (fastest, free)
        2. If poor results, try Docling (for structured documents, tables, layouts)
        3. If still poor and AWS available, try Textract (for scanned PDFs)
        
        Args:
            file_path: Path to the file
            file_content: Optional file content as bytes
            preferred_parser: Optional preferred parser name
            progress_callback: Optional progress callback function
            language: Language code for OCR (default: 'eng'). Use '+' for multiple.
        
        Returns:
            ParsedDocument with best result
        
        Raises:
            ValueError: If file cannot be parsed by any parser
        """
        _, ext = os.path.splitext(file_path.lower())
        ext = ext.lstrip('.')
        
        if ext == 'pdf':
            return cls._parse_pdf_with_fallback(file_path, file_content, preferred_parser, progress_callback, language)
        else:
            # For non-PDF files, use single parser
            parser = cls.get_parser(file_path, preferred_parser, language=language)
            if parser is None:
                raise ValueError(f"No parser available for file type: {ext}")
            # Try to pass progress_callback if parser supports it
            import inspect
            sig = inspect.signature(parser.parse)
            if 'progress_callback' in sig.parameters:
                return parser.parse(file_path, file_content, progress_callback=progress_callback)
            else:
                return parser.parse(file_path, file_content)
    
    @classmethod
    def _parse_pdf_with_fallback(cls, file_path: str, file_content: Optional[bytes] = None,
                                preferred_parser: Optional[str] = None,
                                progress_callback: Optional[callable] = None,
                                language: str = "eng") -> ParsedDocument:
        """Parse PDF with fallback chain."""
        from .pdf_type_detector import detect_pdf_type, is_image_heavy_pdf
        
        # If specific parser requested, use it WITHOUT fallback
        if preferred_parser and preferred_parser.lower() != 'auto':
            logger.info(f"[STEP 2.1] ParserFactory: Explicit parser requested: {preferred_parser}")
            
            # Special handling for OCRmyPDF - check if available
            if preferred_parser.lower() == 'ocrmypdf':
                try:
                    from .ocrmypdf_parser import OCRmyPDFParser
                    parser = OCRmyPDFParser(languages=language)
                    if not parser.is_available():
                        raise ValueError(
                            "OCRmyPDF or Tesseract not installed. "
                            "Install with: sudo apt-get install tesseract-ocr && pip install ocrmypdf"
                        )
                except ImportError:
                    raise ValueError("OCRmyPDF parser not available. Install with: pip install ocrmypdf")
            elif preferred_parser.lower() == 'llamascan':
                try:
                    from .llama_scan_parser import LlamaScanParser
                    parser = LlamaScanParser()
                    if not parser.is_available():
                        logger.warning(
                            "Llama-Scan selected but Ollama is not reachable. Falling back to automatic PDF parsing. "
                            "Set OLLAMA_SERVER_URL and ensure Ollama is running to use Llama-Scan."
                        )
                        parser = None
                except ImportError:
                    logger.warning(
                        "Llama-Scan parser not available (missing llama-scan). Falling back to automatic PDF parsing."
                    )
                    parser = None
            else:
                parser = cls.get_parser(file_path, preferred_parser, language=language)
            
            if parser:
                logger.info(f"[STEP 2.2] ParserFactory: Using {preferred_parser} parser (no fallback)")
                try:
                    # Try to pass progress_callback if parser supports it
                    import inspect
                    sig = inspect.signature(parser.parse)
                    if 'progress_callback' in sig.parameters:
                        result = parser.parse(file_path, file_content, progress_callback=progress_callback)
                    else:
                        result = parser.parse(file_path, file_content)
                    
                    # Verify the result actually used the requested parser
                    if hasattr(result, 'parser_used') and result.parser_used.lower() != preferred_parser.lower():
                        logger.warning(f"⚠️ [STEP 2.2] ParserFactory: Requested {preferred_parser} but got {result.parser_used}")
                    
                    # AUTO-FALLBACK TO OCR: If non-OCR parser extracted 0 text from a PDF with pages,
                    # automatically try an OCR-capable parser (this handles scanned PDFs)
                    text_length = len(result.text) if result.text else 0
                    page_count = getattr(result, 'pages', 0) or 0
                    is_non_ocr_parser = preferred_parser.lower() in ('pymupdf', 'pdfplumber')
                    
                    if is_non_ocr_parser and text_length < 100 and page_count > 0:
                        logger.warning(f"⚠️ [STEP 2.2] ParserFactory: {preferred_parser} extracted only {text_length} chars from {page_count} pages - likely a scanned PDF")
                        logger.info(f"[STEP 2.2] ParserFactory: Auto-falling back to OCR parser (Docling) for scanned PDF...")
                        
                        # Try Docling first (has built-in OCR)
                        try:
                            from .docling_parser import DoclingParser
                            ocr_parser = DoclingParser()
                            if ocr_parser.is_available():
                                logger.info(f"[STEP 2.2] ParserFactory: Attempting Docling OCR for scanned PDF...")
                                if 'progress_callback' in inspect.signature(ocr_parser.parse).parameters:
                                    ocr_result = ocr_parser.parse(file_path, file_content, progress_callback=progress_callback)
                                else:
                                    ocr_result = ocr_parser.parse(file_path, file_content)
                                
                                ocr_text_length = len(ocr_result.text) if ocr_result.text else 0
                                if ocr_text_length > text_length:
                                    logger.info(f"✅ [STEP 2.2] ParserFactory: Docling OCR extracted {ocr_text_length:,} chars (vs {text_length} from {preferred_parser})")
                                    ocr_result.parser_used = 'docling'  # Mark as Docling
                                    return ocr_result
                        except Exception as docling_err:
                            logger.warning(f"⚠️ [STEP 2.2] ParserFactory: Docling OCR failed: {docling_err}")
                        
                        # Try OCRmyPDF as fallback
                        try:
                            from .ocrmypdf_parser import OCRmyPDFParser
                            ocr_parser = OCRmyPDFParser(languages=language)
                            if ocr_parser.is_available():
                                logger.info(f"[STEP 2.2] ParserFactory: Attempting OCRmyPDF for scanned PDF...")
                                if 'progress_callback' in inspect.signature(ocr_parser.parse).parameters:
                                    ocr_result = ocr_parser.parse(file_path, file_content, progress_callback=progress_callback)
                                else:
                                    ocr_result = ocr_parser.parse(file_path, file_content)
                                
                                ocr_text_length = len(ocr_result.text) if ocr_result.text else 0
                                if ocr_text_length > text_length:
                                    logger.info(f"✅ [STEP 2.2] ParserFactory: OCRmyPDF extracted {ocr_text_length:,} chars (vs {text_length} from {preferred_parser})")
                                    return ocr_result
                        except Exception as ocr_err:
                            logger.warning(f"⚠️ [STEP 2.2] ParserFactory: OCRmyPDF failed: {ocr_err}")
                        
                        # If all OCR attempts failed, return original result with warning
                        logger.warning(f"⚠️ [STEP 2.2] ParserFactory: OCR fallback failed, returning original {preferred_parser} result")
                    
                    logger.info(f"✅ [STEP 2.2] ParserFactory: {preferred_parser} parser completed successfully")
                    return result
                except Exception as e:
                    # If explicitly selected parser fails, raise error instead of falling back
                    error_msg = str(e)
                    logger.error(f"❌ [STEP 2.2] ParserFactory: {preferred_parser} parser failed: {error_msg}")
                    if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                        raise ValueError(
                            f"{preferred_parser.capitalize()} parser timed out: {error_msg}. "
                            f"Please try again or use a different parser."
                        )
                    else:
                        raise ValueError(
                            f"{preferred_parser.capitalize()} parser failed: {error_msg}. "
                            f"Please try again or use a different parser."
                        )
            else:
                logger.warning(f"[STEP 2.1] ParserFactory: Parser '{preferred_parser}' is not available, falling back")
        
        # Detect PDF type
        logger.info(f"[STEP 2.1] ParserFactory: Detecting PDF type...")
        pdf_type = detect_pdf_type(file_path, file_content)
        is_image_heavy = is_image_heavy_pdf(file_path, file_content)
        logger.info(f"[STEP 2.1] ParserFactory: PDF type detected - type={pdf_type}, image_heavy={is_image_heavy}")
        
        best_result = None
        best_confidence = 0.0
        pymupdf_result = None  # Keep PyMuPDF result as fallback
        docling_result = None  # Keep Docling result for comparison
        
        # OPTIMIZATION: If images are detected, prefer Docling for OCR capabilities
        # Docling extracts more text (104K vs 74K chars) and has superior OCR
        if is_image_heavy:
            logger.info(f"[STEP 2.2] ParserFactory: Images detected - trying Docling first for OCR capabilities...")
            try:
                from .docling_parser import DoclingParser
                parser = DoclingParser()
                # Check if parser supports progress_callback
                import inspect
                sig = inspect.signature(parser.parse)
                if 'progress_callback' in sig.parameters:
                    result = parser.parse(file_path, file_content, progress_callback=progress_callback)
                else:
                    result = parser.parse(file_path, file_content)
                
                docling_result = result
                # Docling is preferred when images are detected, but we'll still compare with PyMuPDF
                if result.confidence > best_confidence or result.extraction_percentage > best_confidence:
                    best_result = result
                    best_confidence = max(result.confidence, result.extraction_percentage)
                    logger.info(f"✅ [STEP 2.2] ParserFactory: Docling extracted {len(result.text):,} characters (OCR enabled)")
            except ValueError as e:
                # Docling may timeout or fail on large/complex documents
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning(f"Docling parser timed out: {error_msg}")
                elif "too large" in error_msg.lower():
                    logger.warning(f"Docling parser: {error_msg}")
                else:
                    logger.warning(f"Docling parser failed: {error_msg}")
                # Continue to PyMuPDF as fallback
            except Exception as e:
                logger.warning(f"Docling parser failed: {e}")
                # Continue to PyMuPDF as fallback
        
        # Try PyMuPDF (fastest, free) - either as primary (if no images) or for comparison
        logger.info(f"[STEP 2.2] ParserFactory: Trying PyMuPDF parser (fastest, free)...")
        try:
            from .pymupdf_parser import PyMuPDFParser
            parser = PyMuPDFParser()
            # PyMuPDF supports progress_callback
            if progress_callback:
                result = parser.parse(file_path, file_content, progress_callback=progress_callback)
            else:
                result = parser.parse(file_path, file_content)
            pymupdf_result = result  # Always keep PyMuPDF result as fallback
            
            # If images detected and we have Docling result, compare them
            if is_image_heavy and docling_result:
                # Compare extraction quality - prefer the one with more text
                pymupdf_chars = len(result.text) if result.text else 0
                docling_chars = len(docling_result.text) if docling_result.text else 0
                
                logger.info(f"[STEP 2.2] ParserFactory: Comparing parsers - PyMuPDF: {pymupdf_chars:,} chars, Docling: {docling_chars:,} chars")
                
                # Prefer Docling if it extracted significantly more text (OCR advantage)
                # Or if it has better confidence/extraction percentage
                if (docling_chars > pymupdf_chars * 1.1 or  # Docling extracted 10%+ more text
                    docling_result.extraction_percentage > result.extraction_percentage or
                    docling_result.confidence > result.confidence):
                    logger.info(f"✅ [STEP 2.2] ParserFactory: Docling selected (better extraction: {docling_chars:,} vs {pymupdf_chars:,} chars)")
                    return docling_result
                else:
                    logger.info(f"✅ [STEP 2.2] ParserFactory: PyMuPDF selected (similar/better extraction: {pymupdf_chars:,} vs {docling_chars:,} chars)")
                    return result
            
            # If no images or no Docling result, use standard logic
            # Check if result is good enough
            if result.extraction_percentage >= 0.5 and result.confidence >= 0.7:
                logger.info(f"✅ [STEP 2.2] ParserFactory: PyMuPDF result is good enough (extraction={result.extraction_percentage*100:.1f}%, confidence={result.confidence:.2f})")
                return result  # Good enough, return immediately
            
            # Keep as candidate
            if result.confidence > best_confidence:
                best_result = result
                best_confidence = result.confidence
        except Exception as e:
            logger.warning(f"PyMuPDF parser failed: {e}")
        
        # Try Docling if PyMuPDF results are poor (for structured documents and scanned PDFs)
        # Docling is good for complex layouts, tables, structured content, and has OCR for scanned PDFs
        # Skip if we already tried Docling above
        if not is_image_heavy and best_result and (best_result.extraction_percentage < 0.5 or best_result.confidence < 0.7):
            try:
                from .docling_parser import DoclingParser
                parser = DoclingParser()
                # Check if parser supports progress_callback
                import inspect
                sig = inspect.signature(parser.parse)
                if 'progress_callback' in sig.parameters:
                    result = parser.parse(file_path, file_content, progress_callback=progress_callback)
                else:
                    result = parser.parse(file_path, file_content)
                
                # Use Docling if it has better confidence or extraction
                if result.confidence > best_confidence or result.extraction_percentage > best_result.extraction_percentage:
                    best_result = result
                    best_confidence = result.confidence
            except ValueError as e:
                # Docling may timeout or fail on large/complex documents
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    logger.warning(f"Docling parser timed out: {error_msg}")
                elif "too large" in error_msg.lower():
                    logger.warning(f"Docling parser: {error_msg}")
                else:
                    logger.warning(f"Docling parser failed: {error_msg}")
                # Continue to Textract if available
            except Exception as e:
                logger.warning(f"Docling parser failed: {e}")
                # Continue to Textract if available
        
        # If still poor results and AWS available, try Textract
        if best_result and best_result.extraction_percentage < 0.3:
            try:
                from .textract_parser import TextractParser

                parser = TextractParser()
                if parser.is_available():  # Check AWS credentials
                    # Textract has timeout built-in, but catch any errors quickly
                    result = parser.parse(file_path, file_content)
                    
                    if result.confidence > best_confidence:
                        best_result = result
                        best_confidence = result.confidence
            except ValueError as e:
                # ValueError includes timeout errors and other parsing issues
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    print(f"Textract parser timed out: {error_msg}")
                else:
                    print(f"Textract parser failed: {error_msg}")
                # If Textract fails or times out, fall back to PyMuPDF result
                if pymupdf_result:
                    print(f"Falling back to PyMuPDF parser result")
                    return pymupdf_result
            except Exception as e:
                print(f"Textract parser failed: {e}")
                # If Textract fails, fall back to PyMuPDF result (even if it was poor)
                if pymupdf_result:
                    print(f"Falling back to PyMuPDF parser result")
                    return pymupdf_result
        
        # Return best result, or PyMuPDF result as last resort
        if best_result:
            return best_result
        elif pymupdf_result:
            # Return PyMuPDF result even if it wasn't the best (as fallback)
            return pymupdf_result
        
        raise ValueError(f"Failed to parse PDF: {file_path}")

