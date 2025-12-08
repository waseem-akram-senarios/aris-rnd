#!/usr/bin/env python3
"""
Test script to verify UI fixes for hybrid search visibility and functionality.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

def test_ui_conditional_logic():
    """Test that UI conditional logic is correct."""
    print("=" * 70)
    print("Test: UI Conditional Logic for Hybrid Search")
    print("=" * 70)
    
    # Read app.py to check for conditional logic
    app_file = project_root / "app.py"
    content = app_file.read_text()
    
    # Check for conditional check
    has_conditional = 'if hasattr(st.session_state.rag_system, \'vector_store_type\')' in content
    has_opensearch_check = 'vector_store_type.lower() == \'opensearch\'' in content
    has_faiss_fallback = 'search_mode = "Semantic Only"' in content and 'semantic_weight = 1.0' in content
    
    if has_conditional and has_opensearch_check and has_faiss_fallback:
        print("✅ PASS: UI conditional logic correctly implemented")
        print("   - Conditional check for OpenSearch found")
        print("   - FAISS fallback to semantic-only found")
        return True
    else:
        print("❌ FAIL: UI conditional logic missing or incorrect")
        if not has_conditional:
            print("   - Missing conditional check")
        if not has_opensearch_check:
            print("   - Missing OpenSearch check")
        if not has_faiss_fallback:
            print("   - Missing FAISS fallback")
        return False

def test_user_feedback_logic():
    """Test that user feedback is shown when hybrid search is not available."""
    print("\n" + "=" * 70)
    print("Test: User Feedback for Unavailable Hybrid Search")
    print("=" * 70)
    
    app_file = project_root / "app.py"
    content = app_file.read_text()
    
    # Check for user feedback message
    has_feedback = 'Hybrid search is only available for OpenSearch' in content
    has_check = 'vector_store_type.lower() != \'opensearch\'' in content
    has_fallback = 'search_mode_param = "semantic"' in content
    
    if has_feedback and has_check and has_fallback:
        print("✅ PASS: User feedback logic correctly implemented")
        print("   - Feedback message found")
        print("   - Vector store check found")
        print("   - Fallback to semantic found")
        return True
    else:
        print("❌ FAIL: User feedback logic missing or incorrect")
        if not has_feedback:
            print("   - Missing feedback message")
        if not has_check:
            print("   - Missing vector store check")
        if not has_fallback:
            print("   - Missing fallback logic")
        return False

def test_opensearch_knn_query():
    """Test that OpenSearch k-NN query structure is correct."""
    print("\n" + "=" * 70)
    print("Test: OpenSearch k-NN Query Structure")
    print("=" * 70)
    
    opensearch_file = project_root / "vectorstores" / "opensearch_store.py"
    content = opensearch_file.read_text()
    
    # Check that query field is removed from k-NN query
    has_knn_query = '"knn":' in content
    has_no_query_field = '"query":' not in content.split('knn_query = {')[1].split('}')[0] if 'knn_query = {' in content else False
    
    # More reliable check: look for the specific pattern
    lines = content.split('\n')
    in_knn_query = False
    has_query_field = False
    for i, line in enumerate(lines):
        if 'knn_query = {' in line:
            in_knn_query = True
        if in_knn_query and '"query":' in line and 'match_all' in line:
            has_query_field = True
            break
        if in_knn_query and '}' in line and line.strip().startswith('}'):
            break
    
    if has_knn_query and not has_query_field:
        print("✅ PASS: OpenSearch k-NN query structure is correct")
        print("   - k-NN query found")
        print("   - No unnecessary query field found")
        return True
    else:
        print("❌ FAIL: OpenSearch k-NN query structure may be incorrect")
        if not has_knn_query:
            print("   - k-NN query not found")
        if has_query_field:
            print("   - Unnecessary query field still present")
        return False

def test_type_checking():
    """Test that type checking is robust."""
    print("\n" + "=" * 70)
    print("Test: Robust Type Checking for OpenSearchVectorStore")
    print("=" * 70)
    
    rag_system_file = project_root / "rag_system.py"
    content = rag_system_file.read_text()
    
    # Check for improved type checking
    has_isinstance = 'isinstance(self.vectorstore, OpenSearchVectorStore)' in content
    has_class_name_check = "'OpenSearch' in self.vectorstore.__class__.__name__" in content
    has_is_opensearch = 'is_opensearch = False' in content
    
    if has_isinstance and has_class_name_check and has_is_opensearch:
        print("✅ PASS: Robust type checking implemented")
        print("   - isinstance check found")
        print("   - Class name fallback check found")
        print("   - is_opensearch flag found")
        return True
    else:
        print("❌ FAIL: Type checking may not be robust enough")
        if not has_isinstance:
            print("   - Missing isinstance check")
        if not has_class_name_check:
            print("   - Missing class name fallback")
        if not has_is_opensearch:
            print("   - Missing is_opensearch flag")
        return False

def main():
    """Run all tests."""
    results = []
    
    results.append(("UI Conditional Logic", test_ui_conditional_logic()))
    results.append(("User Feedback Logic", test_user_feedback_logic()))
    results.append(("OpenSearch k-NN Query", test_opensearch_knn_query()))
    results.append(("Type Checking", test_type_checking()))
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n✅ All code-level tests passed!")
        print("\n📋 Next Steps:")
        print("   1. Start Streamlit app: streamlit run app.py")
        print("   2. Test FAISS workflow: Select FAISS, verify hybrid search UI does NOT appear")
        print("   3. Test OpenSearch workflow: Select OpenSearch, verify hybrid search UI appears")
        print("   4. Test all three search modes for OpenSearch")
        print("   5. Test duplicate document handling")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the code.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

