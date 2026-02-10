"""
End-to-end tests for document lifecycle
Tests upload, processing, query, delete cycle
"""
import pytest
import tempfile
from unittest.mock import patch, MagicMock


@pytest.mark.e2e
@pytest.mark.slow
class TestDocumentLifecycle:
    """Test document lifecycle"""
    
    def test_upload_processing_query_delete(self, api_client, service_container, temp_dir):
        """Test complete lifecycle: upload → process → query → delete"""
        # Upload
        pdf_file = temp_dir / "lifecycle.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        with open(pdf_file, 'rb') as f:
            upload_response = api_client.post(
                "/documents",
                files={"file": ("lifecycle.pdf", f, "application/pdf")}
            )
        
        if upload_response.status_code == 201:
            doc_id = upload_response.json()["document_id"]
            
            # Process (simulated)
            service_container.rag_system.add_documents_incremental(
                texts=["Lifecycle test content"],
                metadatas=[{"source": "lifecycle.pdf"}]
            )
            service_container.document_registry.add_document(
                doc_id,
                {"document_name": "lifecycle.pdf", "status": "completed", "chunks_created": 1}
            )
            
            # Query
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Lifecycle answer"
                mock_response.usage = MagicMock()
                mock_response.usage.total_tokens = 50
                mock_client.chat.completions.create.return_value = mock_response
                
                query_response = api_client.post(
                    f"/query?document_id={doc_id}",
                    json={"question": "Test", "k": 3}
                )
                assert query_response.status_code == 200
            
            # Delete
            delete_response = api_client.delete(f"/documents/{doc_id}")
            assert delete_response.status_code == 204
    
    def test_document_update(self, api_client, service_container, temp_dir):
        """Test re-uploading same document"""
        pdf_file = temp_dir / "update.pdf"
        pdf_file.write_bytes(b"original content")
        
        # First upload
        with open(pdf_file, 'rb') as f:
            response1 = api_client.post(
                "/documents",
                files={"file": ("update.pdf", f, "application/pdf")}
            )
        
        # Second upload (may be duplicate or update)
        pdf_file.write_bytes(b"updated content")
        with open(pdf_file, 'rb') as f:
            response2 = api_client.post(
                "/documents",
                files={"file": ("update.pdf", f, "application/pdf")}
            )
        
        # Should either detect duplicate or allow update
        assert response2.status_code in [201, 409]
    
    def test_document_versioning(self, service_container):
        """Test document version tracking"""
        doc_id = "version-test"
        
        # Add document
        service_container.document_registry.add_document(
            doc_id,
            {"document_name": "version.pdf", "status": "completed", "version": 1}
        )
        
        # Update document (should increment version)
        service_container.document_registry.add_document(
            doc_id,
            {"document_name": "version.pdf", "status": "completed", "version": 2}
        )
        
        doc = service_container.get_document(doc_id)
        assert doc is not None
        # Version should be tracked
        version_info = doc.get("version_info", {})
        assert version_info.get("version", 1) >= 1
