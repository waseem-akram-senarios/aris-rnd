"""
PDF type detection utilities.
Detects whether a PDF is text-based, image-based, or mixed.
"""
import os
from typing import Literal


def detect_pdf_type(file_path: str, file_content: bytes = None) -> Literal["text", "image", "mixed"]:
    """
    Detect the type of PDF (text-based, image-based, or mixed).
    
    Uses heuristics:
    - Text-to-page ratio
    - Image count per page
    - File size vs page count
    
    Args:
        file_path: Path to the PDF file
        file_content: Optional file content as bytes
    
    Returns:
        "text" if PDF is primarily text-based
        "image" if PDF is primarily image-based (scanned)
        "mixed" if PDF contains both text and images
    """
    try:
        import fitz  # PyMuPDF
        
        # Open PDF
        if file_content:
            doc = fitz.open(stream=file_content, filetype="pdf")
        else:
            doc = fitz.open(file_path)
        
        # Get total pages before processing
        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            return "text"  # Default for empty PDFs
        
        total_text_length = 0
        total_images = 0
        pages_with_text = 0
        pages_with_images = 0
        
        # Analyze each page
        for page_num in range(total_pages):
            page = doc[page_num]
            
            # Extract text
            text = page.get_text()
            text_length = len(text.strip())
            total_text_length += text_length
            
            if text_length > 100:  # Threshold for "has text"
                pages_with_text += 1
            
            # Count images
            image_list = page.get_images()
            image_count = len(image_list)
            total_images += image_count
            
            if image_count > 0:
                pages_with_images += 1
        
        # Calculate ratios before closing
        text_page_ratio = pages_with_text / total_pages if total_pages > 0 else 0
        image_page_ratio = pages_with_images / total_pages if total_pages > 0 else 0
        avg_text_per_page = total_text_length / total_pages if total_pages > 0 else 0
        avg_images_per_page = total_images / total_pages if total_pages > 0 else 0
        
        # Close document
        doc.close()
        
        # Decision logic
        if text_page_ratio >= 0.8 and avg_text_per_page > 500:
            return "text"
        elif text_page_ratio < 0.3 and (image_page_ratio > 0.5 or avg_images_per_page > 1):
            return "image"
        else:
            return "mixed"
            
    except ImportError:
        # PyMuPDF not available, use file size heuristic
        if file_content:
            file_size = len(file_content)
        else:
            file_size = os.path.getsize(file_path)
        
        # Very large files relative to page count might be image-based
        # This is a fallback heuristic
        return "mixed"
    except Exception as e:
        # On any error, default to mixed
        print(f"Warning: Error detecting PDF type: {e}")
        return "mixed"


def is_image_heavy_pdf(file_path: str, file_content: bytes = None) -> bool:
    """
    Quick check if PDF is image-heavy.
    
    Args:
        file_path: Path to the PDF file
        file_content: Optional file content as bytes
    
    Returns:
        True if PDF appears to be image-heavy
    """
    pdf_type = detect_pdf_type(file_path, file_content)
    return pdf_type in ["image", "mixed"]

