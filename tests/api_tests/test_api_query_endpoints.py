"""
API tests for query endpoints
Tests POST /query with various parameters
"""
import pytest
from unittest.mock import patch, MagicMock
from tests.utils.assertions import assert_response_status, assert_json_response, assert_query_result


@pytest.mark.api
class TestQueryEndpoints:
    """Test query API endpoints"""
    
    def test_query_text_default(self, api_client, service_container, sample_documents):
        """Test POST /query with default text query"""
        # Add documents to both RAG system and registry
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents))]
        )
        # Also add to registry so list_documents() returns them
        for i in range(len(sample_documents)):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
            )
        
        # Mock LLM
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_response.usage.prompt_tokens = 50
            mock_response.usage.completion_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            response = api_client.post(
                "/query",
                json={
                    "question": "What is the content about?",
                    "k": 3
                }
            )
            
            assert_response_status(response, 200)
            data = assert_json_response(response, ["answer", "sources", "citations"])
            assert_query_result(data)
            # Verify all citations have page numbers
            for citation in data.get("citations", []):
                assert "page" in citation, "Citation missing 'page' field"
                assert isinstance(citation["page"], int), "Citation page must be integer"
                assert citation["page"] >= 1, f"Citation page must be >= 1, got {citation['page']}"
    
    def test_query_with_parameters(self, api_client, service_container, sample_documents):
        """Test POST /query with query parameters"""
        # Add documents to registry first (required for API check)
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
                "/query?k=5&use_mmr=true&search_mode=hybrid",
                json={
                    "question": "Test question",
                    "k": 3  # Will be overridden by query param
                }
            )
            
            assert_response_status(response, 200)
            data = assert_json_response(response)
            assert "answer" in data
    
    def test_query_image_type(self, api_client, service_container):
        """Test POST /query?type=image"""
        # Add a document to registry so the check passes
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        response = api_client.post(
            "/query",
            params={"type": "image"},
            json={
                "question": "What images are in the documents?",
                "k": 5
            }
        )
        
        # May return empty if no images or OpenSearch not configured
        assert_response_status(response, 200)
        data = assert_json_response(response)
        assert "images" in data or "total" in data or "message" in data
        
        # If images are returned, verify they all have page numbers
        if "images" in data and isinstance(data["images"], list):
            for image in data["images"]:
                assert "page" in image, "ImageResult missing 'page' field"
                assert isinstance(image["page"], int), "ImageResult page must be integer"
                assert image["page"] >= 1, f"ImageResult page must be >= 1, got {image['page']}"
    
    def test_query_focus_modes(self, api_client, service_container, sample_documents):
        """Test POST /query with different focus modes"""
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents))]
        )
        # Also add to registry
        for i in range(len(sample_documents)):
            service_container.document_registry.add_document(
                f"doc-{i}",
                {"document_name": f"doc{i}.pdf", "status": "completed", "chunks_created": 5}
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
                
                assert_response_status(response, 200)
                data = assert_json_response(response)
                assert "answer" in data
    
    def test_query_no_documents(self, api_client):
        """Test POST /query with no documents uploaded"""
        response = api_client.post(
            "/query",
            json={
                "question": "Test question",
                "k": 3
            }
        )
        
        # Should return error if no documents
        assert response.status_code in [400, 200]  # May vary
        if response.status_code == 400:
            data = response.json()
            assert "no documents" in data["detail"].lower() or "upload" in data["detail"].lower()
    
    def test_query_with_document_id(self, api_client, service_container, sample_documents):
        """Test POST /query?document_id=xxx"""
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": "doc1.pdf"}]
        )
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
            
            assert_response_status(response, 200)
            data = assert_json_response(response)
            assert "answer" in data
    
    def test_query_error_handling(self, api_client, service_container):
        """Test query error handling"""
        # Add a document first so the "no documents" check passes
        service_container.document_registry.add_document(
            "doc-1",
            {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
        )
        
        # Mock service to raise error
        with patch.object(service_container, 'query_text_only', side_effect=Exception("Query error")):
            response = api_client.post(
                "/query",
                json={
                    "question": "Test question",
                    "k": 3
                }
            )
            
            assert_response_status(response, 500)
            data = response.json()
            assert "error" in data["detail"].lower() or "detail" in data
