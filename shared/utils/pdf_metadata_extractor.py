"""
PDF metadata extraction utility.
Extracts comprehensive metadata from PDF files including document properties,
structure information, and file characteristics.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def extract_pdf_metadata(file_content: bytes, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract comprehensive PDF metadata.
    
    Args:
        file_content: PDF file content as bytes
        file_path: Optional file path (for logging)
    
    Returns:
        Dictionary containing PDF metadata
    """
    metadata = {
        'title': None,
        'author': None,
        'subject': None,
        'creator': None,
        'producer': None,
        'creation_date': None,
        'modification_date': None,
        'pdf_version': None,
        'encrypted': False,
        'page_count': 0,
        'has_bookmarks': False,
        'has_forms': False,
        'annotations_count': 0,
        'extraction_timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    try:
        # Try using pypdf (newer library)
        try:
            from pypdf import PdfReader
            from io import BytesIO
            
            pdf_file = BytesIO(file_content)
            reader = PdfReader(pdf_file)
            
            # Extract metadata
            if reader.metadata:
                metadata['title'] = reader.metadata.get('/Title')
                metadata['author'] = reader.metadata.get('/Author')
                metadata['subject'] = reader.metadata.get('/Subject')
                metadata['creator'] = reader.metadata.get('/Creator')
                metadata['producer'] = reader.metadata.get('/Producer')
                
                # Parse dates
                creation_date = reader.metadata.get('/CreationDate')
                mod_date = reader.metadata.get('/ModDate')
                
                if creation_date:
                    metadata['creation_date'] = _parse_pdf_date(str(creation_date))
                if mod_date:
                    metadata['modification_date'] = _parse_pdf_date(str(mod_date))
            
            # PDF version
            metadata['pdf_version'] = reader.pdf_header
            
            # Encryption status
            metadata['encrypted'] = reader.is_encrypted
            
            # Page count
            metadata['page_count'] = len(reader.pages)
            
            # Check for bookmarks/outline
            if reader.outline:
                metadata['has_bookmarks'] = True
                metadata['bookmarks_count'] = len(reader.outline)
            
            # Check for form fields
            if reader.metadata and '/AcroForm' in str(reader.metadata):
                metadata['has_forms'] = True
            
            logger.info(f"✅ Extracted PDF metadata: {metadata.get('page_count')} pages, encrypted={metadata.get('encrypted')}")
            
        except ImportError:
            # Fallback to PyPDF2
            try:
                import PyPDF2
                from io import BytesIO
                
                pdf_file = BytesIO(file_content)
                reader = PyPDF2.PdfReader(pdf_file)
                
                # Extract metadata
                if reader.metadata:
                    metadata['title'] = reader.metadata.get('/Title')
                    metadata['author'] = reader.metadata.get('/Author')
                    metadata['subject'] = reader.metadata.get('/Subject')
                    metadata['creator'] = reader.metadata.get('/Creator')
                    metadata['producer'] = reader.metadata.get('/Producer')
                    
                    # Parse dates
                    creation_date = reader.metadata.get('/CreationDate')
                    mod_date = reader.metadata.get('/ModDate')
                    
                    if creation_date:
                        metadata['creation_date'] = _parse_pdf_date(str(creation_date))
                    if mod_date:
                        metadata['modification_date'] = _parse_pdf_date(str(mod_date))
                
                # PDF version
                metadata['pdf_version'] = getattr(reader, 'pdf_header', None)
                
                # Encryption status
                metadata['encrypted'] = reader.is_encrypted
                
                # Page count
                metadata['page_count'] = len(reader.pages)
                
                logger.info(f"✅ Extracted PDF metadata using PyPDF2: {metadata.get('page_count')} pages")
                
            except ImportError:
                logger.warning("⚠️ Neither pypdf nor PyPDF2 available - PDF metadata extraction skipped")
                metadata['extraction_error'] = 'PDF library not available'
        
        # Try to get additional info using PyMuPDF if available
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(stream=file_content, filetype="pdf")
            
            # Verify page count
            if metadata['page_count'] == 0:
                metadata['page_count'] = len(doc)
            
            # Check for annotations
            annotation_count = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                annotation_count += len(page.annots())
            
            if annotation_count > 0:
                metadata['annotations_count'] = annotation_count
            
            doc.close()
            
        except ImportError as e:
            logger.debug(f"operation: {type(e).__name__}: {e}")
            pass  # PyMuPDF not available, skip
        except Exception as e:
            logger.debug(f"Could not extract additional metadata with PyMuPDF: {e}")
    
    except Exception as e:
        logger.error(f"❌ Error extracting PDF metadata: {e}", exc_info=True)
        metadata['extraction_error'] = str(e)
    
    return metadata


def _parse_pdf_date(date_str: str) -> Optional[str]:
    """
    Parse PDF date string to ISO format.
    
    PDF dates are in format: D:YYYYMMDDHHmmSSOHH'mm'
    Example: D:20240101120000-05'00'
    """
    try:
        if date_str.startswith('D:'):
            date_str = date_str[2:]
        
        # Extract date components
        year = int(date_str[0:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        hour = int(date_str[8:10]) if len(date_str) > 8 else 0
        minute = int(date_str[10:12]) if len(date_str) > 10 else 0
        second = int(date_str[12:14]) if len(date_str) > 12 else 0
        
        dt = datetime(year, month, day, hour, minute, second)
        return dt.isoformat() + 'Z'
    
    except (ValueError, IndexError) as e:
        logger.debug(f"Could not parse PDF date '{date_str}': {e}")
        return None
