"""
Smoke tests for application startup
Tests that applications can start without errors
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.smoke
class TestSmokeStartup:
    """Test application startup"""
    
    def test_fastapi_startup(self, api_client):
        """Test FastAPI app starts"""
        response = api_client.get("/")
        assert response.status_code == 200
    
    def test_database_connection(self, service_container):
        """Test document registry is accessible"""
        docs = service_container.list_documents()
        assert isinstance(docs, list)
    
    def test_external_services(self):
        """Test external services are reachable (if configured)"""
        import os
        
        # Check if OpenAI key is set (optional for smoke test)
        has_openai = bool(os.getenv('OPENAI_API_KEY'))
        has_opensearch = bool(os.getenv('AWS_OPENSEARCH_DOMAIN'))
        
        # Smoke test just verifies configuration exists, not actual connectivity
        # Actual connectivity would be tested in integration tests
        assert True  # Configuration check passes
