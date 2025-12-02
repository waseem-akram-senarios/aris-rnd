"""
Parser factory for selecting and managing document parsers.
"""
import os
from typing import Optional, Dict, Type
from .base_parser import BaseParser, ParsedDocument


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
        except ImportError:
            pass
        
        try:
            from .docling_parser import DoclingParser
            cls.register_parser('pdf', DoclingParser)  # Also for PDF
        except ImportError:
            pass
        
        try:
            from .textract_parser import TextractParser
            # Textract is also for PDF, but we'll handle it in get_parser
        except ImportError:
            pass
        
        cls._registered = True
    
    @classmethod
    def get_parser(cls, file_path: str, preferred_parser: Optional[str] = None) -> Optional[BaseParser]:
        """
        Get an appropriate parser for the given file.
        
        Args:
            file_path: Path to the file
            preferred_parser: Optional preferred parser name ('pymupdf', 'docling', 'textract', 'auto')
        
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
                    return DoclingParser()
                elif preferred_parser.lower() == 'textract':
                    from .textract_parser import TextractParser
                    return TextractParser()
            except ImportError:
                pass  # Fall through to default selection
        
        # Default: return first registered parser for this extension
        if ext in cls._parsers:
            parser_class = cls._parsers[ext]
            return parser_class()
        
        return None
    
    @classmethod
    def parse_with_fallback(cls, file_path: str, file_content: Optional[bytes] = None, 
                           preferred_parser: Optional[str] = None,
                           progress_callback: Optional[callable] = None) -> ParsedDocument:
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
        
        Returns:
            ParsedDocument with best result
        
        Raises:
            ValueError: If file cannot be parsed by any parser
        """
        _, ext = os.path.splitext(file_path.lower())
        ext = ext.lstrip('.')
        
        if ext == 'pdf':
            return cls._parse_pdf_with_fallback(file_path, file_content, preferred_parser, progress_callback)
        else:
            # For non-PDF files, use single parser
            parser = cls.get_parser(file_path, preferred_parser)
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
                                progress_callback: Optional[callable] = None) -> ParsedDocument:
        """Parse PDF with fallback chain."""
        from .pdf_type_detector import detect_pdf_type, is_image_heavy_pdf
        
        # If specific parser requested, use it WITHOUT fallback
        if preferred_parser and preferred_parser.lower() != 'auto':
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"ParserFactory: Explicit parser requested: {preferred_parser}")
            
            parser = cls.get_parser(file_path, preferred_parser)
            if parser:
                logger.info(f"ParserFactory: Using {preferred_parser} parser (no fallback)")
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
                        logger.warning(f"ParserFactory: Requested {preferred_parser} but got {result.parser_used}")
                    return result
                except Exception as e:
                    # If explicitly selected parser fails, raise error instead of falling back
                    error_msg = str(e)
                    logger.error(f"ParserFactory: {preferred_parser} parser failed: {error_msg}")
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
                logger.error(f"ParserFactory: Parser '{preferred_parser}' is not available")
                raise ValueError(f"Parser '{preferred_parser}' is not available")
        
        # Detect PDF type
        pdf_type = detect_pdf_type(file_path, file_content)
        is_image_heavy = is_image_heavy_pdf(file_path, file_content)
        
        best_result = None
        best_confidence = 0.0
        pymupdf_result = None  # Keep PyMuPDF result as fallback
        
        # Try PyMuPDF first (fastest, free)
        try:
            from .pymupdf_parser import PyMuPDFParser
            parser = PyMuPDFParser()
            # PyMuPDF supports progress_callback
            if progress_callback:
                result = parser.parse(file_path, file_content, progress_callback=progress_callback)
            else:
                result = parser.parse(file_path, file_content)
            pymupdf_result = result  # Always keep PyMuPDF result as fallback
            
            # Check if result is good enough
            if result.extraction_percentage >= 0.5 and result.confidence >= 0.7:
                return result  # Good enough, return immediately
            
            # Keep as candidate
            if result.confidence > best_confidence:
                best_result = result
                best_confidence = result.confidence
        except Exception as e:
            print(f"PyMuPDF parser failed: {e}")
        
        # Try Docling if PyMuPDF results are poor (for structured documents and scanned PDFs)
        # Docling is good for complex layouts, tables, structured content, and has OCR for scanned PDFs
        if best_result and (best_result.extraction_percentage < 0.5 or best_result.confidence < 0.7 or is_image_heavy):
            try:
                from .docling_parser import DoclingParser
                parser = DoclingParser()
                result = parser.parse(file_path, file_content)
                
                # Use Docling if it has better confidence or extraction
                if result.confidence > best_confidence or result.extraction_percentage > best_result.extraction_percentage:
                    best_result = result
                    best_confidence = result.confidence
            except ValueError as e:
                # Docling may timeout or fail on large/complex documents
                error_msg = str(e)
                if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                    print(f"Docling parser timed out: {error_msg}")
                elif "too large" in error_msg.lower():
                    print(f"Docling parser: {error_msg}")
                else:
                    print(f"Docling parser failed: {error_msg}")
                # Continue to Textract if available
            except Exception as e:
                print(f"Docling parser failed: {e}")
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

