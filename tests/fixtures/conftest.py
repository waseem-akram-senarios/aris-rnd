"""
Enhanced pytest configuration and fixtures for ARIS RAG System
Provides comprehensive fixtures for all test types
"""
import sys
import os
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Optional, Dict, Any
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
project_root_str = str(project_root)
tests_dir_str = str(Path(__file__).parent.parent)

if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Change to project root directory for tests
os.chdir(project_root_str)

# Import after path setup
from dotenv import load_dotenv
load_dotenv()

# Import project modules
from api.service import ServiceContainer, create_service_container
from shared.config.settings import ARISConfig
from storage.document_registry import DocumentRegistry
from services.retrieval.engine import RetrievalEngine
from ingestion.document_processor import DocumentProcessor


# ============================================================================
# FIXTURE SCOPE CONFIGURATION
# ============================================================================

@pytest.fixture(scope="session")
def project_root_path() -> Path:
    """Return project root path"""
    return project_root


@pytest.fixture(scope="session")
def test_data_dir(project_root_path: Path) -> Path:
    """Return test data directory"""
    test_dir = project_root_path / "tests" / "fixtures" / "sample_documents"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


# ============================================================================
# TEMPORARY DIRECTORY FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_registry_file(temp_dir: Path) -> Path:
    """Create a temporary registry file"""
    registry_file = temp_dir / "test_registry.json"
    registry_file.touch()
    return registry_file


@pytest.fixture
def temp_vectorstore_dir(temp_dir: Path) -> Path:
    """Create a temporary vectorstore directory"""
    vs_dir = temp_dir / "vectorstore"
    vs_dir.mkdir(parents=True, exist_ok=True)
    return vs_dir


# ============================================================================
# MOCK EMBEDDINGS FIXTURE
# ============================================================================

@pytest.fixture
def mock_embeddings():
    """Mock OpenAI embeddings for testing"""
    mock = MagicMock()
    
    # Mock embed_query to return a fixed-size vector
    def mock_embed_query(text: str) -> list:
        # Return 3072-dimensional vector (text-embedding-3-large)
        return [0.1] * 3072
    
    def mock_embed_documents(texts: list) -> list:
        return [[0.1] * 3072 for _ in texts]
    
    mock.embed_query = mock_embed_query
    mock.embed_documents = mock_embed_documents
    mock.model = "text-embedding-3-large"
    
    return mock


# ============================================================================
# SERVICE CONTAINER FIXTURES
# ============================================================================

@pytest.fixture
def service_container_faiss(mock_embeddings, temp_dir: Path) -> ServiceContainer:
    """Service container with FAISS vector store for testing"""
    with patch('api.service.OpenAIEmbeddings', return_value=mock_embeddings):
        container = ServiceContainer(
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        # Note: In microservices, vectorstore path is managed by services
        # This fixture is for compatibility testing
        yield container


@pytest.fixture
def service_container_opensearch(mock_embeddings) -> Optional[ServiceContainer]:
    """Service container with OpenSearch vector store (if available)"""
    # Check if OpenSearch credentials are available
    has_creds = bool(
        os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') and 
        os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    )
    has_domain = bool(os.getenv('AWS_OPENSEARCH_DOMAIN'))
    
    if not (has_creds and has_domain):
        pytest.skip("OpenSearch credentials not available")
    
    with patch('api.service.OpenAIEmbeddings', return_value=mock_embeddings):
        container = ServiceContainer(
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="opensearch",
            opensearch_domain=os.getenv('AWS_OPENSEARCH_DOMAIN'),
            opensearch_index="test-index",
            chunk_size=384,
            chunk_overlap=75
        )
        yield container


@pytest.fixture
def service_container(service_container_faiss: ServiceContainer) -> ServiceContainer:
    """Default service container (FAISS)"""
    return service_container_faiss


# ============================================================================
# RAG SYSTEM FIXTURES
# ============================================================================

@pytest.fixture
def rag_system_faiss(mock_embeddings, temp_dir: Path) -> RAGSystem:
    """RAG system with FAISS vector store"""
    with patch('api.rag_system.OpenAIEmbeddings', return_value=mock_embeddings):
        rag = RetrievalEngine(
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        yield rag


# ============================================================================
# DOCUMENT REGISTRY FIXTURES
# ============================================================================

@pytest.fixture
def document_registry(temp_registry_file: Path) -> DocumentRegistry:
    """Document registry with temporary file"""
    return DocumentRegistry(str(temp_registry_file))


@pytest.fixture
def empty_registry(document_registry: DocumentRegistry) -> DocumentRegistry:
    """Empty document registry"""
    document_registry.clear_all()
    return document_registry


# ============================================================================
# DOCUMENT PROCESSOR FIXTURES
# ============================================================================

@pytest.fixture
def document_processor(rag_system_faiss: RAGSystem) -> DocumentProcessor:
    """Document processor with FAISS RAG system"""
    return DocumentProcessor(rag_system_faiss)


# ============================================================================
# SAMPLE DOCUMENT FIXTURES
# ============================================================================

@pytest.fixture
def sample_text_pdf(test_data_dir: Path) -> Optional[Path]:
    """Path to sample text-based PDF"""
    pdf_path = test_data_dir / "sample_text.pdf"
    if not pdf_path.exists():
        # Create a minimal PDF for testing if it doesn't exist
        pytest.skip(f"Sample PDF not found at {pdf_path}")
    return pdf_path


@pytest.fixture
def sample_text_content() -> str:
    """Sample text content for testing"""
    return """
    This is a sample document for testing purposes.
    It contains multiple sentences and paragraphs.
    
    The document discusses various topics including:
    - Machine learning
    - Natural language processing
    - Vector embeddings
    - Retrieval augmented generation
    
    This content will be used to test document processing,
    chunking, and retrieval functionality.
    """


@pytest.fixture
def sample_documents(sample_text_content: str) -> list:
    """List of sample document texts"""
    return [
        sample_text_content,
        "Another document about artificial intelligence and neural networks.",
        "A third document discussing vector databases and similarity search."
    ]


# ============================================================================
# API CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def api_client(service_container: ServiceContainer) -> TestClient:
    """FastAPI test client"""
    from api.main import app
    
    # Override service dependency
    app.dependency_overrides = {}
    
    def get_test_service():
        return service_container
    
    from api.main import get_service
    app.dependency_overrides[get_service] = get_test_service
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def api_client_no_service() -> TestClient:
    """FastAPI test client without service override (for error testing)"""
    from api.main import app
    return TestClient(app)


# ============================================================================
# MOCK EXTERNAL SERVICES
# ============================================================================

@pytest.fixture
def mock_openai():
    """Mock OpenAI API"""
    with patch('openai.OpenAI') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        
        # Mock chat completion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked response"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100
        
        mock_instance.chat.completions.create.return_value = mock_response
        yield mock_instance


@pytest.fixture
def mock_opensearch():
    """Mock OpenSearch client"""
    mock_client = MagicMock()
    
    # Mock index operations
    mock_client.indices.exists.return_value = False
    mock_client.indices.create.return_value = {"acknowledged": True}
    mock_client.indices.delete.return_value = {"acknowledged": True}
    
    # Mock document operations
    mock_client.index.return_value = {"_id": "test_id", "result": "created"}
    mock_client.search.return_value = {
        "hits": {
            "total": {"value": 0},
            "hits": []
        }
    }
    
    return mock_client


# ============================================================================
# PERFORMANCE TESTING FIXTURES
# ============================================================================

@pytest.fixture
def performance_timer():
    """Timer fixture for performance tests"""
    import time
    
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
        
        def elapsed(self) -> float:
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0.0
    
    return Timer()


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Auto-cleanup after each test"""
    yield
    # Add any cleanup logic here
    pass


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================

@pytest.fixture
def generate_test_document():
    """Factory fixture to generate test documents"""
    def _generate(
        text: str = "Test document content",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "document_id": "test-doc-123",
            "document_name": "test_document.pdf",
            "status": "completed",
            "chunks_created": 5,
            "tokens_extracted": 1000,
            "parser_used": "pymupdf",
            "processing_time": 1.5,
            "extraction_percentage": 95.0,
            "images_detected": False,
            "image_count": 0,
            "pages": 10,
            **(metadata or {})
        }
    return _generate


@pytest.fixture
def generate_test_chunk():
    """Factory fixture to generate test chunks"""
    def _generate(
        text: str = "Test chunk content",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return {
            "page_content": text,
            "metadata": {
                "source": "test_document.pdf",
                "page": 1,
                "chunk_index": 0,
                **(metadata or {})
            }
        }
    return _generate
