"""
Static test data for API tests
Provides dummy files, documents, images for testing
"""
import io
from typing import Dict, Any, List, Optional
from pathlib import Path


def create_dummy_pdf_content() -> bytes:
    """Create minimal valid PDF content for testing"""
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000317 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
400
%%EOF"""
    return pdf_content


def create_dummy_image_content(format: str = "png") -> bytes:
    """Create minimal valid image content for testing"""
    if format.lower() == "png":
        # Minimal PNG structure (1x1 transparent pixel)
        png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        return png_content
    elif format.lower() == "jpg" or format.lower() == "jpeg":
        # Minimal JPEG structure
        jpg_content = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xaa\xff\xd9'
        return jpg_content
    else:
        return b"dummy image content"


def create_dummy_document_metadata(
    document_id: str = "test-doc-123",
    document_name: str = "test_document.pdf",
    status: str = "completed"
) -> Dict[str, Any]:
    """Create dummy document metadata"""
    return {
        "document_id": document_id,
        "document_name": document_name,
        "status": status,
        "chunks_created": 5,
        "tokens_extracted": 1000,
        "parser_used": "pymupdf",
        "processing_time": 1.5,
        "extraction_percentage": 95.0,
        "images_detected": True,
        "image_count": 2,
        "pages": 10,
        "text_index": "aris-rag-index",
        "images_index": "aris-rag-images-index",
        "file_hash": "abc123def456",
        "uploaded_at": "2025-01-01T00:00:00Z"
    }


def create_dummy_image_metadata(
    image_id: str = "img-1",
    document_id: str = "test-doc-123",
    image_number: int = 1
) -> Dict[str, Any]:
    """Create dummy image metadata"""
    return {
        "image_id": image_id,
        "document_id": document_id,
        "image_number": image_number,
        "ocr_text": "Mocked OCR text from image",
        "image_hash": "img_hash_123",
        "source": "test_document.pdf",
        "page": 1,
        "width": 800,
        "height": 600,
        "format": "png"
    }


def create_dummy_query_response(
    answer: str = "Mocked answer",
    sources: Optional[List[str]] = None,
    num_chunks: int = 1
) -> Dict[str, Any]:
    """Create dummy query response"""
    if sources is None:
        sources = ["test_document.pdf"]
    
    return {
        "answer": answer,
        "sources": sources,
        "citations": [
            {
                "content": "Mocked citation content",
                "source": source,
                "page": 1,
                "content_type": "text"
            }
            for source in sources
        ],
        "num_chunks_used": num_chunks,
        "context_chunks": [
            {
                "page_content": "Mocked chunk content",
                "metadata": {"source": source, "page": 1}
            }
            for source in sources
        ]
    }


def create_dummy_storage_status(
    document_id: str = "test-doc-123",
    text_chunks: int = 5,
    images: int = 2
) -> Dict[str, Any]:
    """Create dummy storage status"""
    return {
        "document_id": document_id,
        "text_chunks_count": text_chunks,
        "images_count": images,
        "text_stored": True,
        "images_stored": True,
        "text_index": "aris-rag-index",
        "images_index": "aris-rag-images-index"
    }


def create_dummy_upload_response(
    document_id: str = "test-doc-123",
    status: str = "completed"
) -> Dict[str, Any]:
    """Create dummy document upload response"""
    return {
        "document_id": document_id,
        "status": status,
        "message": "Document uploaded and processed successfully",
        "chunks_created": 5,
        "tokens_extracted": 1000,
        "images_detected": True,
        "image_count": 2
    }
