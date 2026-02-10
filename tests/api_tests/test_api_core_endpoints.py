"""
API tests for core endpoints
Tests GET /, GET /health, GET /documents, POST /documents, DELETE /documents/{id}
"""
import sys
import os
from pathlib import Path

# Ensure project root is in path (before any imports)
project_root = Path(__file__).parent.parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Change to project root
os.chdir(project_root_str)

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import assertions after path setup
try:
    from tests.utils.assertions import assert_response_status, assert_json_response
except ImportError:
    # Fallback if import fails
    def assert_response_status(response, expected_status=200):
        assert response.status_code == expected_status
    
    def assert_json_response(response, expected_keys=None):
        assert response.headers.get("content-type", "").startswith("application/json")
        data = response.json()
        if expected_keys:
            for key in expected_keys:
                assert key in data
        return data


@pytest.mark.api
class TestCoreEndpoints:
    """Test core API endpoints"""
    
    def test_root_endpoint(self, api_client):
        """Test GET / root endpoint"""
        response = api_client.get("/")
        
        assert_response_status(response, 200)
        data = assert_json_response(response, ["name", "version", "status"])
        assert data["name"] == "ARIS RAG API - Minimal"
        assert data["version"] == "2.0.0"
        assert data["status"] == "operational"
    
    def test_health_check(self, api_client):
        """Test GET /health endpoint"""
        response = api_client.get("/health")
        
        assert_response_status(response, 200)
        data = assert_json_response(response, ["status"])
        assert data["status"] == "healthy"
    
    def test_list_documents_empty(self, api_client):
        """Test GET /documents with no documents"""
        response = api_client.get("/documents")
        
        assert_response_status(response, 200)
        data = assert_json_response(response, ["documents", "total"])
        assert isinstance(data["documents"], list)
        assert data["total"] == 0
    
    def test_list_documents_with_data(self, api_client, service_container):
        """Test GET /documents with documents"""
        # Add documents to registry
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test1.pdf", "status": "completed", "chunks_created": 5}
        )
        service_container.document_registry.add_document(
            "doc-2",
            {"document_name": "test2.pdf", "status": "completed", "chunks_created": 10}
        )
        
        response = api_client.get("/documents")
        
        assert_response_status(response, 200)
        data = assert_json_response(response, ["documents", "total"])
        assert data["total"] == 2
        assert len(data["documents"]) == 2
    
    def test_upload_document(self, api_client, temp_dir):
        """Test POST /documents upload"""
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")
        
        with open(pdf_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        assert_response_status(response, 201)
        data = assert_json_response(response, ["document_id", "document_name", "status"])
        assert data["document_name"] == "test.pdf"
        assert data["status"] in ["processing", "completed"]
    
    def test_upload_document_invalid_type(self, api_client, temp_dir):
        """Test POST /documents with invalid file type"""
        exe_file = temp_dir / "test.exe"
        exe_file.write_bytes(b"executable")
        
        with open(exe_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.exe", f, "application/x-msdownload")}
            )
        
        assert_response_status(response, 400)
        data = response.json()
        assert "Unsupported file type" in data["detail"] or "invalid" in data["detail"].lower()
    
    def test_upload_document_with_parser(self, api_client, temp_dir):
        """Test POST /documents with parser preference"""
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        with open(pdf_file, 'rb') as f:
            response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"parser_preference": "docling"}
            )
        
        assert_response_status(response, 201)
        data = assert_json_response(response)
        assert "document_id" in data
    
    def test_delete_document(self, api_client, service_container):
        """Test DELETE /documents/{id}"""
        # Add document
        service_container.document_registry.add_document(
            "doc-to-delete",
            {"document_name": "delete_me.pdf", "status": "completed"}
        )
        
        response = api_client.delete("/documents/doc-to-delete")
        
        assert_response_status(response, 204)
        
        # Verify deleted
        doc = service_container.get_document("doc-to-delete")
        assert doc is None
    
    def test_delete_nonexistent_document(self, api_client):
        """Test DELETE /documents/{id} with non-existent document"""
        response = api_client.delete("/documents/non-existent-id")
        
        assert_response_status(response, 404)
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_list_documents_response_structure(self, api_client, service_container):
        """Test GET /documents response structure"""
        service_container.document_registry.add_document(
            "doc-1",
            {
                "document_id": "doc-1",
                "document_name": "test.pdf",
                "status": "completed",
                "chunks_created": 5,
                "image_count": 2
            }
        )
        
        response = api_client.get("/documents")
        data = assert_json_response(response)
        
        assert "documents" in data
        assert "total" in data
        assert "total_chunks" in data
        assert "total_images" in data
        assert data["total_chunks"] == 5
        assert data["total_images"] == 2
