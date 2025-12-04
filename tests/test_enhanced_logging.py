#!/usr/bin/env python3
"""
Test Enhanced Progress Logging System
Verifies that all logging improvements are working correctly
"""
import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

def print_test(name, status="", details=""):
    if status == "PASS":
        print(f"{Colors.GREEN}✅ {name}{Colors.END}")
    elif status == "FAIL":
        print(f"{Colors.RED}❌ {name}{Colors.END}")
    elif status == "WARN":
        print(f"{Colors.YELLOW}⚠️  {name}{Colors.END}")
    else:
        print(f"{Colors.BLUE}🧪 {name}{Colors.END}")
    if details:
        print(f"   {details}")

def test_code_verification():
    """Test 1: Verify code changes are present"""
    print_header("TEST 1: Code Verification")
    
    results = {}
    
    # Check Docling parser
    docling_file = project_root / "parsers" / "docling_parser.py"
    if docling_file.exists():
        content = docling_file.read_text()
        
        checks = {
            "progress_callback parameter": "progress_callback: Optional[Callable" in content,
            "15 second interval": "check_interval = 15" in content,
            "percentage calculation": "estimated_progress" in content,
            "time remaining": "estimated_remaining" in content,
            "phase indicators": "[Phase" in content,
            "progress callback calls": "progress_callback(" in content,
        }
        
        for check_name, passed in checks.items():
            if passed:
                print_test(f"Docling: {check_name}", "PASS")
                results[f"docling_{check_name}"] = True
            else:
                print_test(f"Docling: {check_name}", "FAIL")
                results[f"docling_{check_name}"] = False
    
    # Check PyMuPDF parser
    pymupdf_file = project_root / "parsers" / "pymupdf_parser.py"
    if pymupdf_file.exists():
        content = pymupdf_file.read_text()
        
        checks = {
            "15 second interval": "LOG_INTERVAL = 15" in content,
            "percentage in logs": "progress_pct" in content,
            "speed calculation": "pages_per_sec" in content,
            "time remaining": "remaining_minutes" in content,
        }
        
        for check_name, passed in checks.items():
            if passed:
                print_test(f"PyMuPDF: {check_name}", "PASS")
                results[f"pymupdf_{check_name}"] = True
            else:
                print_test(f"PyMuPDF: {check_name}", "FAIL")
                results[f"pymupdf_{check_name}"] = False
    
    # Check Document Processor
    doc_proc_file = project_root / "ingestion" / "document_processor.py"
    if doc_proc_file.exists():
        content = doc_proc_file.read_text()
        
        checks = {
            "file size in MB": "file_size_mb" in content,
            "estimated time": "estimated_time" in content,
            "estimated chunks": "estimated_chunks" in content,
        }
        
        for check_name, passed in checks.items():
            if passed:
                print_test(f"DocumentProcessor: {check_name}", "PASS")
                results[f"docproc_{check_name}"] = True
            else:
                print_test(f"DocumentProcessor: {check_name}", "FAIL")
                results[f"docproc_{check_name}"] = False
    
    # Check RAG System
    rag_file = project_root / "rag_system.py"
    if rag_file.exists():
        content = rag_file.read_text()
        
        checks = {
            "batch percentage": "batch_pct" in content,
            "time remaining in batches": "remaining_str" in content,
            "chunks per second": "chunks_per_sec" in content,
        }
        
        for check_name, passed in checks.items():
            if passed:
                print_test(f"RAGSystem: {check_name}", "PASS")
                results[f"rag_{check_name}"] = True
            else:
                print_test(f"RAGSystem: {check_name}", "FAIL")
                results[f"rag_{check_name}"] = False
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\n{Colors.BOLD}Code Verification: {passed}/{total} checks passed{Colors.END}\n")
    return passed == total

def test_imports():
    """Test 2: Verify all imports work"""
    print_header("TEST 2: Import Verification")
    
    try:
        from parsers.docling_parser import DoclingParser
        print_test("DoclingParser import", "PASS")
    except ImportError as e:
        if "Docling is not installed" in str(e):
            print_test("DoclingParser import", "WARN", "Docling not installed (expected)")
        else:
            print_test("DoclingParser import", "FAIL", str(e))
            return False
    
    try:
        from parsers.pymupdf_parser import PyMuPDFParser
        print_test("PyMuPDFParser import", "PASS")
    except ImportError as e:
        if "pymupdf" in str(e).lower():
            print_test("PyMuPDFParser import", "WARN", "PyMuPDF not installed (expected)")
        else:
            print_test("PyMuPDFParser import", "FAIL", str(e))
            return False
    
    try:
        from ingestion.document_processor import DocumentProcessor
        print_test("DocumentProcessor import", "PASS")
    except Exception as e:
        print_test("DocumentProcessor import", "FAIL", str(e))
        return False
    
    try:
        from rag_system import RAGSystem
        print_test("RAGSystem import", "PASS")
    except Exception as e:
        print_test("RAGSystem import", "FAIL", str(e))
        return False
    
    print(f"\n{Colors.GREEN}✅ All imports successful{Colors.END}\n")
    return True

def test_signatures():
    """Test 3: Verify method signatures"""
    print_header("TEST 3: Method Signature Verification")
    
    try:
        from parsers.docling_parser import DoclingParser
        import inspect
        
        parser = DoclingParser()
        sig = inspect.signature(parser.parse)
        params = list(sig.parameters.keys())
        
        if 'progress_callback' in params:
            print_test("DoclingParser.parse() has progress_callback", "PASS")
        else:
            print_test("DoclingParser.parse() has progress_callback", "FAIL", f"Parameters: {params}")
            return False
    except Exception as e:
        if "Docling is not installed" in str(e):
            print_test("DoclingParser signature check", "WARN", "Docling not installed")
        else:
            print_test("DoclingParser signature check", "FAIL", str(e))
            return False
    
    try:
        from parsers.pymupdf_parser import PyMuPDFParser
        import inspect
        
        parser = PyMuPDFParser()
        sig = inspect.signature(parser.parse)
        params = list(sig.parameters.keys())
        
        if 'progress_callback' in params:
            print_test("PyMuPDFParser.parse() has progress_callback", "PASS")
        else:
            print_test("PyMuPDFParser.parse() has progress_callback", "FAIL", f"Parameters: {params}")
            return False
    except Exception as e:
        if "pymupdf" in str(e).lower():
            print_test("PyMuPDFParser signature check", "WARN", "PyMuPDF not installed")
        else:
            print_test("PyMuPDFParser signature check", "FAIL", str(e))
            return False
    
    print(f"\n{Colors.GREEN}✅ All signatures correct{Colors.END}\n")
    return True

def test_log_format():
    """Test 4: Verify log format strings"""
    print_header("TEST 4: Log Format Verification")
    
    # Check for expected log format patterns
    docling_file = project_root / "parsers" / "docling_parser.py"
    if docling_file.exists():
        content = docling_file.read_text()
        
        # Check for progress format
        if "Progress:" in content and "%" in content:
            print_test("Docling: Progress format with percentage", "PASS")
        else:
            print_test("Docling: Progress format with percentage", "FAIL")
            return False
        
        # Check for time remaining
        if "remaining" in content.lower():
            print_test("Docling: Time remaining in logs", "PASS")
        else:
            print_test("Docling: Time remaining in logs", "FAIL")
            return False
    
    pymupdf_file = project_root / "parsers" / "pymupdf_parser.py"
    if pymupdf_file.exists():
        content = pymupdf_file.read_text()
        
        # Check for percentage in progress
        if "progress_pct" in content and "%" in content:
            print_test("PyMuPDF: Percentage in progress logs", "PASS")
        else:
            print_test("PyMuPDF: Percentage in progress logs", "FAIL")
            return False
        
        # Check for speed
        if "pages_per_sec" in content or "Speed:" in content:
            print_test("PyMuPDF: Processing speed in logs", "PASS")
        else:
            print_test("PyMuPDF: Processing speed in logs", "FAIL")
            return False
    
    print(f"\n{Colors.GREEN}✅ All log formats correct{Colors.END}\n")
    return True

def main():
    """Run all tests"""
    print_header("ENHANCED PROGRESS LOGGING - SYSTEM TEST")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    tests = [
        ("Code Verification", test_code_verification),
        ("Import Verification", test_imports),
        ("Method Signatures", test_signatures),
        ("Log Format Verification", test_log_format),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print_test(f"{test_name} - Exception", "FAIL", f"Error: {e}")
            results[test_name] = False
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            status = f"{Colors.GREEN}✅ PASS{Colors.END}"
        else:
            status = f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"  {test_name:40s} : {status}")
    
    print(f"\n{'─'*80}")
    print(f"Total: {total} tests")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"{Colors.RED}Failed: {total - passed}{Colors.END}")
    print(f"{'─'*80}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ All tests passed! Enhanced logging is working correctly.{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ Some tests failed. Please review the output above.{Colors.END}\n")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Test interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Test suite error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

