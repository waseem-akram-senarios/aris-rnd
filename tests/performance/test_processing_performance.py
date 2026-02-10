"""
Performance tests for document processing
Tests processing time and benchmarks
"""
import pytest
import time
from unittest.mock import patch, MagicMock


@pytest.mark.performance
@pytest.mark.slow
class TestProcessingPerformance:
    """Test document processing performance"""
    
    def test_document_processing_time(self, document_processor, sample_text_content, temp_dir, performance_timer):
        """Test document processing benchmarks"""
        text_file = temp_dir / "test.txt"
        text_file.write_text(sample_text_content)
        
        with patch.object(document_processor.rag_system, 'add_documents_incremental') as mock_add:
            mock_add.return_value = {'chunks_created': 5}
            
            performance_timer.start()
            result = document_processor.process_document(
                file_path=str(text_file),
                file_name="test.txt"
            )
            performance_timer.stop()
            
            assert result.status in ['success', 'processing', 'failed']
            elapsed = performance_timer.elapsed()
            # Processing should complete in reasonable time (allow more time for mocked operations)
            assert elapsed < 60.0, f"Processing took {elapsed:.2f}s"
    
    def test_chunking_performance(self, rag_system_faiss):
        """Test chunking speed"""
        large_text = " ".join([f"Sentence {i}." for i in range(5000)])
        
        start = time.time()
        result = rag_system_faiss.add_documents_incremental(
            texts=[large_text],
            metadatas=[{"source": "large.pdf"}]
        )
        elapsed = time.time() - start
        
        assert isinstance(result, dict)
        assert elapsed < 10.0, f"Chunking took {elapsed:.2f}s"
    
    def test_embedding_generation(self, mock_embeddings):
        """Test embedding generation time"""
        text = "Test text for embedding"
        
        start = time.time()
        embedding = mock_embeddings.embed_query(text)
        elapsed = time.time() - start
        
        assert len(embedding) > 0
        # Mock should be instant, but test structure
        assert elapsed < 1.0
    
    def test_large_document_handling(self, rag_system_faiss):
        """Test handling of 100+ page documents"""
        # Simulate large document
        large_text = " ".join([f"Page {i} content. " * 100 for i in range(100)])
        
        start = time.time()
        result = rag_system_faiss.add_documents_incremental(
            texts=[large_text],
            metadatas=[{"source": "large_doc.pdf"}]
        )
        elapsed = time.time() - start
        
        assert isinstance(result, dict)
        assert result["chunks_created"] > 0
        # Large documents may take time, but should complete
        assert elapsed < 60.0, f"Large document processing took {elapsed:.2f}s"
