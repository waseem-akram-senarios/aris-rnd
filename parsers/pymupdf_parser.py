"""
PyMuPDF (fitz) parser for PDF documents.
Fast and efficient parser for text-based PDFs.
"""
import os
from typing import Optional
from .base_parser import BaseParser, ParsedDocument


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
        Parse PDF using PyMuPDF.
        
        Args:
            file_path: Path to PDF file
            file_content: Optional file content as bytes
        
        Returns:
            ParsedDocument with extracted text and metadata
        """
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
            
            for page_num in range(total_pages):
                page = doc[page_num]
                
                # Extract text
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    pages_with_text += 1
                
                # Check for images
                image_list = page.get_images()
                if image_list:
                    total_images += len(image_list)
                    images_detected = True
            
            # Combine all text before closing
            full_text = "\n\n".join(text_parts)
            
            # Calculate extraction percentage
            extraction_percentage = pages_with_text / total_pages if total_pages > 0 else 0.0
            
            # Close document
            doc.close()
            
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
                "file_size": len(file_content) if file_content else os.path.getsize(file_path)
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
            raise ValueError(f"Failed to parse PDF with PyMuPDF: {str(e)}")

