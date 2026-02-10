"""
Test fixtures for microservice testing
Provides containers and utilities for testing services
"""
import pytest
import tempfile
import asyncio
import httpx
from pathlib import Path
from typing import AsyncGenerator, Dict, Any
from unittest.mock import patch, MagicMock


@pytest.fixture
def temp_dir() -> Path:
    """Provide temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide HTTP client for testing"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Provide sample PDF content for testing"""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n179\n%%EOF"


@pytest.fixture
def sample_txt_content() -> bytes:
    """Provide sample text content for testing"""
    return b"This is a sample text document for testing purposes. It contains multiple sentences to simulate a real document."


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for testing"""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "This is a test answer from the mock OpenAI API."
    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 100
    mock_response.usage.prompt_tokens = 50
    mock_response.usage.completion_tokens = 50
    return mock_response


@pytest.fixture
def mock_document_metadata():
    """Mock document metadata for testing"""
    return {
        "document_id": "test-doc-123",
        "document_name": "test_document.pdf",
        "status": "completed",
        "chunks_created": 5,
        "file_hash": "abc123",
        "upload_time": "2025-01-01T00:00:00Z",
        "processing_time": "2025-01-01T00:01:00Z",
        "total_chunks": 5,
        "image_count": 2,
        "pdf_metadata": {
            "title": "Test Document",
            "author": "Test Author",
            "pages": 10
        }
    }


@pytest.fixture
def mock_query_response():
    """Mock query response for testing"""
    return {
        "answer": "This is a test answer based on the document content.",
        "sources": ["test_document.pdf"],
        "citations": [
            {
                "id": "1",
                "source": "test_document.pdf",
                "page": 1,
                "snippet": "This is a relevant snippet from the document.",
                "full_text": "This is the full text of the relevant chunk.",
                "source_location": "Page 1"
            }
        ],
        "num_chunks_used": 3,
        "response_time": 1.5,
        "context_tokens": 150,
        "response_tokens": 50,
        "total_tokens": 200
    }


@pytest.fixture
def service_health_check():
    """Mock service health check response"""
    return {
        "status": "healthy",
        "timestamp": "2025-01-01T00:00:00Z",
        "services": {
            "gateway": "healthy",
            "ingestion": "healthy", 
            "retrieval": "healthy"
        }
    }


@pytest.fixture
async def service_health_validator():
    """Validate all services are healthy before running tests"""
    async def validate_services():
        services = {
            "gateway": "http://localhost:8500/health",
            "ingestion": "http://localhost:8501/health",
            "retrieval": "http://localhost:8502/health"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for service_name, url in services.items():
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        pytest.skip(f"Service {service_name} not healthy: {response.status_code}")
                except Exception as e:
                    pytest.skip(f"Service {service_name} unavailable: {e}")
    
    return validate_services


@pytest.fixture
def mock_s3_storage():
    """Mock S3 storage for testing"""
    return {
        "success": True,
        "s3_key": "documents/test-doc-123/test_document.pdf",
        "s3_url": "https://test-bucket.s3.amazonaws.com/documents/test-doc-123/test_document.pdf",
        "bucket": "test-bucket"
    }


@pytest.fixture
def sample_documents_list():
    """Sample list of documents for testing"""
    return [
        {
            "document_id": "doc1",
            "document_name": "document1.pdf",
            "status": "completed",
            "chunks_created": 10,
            "image_count": 3,
            "upload_time": "2025-01-01T00:00:00Z"
        },
        {
            "document_id": "doc2", 
            "document_name": "document2.txt",
            "status": "processing",
            "chunks_created": 0,
            "image_count": 0,
            "upload_time": "2025-01-01T01:00:00Z"
        }
    ]


@pytest.fixture
def mock_settings_response():
    """Mock settings API response"""
    return {
        "models": {
            "api_provider": "openai",
            "openai_model": "gpt-4o",
            "embedding_model": "text-embedding-3-large",
            "temperature": 0.1,
            "max_tokens": 1000
        },
        "parser": {
            "current_parser": "pymupdf",
            "available_parsers": ["pymupdf", "docling", "ocrmypdf"]
        },
        "chunking": {
            "chunk_size": 512,
            "chunk_overlap": 128
        },
        "vector_store": {
            "type": "opensearch",
            "opensearch_domain": "test-domain"
        },
        "retrieval": {
            "default_k": 15,
            "use_mmr": True,
            "search_mode": "hybrid"
        }
    }


class ServiceMocker:
    """Helper class for mocking service responses"""
    
    @staticmethod
    def create_mock_gateway_service():
        """Create mock Gateway service"""
        mock_service = MagicMock()
        mock_service.list_documents.return_value = [
            {"document_id": "test", "document_name": "test.pdf", "status": "completed"}
        ]
        mock_service.get_document.return_value = {
            "document_id": "test", "document_name": "test.pdf", "status": "completed"
        }
        return mock_service
    
    @staticmethod
    def create_mock_ingestion_service():
        """Create mock Ingestion service"""
        mock_service = MagicMock()
        mock_service.process_document.return_value = {
            "document_id": "test",
            "status": "completed",
            "chunks_created": 5
        }
        return mock_service
    
    @staticmethod
    def create_mock_retrieval_service():
        """Create mock Retrieval service"""
        mock_service = MagicMock()
        mock_service.query_text_only.return_value = {
            "answer": "Test answer",
            "sources": ["test.pdf"],
            "citations": [],
            "num_chunks_used": 3
        }
        return mock_service


@pytest.fixture
def service_mocker():
    """Provide ServiceMocker instance"""
    return ServiceMocker()


# Async context manager for service testing
class ServiceTestContext:
    """Context manager for testing services"""
    
    def __init__(self):
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self.client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()


@pytest.fixture
async def service_context():
    """Provide service test context"""
    async with ServiceTestContext() as client:
        yield client


# Helper functions for test setup
async def setup_test_document(client: httpx.AsyncClient, temp_dir: Path) -> Dict[str, Any]:
    """Setup a test document for testing"""
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    test_file = temp_dir / "setup_test.pdf"
    test_file.write_bytes(pdf_content)
    
    with open(test_file, 'rb') as f:
        files = {"file": ("setup_test.pdf", f, "application/pdf")}
        response = await client.post(
            "http://localhost:8500/documents",
            files=files
        )
    
    if response.status_code == 201:
        return response.json()
    return None


async def cleanup_test_document(client: httpx.AsyncClient, document_id: str):
    """Cleanup test document after testing"""
    try:
        await client.delete(f"http://localhost:8500/documents/{document_id}")
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def test_document_setup(http_client: httpx.AsyncClient, temp_dir: Path):
    """Setup and cleanup test document"""
    doc_data = await setup_test_document(http_client, temp_dir)
    yield doc_data
    if doc_data and "document_id" in doc_data:
        await cleanup_test_document(http_client, doc_data["document_id"])
