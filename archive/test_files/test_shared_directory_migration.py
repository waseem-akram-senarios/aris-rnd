#!/usr/bin/env python3
"""
Test shared directory migration - verify all imports work correctly
"""
import sys
import os
import ast
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_shared_directory_structure():
    """Test that shared directory structure exists"""
    print("="*70)
    print("1. Testing Shared Directory Structure")
    print("="*70)
    
    required_paths = [
        "shared/config/settings.py",
        "shared/schemas.py",
        "shared/utils/chunking_strategies.py",
        "shared/utils/tokenizer.py"
    ]
    
    all_exist = True
    for path in required_paths:
        if os.path.exists(path):
            print(f"✅ {path}")
        else:
            print(f"❌ {path} - NOT FOUND")
            all_exist = False
    
    return all_exist

def test_critical_imports():
    """Test all critical imports"""
    print("\n" + "="*70)
    print("2. Testing Critical Imports")
    print("="*70)
    
    imports = [
        ("shared.config.settings", "ARISConfig"),
        ("shared.schemas", "Citation"),
        ("shared.schemas", "ImageResult"),
        ("shared.utils.chunking_strategies", "get_all_strategies"),
        ("shared.utils.tokenizer", "TokenTextSplitter"),
        ("shared.utils.pdf_metadata_extractor", "extract_pdf_metadata"),
        ("api.service", "ServiceContainer"),
        ("api.rag_system", "RAGSystem"),
    ]
    
    results = []
    for module_name, item_name in imports:
        try:
            module = __import__(module_name, fromlist=[item_name])
            getattr(module, item_name)
            print(f"✅ {module_name}.{item_name}")
            results.append(True)
        except Exception as e:
            print(f"❌ {module_name}.{item_name}: {e}")
            results.append(False)
    
    return all(results)

def test_api_files_syntax():
    """Test that API files have valid syntax"""
    print("\n" + "="*70)
    print("3. Testing API Files Syntax")
    print("="*70)
    
    api_files = [
        "api/main.py",
        "api/app.py",
        "api/rag_system.py",
        "api/service.py"
    ]
    
    results = []
    for file_path in api_files:
        if not os.path.exists(file_path):
            print(f"⚠️  {file_path} - File not found")
            results.append(False)
            continue
        
        try:
            with open(file_path, 'r') as f:
                code = f.read()
                ast.parse(code)
            print(f"✅ {file_path} - Syntax valid")
            results.append(True)
        except SyntaxError as e:
            print(f"❌ {file_path} - Syntax error: {e}")
            results.append(False)
        except Exception as e:
            print(f"⚠️  {file_path} - Error: {e}")
            results.append(False)
    
    return all(results)

def test_servicecontainer_initialization():
    """Test ServiceContainer still works with new imports"""
    print("\n" + "="*70)
    print("4. Testing ServiceContainer Initialization")
    print("="*70)
    
    try:
        from api.service import ServiceContainer
        
        container = ServiceContainer(
            use_cerebras=False,
            embedding_model='text-embedding-3-small',
            openai_model='gpt-4o-mini',
            cerebras_model='llama-3.1-8b-instruct',
            vector_store_type='faiss',
            opensearch_domain='',
            chunk_size=384,
            chunk_overlap=120
        )
        
        print("✅ ServiceContainer initialized successfully")
        print(f"  - rag_system: {container.rag_system is not None}")
        print(f"  - document_processor: {container.document_processor is not None}")
        print(f"  - metrics_collector: {container.metrics_collector is not None}")
        print(f"  - document_registry: {container.document_registry is not None}")
        
        return True
    except Exception as e:
        print(f"❌ ServiceContainer initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints_imports():
    """Test that API endpoints can be imported"""
    print("\n" + "="*70)
    print("5. Testing API Endpoints Imports")
    print("="*70)
    
    try:
        # Test main.py imports
        from api.main import app
        print("✅ api.main.app imported")
        
        # Check if schemas are accessible
        from shared.schemas import (
            QueryRequest, QueryResponse, DocumentMetadata,
            Citation, ImageResult
        )
        print("✅ shared.schemas imports working")
        
        return True
    except Exception as e:
        print(f"❌ API endpoints import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_system_imports():
    """Test that RAGSystem imports work"""
    print("\n" + "="*70)
    print("6. Testing RAGSystem Imports")
    print("="*70)
    
    try:
        from api.rag_system import RAGSystem
        
        # Try to initialize (may fail if dependencies missing, but import should work)
        print("✅ api.rag_system.RAGSystem imported")
        
        # Check that it has required methods
        if hasattr(RAGSystem, '__init__'):
            print("✅ RAGSystem has __init__ method")
        else:
            print("⚠️  RAGSystem missing __init__ method")
        
        return True
    except Exception as e:
        print(f"❌ RAGSystem import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_moved_files():
    """Test that moved files are in correct locations"""
    print("\n" + "="*70)
    print("7. Testing Moved Files")
    print("="*70)
    
    # Files that should exist in shared
    shared_files = [
        "shared/schemas.py",
        "shared/config/settings.py",
        "shared/utils/pdf_metadata_extractor.py"
    ]
    
    # Files that should NOT exist in old locations
    old_locations = [
        "api/schemas.py",
        "config/accuracy_config.py"
    ]
    
    all_ok = True
    
    # Check shared files exist
    for file_path in shared_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"⚠️  {file_path} not found (may be expected)")
    
    # Check old locations don't exist
    for file_path in old_locations:
        if not os.path.exists(file_path):
            print(f"✅ {file_path} correctly removed")
        else:
            print(f"⚠️  {file_path} still exists (should be moved)")
            all_ok = False
    
    return all_ok

def main():
    """Run all tests"""
    print("="*70)
    print("SHARED DIRECTORY MIGRATION TEST")
    print("="*70)
    print()
    
    results = []
    
    results.append(("Shared Directory Structure", test_shared_directory_structure()))
    results.append(("Critical Imports", test_critical_imports()))
    results.append(("API Files Syntax", test_api_files_syntax()))
    results.append(("ServiceContainer Initialization", test_servicecontainer_initialization()))
    results.append(("API Endpoints Imports", test_api_endpoints_imports()))
    results.append(("RAGSystem Imports", test_rag_system_imports()))
    results.append(("Moved Files", test_moved_files()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Shared directory migration is working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) had issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())




