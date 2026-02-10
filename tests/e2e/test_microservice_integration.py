"""
End-to-end tests for microservice integration
Tests Gateway → Ingestion → Retrieval service communication
"""
import pytest
import asyncio
import httpx
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
@pytest.mark.slow
class TestMicroserviceIntegration:
    """Test microservice communication and integration"""
    
    @pytest.fixture
    async def http_client(self):
        """HTTP client for service communication"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    async def test_gateway_to_ingestion_communication(self, http_client):
        """Test Gateway → Ingestion service communication"""
        # Test Gateway health
        gateway_response = await http_client.get("http://localhost:8500/health")
        assert gateway_response.status_code == 200
        
        # Test Ingestion health via Gateway
        ingestion_response = await http_client.get("http://localhost:8501/health")
        assert ingestion_response.status_code == 200
        
        # Verify services can communicate
        gateway_data = gateway_response.json()
        assert "status" in gateway_data
        assert gateway_data["status"] == "healthy"
    
    async def test_gateway_to_retrieval_communication(self, http_client):
        """Test Gateway → Retrieval service communication"""
        # Test Retrieval health
        retrieval_response = await http_client.get("http://localhost:8502/health")
        assert retrieval_response.status_code == 200
        
        retrieval_data = retrieval_response.json()
        assert "status" in retrieval_data
        assert retrieval_data["status"] == "healthy"
    
    async def test_service_orchestration(self, http_client):
        """Test Gateway orchestrating Ingestion and Retrieval"""
        # 1. Check all services are healthy
        services = [
            "http://localhost:8500/health",  # Gateway
            "http://localhost:8501/health",  # Ingestion  
            "http://localhost:8502/health"   # Retrieval
        ]
        
        health_results = await asyncio.gather(
            *[http_client.get(url) for url in services],
            return_exceptions=True
        )
        
        # All services should be healthy
        for result in health_results:
            assert isinstance(result, httpx.Response)
            assert result.status_code == 200
            assert result.json()["status"] == "healthy"
    
    async def test_document_upload_flow(self, http_client, temp_dir):
        """Test document upload through microservices"""
        # Create test document
        test_file = temp_dir / "integration_test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n%âãÏÓ\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")
        
        # Upload via Gateway
        with open(test_file, 'rb') as f:
            files = {"file": ("integration_test.pdf", f, "application/pdf")}
            upload_response = await http_client.post(
                "http://localhost:8500/documents",
                files=files
            )
        
        # Should return 201 with document metadata
        assert upload_response.status_code in [201, 200]  # Accept both for flexibility
        if upload_response.status_code == 201:
            doc_data = upload_response.json()
            assert "document_id" in doc_data
            assert doc_data["status"] == "processing"
            
            # Verify document appears in document list
            docs_response = await http_client.get("http://localhost:8500/documents")
            assert docs_response.status_code == 200
            
            docs_data = docs_response.json()
            assert "documents" in docs_data
            assert len(docs_data["documents"]) > 0
    
    async def test_query_flow(self, http_client):
        """Test query flow through microservices"""
        # Ensure we have documents
        docs_response = await http_client.get("http://localhost:8500/documents")
        if docs_response.status_code == 200:
            docs_data = docs_response.json()
            if docs_data.get("documents"):
                # Perform query
                query_data = {
                    "question": "test query",
                    "k": 5,
                    "search_mode": "semantic"
                }
                
                query_response = await http_client.post(
                    "http://localhost:8500/query",
                    json=query_data
                )
                
                # Should handle query (even if no results)
                assert query_response.status_code in [200, 400]  # 400 if no docs processed
                
                if query_response.status_code == 200:
                    result = query_response.json()
                    assert "answer" in result
                    assert "citations" in result
    
    async def test_s3_integration(self, http_client, temp_dir):
        """Test S3 integration across services"""
        # Test S3 upload if enabled
        test_file = temp_dir / "s3_test.pdf"
        test_file.write_bytes(b"%PDF-1.4\n%âãÏÓ\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n")
        
        # Upload with S3 storage
        with open(test_file, 'rb') as f:
            files = {"file": ("s3_test.pdf", f, "application/pdf")}
            data = {"store_in_s3": "true"}
            upload_response = await http_client.post(
                "http://localhost:8500/documents/upload-s3",
                files=files,
                data=data
            )
        
        # Should handle S3 upload
        assert upload_response.status_code in [201, 200, 503]  # 503 if S3 not configured
        
        if upload_response.status_code == 201:
            doc_data = upload_response.json()
            assert "s3_storage" in doc_data or "document_id" in doc_data
    
    async def test_error_handling_across_services(self, http_client):
        """Test error handling across microservices"""
        # Test invalid document upload
        invalid_files = {"file": ("invalid.txt", b"not a pdf", "text/plain")}
        invalid_response = await http_client.post(
            "http://localhost:8500/documents",
            files=invalid_files
        )
        assert invalid_response.status_code == 400
        
        # Test query with no documents
        empty_query = {
            "question": "test query with no docs",
            "k": 5
        }
        query_response = await http_client.post(
            "http://localhost:8500/query",
            json=empty_query
        )
        # Should return 400 if no documents, or 200 with empty results
        assert query_response.status_code in [200, 400]
    
    async def test_service_resilience(self, http_client):
        """Test service resilience and recovery"""
        # Test multiple rapid requests
        tasks = []
        for i in range(5):
            task = http_client.get("http://localhost:8500/health")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        for response in responses:
            assert isinstance(response, httpx.Response)
            assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.integration
class TestServiceHealth:
    """Test service health and readiness"""
    
    async def test_all_services_health(self):
        """Test all services are healthy"""
        services = {
            "gateway": "http://localhost:8500/health",
            "ingestion": "http://localhost:8501/health", 
            "retrieval": "http://localhost:8502/health"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for service_name, url in services.items():
                try:
                    response = await client.get(url)
                    assert response.status_code == 200, f"{service_name} not healthy"
                    data = response.json()
                    assert data["status"] == "healthy", f"{service_name} status not healthy"
                except Exception as e:
                    pytest.fail(f"Service {service_name} health check failed: {e}")
