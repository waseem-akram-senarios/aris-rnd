"""
Tests for sync endpoints
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


def test_sync_status_endpoint(client):
    """Test GET /sync/status endpoint"""
    response = client.get("/sync/status")
    assert response.status_code == 200
    
    data = response.json()
    assert 'document_registry' in data
    assert 'vectorstore' in data
    assert 'rag_stats' in data
    assert 'conflicts' in data
    
    # Check document registry structure
    registry = data['document_registry']
    assert 'total_documents' in registry
    assert 'last_update' in registry
    assert 'registry_path' in registry
    assert 'registry_exists' in registry
    
    # Check vectorstore structure
    vectorstore = data['vectorstore']
    assert 'type' in vectorstore
    assert 'exists' in vectorstore


def test_sync_status_shows_document_count(client):
    """Test that sync status shows correct document count"""
    response = client.get("/sync/status")
    assert response.status_code == 200
    
    data = response.json()
    registry = data['document_registry']
    assert isinstance(registry['total_documents'], int)
    assert registry['total_documents'] >= 0


def test_reload_vectorstore_endpoint_faiss(client):
    """Test POST /sync/reload-vectorstore endpoint with FAISS"""
    response = client.post("/sync/reload-vectorstore")
    
    # May succeed or fail depending on whether vectorstore exists
    # Both are valid responses
    assert response.status_code in [200, 404, 400]
    
    if response.status_code == 200:
        data = response.json()
        assert 'message' in data
        assert 'path' in data


def test_save_vectorstore_endpoint(client):
    """Test POST /sync/save-vectorstore endpoint"""
    response = client.post("/sync/save-vectorstore")
    
    # May succeed or fail depending on whether vectorstore exists
    assert response.status_code in [200, 400]
    
    if response.status_code == 200:
        data = response.json()
        assert 'message' in data
        assert 'path' in data


def test_reload_registry_endpoint(client):
    """Test POST /sync/reload-registry endpoint"""
    response = client.post("/sync/reload-registry")
    assert response.status_code == 200
    
    data = response.json()
    assert 'message' in data
    assert 'conflict_resolved' in data


def test_sync_status_conflict_detection(client):
    """Test that sync status includes conflict information"""
    response = client.get("/sync/status")
    assert response.status_code == 200
    
    data = response.json()
    assert 'conflicts' in data
    # Conflicts may be None or a dict
    assert data['conflicts'] is None or isinstance(data['conflicts'], dict)


def test_reload_vectorstore_resolves_conflicts(client):
    """Test that reload vectorstore resolves conflicts"""
    # First check status
    status_response = client.get("/sync/status")
    assert status_response.status_code == 200
    
    # Reload vectorstore (should handle conflicts if any)
    reload_response = client.post("/sync/reload-vectorstore")
    
    # Should succeed or return appropriate error
    assert reload_response.status_code in [200, 404, 400]
    
    if reload_response.status_code == 200:
        data = reload_response.json()
        assert 'conflict_resolved' in data

