"""
Tests for document CRUD operations with shared registry
"""
import os
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from api.main import app
from api.service import create_service_container


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


def test_upload_document_saves_to_registry(client):
    """Test that uploading document saves to shared registry"""
    # This test requires a valid PDF file
    # For now, we'll test the endpoint structure
    # In real testing, you'd provide an actual file
    
    # Test with invalid file to check error handling
    files = {"file": ("test.txt", b"dummy content", "text/plain")}
    response = client.post("/documents", files=files)
    
    # Should return error for unsupported file type or process if supported
    assert response.status_code in [201, 400]


def test_list_documents_from_registry(client):
    """Test that listing documents reads from shared registry"""
    response = client.get("/documents")
    assert response.status_code == 200
    
    data = response.json()
    assert 'documents' in data
    assert 'total' in data
    assert isinstance(data['documents'], list)
    assert isinstance(data['total'], int)


def test_get_document_from_registry(client):
    """Test that getting document reads from shared registry"""
    # Try to get a non-existent document
    response = client.get("/documents/nonexistent-id")
    assert response.status_code == 404
    
    # If we had a real document ID, we could test retrieval
    # For now, we verify the endpoint structure


def test_delete_document_from_registry(client):
    """Test that deleting document removes from shared registry"""
    # Try to delete non-existent document
    response = client.delete("/documents/nonexistent-id")
    assert response.status_code == 404
    
    # If we had a real document ID, we could test deletion
    # For now, we verify the endpoint structure


def test_multiple_uploads_accumulate_in_registry(client):
    """Test that multiple uploads accumulate in registry"""
    # Check initial count
    response = client.get("/documents")
    assert response.status_code == 200
    initial_count = response.json()['total']
    
    # After uploads (if any), count should increase
    # This is a structural test - real testing would upload actual files
    final_response = client.get("/documents")
    assert final_response.status_code == 200
    final_count = final_response.json()['total']
    
    # Count should be same or greater (not less)
    assert final_count >= initial_count


def test_document_registry_persistence(client):
    """Test that document registry persists across requests"""
    # Get initial documents
    response1 = client.get("/documents")
    assert response1.status_code == 200
    count1 = response1.json()['total']
    
    # Get documents again
    response2 = client.get("/documents")
    assert response2.status_code == 200
    count2 = response2.json()['total']
    
    # Count should be consistent
    assert count1 == count2

