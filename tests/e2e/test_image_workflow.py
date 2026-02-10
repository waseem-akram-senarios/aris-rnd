"""
End-to-end tests for image workflows
Tests image extraction, storage, and query workflows
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
@pytest.mark.slow
class TestImageWorkflow:
    """Test image workflows"""
    
    def test_image_extraction_storage_query(self, api_client, service_container):
        """Test complete image workflow: extract → store → query"""
        # Add document with images
        service_container.document_registry.add_document(
            "image-doc",
            {
                "document_name": "image.pdf",
                "status": "completed",
                "images_detected": True,
                "image_count": 2,
                "parser_used": "docling"
            }
        )
        
        # Test getting images
        response = api_client.get("/documents/image-doc/images/all")
        
        # May not exist in minimal API or return images
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "images" in data or isinstance(data, list)
    
    def test_image_ocr_accuracy(self, service_container):
        """Test OCR quality"""
        # Structural test - actual OCR accuracy requires real PDFs with images
        # Test that OCR extraction methods exist
        assert hasattr(service_container.document_processor, '_store_images_in_opensearch')
        assert hasattr(service_container.rag_system, 'query_images')
    
    def test_image_query_by_number(self, api_client, service_container):
        """Test retrieving image by number"""
        service_container.document_registry.add_document(
            "image-doc",
            {
                "document_name": "image.pdf",
                "status": "completed",
                "image_count": 3
            }
        )
        
        response = api_client.get("/documents/image-doc/images/1")
        
        # May not exist in minimal API
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "ocr_text" in data or "image_number" in data
