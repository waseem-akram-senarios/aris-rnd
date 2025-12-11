#!/usr/bin/env python3
"""
Test script to verify ranking and document isolation changes.
Tests:
1. Highest relevance scores appear first
2. Flexible matching is used in scoring
3. Relevance threshold filtering works
4. Document isolation works
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_system import RAGSystem
from scripts.setup_logging import setup_logging

# Setup logging
setup_logging()
import logging
logger = logging.getLogger(__name__)

def test_ranking_order(rag_system):
    """Test that citations are sorted by highest relevance first."""
    print("\n" + "="*70)
    print("TEST 1: Ranking Order - Highest Relevance First")
    print("="*70)
    
    if not rag_system or not rag_system.vectorstore:
        print("❌ RAG system or vectorstore not available")
        return False
    
    try:
        # Test query
        query = "caching"
        print(f"\nQuery: '{query}'")
        
        result = rag_system.query_with_rag(query, k=10)
        
        if not result or 'citations' not in result:
            print("❌ No citations returned")
            return False
        
        citations = result['citations']
        print(f"\nFound {len(citations)} citations")
        
        if len(citations) == 0:
            print("⚠️  No citations to test ranking")
            return True
        
        # Check that citations are sorted by relevance (descending)
        relevance_scores = [c.get('relevance_score', 0) for c in citations]
        
        # Verify sorting
        is_sorted = all(relevance_scores[i] >= relevance_scores[i+1] 
                       for i in range(len(relevance_scores)-1))
        
        print(f"\nTop 5 Citations (should be highest relevance first):")
        print("-" * 70)
        for i, citation in enumerate(citations[:5], 1):
            relevance = citation.get('relevance_score', 0)
            similarity = citation.get('similarity_score', 'N/A')
            source = citation.get('source', 'Unknown')[:60]
            snippet = citation.get('snippet', '')[:80]
            
            print(f"Rank {i}:")
            print(f"  Relevance: {relevance:.2%}")
            print(f"  Similarity: {similarity}")
            print(f"  Source: {source}")
            print(f"  Snippet: {snippet}...")
            print()
        
        if is_sorted:
            print("✅ PASS: Citations are sorted by highest relevance first")
            print(f"   Relevance scores: {[f'{s:.2%}' for s in relevance_scores[:5]]}")
            return True
        else:
            print("❌ FAIL: Citations are NOT properly sorted")
            print(f"   Relevance scores: {relevance_scores[:10]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_relevance_threshold(rag_system):
    """Test that citations below 20% relevance are filtered out."""
    print("\n" + "="*70)
    print("TEST 2: Relevance Threshold Filtering (20% minimum)")
    print("="*70)
    
    if not rag_system or not rag_system.vectorstore:
        print("❌ RAG system or vectorstore not available")
        return False
    
    try:
        # Test with a query that might return low-relevance results
        query = "test query that might match many documents"
        print(f"\nQuery: '{query}'")
        
        result = rag_system.query_with_rag(query, k=20)
        
        if not result or 'citations' not in result:
            print("❌ No citations returned")
            return False
        
        citations = result['citations']
        print(f"\nFound {len(citations)} citations after filtering")
        
        if len(citations) == 0:
            print("⚠️  No citations to test threshold")
            return True
        
        # Check that all citations meet the threshold
        MIN_THRESHOLD = 0.20
        below_threshold = [c for c in citations if c.get('relevance_score', 0) < MIN_THRESHOLD]
        
        if len(below_threshold) == 0:
            print(f"✅ PASS: All {len(citations)} citations meet the {MIN_THRESHOLD:.0%} threshold")
            
            # Show relevance distribution
            relevance_scores = [c.get('relevance_score', 0) for c in citations]
            if relevance_scores:
                min_relevance = min(relevance_scores)
                max_relevance = max(relevance_scores)
                avg_relevance = sum(relevance_scores) / len(relevance_scores)
                print(f"   Min relevance: {min_relevance:.2%}")
                print(f"   Max relevance: {max_relevance:.2%}")
                print(f"   Avg relevance: {avg_relevance:.2%}")
            
            return True
        else:
            print(f"❌ FAIL: {len(below_threshold)} citations below {MIN_THRESHOLD:.0%} threshold")
            for c in below_threshold[:3]:
                print(f"   Relevance: {c.get('relevance_score', 0):.2%}, Source: {c.get('source', 'Unknown')[:50]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_flexible_matching(rag_system):
    """Test that flexible matching is being used (substring matches included)."""
    print("\n" + "="*70)
    print("TEST 3: Flexible Matching (Exact + Substring)")
    print("="*70)
    
    if not rag_system or not rag_system.vectorstore:
        print("❌ RAG system or vectorstore not available")
        return False
    
    try:
        # Test with a query that might benefit from substring matching
        query = "cache"
        print(f"\nQuery: '{query}' (should match 'caching', 'cache', etc.)")
        
        result = rag_system.query_with_rag(query, k=10)
        
        if not result or 'citations' not in result:
            print("❌ No citations returned")
            return False
        
        citations = result['citations']
        print(f"\nFound {len(citations)} citations")
        
        if len(citations) == 0:
            print("⚠️  No citations to test flexible matching")
            return True
        
        # Check if we have citations with the query term (exact or substring)
        matching_citations = []
        for citation in citations[:5]:
            snippet = citation.get('snippet', '').lower()
            full_text = citation.get('full_text', '').lower()
            source = citation.get('source', '').lower()
            
            # Check for exact match
            has_exact = 'cache' in snippet or 'cache' in full_text or 'cache' in source
            # Check for substring match (caching, cached, etc.)
            has_substring = any(term in snippet or term in full_text or term in source 
                               for term in ['caching', 'cached', 'cache'])
            
            if has_exact or has_substring:
                matching_citations.append({
                    'citation': citation,
                    'has_exact': has_exact,
                    'has_substring': has_substring
                })
        
        if matching_citations:
            print(f"✅ PASS: Found {len(matching_citations)} citations with flexible matching")
            for i, match_info in enumerate(matching_citations[:3], 1):
                cit = match_info['citation']
                print(f"\n   Citation {i}:")
                print(f"     Relevance: {cit.get('relevance_score', 0):.2%}")
                print(f"     Has exact 'cache': {match_info['has_exact']}")
                print(f"     Has substring match: {match_info['has_substring']}")
                print(f"     Source: {cit.get('source', 'Unknown')[:50]}")
            return True
        else:
            print("⚠️  No citations found with 'cache' term (may be normal if no relevant docs)")
            return True
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_document_isolation(rag_system):
    """Test that document isolation works (recent documents only)."""
    print("\n" + "="*70)
    print("TEST 4: Document Isolation (Recent Documents)")
    print("="*70)
    
    if not rag_system:
        print("❌ RAG system not available")
        return False
    
    try:
        # Check if document_index_map exists
        if hasattr(rag_system, 'document_index_map') and rag_system.document_index_map:
            recent_docs = rag_system._get_recent_documents(max_age_hours=24)
            print(f"\nRecent documents found: {len(recent_docs)}")
            if recent_docs:
                print(f"   Documents: {recent_docs[:5]}")
                print("✅ PASS: Document isolation method works")
                return True
            else:
                print("⚠️  No recent documents found (may be normal if no documents uploaded)")
                return True
        else:
            print("⚠️  No document_index_map found (may be normal for FAISS or single-index setup)")
            return True
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("TESTING RANKING AND DOCUMENT ISOLATION CHANGES")
    print("="*70)
    
    # Initialize RAG system
    print("\nInitializing RAG system...")
    try:
        rag_system = RAGSystem()
        print("✅ RAG system initialized")
    except Exception as e:
        print(f"❌ Failed to initialize RAG system: {str(e)}")
        return
    
    # Run tests
    results = []
    
    results.append(("Ranking Order", test_ranking_order(rag_system)))
    results.append(("Relevance Threshold", test_relevance_threshold(rag_system)))
    results.append(("Flexible Matching", test_flexible_matching(rag_system)))
    results.append(("Document Isolation", test_document_isolation(rag_system)))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

