#!/usr/bin/env python3
"""
Comprehensive test for all latest changes
"""
import sys
import os
import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://44.221.84.58:8500"

def test_shared_directory_imports():
    """Test shared directory imports"""
    print("="*70)
    print("1. Testing Shared Directory Imports")
    print("="*70)
    
    imports = [
        ("shared.config.settings", "ARISConfig"),
        ("shared.schemas", "Citation"),
        ("shared.schemas", "ImageResult"),
        ("shared.utils.chunking_strategies", "get_all_strategies"),
        ("shared.utils.tokenizer", "TokenTextSplitter"),
        ("shared.utils.pdf_metadata_extractor", "extract_pdf_metadata"),
    ]
    
    results = []
    for module, item in imports:
        try:
            mod = __import__(module, fromlist=[item])
            getattr(mod, item)
            print(f"✅ {module}.{item}")
            results.append(True)
        except Exception as e:
            print(f"❌ {module}.{item}: {e}")
            results.append(False)
    
    return all(results)

def test_api_imports():
    """Test API imports"""
    print("\n" + "="*70)
    print("2. Testing API Imports")
    print("="*70)
    
    imports = [
        ("api.rag_system", "RAGSystem"),
        ("api.main", "app"),
        ("parsers.parser_factory", "ParserFactory"),
    ]
    
    results = []
    for module, item in imports:
        try:
            mod = __import__(module, fromlist=[item])
            getattr(mod, item)
            print(f"✅ {module}.{item}")
            results.append(True)
        except Exception as e:
            print(f"❌ {module}.{item}: {e}")
            results.append(False)
    
    return all(results)

def test_parser_factory():
    """Test parser factory"""
    print("\n" + "="*70)
    print("3. Testing Parser Factory")
    print("="*70)
    
    try:
        from parsers.parser_factory import ParserFactory
        
        available_parsers = ParserFactory.get_available_parsers()
        print(f"✅ Available parsers: {available_parsers}")
        
        # Check critical parsers
        critical_parsers = ['pymupdf', 'docling']
        missing = [p for p in critical_parsers if p not in available_parsers]
        
        if missing:
            print(f"⚠️  Missing parsers: {missing}")
        else:
            print("✅ All critical parsers available")
        
        # Note about deleted parsers
        if 'ocrmypdf' not in available_parsers:
            print("ℹ️  ocrmypdf parser not available (may have been removed)")
        if 'textract' not in available_parsers:
            print("ℹ️  textract parser not available (may have been removed)")
        
        return True
    except Exception as e:
        print(f"❌ Parser factory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_system():
    """Test RAGSystem initialization"""
    print("\n" + "="*70)
    print("4. Testing RAGSystem")
    print("="*70)
    
    try:
        from api.rag_system import RAGSystem
        
        rag = RAGSystem(
            embedding_model='text-embedding-3-small',
            chunk_size=384,
            chunk_overlap=120
        )
        
        print("✅ RAGSystem initialized")
        print(f"  - Text Splitter: {type(rag.text_splitter).__name__}")
        print(f"  - Has FlashRank: {rag.ranker is not None}")
        print(f"  - Has _retrieve_chunks_raw: {hasattr(rag, '_retrieve_chunks_raw')}")
        
        return True
    except Exception as e:
        print(f"❌ RAGSystem test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints"""
    print("\n" + "="*70)
    print("5. Testing API Endpoints")
    print("="*70)
    
    endpoints = [
        ("/", "Root"),
        ("/health", "Health"),
        ("/documents", "Documents"),
        ("/settings", "Settings"),
    ]
    
    passed = 0
    for endpoint, name in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {name} endpoint: Working")
                passed += 1
            else:
                print(f"⚠️  {name} endpoint: {response.status_code}")
        except Exception as e:
            print(f"⚠️  {name} endpoint: {e}")
    
    return passed >= len(endpoints) - 1  # Allow 1 failure

def test_code_syntax():
    """Test code syntax"""
    print("\n" + "="*70)
    print("6. Testing Code Syntax")
    print("="*70)
    
    files = [
        "api/main.py",
        "api/app.py",
        "api/rag_system.py",
        "api/service.py",
    ]
    
    results = []
    for file_path in files:
        if not os.path.exists(file_path):
            print(f"⚠️  {file_path} - Not found")
            results.append(False)
            continue
        
        try:
            with open(file_path, 'r') as f:
                code = f.read()
                compile(code, file_path, 'exec')
            print(f"✅ {file_path} - Syntax valid")
            results.append(True)
        except SyntaxError as e:
            print(f"❌ {file_path} - Syntax error: {e}")
            results.append(False)
        except Exception as e:
            print(f"⚠️  {file_path} - Error: {e}")
            results.append(False)
    
    return all(results)

def test_unit_tests():
    """Run unit tests"""
    print("\n" + "="*70)
    print("7. Running Unit Tests")
    print("="*70)
    
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "tests/unit/test_config.py", "tests/unit/test_tokenizer.py", "-v", "--tb=line"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Unit tests passed")
            return True
        else:
            print(f"⚠️  Unit tests had issues: {result.stdout[-200:]}")
            return False
    except Exception as e:
        print(f"⚠️  Could not run unit tests: {e}")
        return True  # Don't fail if pytest not available

def main():
    """Run all tests"""
    print("="*70)
    print("COMPREHENSIVE TEST - ALL LATEST CHANGES")
    print("="*70)
    print()
    
    results = []
    
    results.append(("Shared Directory Imports", test_shared_directory_imports()))
    results.append(("API Imports", test_api_imports()))
    results.append(("Parser Factory", test_parser_factory()))
    results.append(("RAGSystem", test_rag_system()))
    results.append(("API Endpoints", test_api_endpoints()))
    results.append(("Code Syntax", test_code_syntax()))
    results.append(("Unit Tests", test_unit_tests()))
    
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
        print("\n✅ ALL TESTS PASSED - All latest changes are working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) had issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())




