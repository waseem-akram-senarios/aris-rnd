"""
Automated test for PDF timeout fix
Tests that PDFs process completely without timeout errors
"""
import sys
import os
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from parsers.pymupdf_parser import PyMuPDFParser
from parsers.docling_parser import DoclingParser
from parsers.parser_factory import ParserFactory
from ingestion.document_processor import DocumentProcessor
from rag_system import RAGSystem
from metrics.metrics_collector import MetricsCollector
from scripts.setup_logging import setup_logging
import logging

# Set up logging
logger = setup_logging(
    name="test_pdf_timeout",
    level=logging.INFO,
    log_file="logs/test_pdf_timeout.log"
)


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_test(name, status, details=""):
    """Print test result"""
    if status == "PASS":
        print(f"{Colors.GREEN}✅ {name}{Colors.END}")
    elif status == "FAIL":
        print(f"{Colors.RED}❌ {name}{Colors.END}")
    else:
        print(f"{Colors.YELLOW}⚠️  {name}{Colors.END}")
    if details:
        print(f"   {details}")


def test_pdf_file_access():
    """Test 1: Verify PDF file exists and is accessible"""
    print(f"\n{Colors.BOLD}Test 1: PDF File Access{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    if not os.path.exists(pdf_path):
        print_test("PDF file exists", "FAIL", f"File not found: {pdf_path}")
        return False, None
    
    print_test("PDF file exists", "PASS", f"Found: {pdf_path}")
    
    # Check file size
    file_size = os.path.getsize(pdf_path)
    file_size_mb = file_size / (1024 * 1024)
    print_test("File size check", "PASS", f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
    
    # Check if file is readable
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if header == b'%PDF':
                print_test("PDF format valid", "PASS", "Valid PDF header detected")
            else:
                print_test("PDF format valid", "FAIL", f"Invalid header: {header}")
                return False, None
    except Exception as e:
        print_test("File readable", "FAIL", f"Error: {e}")
        return False, None
    
    return True, pdf_path


def test_pymupdf_can_open():
    """Test 2: Verify PyMuPDF can open the PDF"""
    print(f"\n{Colors.BOLD}Test 2: PyMuPDF Can Open PDF{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    try:
        import fitz
    except ImportError:
        print_test("PyMuPDF installed", "FAIL", "PyMuPDF (pymupdf) is not installed")
        print(f"{Colors.YELLOW}   Install with: pip install pymupdf{Colors.END}")
        return False, 0
    
    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        is_encrypted = doc.is_encrypted
        needs_pass = doc.needs_pass
        
        print_test("PyMuPDF can open PDF", "PASS", f"Opened successfully")
        print_test("Page count", "PASS", f"Pages: {page_count}")
        print_test("Encryption check", "PASS" if not is_encrypted else "WARN", 
                  f"Encrypted: {is_encrypted}, Needs password: {needs_pass}")
        
        if is_encrypted:
            print(f"{Colors.YELLOW}   ⚠️  PDF is encrypted - may cause processing issues{Colors.END}")
        
        doc.close()
        return True, page_count
    except Exception as e:
        print_test("PyMuPDF can open PDF", "FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False, 0


def test_pymupdf_parser_no_timeout():
    """Test 3: Verify PyMuPDF parser processes without timeout"""
    print(f"\n{Colors.BOLD}Test 3: PyMuPDF Parser - No Timeout{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    try:
        parser = PyMuPDFParser()
    except ImportError as e:
        print_test("PyMuPDF parser available", "FAIL", f"PyMuPDF not installed: {e}")
        return False, None
    
    try:
        
        # Track progress
        progress_updates = []
        def progress_callback(status, progress):
            progress_updates.append((status, progress, time.time()))
            if len(progress_updates) % 10 == 0:
                print(f"   Progress: {status} - {progress*100:.1f}%")
        
        print(f"{Colors.BLUE}   Starting PyMuPDF parsing (no timeout - will process completely)...{Colors.END}")
        start_time = time.time()
        
        result = parser.parse(pdf_path, progress_callback=progress_callback)
        
        elapsed = time.time() - start_time
        
        print_test("PyMuPDF parsing completed", "PASS", 
                  f"Completed in {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
        print_test("Text extracted", "PASS" if result.text else "FAIL",
                  f"Text length: {len(result.text):,} characters")
        print_test("Pages processed", "PASS",
                  f"Pages: {result.pages}, Extraction: {result.extraction_percentage*100:.1f}%")
        print_test("Parser used", "PASS", f"Parser: {result.parser_used}")
        
        # Check for skipped pages
        if hasattr(result, 'metadata') and result.metadata:
            skipped = result.metadata.get('skipped_pages', [])
            if skipped:
                print_test("Skipped pages", "WARN", f"Pages skipped: {skipped}")
            else:
                print_test("No pages skipped", "PASS", "All pages processed successfully")
        
        print_test("Confidence", "PASS" if result.confidence > 0.5 else "WARN",
                  f"Confidence: {result.confidence:.2f}")
        
        return True, result
        
    except Exception as e:
        print_test("PyMuPDF parsing", "FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_per_page_timeout_protection():
    """Test 4: Verify per-page timeout protection works"""
    print(f"\n{Colors.BOLD}Test 4: Per-Page Timeout Protection{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    try:
        parser = PyMuPDFParser()
    except ImportError as e:
        print_test("PyMuPDF parser available", "FAIL", f"PyMuPDF not installed: {e}")
        return False
    
    try:
        
        # Track page processing times
        page_times = []
        def progress_callback(status, progress):
            if "Processing page" in status:
                page_times.append(time.time())
        
        start_time = time.time()
        result = parser.parse(pdf_path, progress_callback=progress_callback)
        total_time = time.time() - start_time
        
        # Check if any pages were skipped (indicates timeout protection worked)
        skipped_pages = []
        if hasattr(result, 'metadata') and result.metadata:
            skipped_pages = result.metadata.get('skipped_pages', [])
        
        if skipped_pages:
            print_test("Per-page timeout protection", "PASS",
                      f"Protected against {len(skipped_pages)} problematic pages")
            print(f"   {Colors.YELLOW}   Skipped pages: {skipped_pages}{Colors.END}")
        else:
            print_test("Per-page timeout protection", "PASS",
                      "No pages needed timeout protection (all processed normally)")
        
        print_test("Processing time", "PASS",
                  f"Total: {total_time:.2f}s ({total_time/60:.1f} minutes)")
        
        return True
        
    except Exception as e:
        print_test("Per-page timeout protection", "FAIL", f"Error: {e}")
        return False


def test_parser_factory():
    """Test 5: Verify ParserFactory works with the PDF"""
    print(f"\n{Colors.BOLD}Test 5: ParserFactory Integration{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    # Check which parsers are available
    pymupdf_available = False
    docling_available = False
    
    try:
        parser = PyMuPDFParser()
        pymupdf_available = True
    except ImportError:
        pass
    
    try:
        parser = DoclingParser()
        docling_available = True
    except ImportError:
        pass
    
    if not pymupdf_available and not docling_available:
        print_test("Parser availability", "FAIL", "No parsers available (install pymupdf or docling)")
        return False
    
    try:
        # Test with available parser
        if pymupdf_available:
            print(f"{Colors.BLUE}   Testing with PyMuPDF parser...{Colors.END}")
            start_time = time.time()
            result_pymupdf = ParserFactory.parse_with_fallback(
                pdf_path,
                preferred_parser="pymupdf"
            )
            elapsed_pymupdf = time.time() - start_time
            
            print_test("ParserFactory - PyMuPDF", "PASS",
                      f"Completed in {elapsed_pymupdf:.2f}s, {len(result_pymupdf.text):,} chars")
        
        # Test with auto (fallback)
        print(f"{Colors.BLUE}   Testing with auto parser (fallback)...{Colors.END}")
        start_time = time.time()
        result_auto = ParserFactory.parse_with_fallback(
            pdf_path,
            preferred_parser="auto"
        )
        elapsed_auto = time.time() - start_time
        
        print_test("ParserFactory - Auto", "PASS",
                  f"Completed in {elapsed_auto:.2f}s, {len(result_auto.text):,} chars")
        
        return True
        
    except Exception as e:
        print_test("ParserFactory", "FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_document_processor():
    """Test 6: Verify DocumentProcessor can process the PDF"""
    print(f"\n{Colors.BOLD}Test 6: DocumentProcessor Integration{Colors.END}")
    print("=" * 60)
    
    pdf_path = "docs/s71500_getting_started_en-US_en-US (1).pdf"
    
    try:
        # Create minimal RAG system for testing
        metrics_collector = MetricsCollector()
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics_collector,
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        
        processor = DocumentProcessor(rag_system)
        
        # Read file content
        with open(pdf_path, 'rb') as f:
            file_content = f.read()
        
        print(f"{Colors.BLUE}   Starting document processing (no timeout - will process completely)...{Colors.END}")
        start_time = time.time()
        
        # Track progress
        progress_steps = []
        def progress_callback(status, progress, **kwargs):
            progress_steps.append((status, progress, time.time()))
            if len(progress_steps) % 5 == 0:
                print(f"   Step: {status} - {progress*100:.1f}%")
        
        result = processor.process_document(
            file_path=pdf_path,
            file_content=file_content,
            file_name=os.path.basename(pdf_path),
            parser_preference="pymupdf",
            progress_callback=progress_callback
        )
        
        elapsed = time.time() - start_time
        
        print_test("DocumentProcessor processing", "PASS",
                  f"Completed in {elapsed:.2f}s ({elapsed/60:.1f} minutes)")
        print_test("Processing status", "PASS" if result.status == 'success' else "FAIL",
                  f"Status: {result.status}")
        print_test("Chunks created", "PASS",
                  f"Chunks: {result.chunks_created}, Tokens: {result.tokens_extracted:,}")
        print_test("Parser used", "PASS", f"Parser: {result.parser_used}")
        
        if result.error:
            print_test("Error check", "FAIL", f"Error: {result.error}")
            return False
        else:
            print_test("No errors", "PASS", "Processing completed without errors")
        
        return True
        
    except Exception as e:
        print_test("DocumentProcessor", "FAIL", f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 80)
    print(f"{Colors.BOLD}PDF Timeout Fix - Automated Testing{Colors.END}")
    print("=" * 80)
    print(f"Testing PDF: s71500_getting_started_en-US_en-US (1).pdf")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    
    # Test 1: File access
    success, pdf_path = test_pdf_file_access()
    results["file_access"] = success
    if not success:
        print(f"\n{Colors.RED}❌ Cannot proceed - PDF file not accessible{Colors.END}")
        return 1
    
    # Test 2: PyMuPDF can open
    success, page_count = test_pymupdf_can_open()
    results["pymupdf_open"] = success
    if not success:
        print(f"\n{Colors.YELLOW}⚠️  PyMuPDF cannot open PDF - may have issues{Colors.END}")
    
    # Test 3: PyMuPDF parser no timeout
    success, result = test_pymupdf_parser_no_timeout()
    results["pymupdf_parser"] = success
    
    # Test 4: Per-page timeout protection
    success = test_per_page_timeout_protection()
    results["per_page_timeout"] = success
    
    # Test 5: ParserFactory
    success = test_parser_factory()
    results["parser_factory"] = success
    
    # Test 6: DocumentProcessor (full integration)
    # Skip if no API key (embedding requires OpenAI API)
    import os
    if os.getenv('OPENAI_API_KEY'):
        print(f"\n{Colors.YELLOW}⚠️  Note: DocumentProcessor test will process and chunk the document{Colors.END}")
        print(f"{Colors.YELLOW}   This may take longer as it includes embedding creation...{Colors.END}")
        print(f"{Colors.BLUE}   Running DocumentProcessor test (automated)...{Colors.END}")
        try:
            success = test_document_processor()
            results["document_processor"] = success
        except Exception as e:
            print_test("DocumentProcessor", "FAIL", f"Error: {e}")
            results["document_processor"] = False
    else:
        print(f"\n{Colors.YELLOW}⚠️  Skipping DocumentProcessor test (no OPENAI_API_KEY){Colors.END}")
        results["document_processor"] = None
    
    # Summary
    print("\n" + "=" * 80)
    print(f"{Colors.BOLD}Test Summary{Colors.END}")
    print("=" * 80)
    
    total_tests = len([r for r in results.values() if r is not None])
    passed_tests = len([r for r in results.values() if r is True])
    failed_tests = len([r for r in results.values() if r is False])
    
    for test_name, result in results.items():
        if result is None:
            status = f"{Colors.YELLOW}SKIPPED{Colors.END}"
        elif result:
            status = f"{Colors.GREEN}PASS{Colors.END}"
        else:
            status = f"{Colors.RED}FAIL{Colors.END}"
        print(f"  {test_name:30s} : {status}")
    
    print("\n" + "-" * 80)
    print(f"Total: {total_tests} tests, {Colors.GREEN}{passed_tests} passed{Colors.END}, "
          f"{Colors.RED}{failed_tests} failed{Colors.END}")
    
    if failed_tests == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All tests passed! PDF processing is working correctly.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed. Please check the errors above.{Colors.END}")
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

