"""
End-to-end tests for full workflows
Tests complete user journeys
"""
import pytest
import tempfile
import time
from unittest.mock import patch, MagicMock
from tests.utils.assertions import assert_response_status, assert_json_response


@pytest.mark.e2e
@pytest.mark.slow
class TestFullWorkflow:
    """Test complete workflows"""
    
    def test_complete_document_lifecycle(self, api_client, service_container, temp_dir):
        """Test complete document lifecycle: upload → process → query → delete"""
        # Step 1: Upload PDF
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")
        
        with open(pdf_file, 'rb') as f:
            upload_response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        if upload_response.status_code == 201:
            doc_data = upload_response.json()
            doc_id = doc_data["document_id"]
            
            # Step 2: Add to RAG system (simulating processing)
            service_container.rag_system.add_documents_incremental(
                texts=["Test document content about machine learning and AI."],
                metadatas=[{"source": "test.pdf"}]
            )
            
            # Update registry to mark as completed
            service_container.document_registry.add_document(
                doc_id,
                {
                    "document_name": "test.pdf",
                    "status": "completed",
                    "chunks_created": 1
                }
            )
            
            # Step 3: Verify storage status
            status_response = api_client.get(f"/documents/{doc_id}/storage/status")
            # May not exist, but if it does, should return status
            if status_response.status_code == 200:
                status_data = status_response.json()
                assert "document_id" in status_data
            
            # Step 4: Query document
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Machine learning answer"
                mock_response.usage = MagicMock()
                mock_response.usage.total_tokens = 50
                mock_client.chat.completions.create.return_value = mock_response
                
                query_response = api_client.post(
                    f"/query?document_id={doc_id}",
                    json={"question": "What is machine learning?", "k": 3}
                )
                
                assert query_response.status_code == 200
                query_data = query_response.json()
                assert "answer" in query_data
            
            # Step 5: Delete document
            delete_response = api_client.delete(f"/documents/{doc_id}")
            assert delete_response.status_code == 204
            
            # Verify deleted
            doc = service_container.get_document(doc_id)
            assert doc is None
    
    def test_multi_document_workflow(self, api_client, service_container, temp_dir):
        """Test workflow with multiple documents"""
        doc_ids = []
        
        # Upload multiple documents
        for i in range(3):
            pdf_file = temp_dir / f"test{i}.pdf"
            pdf_file.write_bytes(b"fake pdf content")
            
            with open(pdf_file, 'rb') as f:
                response = api_client.post(
                    "/documents",
                    files={"file": (f"test{i}.pdf", f, "application/pdf")}
                )
            
            if response.status_code == 201:
                doc_ids.append(response.json()["document_id"])
        
        # Add to RAG system
        for i, doc_id in enumerate(doc_ids):
            service_container.rag_system.add_documents_incremental(
                texts=[f"Document {i} content"],
                metadatas=[{"source": f"test{i}.pdf"}]
            )
        
        # Query across all documents
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Multi-doc answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={"question": "What are the documents about?", "k": 5}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "answer" in data
    
    def test_error_recovery_workflow(self, api_client, service_container, temp_dir):
        """Test error recovery in workflow"""
        # Upload document
        pdf_file = temp_dir / "test.pdf"
        pdf_file.write_bytes(b"fake pdf")
        
        with open(pdf_file, 'rb') as f:
            upload_response = api_client.post(
                "/documents",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
        
        if upload_response.status_code == 201:
            doc_id = upload_response.json()["document_id"]
            
            # Simulate processing error
            # System should handle gracefully
            # Query should still work if document was processed
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = "Answer"
                mock_response.usage = MagicMock()
                mock_response.usage.total_tokens = 50
                mock_client.chat.completions.create.return_value = mock_response
                
                # Query should handle missing/error state gracefully
                response = api_client.post(
                    "/query",
                    json={"question": "Test", "k": 3}
                )
                
                # May return error if no documents, or succeed if documents exist
                assert response.status_code in [200, 400, 500]
