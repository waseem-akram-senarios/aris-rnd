"""
API tests for focused endpoints (v1/config, v1/library, v1/metrics, etc.)
"""
import pytest
import json
import os
from unittest.mock import patch
from tests.utils.assertions import assert_response_status, assert_json_response
from shared.config.settings import ARISConfig


@pytest.mark.api
class TestFocusedEndpoints:
    """Test focused API endpoints"""
    
    def test_get_config(self, api_client):
        """Test GET /v1/config"""
        response = api_client.get("/v1/config")
        
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert isinstance(data, dict)
    
    def test_get_config_section(self, api_client):
        """Test GET /v1/config?section=model"""
        response = api_client.get("/v1/config?section=model")
        
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert isinstance(data, dict)
    
    def test_post_config(self, api_client):
        """Test POST /v1/config"""
        response = api_client.post(
            "/v1/config",
            json={
                "model_settings": {
                    "embedding_model": "text-embedding-3-small"
                }
            }
        )
        
        # May return 200 or 400 depending on validation
        assert response.status_code in [200, 400, 422]
    
    def test_get_library(self, api_client, service_container):
        """Test GET /v1/library"""
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed"}
        )
        
        response = api_client.get("/v1/library")
        
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert "documents" in data or "total_documents" in data
    
    def test_get_library_document(self, api_client, service_container, temp_registry_file):
        """Test GET /v1/library/{document_id}"""
        import json
        import os
        from shared.config.settings import ARISConfig
        
        # Add document to registry
        service_container.document_registry.add_document(
            "doc-1",
            {"document_id": "doc-1", "document_name": "test.pdf", "status": "completed"}
        )
        
        # The focused endpoint reads from registry file, so we need to ensure it exists
        # Patch the registry path to use our temp file
        registry_data = {"doc-1": {"document_id": "doc-1", "document_name": "test.pdf", "status": "completed"}}
        with open(temp_registry_file, 'w') as f:
            json.dump(registry_data, f)
        
        # Patch ARISConfig to use temp registry file
        with patch.object(ARISConfig, 'DOCUMENT_REGISTRY_PATH', str(temp_registry_file)):
            response = api_client.get("/v1/library/doc-1")
            
            assert_response_status(response, 200)
            data = assert_json_response(response)
            assert "document_name" in data or "document_id" in data
    
    def test_get_metrics(self, api_client):
        """Test GET /v1/metrics"""
        response = api_client.get("/v1/metrics")
        
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert isinstance(data, dict)
    
    def test_get_status(self, api_client):
        """Test GET /v1/status"""
        response = api_client.get("/v1/status")
        
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert isinstance(data, dict)
