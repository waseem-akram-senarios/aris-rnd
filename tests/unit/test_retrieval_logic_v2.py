import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from services.retrieval.engine import RetrievalEngine
from shared.config.settings import ARISConfig

def test_extract_query_keywords_spanish_and_unicode():
    """Test that Spanish stop words are removed and accented characters are handled."""
    # Mock dependencies to avoid OpenSearch requirement
    with MagicMock() as mock_embeddings:
        engine = RetrievalEngine(vector_store_type="opensearch", opensearch_domain="test-domain")
        engine.embeddings = mock_embeddings
        
        # Test query with Spanish stop words and accented characters
        query = "¿Cuál es el procedimiento de degasado de la bolsa?"
        keywords = engine._extract_query_keywords(query)
        
        # Expected keywords: 'cuál' (if >2 chars), 'procedimiento', 'degasado', 'bolsa'
        # Note: stop words 'el', 'de', 'la' should be removed
        print(f"Keywords found: {keywords}")
        
        assert "procedimiento" in keywords
        assert "degasado" in keywords
        assert "bolsa" in keywords
        assert "el" not in keywords
        assert "de" not in keywords
        assert "la" not in keywords
        
        # Check accented character support
        # 'cuál' is 4 chars, should be there if regex supports Unicode word boundaries
        assert "cuál" in keywords or "cual" in keywords
        
        # Test phrases
        assert "procedimiento degasado" in keywords
        assert "degasado bolsa" in keywords

def test_rank_citations_relaxed_filtering():
    """Test that citations with only 1 keyword match are kept (not filtered out)."""
    with MagicMock() as mock_embeddings:
        engine = RetrievalEngine(vector_store_type="opensearch", opensearch_domain="test-domain")
        engine.embeddings = mock_embeddings
        
        # Setup test data
        query = "email contact"
        # Extract keywords would be ['email', 'contact']
        
        citations = [
            {
                'id': 1,
                'source': 'doc1.pdf',
                'full_text': 'This is an email address: test@example.com',
                'snippet': 'email address',
                'similarity_score': 0.8
            },
            {
                'id': 2,
                'source': 'doc2.pdf',
                'full_text': 'Nothing relevant here, just some random text about birds.',
                'snippet': 'random text',
                'similarity_score': 0.7
            }
        ]
        
        # Run ranking
        ranked = engine._rank_citations_by_relevance(citations, query)
        
        # Previously, doc1 might have been filtered if it only matched 'email' 
        # (if 2 matches required). But with my fix, it should be kept.
        # Actually, doc1 matches 'email' (1 keyword).
        # doc2 matches 0 keywords.
        
        # Check doc1
        doc1_matches = [c for c in ranked if 'doc1.pdf' in c['source']]
        assert len(doc1_matches) == 1
        assert doc1_matches[0]['similarity_percentage'] > 0
        
        # doc2 should be filtered out because it has 0 matches
        doc2_matches = [c for c in ranked if 'doc2.pdf' in c['source']]
        assert len(doc2_matches) == 0

if __name__ == "__main__":
    try:
        print("Running test_extract_query_keywords_spanish_and_unicode...")
        test_extract_query_keywords_spanish_and_unicode()
        print("✅ PASS")
        
        print("\nRunning test_rank_citations_relaxed_filtering...")
        test_rank_citations_relaxed_filtering()
        print("✅ PASS")
    except Exception as e:
        print(f"❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
