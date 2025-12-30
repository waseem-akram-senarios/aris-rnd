"""
Regression tests for backward compatibility
Ensures old features still work after changes
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.mark.regression
class TestBackwardCompatibility:
    """Test backward compatibility"""
    
    def test_old_vectorstore_format(self, rag_system_faiss, temp_vectorstore_dir):
        """Test loading old vectorstore format"""
        # This tests that old FAISS stores can still be loaded
        # Implementation may vary, but structure should be compatible
        from langchain_core.documents import Document
        
        docs = [
            Document(page_content="Old format content", metadata={"source": "old.pdf"})
        ]
        
        # Create and save store
        rag_system_faiss.add_documents_incremental(
            texts=["Old format content"],
            metadatas=[{"source": "old.pdf"}]
        )
        
        # Should be able to query old format
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            result = rag_system_faiss.query_with_rag("Test question", k=3)
            assert isinstance(result, dict)
            assert "answer" in result
    
    def test_old_document_registry_format(self, temp_registry_file):
        """Test migrating old document registry format"""
        from storage.document_registry import DocumentRegistry
        
        # Create old format registry
        old_format = {
            "doc-1": {
                "name": "old.pdf",  # Old field name
                "status": "completed"
            }
        }
        
        import json
        with open(temp_registry_file, 'w') as f:
            json.dump(old_format, f)
        
        # Should handle old format gracefully
        registry = DocumentRegistry(str(temp_registry_file))
        docs = registry.list_documents()
        
        # Should either migrate or handle gracefully
        assert isinstance(docs, list)
    
    def test_api_response_format(self, api_client):
        """Test API response format hasn't changed"""
        response = api_client.get("/")
        data = response.json()
        
        # Verify expected fields exist
        assert "name" in data
        assert "version" in data
        assert "status" in data
    
    def test_query_response_format(self, api_client, service_container, sample_documents):
        """Test query response format compatibility"""
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
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={"question": "Test", "k": 3}
            )
            
            data = response.json()
            # Verify response structure matches expected format
            assert "answer" in data
            assert "sources" in data
            assert "citations" in data
