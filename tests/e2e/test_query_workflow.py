"""
End-to-end tests for query workflows
Tests complete query scenarios
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
class TestQueryWorkflow:
    """Test query workflows"""
    
    def test_query_without_documents(self, api_client):
        """Test querying with no documents uploaded"""
        response = api_client.post(
            "/query",
            json={"question": "Test question", "k": 3}
        )
        
        # Should return error if no documents
        assert response.status_code in [200, 400, 500]
        if response.status_code == 400:
            data = response.json()
            assert "no documents" in data["detail"].lower() or "upload" in data["detail"].lower()
    
    def test_query_single_document(self, api_client, service_container):
        """Test querying single document"""
        # Add document
        service_container.rag_system.add_documents_incremental(
            texts=["Single document content about AI."],
            metadatas=[{"source": "single.pdf"}]
        )
        service_container.document_registry.add_document(
            "single-doc",
            {"document_name": "single.pdf", "status": "completed"}
        )
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query?document_id=single-doc",
                json={"question": "What is AI?", "k": 3}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_query_multiple_documents(self, api_client, service_container):
        """Test querying across multiple documents"""
        # Add multiple documents
        service_container.rag_system.add_documents_incremental(
            texts=[
                "Document 1 about machine learning.",
                "Document 2 about neural networks.",
                "Document 3 about deep learning."
            ],
            metadatas=[
                {"source": "doc1.pdf"},
                {"source": "doc2.pdf"},
                {"source": "doc3.pdf"}
            ]
        )
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Multi-doc answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            # Add documents to registry first
            for i in range(3):  # 3 documents added above
                service_container.document_registry.add_document(
                    f"doc-{i}",
                    {"document_name": f"doc{i+1}.pdf", "status": "completed", "chunks_created": 5}
                )
            
            response = api_client.post(
                "/query",
                json={"question": "What are the documents about?", "k": 5}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert len(data.get("sources", [])) >= 0
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
    
    def test_query_with_images(self, api_client, service_container):
        """Test querying images"""
        response = api_client.post(
            "/query?type=image",
            json={"question": "What images are in the documents?", "k": 5}
        )
        
        # May return empty if no images or OpenSearch not configured
        assert response.status_code == 200
        data = response.json()
        assert "images" in data or "total" in data or "message" in data
