"""
Sanity tests for critical paths
Quick checks after small fixes
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.sanity
class TestSanityCriticalPaths:
    """Test critical paths work"""
    
    def test_upload_and_query(self, api_client, service_container, temp_dir):
        """Test basic upload → query flow"""
        # Upload
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        with open(pdf_file, 'rb') as f:
            upload_response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        if upload_response.status_code == 201:
            doc_id = upload_response.json()["document_id"]
            
            # Add to RAG system for query
            service_container.rag_system.add_documents_incremental(
                texts=["Test content"],
                metadatas=[{"source": "test.pdf"}]
            )
            
            # Query
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Answer"
                mock_response.usage = MagicMock()
                mock_response.usage.total_tokens = 50
                mock_client.chat.completions.create.return_value = mock_response
                
                query_response = api_client.post(
                    "/query",
                    json={"question": "Test", "k": 3}
                )
                
                assert query_response.status_code == 200
    
    def test_image_extraction(self, service_container):
        """Test image extraction works"""
        # Structural test - verify method exists
        assert hasattr(service_container.document_processor, '_store_images_in_opensearch')
        assert hasattr(service_container.rag_system, 'query_images')
    
    def test_storage_status(self, api_client, service_container):
        """Test storage status accessible"""
        service_container.document_registry.add_document(
            "test-doc",
            {"document_name": "test.pdf", "status": "completed"}
        )
        
        status = service_container.get_storage_status("test-doc")
        assert isinstance(status, dict)
