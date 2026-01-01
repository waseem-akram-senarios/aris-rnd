"""
Quick sanity tests
Very fast tests (< 30 seconds total)
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.sanity
class TestSanityQuick:
    """Quick sanity checks"""
    
    def test_health_endpoint(self, api_client):
        """Test health check works"""
        response = api_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_list_documents(self, api_client):
        """Test document listing works"""
        response = api_client.get("/documents")
        assert response.status_code == 200
        assert "documents" in response.json()
    
    def test_simple_query(self, api_client, service_container, sample_documents):
        """Test basic query works"""
        # Add documents to registry first
        for i in range(len(sample_documents)):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
            )
        
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents))]
        )
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Quick answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 30
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={"question": "Quick test", "k": 2}
            )
            
            assert response.status_code == 200
            assert "answer" in response.json()
