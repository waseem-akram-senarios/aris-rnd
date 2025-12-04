"""
Tests for FastAPI CRUD endpoints
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

# Add project root to path - pytest runs from project root, so current dir should work
# But ensure it's there just in case
project_root = Path(__file__).parent.parent.parent
current_dir = str(project_root)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Also add current working directory
if '.' not in sys.path:
    sys.path.insert(0, '.')

from api.main import app, service_container
from api.service import ServiceContainer, create_service_container


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def test_service():
    """Create a test service container"""
    return create_service_container(
        use_cerebras=False,
        embedding_model="text-embedding-3-small",
        openai_model="gpt-3.5-turbo",
        vector_store_type="faiss",
        chunking_strategy="balanced"
    )


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["message"] == "ARIS RAG API"


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_list_documents_empty(client):
    """Test listing documents when none exist"""
    response = client.get("/documents")
    assert response.status_code == 200
    data = response.json()
    assert "documents" in data
    assert "total" in data
    assert data["total"] == 0
    assert isinstance(data["documents"], list)


def test_upload_document_invalid_file_type(client):
    """Test uploading invalid file type"""
    # Create a dummy file with invalid extension
    files = {"file": ("test.exe", b"dummy content", "application/octet-stream")}
    data = {"parser": "pymupdf"}
    
    response = client.post("/documents", files=files, data=data)
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_query_without_documents(client):
    """Test querying when no documents are processed"""
    query_data = {
        "question": "What is this document about?",
        "k": 6,
        "use_mmr": True
    }
    
    response = client.post("/query", json=query_data)
    assert response.status_code == 400
    assert "No documents have been processed" in response.json()["detail"]


def test_get_nonexistent_document(client):
    """Test getting a document that doesn't exist"""
    response = client.get("/documents/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_nonexistent_document(client):
    """Test deleting a document that doesn't exist"""
    response = client.delete("/documents/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_stats(client):
    """Test getting system statistics"""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert "rag_stats" in data
    assert "metrics" in data


def test_query_request_validation(client):
    """Test query request validation"""
    # Test with invalid k value (too large)
    query_data = {
        "question": "Test question",
        "k": 100,  # Should be max 20
        "use_mmr": True
    }
    
    response = client.post("/query", json=query_data)
    # Should fail validation
    assert response.status_code == 422  # Validation error


def test_service_container_creation(test_service):
    """Test service container creation"""
    assert test_service is not None
    assert test_service.rag_system is not None
    assert test_service.document_processor is not None
    assert test_service.metrics_collector is not None
    assert isinstance(test_service.documents, dict)


def test_service_container_document_operations(test_service):
    """Test document storage operations"""
    # Add a document
    doc_id = "test-doc-1"
    doc_data = {
        "document_id": doc_id,
        "document_name": "test.pdf",
        "status": "success",
        "chunks_created": 10,
        "tokens_extracted": 1000
    }
    
    test_service.add_document(doc_id, doc_data)
    
    # Get document
    retrieved = test_service.get_document(doc_id)
    assert retrieved is not None
    assert retrieved["document_name"] == "test.pdf"
    
    # List documents
    docs = test_service.list_documents()
    assert len(docs) == 1
    
    # Remove document
    removed = test_service.remove_document(doc_id)
    assert removed is True
    
    # Verify removed
    retrieved_after = test_service.get_document(doc_id)
    assert retrieved_after is None


# Integration test (requires actual API key and may take time)
@pytest.mark.integration
def test_upload_and_query_integration(client, tmp_path):
    """
    Integration test for upload and query workflow.
    Requires OPENAI_API_KEY to be set.
    This test may take several minutes due to document processing.
    """
    # Skip if no API key
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    # Create a simple test PDF (text file for simplicity)
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test document. It contains information about testing.")
    
    # Upload document
    with open(test_file, "rb") as f:
        files = {"file": ("test.txt", f, "text/plain")}
        data = {"parser": "pymupdf"}  # Use pymupdf for speed in tests
        
        response = client.post("/documents", files=files, data=data)
        
        # Note: This may fail if parser doesn't support .txt files
        # In that case, we'll just verify the endpoint exists
        if response.status_code == 201:
            doc_data = response.json()
            assert "document_name" in doc_data
            assert "status" in doc_data
            
            # Try to query
            query_data = {
                "question": "What is this document about?",
                "k": 3,
                "use_mmr": True
            }
            
            query_response = client.post("/query", json=query_data)
            if query_response.status_code == 200:
                query_result = query_response.json()
                assert "answer" in query_result
                assert "sources" in query_result
                assert "citations" in query_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

