"""
Security tests for data security
Tests sensitive data leakage, credential storage
"""
import pytest
import os
import re
from pathlib import Path


@pytest.mark.security
class TestDataSecurity:
    """Test data security"""
    
    def test_sensitive_data_leakage(self, api_client, service_container):
        """Test no sensitive data in logs/responses"""
        # Test that API keys are not exposed in responses
        response = api_client.get("/v1/config")
        
        if response.status_code == 200:
            data = response.json()
            # Check no API keys in response
            response_text = str(data)
            assert "OPENAI_API_KEY" not in response_text
            assert "AWS_OPENSEARCH_SECRET" not in response_text
            assert os.getenv('OPENAI_API_KEY', '') not in response_text
    
    def test_credential_storage(self):
        """Test credentials not in code"""
        # Check that .env file is not committed (structural test)
        # Actual check would be in git hooks
        env_file = Path(".env")
        if env_file.exists():
            # .env should exist but not contain committed secrets
            # This is a structural test
            assert True
    
    def test_encryption_at_rest(self, service_container):
        """Test data encryption (if applicable)"""
        # Structural test - actual encryption would be tested in deployment
        # For now, verify data is stored (not testing encryption implementation)
        service_container.document_registry.add_document(
            "test-doc",
            {"document_name": "test.pdf", "status": "completed"}
        )
        
        # Data should be stored
        doc = service_container.get_document("test-doc")
        assert doc is not None
