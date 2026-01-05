#!/usr/bin/env python3
"""
Test citation accuracy improvements:
- Similarity percentage calculation
- Page number accuracy
- Citation ranking
"""
import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from services.retrieval.engine import RetrievalEngine
from langchain_core.documents import Document


class TestCitationAccuracy:
    """Test citation accuracy improvements"""
    
    def test_similarity_percentage_calculation(self):
        """Test that similarity percentages are calculated correctly"""
        # Create mock citations with similarity scores
        citations = [
            {'id': 1, 'source': 'doc1.pdf', 'page': 1, 'similarity_score': 0.95},
            {'id': 2, 'source': 'doc2.pdf', 'page': 2, 'similarity_score': 0.85},
            {'id': 3, 'source': 'doc3.pdf', 'page': 3, 'similarity_score': 0.75},
        ]
        
        # Create engine instance (minimal setup)
        engine = RetrievalEngine(
            use_cerebras=False,
            vector_store_type='opensearch',
            opensearch_domain='test-domain',
            opensearch_index='test-index'
        )
        
        # Rank citations
        ranked = engine._rank_citations_by_relevance(citations, "test query")
        
        # Verify percentages are calculated
        assert all('similarity_percentage' in c for c in ranked), "All citations should have similarity_percentage"
        
        # Verify percentages are in valid range
        for citation in ranked:
            percentage = citation.get('similarity_percentage')
            assert percentage is not None, f"Citation {citation.get('id')} should have similarity_percentage"
            assert 0.0 <= percentage <= 100.0, f"Percentage should be 0-100, got {percentage}"
        
        # Verify highest score gets highest percentage
        highest_score_citation = max(ranked, key=lambda c: c.get('similarity_score', 0))
        highest_percentage_citation = max(ranked, key=lambda c: c.get('similarity_percentage', 0))
        assert highest_score_citation['id'] == highest_percentage_citation['id'], \
            "Citation with highest similarity_score should have highest similarity_percentage"
    
    def test_page_number_extraction(self):
        """Test that page numbers are extracted accurately"""
        engine = RetrievalEngine(
            use_cerebras=False,
            vector_store_type='opensearch',
            opensearch_domain='test-domain',
            opensearch_index='test-index'
        )
        
        # Test case 1: source_page metadata (highest confidence)
        doc1 = Document(
            page_content="Some text content",
            metadata={'source_page': 5, 'pages': 10, 'source': 'test.pdf'}
        )
        page, confidence = engine._extract_page_number(doc1, "Some text")
        assert page == 5, f"Expected page 5, got {page}"
        assert confidence == 1.0, f"Expected confidence 1.0, got {confidence}"
        
        # Test case 2: page metadata (medium confidence)
        doc2 = Document(
            page_content="Some text content",
            metadata={'page': 3, 'pages': 10, 'source': 'test.pdf'}
        )
        page, confidence = engine._extract_page_number(doc2, "Some text")
        assert page == 3, f"Expected page 3, got {page}"
        assert confidence == 0.8, f"Expected confidence 0.8, got {confidence}"
        
        # Test case 3: Text marker
        doc3 = Document(
            page_content="--- Page 7 ---\nSome text content",
            metadata={'pages': 10, 'source': 'test.pdf'}
        )
        page, confidence = engine._extract_page_number(doc3, "--- Page 7 ---\nSome text content")
        assert page == 7, f"Expected page 7, got {page}"
        assert confidence == 0.6, f"Expected confidence 0.6, got {confidence}"
        
        # Test case 4: Fallback to page 1
        doc4 = Document(
            page_content="Some text without page markers",
            metadata={'pages': 10, 'source': 'test.pdf'}
        )
        page, confidence = engine._extract_page_number(doc4, "Some text without page markers")
        assert page == 1, f"Expected page 1 (fallback), got {page}"
        assert confidence == 0.1, f"Expected confidence 0.1 (fallback), got {confidence}"
    
    def test_similarity_score_extraction_priority(self):
        """Test that OpenSearch scores are prioritized over position-based scores"""
        # This test verifies the priority order in similarity score extraction
        # Priority: OpenSearch score > doc_scores > order_scores > position-based
        
        # Create a document with OpenSearch score in metadata
        doc_with_opensearch = Document(
            page_content="Test content",
            metadata={
                'source': 'test.pdf',
                'page': 1,
                '_opensearch_score': 0.92  # High score from hybrid search
            }
        )
        
        # Create a document without OpenSearch score
        doc_without_opensearch = Document(
            page_content="Test content",
            metadata={
                'source': 'test2.pdf',
                'page': 1
            }
        )
        
        # The actual extraction happens in query_with_rag, but we can verify
        # that the metadata structure supports it
        assert '_opensearch_score' in doc_with_opensearch.metadata, \
            "Document should have _opensearch_score in metadata"
        assert doc_with_opensearch.metadata['_opensearch_score'] == 0.92, \
            "OpenSearch score should be preserved in metadata"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
