"""
Regression tests for similarity percentage calculation accuracy.
Ensures similarity_percentage is not misleadingly set to 100% when all scores are equal.
"""
import pytest
from unittest.mock import MagicMock, patch
import os


@pytest.mark.api
class TestSimilarityPercentageAccuracy:
    """Test similarity percentage calculation accuracy"""
    
    def test_similarity_percentage_not_always_100_when_scores_equal(self):
        """Test that similarity_percentage is None (not 100%) when all scores are equal"""
        from services.retrieval.engine import RetrievalEngine
        
        # Create mock citations with equal scores
        citations = [
            {
                'id': 1,
                'source': 'test.pdf',
                'page': 1,
                'similarity_score': 0.85,
                'snippet': 'Test snippet 1'
            },
            {
                'id': 2,
                'source': 'test.pdf',
                'page': 2,
                'similarity_score': 0.85,  # Same score
                'snippet': 'Test snippet 2'
            },
            {
                'id': 3,
                'source': 'test.pdf',
                'page': 3,
                'similarity_score': 0.85,  # Same score
                'snippet': 'Test snippet 3'
            }
        ]
        
        # Mock the entire OpenSearch initialization to avoid connection issues
        with patch('vectorstores.opensearch_store.OpenSearch'), \
             patch('vectorstores.opensearch_store.AWSV4SignerAuth'), \
             patch.dict(os.environ, {
                 'VECTOR_STORE_TYPE': 'opensearch',
                 'AWS_OPENSEARCH_DOMAIN': 'test-domain',
                 'AWS_REGION': 'us-east-2'
             }):
            engine = RetrievalEngine(
                use_cerebras=False,
                vector_store_type='opensearch',
                opensearch_domain='test-domain',
                chunk_size=512,
                chunk_overlap=128
            )
            
            # Call _rank_citations_by_relevance
            ranked = engine._rank_citations_by_relevance(citations, "test query")
            
            # Verify that similarity_percentage is None (not 100%) when all scores are equal
            for citation in ranked:
                similarity_percentage = citation.get('similarity_percentage')
                # When all scores are equal, percentage should be None (not 100%)
                assert similarity_percentage is None, \
                    f"Expected None when all scores are equal, got {similarity_percentage}%"
    
    def test_similarity_percentage_calculated_when_scores_differ(self):
        """Test that similarity_percentage is calculated correctly when scores differ"""
        from services.retrieval.engine import RetrievalEngine
        
        citations = [
            {
                'id': 1,
                'source': 'test.pdf',
                'page': 1,
                'similarity_score': 0.95,  # Highest
                'snippet': 'Test snippet 1'
            },
            {
                'id': 2,
                'source': 'test.pdf',
                'page': 2,
                'similarity_score': 0.80,  # Middle
                'snippet': 'Test snippet 2'
            },
            {
                'id': 3,
                'source': 'test.pdf',
                'page': 3,
                'similarity_score': 0.65,  # Lowest
                'snippet': 'Test snippet 3'
            }
        ]
        
        with patch('vectorstores.opensearch_store.OpenSearch'), \
             patch('vectorstores.opensearch_store.AWSV4SignerAuth'), \
             patch.dict(os.environ, {
                 'VECTOR_STORE_TYPE': 'opensearch',
                 'AWS_OPENSEARCH_DOMAIN': 'test-domain',
                 'AWS_REGION': 'us-east-2'
             }):
            engine = RetrievalEngine(
                use_cerebras=False,
                vector_store_type='opensearch',
                opensearch_domain='test-domain',
                chunk_size=512,
                chunk_overlap=128
            )
            
            ranked = engine._rank_citations_by_relevance(citations, "test query")
            
            # Verify that similarity_percentage is calculated (not None) when scores differ
            percentages = [c.get('similarity_percentage') for c in ranked]
            
            # All should have percentages (not None)
            assert all(p is not None for p in percentages), \
                f"Expected all citations to have similarity_percentage, got: {percentages}"
            
            # Highest score should have highest percentage (100%)
            assert ranked[0].get('similarity_percentage') == 100.0, \
                f"Highest score should have 100% similarity, got {ranked[0].get('similarity_percentage')}"
            
            # Percentages should be in descending order (highest to lowest)
            for i in range(len(percentages) - 1):
                assert percentages[i] >= percentages[i + 1], \
                    f"Percentages should be in descending order: {percentages}"
    
    def test_similarity_percentage_none_when_no_score(self):
        """Test that similarity_percentage is 0.0 (not None) when similarity_score is missing"""
        from services.retrieval.engine import RetrievalEngine
        
        citations = [
            {
                'id': 1,
                'source': 'test.pdf',
                'page': 1,
                # No similarity_score
                'snippet': 'Test snippet 1'
            }
        ]
        
        with patch('vectorstores.opensearch_store.OpenSearch'), \
             patch('vectorstores.opensearch_store.AWSV4SignerAuth'), \
             patch.dict(os.environ, {
                 'VECTOR_STORE_TYPE': 'opensearch',
                 'AWS_OPENSEARCH_DOMAIN': 'test-domain',
                 'AWS_REGION': 'us-east-2'
             }):
            engine = RetrievalEngine(
                use_cerebras=False,
                vector_store_type='opensearch',
                opensearch_domain='test-domain',
                chunk_size=512,
                chunk_overlap=128
            )
            
            ranked = engine._rank_citations_by_relevance(citations, "test query")
            
            # When no score, percentage should be 0.0 (not None)
            assert ranked[0].get('similarity_percentage') == 0.0, \
                f"Expected 0.0 when no similarity_score, got {ranked[0].get('similarity_percentage')}"
