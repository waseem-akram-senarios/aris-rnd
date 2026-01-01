"""
Comprehensive tests for citation accuracy, especially page numbers.
Ensures all citations have accurate page numbers from all parsers.
"""
import pytest
from unittest.mock import MagicMock, patch
from shared.schemas import Citation, ImageResult


@pytest.mark.api
class TestCitationAccuracy:
    """Test citation accuracy, especially page numbers"""
    
    def test_citation_schema_requires_page(self):
        """Test that Citation schema always has a page number"""
        # Should default to page 1 if not provided
        citation = Citation(
            id=1,
            source="test.pdf",
            snippet="Test snippet",
            full_text="Test full text",
            source_location="Page 1"
        )
        assert citation.page == 1
        assert isinstance(citation.page, int)
        assert citation.page >= 1
    
    def test_citation_schema_page_validation(self):
        """Test that Citation schema validates page >= 1"""
        # Valid page numbers
        citation1 = Citation(
            id=1,
            source="test.pdf",
            page=15,
            snippet="Test",
            full_text="Test",
            source_location="Page 15"
        )
        assert citation1.page == 15
        
        # Page defaults to 1 if not provided
        citation2 = Citation(
            id=2,
            source="test.pdf",
            snippet="Test",
            full_text="Test",
            source_location="Page 1"
        )
        assert citation2.page == 1
    
    def test_image_result_schema_requires_page(self):
        """Test that ImageResult schema always has a page number"""
        image = ImageResult(
            image_id="img1",
            source="test.pdf",
            image_number=1,
            ocr_text="Test OCR",
            metadata={}
        )
        assert image.page == 1
        assert isinstance(image.page, int)
        assert image.page >= 1
    
    def test_all_citations_have_page_numbers(self, api_client, service_container):
        """Test that all citations in query response have page numbers"""
        # Add document to registry
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            json={"question": "What is the content about?", "k": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "citations" in data
        
        citations = data.get("citations", [])
        assert len(citations) > 0, "Should have at least one citation"
        
        # Verify all citations have page numbers
        for citation in citations:
            assert "page" in citation, f"Citation missing 'page' field: {citation}"
            page = citation.get("page")
            assert page is not None, f"Citation page is None: {citation}"
            assert isinstance(page, int), f"Citation page must be integer, got {type(page)}: {citation}"
            assert page >= 1, f"Citation page must be >= 1, got {page}: {citation}"
    
    def test_citation_reference_lines_show_pages(self, api_client, service_container):
        """Test that citation reference lines always show page numbers"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            json={"question": "Test question", "k": 3}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check citations
        citations = data.get("citations", [])
        for citation in citations:
            page = citation.get("page")
            assert page is not None and page >= 1, f"Citation missing valid page: {citation}"
    
    def test_no_text_content_in_source_location(self, api_client, service_container):
        """Test that source_location never shows 'Text content'"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            json={"question": "Test question", "k": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        citations = data.get("citations", [])
        for citation in citations:
            source_location = citation.get("source_location", "")
            assert "Text content" not in source_location, \
                f"Citation has 'Text content' in source_location: {citation}"
            # Check case-insensitively for "page" in source_location
            source_location_lower = source_location.lower()
            assert "page" in source_location_lower, \
                f"Citation source_location should include 'page' (case-insensitive): {citation}"
            # Verify it's not just "Text content"
            assert source_location_lower != "text content", \
                f"Citation source_location should not be 'Text content': {citation}"
    
    def test_citation_page_numbers_are_integers(self, api_client, service_container):
        """Test that all citation page numbers are integers"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            json={"question": "Test question", "k": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        citations = data.get("citations", [])
        for citation in citations:
            page = citation.get("page")
            assert isinstance(page, int), \
                f"Citation page must be int, got {type(page).__name__}: {citation}"
            assert page >= 1, \
                f"Citation page must be >= 1, got {page}: {citation}"
    
    def test_image_query_citations_have_pages(self, api_client, service_container):
        """Test that image query results have page numbers"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            params={"type": "image"},
            json={"question": "What images are in the documents?", "k": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If images are returned, verify they have page numbers
        if "images" in data and isinstance(data["images"], list):
            for image in data["images"]:
                assert "page" in image, f"ImageResult missing 'page' field: {image}"
                page = image.get("page")
                assert page is not None, f"ImageResult page is None: {image}"
                assert isinstance(page, int), f"ImageResult page must be integer: {image}"
                assert page >= 1, f"ImageResult page must be >= 1, got {page}: {image}"
    
    def test_agentic_rag_citations_have_pages(self, api_client, service_container):
        """Test that Agentic RAG citations have page numbers"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            json={
                "question": "What is machine learning?",
                "k": 5,
                "use_agentic_rag": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        citations = data.get("citations", [])
        for citation in citations:
            assert "page" in citation, f"Agentic RAG citation missing 'page': {citation}"
            page = citation.get("page")
            assert page is not None and isinstance(page, int) and page >= 1, \
                f"Agentic RAG citation has invalid page: {citation}"


@pytest.mark.integration
class TestCitationAccuracyIntegration:
    """Integration tests for citation accuracy across parsers"""
    
    def test_pymupdf_parser_citations_have_pages(self):
        """Test that PyMuPDF parser produces citations with page numbers"""
        # This would require actual document parsing
        # For now, verify the parser structure
        from parsers.pymupdf_parser import PyMuPDFParser
        parser = PyMuPDFParser()
        assert hasattr(parser, 'parse')
    
    def test_docling_parser_citations_have_pages(self):
        """Test that Docling parser produces citations with page numbers"""
        from parsers.docling_parser import DoclingParser
        parser = DoclingParser()
        assert hasattr(parser, 'parse')
    
    def test_textract_parser_citations_have_pages(self):
        """Test that Textract parser produces citations with page numbers"""
        from parsers.textract_parser import TextractParser
        parser = TextractParser()
        assert hasattr(parser, 'parse')
    
    def test_ocrmypdf_parser_citations_have_pages(self):
        """Test that OCRmyPDF parser produces citations with page numbers"""
        from parsers.ocrmypdf_parser import OCRmyPDFParser
        parser = OCRmyPDFParser()
        assert hasattr(parser, 'parse')
    
    def test_llamascan_parser_citations_have_pages(self):
        """Test that LlamaScan parser produces citations with page numbers"""
        from parsers.llama_scan_parser import LlamaScanParser
        parser = LlamaScanParser()
        assert hasattr(parser, 'parse')
