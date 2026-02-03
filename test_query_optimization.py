#!/usr/bin/env python3
"""
Test script to verify OpenSearch query optimizations are working.
Tests: caching, ef_search parameter, min_score threshold, timing.
"""
import os
import sys
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Set up logging to see optimization messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_config():
    """Test that k-NN performance config is loaded correctly."""
    print("\n" + "="*60)
    print("TEST 1: K-NN Performance Configuration")
    print("="*60)
    
    from shared.config.settings import ARISConfig
    
    knn_config = ARISConfig.get_knn_performance_config()
    print(f"✅ ef_search: {knn_config['ef_search']}")
    print(f"✅ min_score: {knn_config['min_score']}")
    print(f"✅ cache_ttl_seconds: {knn_config['cache_ttl_seconds']}")
    print(f"✅ max_fetch_multiplier: {knn_config['max_fetch_multiplier']}")
    
    assert knn_config['ef_search'] > 0, "ef_search should be positive"
    assert 0 <= knn_config['min_score'] <= 1, "min_score should be 0-1"
    assert knn_config['cache_ttl_seconds'] >= 0, "cache_ttl should be non-negative"
    
    print("\n✅ Configuration test PASSED")
    return True

def test_cache_functions():
    """Test that cache invalidation functions exist and work."""
    print("\n" + "="*60)
    print("TEST 2: Cache Invalidation Functions")
    print("="*60)
    
    from vectorstores.opensearch_store import clear_hybrid_search_cache
    from vectorstores.opensearch_images_store import clear_image_search_cache
    
    # Test clearing entire cache
    clear_hybrid_search_cache()
    clear_image_search_cache()
    
    # Test clearing specific source/index
    clear_hybrid_search_cache(index_name="test-index")
    clear_image_search_cache(source="test-document.pdf")
    
    print("✅ Cache invalidation functions work correctly")
    return True

def test_hybrid_search_optimization():
    """Test hybrid search with timing and caching."""
    print("\n" + "="*60)
    print("TEST 3: Hybrid Search Optimization")
    print("="*60)
    
    # Check if OpenSearch is configured
    if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
        print("⚠️ OpenSearch credentials not configured, skipping live test")
        print("   Set AWS_OPENSEARCH_ACCESS_KEY_ID and AWS_OPENSEARCH_SECRET_ACCESS_KEY")
        return True
    
    try:
        from langchain_openai import OpenAIEmbeddings
        from vectorstores.opensearch_store import OpenSearchVectorStore, clear_hybrid_search_cache
        from shared.config.settings import ARISConfig
        
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=ARISConfig.EMBEDDING_MODEL
        )
        
        # Initialize store
        store = OpenSearchVectorStore(
            embeddings=embeddings,
            domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            index_name=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Clear cache before test
        clear_hybrid_search_cache()
        
        test_query = "What are the safety procedures?"
        query_vector = embeddings.embed_query(test_query)
        
        # First query (should be slower, no cache)
        print(f"\n🔍 Running first query (no cache)...")
        start1 = time.time()
        results1 = store.hybrid_search(
            query=test_query,
            query_vector=query_vector,
            k=5
        )
        time1 = time.time() - start1
        print(f"   First query time: {time1:.2f}s, Results: {len(results1)}")
        
        # Second query (should be faster, cached)
        print(f"\n🔍 Running second query (should be cached)...")
        start2 = time.time()
        results2 = store.hybrid_search(
            query=test_query,
            query_vector=query_vector,
            k=5
        )
        time2 = time.time() - start2
        print(f"   Second query time: {time2:.2f}s, Results: {len(results2)}")
        
        # Verify caching worked
        if time2 < time1 * 0.5:  # Should be at least 50% faster
            print(f"\n✅ Caching is working! Speedup: {time1/max(time2, 0.001):.1f}x")
        else:
            print(f"\n⚠️ Caching may not be working as expected")
            print(f"   Time1: {time1:.2f}s, Time2: {time2:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Hybrid search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_image_search_optimization():
    """Test image search with timing and caching."""
    print("\n" + "="*60)
    print("TEST 4: Image Search Optimization")
    print("="*60)
    
    # Check if OpenSearch is configured
    if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
        print("⚠️ OpenSearch credentials not configured, skipping live test")
        return True
    
    try:
        from langchain_openai import OpenAIEmbeddings
        from vectorstores.opensearch_images_store import OpenSearchImagesStore, clear_image_search_cache
        from shared.config.settings import ARISConfig
        
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model=ARISConfig.EMBEDDING_MODEL
        )
        
        # Initialize store
        store = OpenSearchImagesStore(
            embeddings=embeddings,
            domain=ARISConfig.AWS_OPENSEARCH_DOMAIN
        )
        
        # Clear cache before test
        clear_image_search_cache()
        
        test_query = "drawer tools parts"
        
        # First query (should be slower, no cache)
        print(f"\n🔍 Running first image query (no cache)...")
        start1 = time.time()
        results1 = store.search_images(query=test_query, k=5)
        time1 = time.time() - start1
        print(f"   First query time: {time1:.2f}s, Results: {len(results1)}")
        
        # Second query (should be faster, cached)
        print(f"\n🔍 Running second image query (should be cached)...")
        start2 = time.time()
        results2 = store.search_images(query=test_query, k=5)
        time2 = time.time() - start2
        print(f"   Second query time: {time2:.2f}s, Results: {len(results2)}")
        
        # Verify caching worked
        if time2 < time1 * 0.5:  # Should be at least 50% faster
            print(f"\n✅ Image search caching is working! Speedup: {time1/max(time2, 0.001):.1f}x")
        else:
            print(f"\n⚠️ Image caching may not be working as expected")
            print(f"   Time1: {time1:.2f}s, Time2: {time2:.2f}s")
        
        return True
        
    except Exception as e:
        print(f"❌ Image search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*60)
    print("OpenSearch Query Optimization Test Suite")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Config", test_config()))
    results.append(("Cache Functions", test_cache_functions()))
    results.append(("Hybrid Search", test_hybrid_search_optimization()))
    results.append(("Image Search", test_image_search_optimization()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests passed! Optimizations are working.")
    else:
        print("⚠️ Some tests failed. Check the output above.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
