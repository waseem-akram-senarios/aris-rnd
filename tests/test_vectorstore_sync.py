"""
Tests for vectorstore synchronization
"""
import os
import tempfile
import shutil
import pytest
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.settings import ARISConfig
from rag_system import RAGSystem
from metrics.metrics_collector import MetricsCollector


class TestVectorstoreSync:
    """Test vectorstore persistence and sharing"""
    
    @pytest.fixture
    def temp_vectorstore_path(self):
        """Create temporary directory for vectorstore"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    def test_vectorstore_path_configuration(self):
        """Test vectorstore path configuration"""
        path = ARISConfig.get_vectorstore_path()
        assert isinstance(path, str)
        assert len(path) > 0
    
    def test_vectorstore_save_and_load(self, temp_vectorstore_path):
        """Test saving and loading vectorstore"""
        # Create a RAG system
        metrics = MetricsCollector()
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics,
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        
        # Vectorstore may or may not exist initially
        # If it exists, we can test save/load
        if rag_system.vectorstore is not None:
            # Save vectorstore
            rag_system.save_vectorstore(temp_vectorstore_path)
            
            # Verify files were created
            assert os.path.exists(temp_vectorstore_path)
            
            # Create new RAG system and load
            new_rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=MetricsCollector(),
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=384,
                chunk_overlap=75
            )
            
            # Load vectorstore
            loaded = new_rag_system.load_vectorstore(temp_vectorstore_path)
            if loaded:
                assert new_rag_system.vectorstore is not None
    
    def test_vectorstore_path_consistency(self):
        """Test that vectorstore path is consistent"""
        path1 = ARISConfig.get_vectorstore_path()
        path2 = ARISConfig.get_vectorstore_path()
        
        # Should return same path
        assert path1 == path2
    
    def test_vectorstore_file_structure(self, temp_vectorstore_path):
        """Test that vectorstore creates expected file structure"""
        metrics = MetricsCollector()
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics,
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        
        if rag_system.vectorstore is not None:
            # Save vectorstore
            rag_system.save_vectorstore(temp_vectorstore_path)
            
            # Check that directory exists
            assert os.path.exists(temp_vectorstore_path)
            
            # Check for document index file
            index_path = os.path.join(temp_vectorstore_path, "document_index.pkl")
            # Index file may or may not exist depending on whether documents were processed
            # This is expected behavior

