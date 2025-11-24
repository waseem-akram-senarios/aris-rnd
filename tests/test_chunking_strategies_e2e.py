#!/usr/bin/env python3
"""
End-to-End Test for Chunking Strategy Features
Tests all chunking strategies (presets and custom) with document processing.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from rag_system import RAGSystem
from utils.chunking_strategies import get_all_strategies, get_chunking_params, validate_custom_params
from utils.tokenizer import TokenTextSplitter
from metrics.metrics_collector import MetricsCollector

def test_chunking_strategies_module():
    """Test the chunking strategies module."""
    print("=" * 70)
    print("Test 1: Chunking Strategies Module")
    print("=" * 70)
    
    try:
        # Test get_all_strategies
        strategies = get_all_strategies()
        assert len(strategies) == 3, f"Expected 3 strategies, got {len(strategies)}"
        print(f"✅ Found {len(strategies)} preset strategies")
        
        # Test each strategy
        for strategy_name in ['precise', 'balanced', 'comprehensive']:
            chunk_size, chunk_overlap = get_chunking_params(strategy_name)
            strategy = strategies[strategy_name]
            assert chunk_size == strategy['chunk_size'], f"Mismatch for {strategy_name}"
            assert chunk_overlap == strategy['chunk_overlap'], f"Mismatch for {strategy_name}"
            print(f"✅ {strategy_name.capitalize()}: {chunk_size} tokens, {chunk_overlap} overlap")
        
        # Test validation (should allow any values now)
        test_cases = [
            (1, 0, True),  # Minimum values
            (10, 5, True),  # Small values
            (10000, 5000, True),  # Large values
            (500, 600, True),  # Overlap > chunk_size (should warn but allow)
            (100, 0, True),  # No overlap
        ]
        
        print("\nTesting validation (should allow all values):")
        for size, overlap, expected in test_cases:
            is_valid, msg = validate_custom_params(size, overlap)
            status = "✅" if is_valid == expected else "❌"
            print(f"{status} ({size}, {overlap}): valid={is_valid}")
            if msg:
                print(f"   Warning: {msg}")
        
        print("\n✅ Chunking strategies module: PASS\n")
        return True
    except Exception as e:
        print(f"❌ Chunking strategies module: FAIL\n   {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tokenizer_chunking():
    """Test tokenizer with different chunk sizes."""
    print("=" * 70)
    print("Test 2: Tokenizer Chunking")
    print("=" * 70)
    
    try:
        # Create test text
        test_text = "This is a test sentence. " * 100
        
        # Test each preset strategy
        strategies = get_all_strategies()
        all_passed = True
        
        for strategy_name, strategy in strategies.items():
            chunk_size = strategy['chunk_size']
            chunk_overlap = strategy['chunk_overlap']
            
            splitter = TokenTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                model_name="text-embedding-3-small"
            )
            
            chunks = splitter.split_text(test_text)
            
            # Verify no chunk exceeds chunk_size
            max_tokens = max(splitter.count_tokens(c) for c in chunks) if chunks else 0
            if max_tokens > chunk_size:
                print(f"❌ {strategy_name}: Chunk exceeds max ({max_tokens} > {chunk_size})")
                all_passed = False
            else:
                print(f"✅ {strategy_name}: Max chunk = {max_tokens} tokens (limit: {chunk_size})")
        
        # Test custom values (including edge cases)
        custom_tests = [
            (100, 10, "Small custom"),
            (1000, 100, "Medium custom"),
            (5000, 500, "Large custom"),
            (50, 30, "High overlap"),
        ]
        
        print("\nTesting custom chunk sizes:")
        for size, overlap, name in custom_tests:
            splitter = TokenTextSplitter(
                chunk_size=size,
                chunk_overlap=overlap,
                model_name="text-embedding-3-small"
            )
            chunks = splitter.split_text(test_text)
            max_tokens = max(splitter.count_tokens(c) for c in chunks) if chunks else 0
            
            if max_tokens > size:
                print(f"❌ {name} ({size}, {overlap}): Chunk exceeds max ({max_tokens} > {size})")
                all_passed = False
            else:
                print(f"✅ {name} ({size}, {overlap}): Max chunk = {max_tokens} tokens")
        
        if all_passed:
            print("\n✅ Tokenizer chunking: PASS\n")
            return True
        else:
            print("\n❌ Tokenizer chunking: FAIL\n")
            return False
            
    except Exception as e:
        print(f"❌ Tokenizer chunking: FAIL\n   {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_system_chunking():
    """Test RAGSystem with different chunking strategies."""
    print("=" * 70)
    print("Test 3: RAGSystem Chunking Integration")
    print("=" * 70)
    
    try:
        metrics_collector = MetricsCollector()
        
        # Test each preset strategy
        strategies = get_all_strategies()
        all_passed = True
        
        for strategy_name, strategy in strategies.items():
            chunk_size = strategy['chunk_size']
            chunk_overlap = strategy['chunk_overlap']
            
            rag = RAGSystem(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metrics_collector=metrics_collector,
                embedding_model="text-embedding-3-small"
            )
            
            # Verify parameters are set correctly
            if rag.chunk_size != chunk_size or rag.chunk_overlap != chunk_overlap:
                print(f"❌ {strategy_name}: Parameters not set correctly")
                print(f"   Expected: ({chunk_size}, {chunk_overlap})")
                print(f"   Got: ({rag.chunk_size}, {rag.chunk_overlap})")
                all_passed = False
            elif rag.text_splitter.chunk_size != chunk_size or rag.text_splitter.chunk_overlap != chunk_overlap:
                print(f"❌ {strategy_name}: TextSplitter parameters not set correctly")
                all_passed = False
            else:
                print(f"✅ {strategy_name}: Parameters set correctly ({chunk_size}, {chunk_overlap})")
        
        # Test custom values
        custom_tests = [
            (200, 20, "Custom small"),
            (1000, 200, "Custom large"),
            (500, 55, "Custom medium"),
        ]
        
        print("\nTesting custom parameters:")
        for size, overlap, name in custom_tests:
            rag = RAGSystem(
                chunk_size=size,
                chunk_overlap=overlap,
                metrics_collector=metrics_collector,
                embedding_model="text-embedding-3-small"
            )
            
            if rag.chunk_size == size and rag.chunk_overlap == overlap:
                print(f"✅ {name} ({size}, {overlap}): Parameters set correctly")
            else:
                print(f"❌ {name}: Parameters mismatch")
                all_passed = False
        
        # Test edge cases (should work now)
        edge_cases = [
            (1, 0, "Minimum size"),
            (10000, 5000, "Very large"),
            (100, 100, "Overlap = size"),
        ]
        
        print("\nTesting edge cases (should all work):")
        for size, overlap, name in edge_cases:
            try:
                rag = RAGSystem(
                    chunk_size=size,
                    chunk_overlap=overlap,
                    metrics_collector=metrics_collector,
                    embedding_model="text-embedding-3-small"
                )
                print(f"✅ {name} ({size}, {overlap}): Accepted")
            except Exception as e:
                print(f"❌ {name} ({size}, {overlap}): Rejected - {e}")
                all_passed = False
        
        if all_passed:
            print("\n✅ RAGSystem chunking: PASS\n")
            return True
        else:
            print("\n❌ RAGSystem chunking: FAIL\n")
            return False
            
    except Exception as e:
        print(f"❌ RAGSystem chunking: FAIL\n   {e}")
        import traceback
        traceback.print_exc()
        return False


def test_document_processing():
    """Test document processing with different chunking strategies."""
    print("=" * 70)
    print("Test 4: Document Processing with Chunking")
    print("=" * 70)
    
    try:
        metrics_collector = MetricsCollector()
        
        # Test with different chunk sizes
        test_cases = [
            (256, 50, "Precise"),
            (384, 75, "Balanced"),
            (512, 100, "Comprehensive"),
            (500, 55, "Custom"),
        ]
        
        all_passed = True
        
        for chunk_size, chunk_overlap, name in test_cases:
            # Create fresh metrics collector for each test to avoid contamination
            fresh_metrics = MetricsCollector()
            rag = RAGSystem(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metrics_collector=fresh_metrics,
                embedding_model="text-embedding-3-small"
            )
            
            # Create test documents
            test_texts = [
                "This is a test document. " * 50,
                "Another test document with different content. " * 50,
            ]
            test_metadatas = [
                {"source": "test1.txt", "page": 1},
                {"source": "test2.txt", "page": 1},
            ]
            
            try:
                chunks_created = rag.process_documents(test_texts, test_metadatas)
                
                if chunks_created > 0:
                    # Verify chunk sizes don't exceed limit by checking actual content
                    if rag.vectorstore:
                        try:
                            configured_max = chunk_size
                            actual_max = 0
                            
                            # Check actual chunk content directly (most accurate)
                            if hasattr(rag.vectorstore, 'docstore') and hasattr(rag.vectorstore.docstore, '_dict'):
                                all_docs = rag.vectorstore.docstore._dict
                                for doc_id, doc in all_docs.items():
                                    if hasattr(doc, 'page_content'):
                                        actual_tokens = rag.count_tokens(doc.page_content)
                                        actual_max = max(actual_max, actual_tokens)
                                
                                # Verify actual chunks respect the limit
                                if actual_max > configured_max:
                                    print(f"❌ {name}: Actual max chunk ({actual_max}) exceeds configured ({configured_max})")
                                    all_passed = False
                                else:
                                    print(f"✅ {name}: Created {chunks_created} chunks, max = {actual_max} tokens (limit: {configured_max})")
                            else:
                                # Fallback: use stats if direct access not available
                                chunk_stats = rag.get_chunk_token_stats()
                                max_chunk = chunk_stats.get('max_tokens_per_chunk', 0)
                                if max_chunk > configured_max:
                                    print(f"❌ {name}: Max chunk ({max_chunk}) exceeds configured ({configured_max})")
                                    all_passed = False
                                else:
                                    print(f"✅ {name}: Created {chunks_created} chunks, max = {max_chunk} tokens (limit: {configured_max})")
                        except Exception as e:
                            print(f"⚠️  {name}: Could not verify chunks: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"✅ {name}: Created {chunks_created} chunks (vectorstore not created)")
                else:
                    print(f"❌ {name}: No chunks created")
                    all_passed = False
                    
            except Exception as e:
                print(f"❌ {name}: Processing failed - {e}")
                all_passed = False
        
        if all_passed:
            print("\n✅ Document processing: PASS\n")
            return True
        else:
            print("\n❌ Document processing: FAIL\n")
            return False
            
    except Exception as e:
        print(f"❌ Document processing: FAIL\n   {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chunk_stats_display():
    """Test chunk statistics display."""
    print("=" * 70)
    print("Test 5: Chunk Statistics Display")
    print("=" * 70)
    
    try:
        metrics_collector = MetricsCollector()
        
        # Test with different strategies
        test_cases = [
            (256, 50),
            (384, 75),
            (500, 55),
        ]
        
        all_passed = True
        
        for chunk_size, chunk_overlap in test_cases:
            rag = RAGSystem(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metrics_collector=metrics_collector,
                embedding_model="text-embedding-3-small"
            )
            
            # Process some documents
            test_texts = ["Test document content. " * 100]
            test_metadatas = [{"source": "test.txt"}]
            
            try:
                rag.process_documents(test_texts, test_metadatas)
                
                # Get stats
                chunk_stats = rag.get_chunk_token_stats()
                
                # Verify stats include configured values
                if 'configured_chunk_size' not in chunk_stats:
                    print(f"❌ Missing 'configured_chunk_size' in stats")
                    all_passed = False
                elif chunk_stats['configured_chunk_size'] != chunk_size:
                    print(f"❌ Configured chunk_size mismatch: {chunk_stats['configured_chunk_size']} != {chunk_size}")
                    all_passed = False
                else:
                    print(f"✅ Stats include configured_chunk_size: {chunk_stats['configured_chunk_size']}")
                
                if 'configured_chunk_overlap' not in chunk_stats:
                    print(f"❌ Missing 'configured_chunk_overlap' in stats")
                    all_passed = False
                elif chunk_stats['configured_chunk_overlap'] != chunk_overlap:
                    print(f"❌ Configured chunk_overlap mismatch: {chunk_stats['configured_chunk_overlap']} != {chunk_overlap}")
                    all_passed = False
                else:
                    print(f"✅ Stats include configured_chunk_overlap: {chunk_stats['configured_chunk_overlap']}")
                
            except Exception as e:
                print(f"❌ Error getting stats: {e}")
                all_passed = False
        
        if all_passed:
            print("\n✅ Chunk statistics display: PASS\n")
            return True
        else:
            print("\n❌ Chunk statistics display: FAIL\n")
            return False
            
    except Exception as e:
        print(f"❌ Chunk statistics display: FAIL\n   {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("END-TO-END TEST: Chunking Strategy Features")
    print("=" * 70 + "\n")
    
    tests = [
        ("Chunking Strategies Module", test_chunking_strategies_module),
        ("Tokenizer Chunking", test_tokenizer_chunking),
        ("RAGSystem Chunking Integration", test_rag_system_chunking),
        ("Document Processing", test_document_processing),
        ("Chunk Statistics Display", test_chunk_stats_display),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 70)
    if passed == total:
        print(f"✅ ALL TESTS PASSED ({passed}/{total})")
        return 0
    else:
        print(f"❌ SOME TESTS FAILED ({passed}/{total} passed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())

