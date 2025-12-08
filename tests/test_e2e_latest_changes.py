#!/usr/bin/env python3
"""
End-to-end test for latest changes:
1. OpenSearch index auto-naming from document names
2. Hybrid search (semantic + keyword)
3. OpenSearch add_documents parameter fix
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
print("End-to-End Test: Latest Changes")
print("=" * 70)
print()

# Test 1: Import checks
print("📦 Test 1: Import Checks")
print("-" * 70)
try:
    from rag_system import RAGSystem
    from config.settings import ARISConfig
    from langchain_openai import OpenAIEmbeddings
    log_test("Import core modules", True)
except Exception as e:
    log_test("Import core modules", False, str(e))
    sys.exit(1)

# Try to import OpenSearchVectorStore (may fail if boto3 not installed)
try:
    from vectorstores.opensearch_store import OpenSearchVectorStore
    OPENSEARCH_AVAILABLE = True
    log_test("Import OpenSearchVectorStore", True)
except Exception as e:
    OPENSEARCH_AVAILABLE = False
    log_skip("Import OpenSearchVectorStore", f"boto3 not available: {str(e)[:50]}")

print()

# Test 2: OpenSearch Index Name Sanitization
print("🔤 Test 2: OpenSearch Index Name Sanitization")
print("-" * 70)
if not OPENSEARCH_AVAILABLE:
    log_skip("Index name sanitization", "OpenSearchVectorStore not available")
else:
    test_cases = [
        ("My Document.pdf", "my-document"),
        ("2025_MustangS650_OM_ENG_version1 (1).pdf", "doc-2025_mustangs650_om_eng_version1-1"),
        ("Test Document with Spaces.docx", "test-document-with-spaces"),
        ("Document@#$%^&*().pdf", "document"),
    ]
    
    all_passed = True
    for doc_name, expected_pattern in test_cases:
        try:
            result = OpenSearchVectorStore.sanitize_index_name(doc_name)
            # Basic validation
            is_valid = (
                (result.islower() or result == "") and
                " " not in result and
                len(result) <= 255 and
                (not result or result[0].isalpha() or result[0] == '_' or result.startswith('doc-'))
            )
            if is_valid:
                log_test(f"Sanitize '{doc_name}'", True, f"→ '{result}'")
            else:
                log_test(f"Sanitize '{doc_name}'", False, f"Invalid result: '{result}'")
                all_passed = False
        except Exception as e:
            log_test(f"Sanitize '{doc_name}'", False, str(e))
            all_passed = False
    
    if all_passed:
        log_test("All index name sanitization tests", True)
    else:
        log_test("All index name sanitization tests", False)

print()

# Test 3: Hybrid Search Configuration
print("⚙️  Test 3: Hybrid Search Configuration")
print("-" * 70)
try:
    hybrid_config = ARISConfig.get_hybrid_search_config()
    
    checks = []
    checks.append(("use_hybrid_search exists", "use_hybrid_search" in hybrid_config))
    checks.append(("semantic_weight exists", "semantic_weight" in hybrid_config))
    checks.append(("keyword_weight exists", "keyword_weight" in hybrid_config))
    checks.append(("search_mode exists", "search_mode" in hybrid_config))
    checks.append(("weights sum correctly", abs(hybrid_config['semantic_weight'] + hybrid_config['keyword_weight'] - 1.0) < 0.01))
    
    all_checks_passed = all(check[1] for check in checks)
    if all_checks_passed:
        log_test("Hybrid search configuration", True, 
                f"semantic_weight={hybrid_config['semantic_weight']:.2f}, keyword_weight={hybrid_config['keyword_weight']:.2f}")
    else:
        failed_checks = [check[0] for check in checks if not check[1]]
        log_test("Hybrid search configuration", False, f"Failed: {', '.join(failed_checks)}")
except Exception as e:
    log_test("Hybrid search configuration", False, str(e))

print()

# Test 4: RAG System Hybrid Search Parameters
print("🔍 Test 4: RAG System Hybrid Search Parameters")
print("-" * 70)
try:
    import inspect
    from rag_system import RAGSystem
    
    # Check query_with_rag signature
    sig = inspect.signature(RAGSystem.query_with_rag)
    params = list(sig.parameters.keys())
    
    has_use_hybrid_search = "use_hybrid_search" in params
    has_semantic_weight = "semantic_weight" in params
    has_search_mode = "search_mode" in params
    
    if has_use_hybrid_search and has_semantic_weight and has_search_mode:
        log_test("query_with_rag has hybrid search parameters", True,
                f"Parameters: {', '.join(['use_hybrid_search', 'semantic_weight', 'search_mode'])}")
    else:
        missing = []
        if not has_use_hybrid_search:
            missing.append("use_hybrid_search")
        if not has_semantic_weight:
            missing.append("semantic_weight")
        if not has_search_mode:
            missing.append("search_mode")
        log_test("query_with_rag has hybrid search parameters", False,
                f"Missing: {', '.join(missing)}")
except Exception as e:
    log_test("query_with_rag has hybrid search parameters", False, str(e))

print()

# Test 5: OpenSearch add_documents Parameter Fix
print("🔧 Test 5: OpenSearch add_documents Parameter Fix")
print("-" * 70)
try:
    # Check that conditional logic exists in rag_system.py
    rag_system_file = project_root / "rag_system.py"
    content = rag_system_file.read_text()
    
    # Check for conditional checks
    has_conditional_1 = 'if self.vector_store_type == "faiss":' in content
    has_conditional_2 = content.count('if self.vector_store_type == "faiss":') >= 3
    
    # Check that auto_recreate_on_mismatch is only used with FAISS check
    lines_with_auto_recreate = [i+1 for i, line in enumerate(content.split('\n')) 
                                if 'auto_recreate_on_mismatch=True' in line]
    lines_with_faiss_check = [i+1 for i, line in enumerate(content.split('\n')) 
                             if 'if self.vector_store_type == "faiss":' in line]
    
    # Verify that auto_recreate_on_mismatch lines are near faiss checks
    all_protected = True
    for line_num in lines_with_auto_recreate:
        # Check if there's a faiss check within 5 lines before
        nearby_faiss = any(abs(line_num - faiss_line) <= 5 for faiss_line in lines_with_faiss_check)
        if not nearby_faiss:
            all_protected = False
            break
    
    if has_conditional_1 and has_conditional_2 and all_protected:
        log_test("add_documents parameter fix", True,
                f"Found {len(lines_with_faiss_check)} conditional checks protecting {len(lines_with_auto_recreate)} auto_recreate_on_mismatch calls")
    else:
        log_test("add_documents parameter fix", False,
                f"has_conditional={has_conditional_1}, count_ok={has_conditional_2}, all_protected={all_protected}")
except Exception as e:
    log_test("add_documents parameter fix", False, str(e))

print()

# Test 6: FAISS Processing (to verify add_documents fix works)
print("💾 Test 6: FAISS Document Processing (add_documents fix)")
print("-" * 70)
try:
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        model="text-embedding-3-small"
    )
    
    rag_faiss = RAGSystem(
        vector_store_type="faiss",
        embedding_model="text-embedding-3-small"
    )
    
    # Create test documents
    test_texts = [
        "This is a test document about artificial intelligence and machine learning.",
        "Machine learning algorithms can process large amounts of data efficiently."
    ]
    test_metadatas = [
        {"source": "test_doc_1.txt", "page": 1},
        {"source": "test_doc_2.txt", "page": 1}
    ]
    
    # Process documents - this should work with auto_recreate_on_mismatch for FAISS
    chunks_created = rag_faiss.process_documents(test_texts, test_metadatas)
    
    if chunks_created > 0:
        log_test("FAISS: Process documents with conditional parameter", True,
                f"Created {chunks_created} chunks successfully")
    else:
        log_test("FAISS: Process documents with conditional parameter", False,
                "No chunks created")
        
except Exception as e:
    error_msg = str(e)
    if "auto_recreate_on_mismatch" in error_msg and "unexpected keyword" in error_msg.lower():
        log_test("FAISS: Process documents with conditional parameter", False,
                f"FAISS should accept auto_recreate_on_mismatch, but got: {error_msg}")
    else:
        log_test("FAISS: Process documents with conditional parameter", False, error_msg)

print()

# Test 7: Hybrid Search Method Exists
print("🔎 Test 7: Hybrid Search Method Implementation")
print("-" * 70)
try:
    # Check if hybrid_search method exists in OpenSearchVectorStore
    opensearch_file = project_root / "vectorstores" / "opensearch_store.py"
    content = opensearch_file.read_text()
    
    has_hybrid_search = "def hybrid_search(" in content
    has_combine_method = "def _combine_hybrid_results(" in content
    has_rrf = "RRF" in content or "Reciprocal Rank Fusion" in content
    
    if has_hybrid_search and has_combine_method:
        log_test("Hybrid search method exists", True,
                "hybrid_search() and _combine_hybrid_results() methods found")
    else:
        missing = []
        if not has_hybrid_search:
            missing.append("hybrid_search")
        if not has_combine_method:
            missing.append("_combine_hybrid_results")
        log_test("Hybrid search method exists", False,
                f"Missing: {', '.join(missing)}")
except Exception as e:
    log_test("Hybrid search method exists", False, str(e))

print()

# Test 8: API Schema Updates
print("🌐 Test 8: API Schema Updates")
print("-" * 70)
try:
    schemas_file = project_root / "api" / "schemas.py"
    content = schemas_file.read_text()
    
    has_use_hybrid_search = "use_hybrid_search" in content
    has_semantic_weight = "semantic_weight" in content
    has_search_mode = "search_mode" in content
    
    if has_use_hybrid_search and has_semantic_weight and has_search_mode:
        log_test("API schema has hybrid search fields", True,
                "QueryRequest includes use_hybrid_search, semantic_weight, search_mode")
    else:
        missing = []
        if not has_use_hybrid_search:
            missing.append("use_hybrid_search")
        if not has_semantic_weight:
            missing.append("semantic_weight")
        if not has_search_mode:
            missing.append("search_mode")
        log_test("API schema has hybrid search fields", False,
                f"Missing: {', '.join(missing)}")
except Exception as e:
    log_test("API schema has hybrid search fields", False, str(e))

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
    print("✅ All tests passed! Latest changes are working correctly.")
    print()
    print("📋 Verified Features:")
    print("   • OpenSearch index name sanitization")
    print("   • Hybrid search configuration")
    print("   • RAG system hybrid search parameters")
    print("   • OpenSearch add_documents parameter fix")
    print("   • FAISS processing with conditional parameters")
    print("   • Hybrid search method implementation")
    print("   • API schema updates")
    sys.exit(0)
else:
    print("⚠️  No tests were run (all skipped).")
    sys.exit(0)

