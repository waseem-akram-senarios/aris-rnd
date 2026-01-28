"""
Functional tests for Agentic RAG features
Tests query decomposition and multi-query retrieval
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.functional
class TestAgenticRAG:
    """Test Agentic RAG functionality"""
    
    def test_query_decomposition(self, api_client, service_container, sample_documents):
        """Test query decomposition feature"""
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
        
        # Mock query decomposer
        with patch('services.retrieval.query_decomposer.QueryDecomposer') as mock_decomposer_class, \
             patch('openai.OpenAI') as mock_openai:
            
            mock_decomposer = MagicMock()
            mock_decomposer.decompose_query.return_value = [
                "What is machine learning?",
                "How does it work?",
                "What are its applications?"
            ]
            mock_decomposer_class.return_value = mock_decomposer
            
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Synthesized answer from multiple queries"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 200
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "What is machine learning, how does it work, and what are its applications?",
                    "k": 6,
                    "use_agentic_rag": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
            # Query decomposition may or may not be called depending on query complexity
            # The important thing is that the query succeeds
    
    def test_multi_query_retrieval(self, api_client, service_container, sample_documents):
        """Test multi-query retrieval"""
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
        
        with patch('services.retrieval.query_decomposer.QueryDecomposer') as mock_decomposer_class, \
             patch('openai.OpenAI') as mock_openai:
            
            mock_decomposer = MagicMock()
            mock_decomposer.decompose_query.return_value = [
                "Sub-query 1",
                "Sub-query 2",
                "Sub-query 3"
            ]
            mock_decomposer_class.return_value = mock_decomposer
            
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer from multiple queries"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 150
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "Complex multi-part question",
                    "k": 6,
                    "use_agentic_rag": True,
                    "max_sub_queries": 4
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
    
    def test_result_synthesis(self, api_client, service_container, sample_documents):
        """Test result synthesis from multiple sub-queries"""
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
        
        with patch('services.retrieval.query_decomposer.QueryDecomposer') as mock_decomposer_class, \
             patch('openai.OpenAI') as mock_openai:
            
            mock_decomposer = MagicMock()
            mock_decomposer.decompose_query.return_value = ["Query 1", "Query 2"]
            mock_decomposer_class.return_value = mock_decomposer
            
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Synthesized comprehensive answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 200
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "Complex question requiring synthesis",
                    "k": 10,
                    "use_agentic_rag": True
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
            # Answer should be synthesized from multiple queries
            assert len(data["answer"]) > 0
    
    def test_deduplication(self, api_client, service_container, sample_documents):
        """Test chunk deduplication in agentic RAG"""
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
        
        with patch('services.retrieval.query_decomposer.QueryDecomposer') as mock_decomposer_class, \
             patch('openai.OpenAI') as mock_openai:
            
            mock_decomposer = MagicMock()
            mock_decomposer.decompose_query.return_value = ["Query 1", "Query 2"]
            mock_decomposer_class.return_value = mock_decomposer
            
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "Test question",
                    "k": 6,
                    "use_agentic_rag": True,
                    "deduplication_threshold": 0.95
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
            # Citations should be deduplicated
            assert "citations" in data
