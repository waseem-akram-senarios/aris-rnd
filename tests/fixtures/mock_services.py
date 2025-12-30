"""
Mock services for testing external dependencies
"""
from unittest.mock import MagicMock, Mock
from typing import List, Dict, Any, Optional


class MockOpenAIEmbeddings:
    """Mock OpenAI embeddings"""
    
    def __init__(self, dimension: int = 3072):
        self.dimension = dimension
        self.model = "text-embedding-3-large"
    
    def embed_query(self, text: str) -> List[float]:
        """Mock embed_query"""
        return [0.1] * self.dimension
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Mock embed_documents"""
        return [[0.1] * self.dimension for _ in texts]


class MockOpenAIClient:
    """Mock OpenAI client"""
    
    def __init__(self):
        self.chat = Mock()
        self.chat.completions = Mock()
        
        # Default mock response
        self.mock_response = MagicMock()
        self.mock_response.choices = [MagicMock()]
        self.mock_response.choices[0].message.content = "Mocked response"
        self.mock_response.usage = MagicMock()
        self.mock_response.usage.total_tokens = 100
        self.mock_response.usage.prompt_tokens = 50
        self.mock_response.usage.completion_tokens = 50
        
        self.chat.completions.create = Mock(return_value=self.mock_response)
    
    def set_response(self, content: str, total_tokens: int = 100):
        """Set custom response"""
        self.mock_response.choices[0].message.content = content
        self.mock_response.usage.total_tokens = total_tokens


class MockOpenSearchClient:
    """Mock OpenSearch client"""
    
    def __init__(self):
        self.indices = Mock()
        self.indices.exists = Mock(return_value=False)
        self.indices.create = Mock(return_value={"acknowledged": True})
        self.indices.delete = Mock(return_value={"acknowledged": True})
        self.indices.get = Mock(return_value={})
        
        self.index = Mock(return_value={"_id": "test_id", "result": "created"})
        self.search = Mock(return_value={
            "hits": {
                "total": {"value": 0},
                "hits": []
            }
        })
        self.delete = Mock(return_value={"result": "deleted"})


class MockDocumentConverter:
    """Mock Docling DocumentConverter"""
    
    def __init__(self):
        self.convert = Mock()
        
        # Default mock result
        self.mock_result = MagicMock()
        self.mock_result.document = MagicMock()
        self.mock_result.document.export_to_markdown = Mock(
            return_value="Mocked markdown content"
        )
        self.mock_result.document.images = []
        
        self.convert.return_value = self.mock_result
    
    def set_result(self, markdown: str, images: Optional[List[Dict]] = None):
        """Set custom conversion result"""
        self.mock_result.document.export_to_markdown.return_value = markdown
        if images:
            self.mock_result.document.images = images


class MockPyMuPDF:
    """Mock PyMuPDF (fitz)"""
    
    def __init__(self):
        self.open = Mock()
        
        # Default mock document
        self.mock_doc = MagicMock()
        self.mock_doc.page_count = 1
        self.mock_doc.metadata = {"title": "Test Document"}
        
        # Mock page
        self.mock_page = MagicMock()
        self.mock_page.get_text = Mock(return_value="Mocked page text")
        self.mock_page.get_images = Mock(return_value=[])
        self.mock_doc.__getitem__ = Mock(return_value=self.mock_page)
        self.mock_doc.__len__ = Mock(return_value=1)
        
        self.open.return_value = self.mock_doc
    
    def set_text(self, text: str):
        """Set page text"""
        self.mock_page.get_text.return_value = text
    
    def set_page_count(self, count: int):
        """Set page count"""
        self.mock_doc.page_count = count
        self.mock_doc.__len__ = Mock(return_value=count)


def create_mock_service_container(
    vector_store_type: str = "faiss",
    embedding_model: str = "text-embedding-3-small"
) -> MagicMock:
    """Create a fully-mocked service container with all nested attributes and methods"""
    container = MagicMock()
    
    # Mock rag_system with all needed attributes and methods
    container.rag_system = MagicMock()
    container.rag_system.vector_store_type = vector_store_type
    container.rag_system.embedding_model = embedding_model
    container.rag_system.opensearch_domain = None
    container.rag_system.opensearch_index = "aris-rag-index"
    container.rag_system.active_sources = None
    container.rag_system.document_index_map = {}
    container.rag_system.vectorstore_path = "/tmp/test_vectorstore"
    
    # Mock RAG system methods
    def mock_add_documents_incremental(texts, metadatas=None):
        """Mock add_documents_incremental that returns proper counts"""
        num_docs = len(texts) if isinstance(texts, list) else 1
        return {
            "chunks_created": num_docs * 5,
            "tokens_added": num_docs * 1000,
            "documents_added": num_docs
        }
    
    container.rag_system.add_documents_incremental = Mock(side_effect=mock_add_documents_incremental)
    
    def mock_query_with_rag(**kwargs):
        """Mock query_with_rag that returns proper dict structure"""
        return {
            "answer": "Mocked answer from RAG system",
            "sources": ["test_document.pdf"],
            "citations": [
                {
                    "content": "Mocked citation content",
                    "source": "test_document.pdf",
                    "page": 1,
                    "content_type": "text"
                }
            ],
            "num_chunks_used": 1,
            "context_chunks": [
                {
                    "page_content": "Mocked chunk content",
                    "metadata": {"source": "test_document.pdf", "page": 1}
                }
            ]
        }
    
    container.rag_system.query_with_rag = Mock(side_effect=mock_query_with_rag)
    container.rag_system.query_images = Mock(return_value=[
        {
            "image_id": "img-1",
            "document_id": "doc-123",
            "image_number": 1,
            "ocr_text": "Mocked OCR text",
            "image_hash": "abc123",
            "source": "test_document.pdf"
        }
    ])
    container.rag_system.delete_document = Mock(return_value=True)
    
    # Use a dict to track documents for dynamic behavior
    _mock_documents = {}
    
    # Mock document_registry with dynamic storage
    def mock_add_document(doc_id, metadata):
        _mock_documents[doc_id] = metadata
        return None
    
    def mock_get_document(doc_id):
        return _mock_documents.get(doc_id)
    
    def mock_list_documents():
        return list(_mock_documents.values())
    
    def mock_remove_document(doc_id):
        if doc_id in _mock_documents:
            del _mock_documents[doc_id]
            return True
        return False
    
    container.document_registry = MagicMock()
    container.document_registry.add_document = Mock(side_effect=mock_add_document)
    container.document_registry.get_document = Mock(side_effect=mock_get_document)
    container.document_registry.list_documents = Mock(side_effect=mock_list_documents)
    container.document_registry.remove_document = Mock(side_effect=mock_remove_document)
    container.document_registry.clear_all = Mock(side_effect=lambda: _mock_documents.clear())
    container.document_registry.save_document = Mock(side_effect=mock_add_document)
    
    # Mock document_processor
    container.document_processor = MagicMock()
    container.document_processor.process_document = Mock(return_value={
        "document_id": "test-doc-123",
        "status": "completed",
        "chunks_created": 5,
        "tokens_extracted": 1000
    })
    
    # Mock metrics_collector
    container.metrics_collector = MagicMock()
    container.metrics_collector.record_query = Mock(return_value=None)
    container.metrics_collector.record_document_upload = Mock(return_value=None)
    
    # Mock ServiceContainer methods
    container.get_document = Mock(side_effect=lambda doc_id: container.document_registry.get_document(doc_id))
    container.list_documents = Mock(side_effect=lambda: container.document_registry.list_documents())
    container.add_document = Mock(side_effect=lambda doc_id, result: container.document_registry.add_document(doc_id, result))
    container.remove_document = Mock(side_effect=lambda doc_id: container.document_registry.remove_document(doc_id))
    container.clear_documents = Mock(side_effect=lambda: container.document_registry.clear_all())
    def mock_query_text_only(question, k=6, document_id=None, use_mmr=True):
        """Mock query_text_only that returns proper dict structure"""
        return {
            "answer": "Mocked answer",
            "sources": [
                {
                    "source": "test_document.pdf",
                    "page": 1,
                    "snippet": "Mocked snippet",
                    "full_text": "Mocked full text",
                    "source_location": "Page 1"
                }
            ],
            "source_names": ["test_document.pdf"],
            "citations": [
                {
                    "content": "Mocked citation",
                    "source": "test_document.pdf",
                    "page": 1,
                    "content_type": "text",
                    "snippet": "Mocked snippet",
                    "full_text": "Mocked full text",
                    "source_location": "Page 1"
                }
            ],
            "num_chunks_used": 1,
            "response_time": 0.5,
            "context_tokens": 100,
            "response_tokens": 50,
            "total_tokens": 150
        }
    
    container.query_text_only = Mock(side_effect=mock_query_text_only)
    container.query_images_only = Mock(return_value=[
        {
            "image_id": "img-1",
            "document_id": "doc-123",
            "image_number": 1,
            "ocr_text": "Mocked OCR text"
        }
    ])
    container.get_storage_status = Mock(return_value={
        "document_id": "test-doc-123",
        "text_chunks_count": 5,
        "images_count": 2,
        "text_stored": True,
        "images_stored": True
    })
    
    return container
