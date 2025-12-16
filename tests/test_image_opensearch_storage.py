"""
Tests for image OpenSearch storage functionality.
"""
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from vectorstores.opensearch_images_store import OpenSearchImagesStore
from utils.image_extraction_logger import ImageExtractionLogger, image_logger


class TestOpenSearchImagesStore(unittest.TestCase):
    """Test OpenSearchImagesStore functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_embeddings = Mock()
        self.mock_embeddings.embed_query.return_value = [0.1] * 1536  # Mock embedding
        
        # Mock OpenSearchVectorStore
        self.mock_vectorstore = Mock()
        self.mock_vectorstore.add_documents = Mock()
        self.mock_vectorstore.vectorstore = Mock()
        self.mock_vectorstore.vectorstore.client = Mock()
        self.mock_vectorstore.vectorstore.similarity_search = Mock(return_value=[])
    
    @patch('vectorstores.opensearch_images_store.OpenSearchVectorStore')
    def test_store_image(self, mock_opensearch_store):
        """Test storing a single image."""
        mock_opensearch_store.return_value.vectorstore = self.mock_vectorstore.vectorstore
        mock_opensearch_store.return_value.add_documents = self.mock_vectorstore.add_documents
        
        store = OpenSearchImagesStore(
            embeddings=self.mock_embeddings,
            index_name="test-images-index"
        )
        store.vectorstore = mock_opensearch_store.return_value
        
        image_id = store.store_image(
            source="test.pdf",
            image_number=1,
            ocr_text="Test OCR text",
            page=1,
            extraction_method="docling_ocr"
        )
        
        self.assertIsNotNone(image_id)
        self.assertIn("test", image_id.lower())
        self.assertIn("image", image_id.lower())
        self.assertIn("1", image_id)
    
    @patch('vectorstores.opensearch_images_store.OpenSearchVectorStore')
    def test_store_images_batch(self, mock_opensearch_store):
        """Test storing multiple images in batch."""
        mock_opensearch_store.return_value.vectorstore = self.mock_vectorstore.vectorstore
        mock_opensearch_store.return_value.add_documents = self.mock_vectorstore.add_documents
        
        store = OpenSearchImagesStore(
            embeddings=self.mock_embeddings,
            index_name="test-images-index"
        )
        store.vectorstore = mock_opensearch_store.return_value
        
        images = [
            {
                'source': 'test.pdf',
                'image_number': 1,
                'ocr_text': 'OCR text 1',
                'page': 1
            },
            {
                'source': 'test.pdf',
                'image_number': 2,
                'ocr_text': 'OCR text 2',
                'page': 2
            }
        ]
        
        image_ids = store.store_images_batch(images)
        
        self.assertEqual(len(image_ids), 2)
        self.assertEqual(mock_opensearch_store.return_value.add_documents.call_count, 1)
    
    @patch('vectorstores.opensearch_images_store.OpenSearchVectorStore')
    def test_extract_metadata(self, mock_opensearch_store):
        """Test metadata extraction from OCR text."""
        mock_opensearch_store.return_value.vectorstore = self.mock_vectorstore.vectorstore
        
        store = OpenSearchImagesStore(
            embeddings=self.mock_embeddings,
            index_name="test-images-index"
        )
        
        ocr_text = "DRAWER 1 Quantity: 65300077- Wire Stripper 65300081- Snips"
        metadata = store._extract_image_metadata(ocr_text)
        
        self.assertIn('drawer_references', metadata)
        self.assertIn('part_numbers', metadata)
        self.assertIn('tools_found', metadata)
        self.assertEqual(metadata['drawer_references'], ['1'])
        self.assertIn('65300077', metadata['part_numbers'])
        self.assertIn('snips', metadata['tools_found'])


class TestImageExtractionLogger(unittest.TestCase):
    """Test image extraction logger functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.logger = ImageExtractionLogger()
    
    def test_log_image_detection_start(self):
        """Test logging image detection start."""
        # Should not raise exception
        self.logger.log_image_detection_start("test.pdf", "docling")
    
    def test_log_image_detected(self):
        """Test logging image detection."""
        # Should not raise exception
        self.logger.log_image_detected(
            source="test.pdf",
            image_count=5,
            detection_methods=["docling"]
        )
    
    def test_log_ocr_complete(self):
        """Test logging OCR completion."""
        # Should not raise exception
        self.logger.log_ocr_complete(
            source="test.pdf",
            ocr_text_length=1000,
            extraction_method="docling",
            success=True
        )
    
    def test_log_storage_success(self):
        """Test logging storage success."""
        # Should not raise exception
        self.logger.log_storage_success(
            source="test.pdf",
            images_stored=3,
            image_ids=["id1", "id2", "id3"]
        )


if __name__ == '__main__':
    unittest.main()

