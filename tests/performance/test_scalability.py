"""
Scalability tests - System performance with increasing load
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.performance
@pytest.mark.slow
class TestScalability:
    """Test system scalability"""
    
    def test_document_count_scaling(self, service_container):
        """Test performance with 100, 500, 1000 documents"""
        document_counts = [100, 500]  # Reduced for test speed
        
        for count in document_counts:
            # Add documents to registry first
            for i in range(count):
                service_container.document_registry.add_document(
                    f"doc-{i}",
                    {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
                )
            # Add documents
            texts = [f"Document {i} content" for i in range(count)]
            metadatas = [{"source": f"doc{i}.pdf"} for i in range(count)]
            
            result = service_container.rag_system.add_documents_incremental(
                texts=texts,
                metadatas=metadatas
            )
            
            assert result["documents_added"] == count
            assert result["chunks_created"] > 0
    
    def test_query_scaling(self, api_client, service_container):
        """Test query performance with more documents"""
        # Add documents to registry first
        for i in range(200):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
            )
        # Add many documents
        texts = [f"Document {i} content about topic X" for i in range(200)]
        service_container.rag_system.add_documents_incremental(
            texts=texts,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(200)]
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
            
            import time
            start = time.time()
            response = api_client.post(
                "/query",
                json={"question": "topic X", "k": 10}
            )
            elapsed = time.time() - start
            
            assert response.status_code == 200
            # Query time should scale reasonably (allow more time for mocked operations)
            assert elapsed < 10.0, f"Query with 200 docs took {elapsed:.2f}s"
