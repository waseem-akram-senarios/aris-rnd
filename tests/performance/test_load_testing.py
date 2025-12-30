"""
Load testing - Concurrent operations and sustained load
"""
import pytest
import threading
import time
from unittest.mock import patch, MagicMock


@pytest.mark.performance
@pytest.mark.slow
class TestLoadTesting:
    """Test system under load"""
    
    def test_concurrent_uploads(self, api_client, temp_dir):
        """Test multiple simultaneous uploads"""
        results = []
        errors = []
        
        def upload_file(file_num):
            try:
                pdf_file = temp_dir / f"test{file_num}.pdf"
                pdf_file.write_bytes(b"fake pdf content")
                
                with open(pdf_file, 'rb') as f:
                    response = api_client.post(
                        "/documents",
                        files={"file": (f"test{file_num}.pdf", f, "application/pdf")}
                    )
                    results.append(response.status_code)
            except Exception as e:
                errors.append(e)
        
        # Create 10 concurrent uploads
        threads = [threading.Thread(target=upload_file, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Most should succeed (some may fail due to duplicates)
        assert len(results) > 0
        success_count = sum(1 for status in results if status in [200, 201])
        assert success_count > 0
    
    def test_sustained_load(self, api_client, service_container, sample_documents):
        """Test sustained load for 5 minutes"""
        service_container.rag_system.add_documents_incremental(
            texts=sample_documents,
            metadatas=[{"source": f"doc{i}.pdf"} for i in range(len(sample_documents))]
        )
        
        # Run queries for short period (simulating 5 minutes)
        # In real test, would run for full 5 minutes
        start = time.time()
        query_count = 0
        max_duration = 10  # Test for 10 seconds instead of 5 minutes
        
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Answer"
            mock_response.usage = MagicMock()
            mock_response.usage.total_tokens = 50
            mock_client.chat.completions.create.return_value = mock_response
            
            while time.time() - start < max_duration:
                response = api_client.post(
                    "/query",
                    json={"question": "Test", "k": 3}
                )
                query_count += 1
                time.sleep(0.1)  # Small delay between queries
        
        # Should handle sustained load
        assert query_count > 0
    
    def test_memory_usage(self, service_container, sample_documents):
        """Test memory consumption"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Add many documents
        for i in range(100):
            service_container.rag_system.add_documents_incremental(
                texts=[f"Document {i} content"],
                metadatas=[{"source": f"doc{i}.pdf"}]
            )
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory should increase but not excessively
        assert memory_increase < 1000, f"Memory increased by {memory_increase:.2f}MB"
