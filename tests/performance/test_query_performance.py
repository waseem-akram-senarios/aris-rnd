"""
Performance tests for query operations
Tests query latency and performance
"""
import pytest
import time
from unittest.mock import patch, MagicMock


@pytest.mark.performance
@pytest.mark.slow
class TestQueryPerformance:
    """Test query performance"""
    
    def test_query_latency(self, api_client, service_container, sample_documents, performance_timer):
        """Test query response time < 2s"""
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
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            performance_timer.start()
            response = api_client.post(
                "/query",
                json={"question": "Test question", "k": 3}
            )
            performance_timer.stop()
            
            assert response.status_code == 200
            elapsed = performance_timer.elapsed()
            assert elapsed < 2.0, f"Query took {elapsed:.2f}s, expected < 2.0s"
    
    def test_concurrent_queries(self, api_client, service_container, sample_documents):
        """Test multiple simultaneous queries"""
        import threading
        
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
        
        results = []
        errors = []
        
        def make_query():
            try:
                with patch('openai.OpenAI') as mock_openai:
                    mock_client = MagicMock()
                    mock_openai.return_value = mock_client
                    mock_response = MagicMock()
                    mock_response.choices = [MagicMock()]
                    mock_response.choices[0].message.content = "Answer"
                    mock_response.usage = MagicMock()
                    mock_response.usage.total_tokens = 50
                    mock_client.chat.completions.create.return_value = mock_response
                    
                    response = api_client.post(
                        "/query",
                        json={"question": "Test", "k": 3}
                    )
                    results.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Create 5 concurrent queries
        threads = [threading.Thread(target=make_query) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(results) == 5
        assert all(status == 200 for status in results)
        assert len(errors) == 0
    
    def test_large_result_set(self, api_client, service_container, sample_documents):
        """Test query with k=50 (large result set)"""
        # Add documents to registry first
        for i in range(len(sample_documents) * 20):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
            )
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents * 20,  # More documents
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents) * 20)]
        )
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            start = time.time()
            response = api_client.post(
                "/query",
                json={"question": "Test", "k": 20}  # Reduced from 50 to fit schema limit (le=20)
            )
            elapsed = time.time() - start
            
            assert response.status_code == 200
            # Large k may take longer, but should complete
            assert elapsed < 10.0  # Should complete within 10s
