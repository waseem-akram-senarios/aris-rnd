"""
Functional tests for query features
Tests query functionality against requirements
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.mark.functional
class TestQueryFeatures:
    """Test query functionality"""
    
    def test_semantic_search(self, api_client, service_container, sample_documents):
        """Test semantic search feature"""
        # Add documents to registry first
        for i in range(len(sample_documents)):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
            )
        # Add documents to service
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents))]
        )
        
        # Mock LLM
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Semantic search answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "What is the content about?",
                    "k": 3,
                    "search_mode": "semantic"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert "citations" in data
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
    
    def test_keyword_search(self, api_client, service_container, sample_documents):
        """Test keyword search feature"""
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
            mock_response.choices[0].message.content = "Keyword search answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "machine learning",
                    "k": 3,
                    "search_mode": "keyword"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_hybrid_search(self, api_client, service_container, sample_documents):
        """Test hybrid search feature"""
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
            mock_response.choices[0].message.content = "Hybrid search answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "What is AI?",
                    "k": 3,
                    "search_mode": "hybrid"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_document_filtering(self, api_client, service_container, sample_documents):
        """Test querying specific document"""
        # Add documents
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": "doc1.pdf"}, {"source": "doc2.pdf"}]
        )
        
        # Add to registry
        service_container.document_registry.add_document(
            "doc1-id",
            {"document_name": "doc1.pdf", "status": "completed"}
        )
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Filtered answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query?document_id=doc1-id",
                json={
                    "question": "Test question",
                    "k": 3
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_focus_modes(self, api_client, service_container, sample_documents):
        """Test query focus modes"""
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
        
        focus_modes = ["all", "important", "summary", "specific"]
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            for focus in focus_modes:
                response = api_client.post(
                    f"/query?focus={focus}",
                    json={
                        "question": "Test question",
                        "k": 3
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "answer" in data
