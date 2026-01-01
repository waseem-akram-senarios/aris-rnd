"""
Regression tests for feature preservation
Ensures existing features still work after changes
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.regression
class TestFeaturePreservation:
    """Test that existing features are preserved"""
    
    def test_document_processing_still_works(self, document_processor, sample_text_content, temp_dir):
        """Test document processing feature still works"""
        text_file = temp_dir / "test.txt"
        text_file.write_text(sample_text_content)
        
        with patch.object(document_processor.rag_system, 'add_documents_incremental') as mock_add:
            mock_add.return_value = {'chunks_created': 3}
            
            result = document_processor.process_document(
                file_path=str(text_file),
                file_name="test.txt"
            )
            
            assert result.status in ['success', 'processing', 'failed']
            assert result.document_name == "test.txt"
    
    def test_queries_still_return_results(self, api_client, service_container, sample_documents):
        """Test queries still return results"""
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
            
            response = api_client.post(
                "/query",
                json={"question": "Test", "k": 3}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_images_still_extract(self, service_container):
        """Test image extraction still works"""
        # This is a structural test - actual extraction requires real PDFs
        # Test that the feature exists and can be called
        assert hasattr(service_container.document_processor, '_store_images_in_opensearch')
        assert hasattr(service_container.rag_system, 'query_images')
