"""
Integration tests for ServiceContainer
Tests service container initialization and integration
"""
import pytest
from unittest.mock import patch, MagicMock
from api.service import ServiceContainer, create_service_container


@pytest.mark.integration
class TestServiceContainer:
    """Test service container integration"""
    
    def test_service_container_initialization(self, mock_embeddings, temp_dir):
        """Test service container initialization"""
        # Patch at the api.rag_system level where OpenAIEmbeddings is imported
        with patch('api.rag_system.OpenAIEmbeddings', return_value=mock_embeddings):
            container = ServiceContainer(
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=384,
                chunk_overlap=75
            )
            
            assert container.rag_system is not None
            assert container.document_processor is not None
            assert container.document_registry is not None
            assert container.metrics_collector is not None
    
    def test_create_service_container(self, mock_embeddings):
        """Test create_service_container function"""
        # Patch at the api.rag_system level
        with patch('api.rag_system.OpenAIEmbeddings', return_value=mock_embeddings):
            container = create_service_container(
                vector_store_type="faiss",
                embedding_model="text-embedding-3-small"
            )
            
            assert isinstance(container, ServiceContainer)
            assert container.rag_system is not None
    
    def test_service_container_list_documents(self, service_container):
        """Test listing documents through service container"""
        docs = service_container.list_documents()
        assert isinstance(docs, list)
    
    def test_service_container_get_document(self, service_container):
        """Test getting document through service container"""
        # Add a document first
        service_container.document_registry.add_document(
            "test-doc",
            {"document_name": "test.pdf", "status": "completed"}
        )
        
        doc = service_container.get_document("test-doc")
        assert doc is not None
        assert doc["document_name"] == "test.pdf"
    
    def test_service_container_query_text_only(self, service_container, sample_documents):
        """Test querying text through service container"""
        # Add documents to RAG system
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
            mock_response.choices[0].message.content = "Test answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 100
            mock_client.chat.completions.create.return_value = mock_response
            
            result = service_container.query_text_only(
                question="What is the content?",
                k=3
            )
            
            assert isinstance(result, dict)
            assert 'answer' in result
            assert 'sources' in result
    
    def test_service_container_get_storage_status(self, service_container):
        """Test getting storage status"""
        # Add a document
        service_container.document_registry.add_document(
            "test-doc",
            {
                "document_name": "test.pdf",
                "status": "completed",
                "chunks_created": 10,
                "image_count": 2
            }
        )
        
        status = service_container.get_storage_status("test-doc")
        
        assert isinstance(status, dict)
        assert 'document_id' in status
        assert 'text_chunks_count' in status
        assert 'images_count' in status
    
    def test_service_container_document_filtering(self, service_container, sample_documents):
        """Test querying with document filtering"""
        # Add documents
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[
                {"source": "doc1.pdf"},
                {"source": "doc2.pdf"}
            ]
        )
        
        # Add to registry
        service_container.document_registry.add_document(
            "doc1-id",
            {"document_name": "doc1.pdf", "status": "completed"}
        )
        
        # Mock LLM
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            result = service_container.query_text_only(
                question="Test question",
                k=3,
                document_id="doc1-id"
            )
            
            assert isinstance(result, dict)
            # Should filter to doc1.pdf
