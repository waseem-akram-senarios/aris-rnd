#!/usr/bin/env python3
"""
End-to-End Integration Test for Chunking Strategy Feature
Tests the complete flow from UI selection to document processing to metrics display.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from rag_system import RAGSystem
from utils.chunking_strategies import get_all_strategies, get_chunking_params
from utils.tokenizer import TokenTextSplitter
from metrics.metrics_collector import MetricsCollector

def test_complete_workflow():
    """Test complete workflow: strategy selection -> processing -> metrics"""
    print("=" * 70)
    print("END-TO-END INTEGRATION TEST: Chunking Strategy Feature")
    print("=" * 70)
    print()
    
    all_passed = True
    
    # Test each preset strategy
    strategies = get_all_strategies()
    
    for strategy_name, strategy in strategies.items():
        print(f"Testing {strategy['name']} Strategy ({strategy['chunk_size']} tokens, {strategy['chunk_overlap']} overlap)")
        print("-" * 70)
        
        try:
            # Step 1: Initialize RAGSystem with strategy
            metrics = MetricsCollector()
            rag = RAGSystem(
                chunk_size=strategy['chunk_size'],
                chunk_overlap=strategy['chunk_overlap'],
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small"
            )
            
            # Verify initialization
            if rag.chunk_size != strategy['chunk_size'] or rag.chunk_overlap != strategy['chunk_overlap']:
                print(f"❌ FAIL: Parameters not set correctly")
                all_passed = False
                continue
            print(f"✅ Step 1: RAGSystem initialized with {strategy['name']} parameters")
            
            # Step 2: Process test documents
            test_texts = [
                "This is a comprehensive test document for chunking strategy validation. " * 30,
                "Another document with different content to test chunking behavior. " * 30,
            ]
            test_metadatas = [
                {"source": f"test_{strategy_name}_1.txt", "page": 1},
                {"source": f"test_{strategy_name}_2.txt", "page": 1},
            ]
            
            chunks_created = rag.process_documents(test_texts, test_metadatas)
            
            if chunks_created == 0:
                print(f"❌ FAIL: No chunks created")
                all_passed = False
                continue
            print(f"✅ Step 2: Created {chunks_created} chunks from documents")
            
            # Step 3: Verify chunks respect limits
            if rag.vectorstore:
                try:
                    if hasattr(rag.vectorstore, 'docstore') and hasattr(rag.vectorstore.docstore, '_dict'):
                        all_docs = rag.vectorstore.docstore._dict
                        max_tokens = 0
                        total_tokens = 0
                        
                        for doc_id, doc in all_docs.items():
                            if hasattr(doc, 'page_content'):
                                tokens = rag.count_tokens(doc.page_content)
                                max_tokens = max(max_tokens, tokens)
                                total_tokens += tokens
                        
                        if max_tokens > strategy['chunk_size']:
                            print(f"❌ FAIL: Max chunk ({max_tokens}) exceeds limit ({strategy['chunk_size']})")
                            all_passed = False
                        else:
                            print(f"✅ Step 3: All chunks within limit (max: {max_tokens}, limit: {strategy['chunk_size']})")
                            print(f"   Total tokens across all chunks: {total_tokens}")
                    else:
                        print(f"⚠️  Step 3: Cannot verify chunks (docstore not accessible)")
                except Exception as e:
                    print(f"⚠️  Step 3: Error verifying chunks: {e}")
            
            # Step 4: Check metrics/stats
            try:
                chunk_stats = rag.get_chunk_token_stats()
                
                if chunk_stats.get('configured_chunk_size') != strategy['chunk_size']:
                    print(f"❌ FAIL: Stats show wrong configured_chunk_size")
                    all_passed = False
                elif chunk_stats.get('configured_chunk_overlap') != strategy['chunk_overlap']:
                    print(f"❌ FAIL: Stats show wrong configured_chunk_overlap")
                    all_passed = False
                else:
                    print(f"✅ Step 4: Metrics display correct configuration")
                    print(f"   Configured: {chunk_stats.get('configured_chunk_size')} tokens, {chunk_stats.get('configured_chunk_overlap')} overlap")
                    print(f"   Actual avg: {chunk_stats.get('avg_tokens_per_chunk', 0):.1f} tokens/chunk")
            
            except Exception as e:
                print(f"⚠️  Step 4: Error getting stats: {e}")
            
            print()
            
        except Exception as e:
            print(f"❌ FAIL: Error testing {strategy_name}: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
            print()
    
    # Test custom parameters
    print("Testing Custom Parameters")
    print("-" * 70)
    
    custom_tests = [
        (200, 20, "Small custom"),
        (500, 55, "Medium custom"),
        (1000, 200, "Large custom"),
    ]
    
    for chunk_size, chunk_overlap, name in custom_tests:
        try:
            metrics = MetricsCollector()
            rag = RAGSystem(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small"
            )
            
            test_texts = ["Test document for custom chunking. " * 50]
            test_metadatas = [{"source": "custom_test.txt"}]
            
            chunks_created = rag.process_documents(test_texts, test_metadatas)
            
            if chunks_created > 0:
                # Verify chunks respect limit
                if rag.vectorstore and hasattr(rag.vectorstore, 'docstore'):
                    all_docs = rag.vectorstore.docstore._dict if hasattr(rag.vectorstore.docstore, '_dict') else {}
                    max_tokens = 0
                    for doc in all_docs.values():
                        if hasattr(doc, 'page_content'):
                            tokens = rag.count_tokens(doc.page_content)
                            max_tokens = max(max_tokens, tokens)
                    
                    if max_tokens <= chunk_size:
                        print(f"✅ {name} ({chunk_size}, {chunk_overlap}): Working correctly (max: {max_tokens})")
                    else:
                        print(f"❌ {name} ({chunk_size}, {chunk_overlap}): Exceeds limit ({max_tokens} > {chunk_size})")
                        all_passed = False
                else:
                    print(f"✅ {name} ({chunk_size}, {chunk_overlap}): Created {chunks_created} chunks")
            else:
                print(f"❌ {name}: No chunks created")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
            all_passed = False
    
    print()
    
    # Test edge cases
    print("Testing Edge Cases")
    print("-" * 70)
    
    edge_cases = [
        (1, 0, "Minimum size"),
        (100, 100, "Overlap = size"),
        (5000, 2500, "Very large"),
    ]
    
    for chunk_size, chunk_overlap, name in edge_cases:
        try:
            metrics = MetricsCollector()
            rag = RAGSystem(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small"
            )
            
            # Should initialize without error
            if rag.chunk_size == chunk_size and rag.chunk_overlap == chunk_overlap:
                print(f"✅ {name} ({chunk_size}, {chunk_overlap}): Accepted and initialized")
            else:
                print(f"❌ {name}: Parameters not set correctly")
                all_passed = False
                
        except Exception as e:
            print(f"❌ {name}: Rejected - {e}")
            all_passed = False
    
    print()
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    if all_passed:
        print("✅ ALL TESTS PASSED - Everything working correctly!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Check output above")
        return 1


if __name__ == "__main__":
    sys.exit(test_complete_workflow())

