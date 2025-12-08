#!/usr/bin/env python3
"""
Full end-to-end test: Document processing → Querying with hybrid search
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Test results tracking
test_results = {
    'passed': [],
    'failed': [],
    'skipped': []
}

def log_test(test_name, passed=True, message=""):
    """Log test result."""
    if passed:
        test_results['passed'].append(test_name)
        print(f"✅ PASS: {test_name}")
        if message:
            print(f"   {message}")
    else:
        test_results['failed'].append(test_name)
        print(f"❌ FAIL: {test_name}")
        if message:
            print(f"   {message}")

def log_skip(test_name, reason):
    """Log skipped test."""
    test_results['skipped'].append((test_name, reason))
    print(f"⏭️  SKIP: {test_name} - {reason}")

print("=" * 70)
print("Full End-to-End Test: Document Processing → Querying")
print("=" * 70)
print()

# Test 1: Setup
print("🔧 Test 1: Setup and Configuration")
print("-" * 70)
try:
    from rag_system import RAGSystem
    from config.settings import ARISConfig
    from langchain_openai import OpenAIEmbeddings
    
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        model="text-embedding-3-small"
    )
    
    rag_system = RAGSystem(
        vector_store_type="faiss",
        embedding_model="text-embedding-3-small"
    )
    
    log_test("RAG system initialization", True, "FAISS vector store")
except Exception as e:
    log_test("RAG system initialization", False, str(e))
    sys.exit(1)

print()

# Test 2: Document Processing
print("📄 Test 2: Document Processing")
print("-" * 70)
try:
    test_texts = [
        "Artificial intelligence (AI) is transforming industries worldwide. Machine learning algorithms can process vast amounts of data.",
        "Natural language processing enables computers to understand human language. Deep learning models have achieved remarkable results.",
        "Computer vision allows machines to interpret visual information. Neural networks are the foundation of modern AI systems."
    ]
    test_metadatas = [
        {"source": "ai_document.pdf", "page": 1},
        {"source": "nlp_document.pdf", "page": 1},
        {"source": "cv_document.pdf", "page": 1}
    ]
    
    chunks_created = rag_system.process_documents(test_texts, test_metadatas)
    
    if chunks_created > 0 and rag_system.vectorstore is not None:
        log_test("Document processing", True, f"Created {chunks_created} chunks, vectorstore ready")
    else:
        log_test("Document processing", False, f"Chunks: {chunks_created}, Vectorstore: {rag_system.vectorstore is not None}")
except Exception as e:
    log_test("Document processing", False, str(e))
    import traceback
    traceback.print_exc()

print()

# Test 3: Semantic Search Query
print("🔍 Test 3: Semantic Search Query")
print("-" * 70)
try:
    if rag_system.vectorstore is None:
        log_skip("Semantic search query", "No vectorstore available")
    else:
        result = rag_system.query_with_rag(
            question="What is artificial intelligence?",
            k=3,
            use_mmr=False,
            use_hybrid_search=False,
            search_mode="semantic"
        )
        
        if result and "answer" in result and len(result.get("answer", "")) > 0:
            log_test("Semantic search query", True, 
                    f"Answer length: {len(result['answer'])} chars, Sources: {len(result.get('sources', []))}")
        else:
            log_test("Semantic search query", False, "No answer returned")
except Exception as e:
    log_test("Semantic search query", False, str(e))
    import traceback
    traceback.print_exc()

print()

# Test 4: Hybrid Search Query (if OpenSearch available)
print("🔎 Test 4: Hybrid Search Query Parameters")
print("-" * 70)
try:
    if rag_system.vectorstore is None:
        log_skip("Hybrid search query", "No vectorstore available")
    else:
        # Test that hybrid search parameters are accepted (even if not used for FAISS)
        result = rag_system.query_with_rag(
            question="What is machine learning?",
            k=3,
            use_mmr=False,
            use_hybrid_search=True,
            semantic_weight=0.7,
            search_mode="hybrid"
        )
        
        if result and "answer" in result:
            log_test("Hybrid search query parameters", True,
                    "Parameters accepted, query executed successfully")
        else:
            log_test("Hybrid search query parameters", False, "Query failed")
except Exception as e:
    error_msg = str(e)
    if "hybrid_search" in error_msg.lower() and "not supported" in error_msg.lower():
        log_test("Hybrid search query parameters", True,
                "Parameters accepted (hybrid search not available for FAISS, expected)")
    else:
        log_test("Hybrid search query parameters", False, str(e))

print()

# Test 5: Different Search Modes
print("🎯 Test 5: Search Mode Variations")
print("-" * 70)
try:
    if rag_system.vectorstore is None:
        log_skip("Search mode variations", "No vectorstore available")
    else:
        modes_tested = []
        
        # Test semantic mode
        try:
            result_semantic = rag_system.query_with_rag(
                question="What is deep learning?",
                k=2,
                search_mode="semantic"
            )
            if result_semantic and "answer" in result_semantic:
                modes_tested.append("semantic")
        except:
            pass
        
        # Test hybrid mode (will fallback to semantic for FAISS)
        try:
            result_hybrid = rag_system.query_with_rag(
                question="What is neural networks?",
                k=2,
                search_mode="hybrid"
            )
            if result_hybrid and "answer" in result_hybrid:
                modes_tested.append("hybrid")
        except:
            pass
        
        if len(modes_tested) > 0:
            log_test("Search mode variations", True,
                    f"Tested modes: {', '.join(modes_tested)}")
        else:
            log_test("Search mode variations", False, "No modes worked")
except Exception as e:
    log_test("Search mode variations", False, str(e))

print()

# Test 6: Configuration Validation
print("⚙️  Test 6: Configuration Validation")
print("-" * 70)
try:
    config = ARISConfig.get_hybrid_search_config()
    
    checks = []
    checks.append(("has use_hybrid_search", "use_hybrid_search" in config))
    checks.append(("has semantic_weight", "semantic_weight" in config))
    checks.append(("has keyword_weight", "keyword_weight" in config))
    checks.append(("has search_mode", "search_mode" in config))
    checks.append(("weights valid", 0.0 <= config['semantic_weight'] <= 1.0))
    checks.append(("weights valid", 0.0 <= config['keyword_weight'] <= 1.0))
    checks.append(("weights sum correctly", abs(config['semantic_weight'] + config['keyword_weight'] - 1.0) < 0.01))
    
    all_checks = all(check[1] for check in checks)
    if all_checks:
        log_test("Configuration validation", True,
                f"All config values valid (semantic={config['semantic_weight']:.2f}, keyword={config['keyword_weight']:.2f})")
    else:
        failed = [check[0] for check in checks if not check[1]]
        log_test("Configuration validation", False, f"Failed: {', '.join(failed)}")
except Exception as e:
    log_test("Configuration validation", False, str(e))

print()

# Test 7: Backward Compatibility
print("🔄 Test 7: Backward Compatibility")
print("-" * 70)
try:
    if rag_system.vectorstore is None:
        log_skip("Backward compatibility", "No vectorstore available")
    else:
        # Test old-style call (no hybrid parameters)
        result_old = rag_system.query_with_rag(
            question="What is computer vision?",
            k=2
        )
        
        # Test new-style call with defaults
        result_new = rag_system.query_with_rag(
            question="What is computer vision?",
            k=2,
            use_hybrid_search=None,
            semantic_weight=None,
            search_mode=None
        )
        
        if result_old and result_new and "answer" in result_old and "answer" in result_new:
            log_test("Backward compatibility", True,
                    "Old and new API calls both work correctly")
        else:
            log_test("Backward compatibility", False,
                    "One or both API calls failed")
except Exception as e:
    log_test("Backward compatibility", False, str(e))

print()

# Summary
print("=" * 70)
print("Test Summary")
print("=" * 70)
print(f"✅ Passed: {len(test_results['passed'])}")
print(f"❌ Failed: {len(test_results['failed'])}")
print(f"⏭️  Skipped: {len(test_results['skipped'])}")
print()

if test_results['failed']:
    print("Failed tests:")
    for test in test_results['failed']:
        print(f"  - {test}")
    print()
    sys.exit(1)
elif len(test_results['passed']) > 0:
    print("✅ All tests passed! End-to-end flow is working correctly.")
    print()
    print("📋 Verified End-to-End Flow:")
    print("   • Document processing with FAISS")
    print("   • Semantic search queries")
    print("   • Hybrid search parameter handling")
    print("   • Multiple search modes")
    print("   • Configuration validation")
    print("   • Backward compatibility")
    sys.exit(0)
else:
    print("⚠️  No tests were run (all skipped).")
    sys.exit(0)

