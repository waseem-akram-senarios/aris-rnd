"""
End-to-end tests for FastAPI endpoints
Tests all major API endpoints with real service communication
"""
import pytest
import httpx
import json
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
@pytest.mark.api
class TestAPIEndpoints:
    """Test FastAPI endpoints with real services"""
    
    @pytest.fixture
    async def api_client(self):
        """HTTP client for API testing"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    async def test_root_endpoint(self, api_client):
        """Test root endpoint"""
        response = await api_client.get("http://localhost:8500/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "endpoints" in data
        assert data["name"] == "ARIS RAG API - Unified"
    
    async def test_health_endpoint(self, api_client):
        """Test health check endpoint"""
        response = await api_client.get("http://localhost:8500/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
    
    async def test_documents_list_empty(self, api_client):
        """Test listing documents when empty"""
        response = await api_client.get("http://localhost:8500/documents")
        assert response.status_code == 200
        
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert "total_chunks" in data
        assert "total_images" in data
        assert isinstance(data["documents"], list)
    
    async def test_document_upload_pdf(self, api_client, temp_dir):
        """Test PDF document upload"""
        # Create a simple PDF
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"
        
        test_file = temp_dir / "test_api.pdf"
        test_file.write_bytes(pdf_content)
        
        with open(test_file, 'rb') as f:
            files = {"file": ("test_api.pdf", f, "application/pdf")}
            response = await api_client.post(
                "http://localhost:8500/documents",
                files=files
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "processing"
        assert data["document_name"] == "test_api.pdf"
    
    async def test_document_upload_txt(self, api_client, temp_dir):
        """Test TXT document upload"""
        txt_content = b"This is a test text document for API testing."
        
        test_file = temp_dir / "test_api.txt"
        test_file.write_bytes(txt_content)
        
        with open(test_file, 'rb') as f:
            files = {"file": ("test_api.txt", f, "text/plain")}
            response = await api_client.post(
                "http://localhost:8500/documents",
                files=files
            )
        
        assert response.status_code == 201
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "processing"
    
    async def test_document_upload_invalid_type(self, api_client, temp_dir):
        """Test upload of invalid file type"""
        invalid_file = temp_dir / "test.invalid"
        invalid_file.write_bytes(b"invalid content")
        
        with open(invalid_file, 'rb') as f:
            files = {"file": ("test.invalid", f, "application/octet-stream")}
            response = await api_client.post(
                "http://localhost:8500/documents",
                files=files
            )
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported file type" in data["detail"]
    
    async def test_query_text_no_documents(self, api_client):
        """Test text query when no documents exist"""
        query_data = {
            "question": "What is the meaning of life?",
            "k": 5,
            "search_mode": "semantic"
        }
        
        response = await api_client.post(
            "http://localhost:8500/query",
            json=query_data
        )
        
        # Should return 400 when no documents
        assert response.status_code == 400
        data = response.json()
        assert "No documents have been processed yet" in data["detail"]
    
    async def test_query_with_parameters(self, api_client):
        """Test query with various parameters"""
        # First ensure we have a document
        docs_response = await api_client.get("http://localhost:8500/documents")
        if docs_response.status_code == 200:
            docs_data = docs_response.json()
            if docs_data.get("documents") and docs_data["total"] > 0:
                # Test query with parameters
                query_data = {
                    "question": "test query",
                    "k": 3,
                    "search_mode": "hybrid",
                    "use_mmr": True,
                    "temperature": 0.1,
                    "max_tokens": 500
                }
                
                response = await api_client.post(
                    "http://localhost:8500/query",
                    json=query_data
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "answer" in data
                assert "citations" in data
                assert "num_chunks_used" in data
                assert "response_time" in data
    
    async def test_query_image_no_documents(self, api_client):
        """Test image query when no documents exist"""
        query_data = {
            "question": "find images",
            "k": 5
        }
        
        response = await api_client.post(
            "http://localhost:8500/query?type=image",
            json=query_data
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert "images" in data
            assert "total" in data
            assert data["total"] == 0
    
    async def test_query_with_document_filter(self, api_client):
        """Test query filtered to specific document"""
        # Get a document ID
        docs_response = await api_client.get("http://localhost:8500/documents")
        if docs_response.status_code == 200:
            docs_data = docs_response.json()
            if docs_data.get("documents"):
                doc_id = docs_data["documents"][0]["document_id"]
                
                query_data = {
                    "question": "test query",
                    "k": 5,
                    "document_id": doc_id
                }
                
                response = await api_client.post(
                    "http://localhost:8500/query",
                    json=query_data
                )
                
                assert response.status_code in [200, 400]
    
    async def test_query_focus_parameters(self, api_client):
        """Test query with focus parameters"""
        # Test different focus modes
        focus_modes = ["all", "important", "summary", "specific"]
        
        for focus in focus_modes:
            response = await api_client.post(
                f"http://localhost:8500/query?focus={focus}",
                json={"question": "test query", "k": 5}
            )
            
            # Should handle focus parameter
            assert response.status_code in [200, 400]
    
    async def test_s3_upload_endpoint(self, api_client, temp_dir):
        """Test S3 upload endpoint"""
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        test_file = temp_dir / "s3_upload_test.pdf"
        test_file.write_bytes(pdf_content)
        
        with open(test_file, 'rb') as f:
            files = {"file": ("s3_upload_test.pdf", f, "application/pdf")}
            data = {
                "store_in_s3": "true",
                "parser_preference": "pymupdf"
            }
            response = await api_client.post(
                "http://localhost:8500/documents/upload-s3",
                files=files,
                data=data
            )
        
        # Should handle S3 upload (may fail if S3 not configured)
        assert response.status_code in [201, 503]  # 503 if S3 not available
        
        if response.status_code == 201:
            doc_data = response.json()
            assert "document_id" in doc_data
            assert doc_data["status"] == "processing"
    
    async def test_settings_endpoint(self, api_client):
        """Test settings endpoint"""
        response = await api_client.get("http://localhost:8500/settings")
        assert response.status_code == 200
        
        data = response.json()
        assert "models" in data
        assert "parser" in data
        assert "chunking" in data
        assert "vector_store" in data
        assert "retrieval" in data
        
        # Test specific sections
        sections = ["models", "parser", "chunking", "vector_store", "retrieval"]
        for section in sections:
            response = await api_client.get(f"http://localhost:8500/settings?section={section}")
            assert response.status_code == 200
    
    async def test_document_delete(self, api_client, temp_dir):
        """Test document deletion"""
        # First upload a document
        pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        test_file = temp_dir / "delete_test.pdf"
        test_file.write_bytes(pdf_content)
        
        with open(test_file, 'rb') as f:
            files = {"file": ("delete_test.pdf", f, "application/pdf")}
            upload_response = await api_client.post(
                "http://localhost:8500/documents",
                files=files
            )
        
        if upload_response.status_code == 201:
            doc_id = upload_response.json()["document_id"]
            
            # Delete the document
            delete_response = await api_client.delete(
                f"http://localhost:8500/documents/{doc_id}"
            )
            
            assert delete_response.status_code == 204
            
            # Verify document is gone
            get_response = await api_client.get(f"http://localhost:8500/documents/{doc_id}")
            assert get_response.status_code == 404
    
    async def test_document_not_found(self, api_client):
        """Test getting non-existent document"""
        fake_id = "non-existent-document-id"
        response = await api_client.get(f"http://localhost:8500/documents/{fake_id}")
        assert response.status_code == 404
    
    async def test_delete_nonexistent_document(self, api_client):
        """Test deleting non-existent document"""
        fake_id = "non-existent-document-id"
        response = await api_client.delete(f"http://localhost:8500/documents/{fake_id}")
        assert response.status_code == 404


@pytest.mark.e2e
@pytest.mark.api
class TestAPIErrorHandling:
    """Test API error handling"""
    
    async def test_invalid_json(self):
        """Test handling of invalid JSON"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8500/query",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422
    
    async def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        async with httpx.AsyncClient() as client:
            # Missing question field
            response = await client.post(
                "http://localhost:8500/query",
                json={"k": 5}
            )
            assert response.status_code == 422
    
    async def test_invalid_parameter_values(self):
        """Test handling of invalid parameter values"""
        async with httpx.AsyncClient() as client:
            # Invalid k value (negative)
            response = await client.post(
                "http://localhost:8500/query?k=-1",
                json={"question": "test"}
            )
            assert response.status_code == 422
            
            # Invalid temperature (too high)
            response = await client.post(
                "http://localhost:8500/query?temperature=3.0",
                json={"question": "test"}
            )
            assert response.status_code == 422
