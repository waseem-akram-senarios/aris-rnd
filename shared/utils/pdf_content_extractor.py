"""
PDF content extraction utility for verification.
Extracts raw text and images directly from PDF for comparison with stored OCR.
"""
import logging
from typing import Dict, Any, List, Optional
from io import BytesIO
import hashlib

logger = logging.getLogger(__name__)


def extract_pdf_content(file_content: bytes, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract raw content from PDF for verification.
    
    Extracts:
    - Native text per page (without OCR)
    - Images per page (raw image data)
    - Page structure
    - Content hashes for comparison
    
    Args:
        file_content: PDF file content as bytes
        file_path: Optional file path (for logging)
    
    Returns:
        Dictionary containing extracted content per page
    """
    result = {
        'pages': [],
        'total_pages': 0,
        'total_native_text_length': 0,
        'total_images': 0,
        'extraction_timestamp': None
    }
    
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(stream=file_content, filetype="pdf")
        result['total_pages'] = len(doc)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Extract native text (without OCR)
            native_text = page.get_text()
            text_hash = hashlib.md5(native_text.encode('utf-8')).hexdigest()
            
            # Extract images
            image_list = page.get_images(full=True)
            images = []
            
            for img_idx, img in enumerate(image_list):
                try:
                    # Get image data
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Calculate image hash
                    image_hash = hashlib.md5(image_bytes).hexdigest()
                    
                    images.append({
                        'image_index': img_idx,
                        'xref': xref,
                        'image_data': image_bytes,
                        'image_hash': image_hash,
                        'format': image_ext,
                        'width': base_image.get('width'),
                        'height': base_image.get('height'),
                        'colorspace': base_image.get('colorspace')
                    })
                except Exception as e:
                    logger.warning(f"Could not extract image {img_idx} from page {page_num + 1}: {e}")
            
            page_data = {
                'page_number': page_num + 1,
                'native_text': native_text,
                'text_length': len(native_text),
                'text_hash': text_hash,
                'images': images,
                'image_count': len(images)
            }
            
            result['pages'].append(page_data)
            result['total_native_text_length'] += len(native_text)
            result['total_images'] += len(images)
        
        doc.close()
        
        from datetime import datetime
        result['extraction_timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"✅ Extracted PDF content: {result['total_pages']} pages, "
                   f"{result['total_native_text_length']} chars, {result['total_images']} images")
        
    except ImportError:
        logger.error("❌ PyMuPDF (fitz) not available - cannot extract PDF content")
        result['extraction_error'] = 'PyMuPDF not available'
    except Exception as e:
        logger.error(f"❌ Error extracting PDF content: {e}", exc_info=True)
        result['extraction_error'] = str(e)
    
    return result


def get_page_content(file_content: bytes, page_number: int) -> Optional[Dict[str, Any]]:
    """
    Get content for a specific page.
    
    Args:
        file_content: PDF file content as bytes
        page_number: Page number (1-indexed)
    
    Returns:
        Page content dictionary or None if page not found
    """
    try:
        content = extract_pdf_content(file_content)
        for page in content.get('pages', []):
            if page.get('page_number') == page_number:
                return page
    except Exception as e:
        logger.error(f"Error getting page {page_number} content: {e}")
    
    return None


def get_page_images(file_content: bytes, page_number: int) -> List[Dict[str, Any]]:
    """
    Get images from a specific page.
    
    Args:
        file_content: PDF file content as bytes
        page_number: Page number (1-indexed)
    
    Returns:
        List of image dictionaries
    """
    page_content = get_page_content(file_content, page_number)
    if page_content:
        return page_content.get('images', [])
    return []
