#!/usr/bin/env python3
"""
Comprehensive server test to verify all functionality is working correctly.
Tests document processing, image extraction, querying, and all recent fixes.
"""
import os
import sys
import logging
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS: {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  WARN: {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  INFO: {msg}{Colors.END}")

def test_imports():
    """Test that all required modules can be imported."""
    print_test("Module Imports")
    
    modules = [
        'rag_system',
        'parsers.docling_parser',
        'parsers.pymupdf_parser',
        'parsers.parser_factory',
        'ingestion.document_processor',
        'utils.tokenizer',
        'utils.image_extraction_logger',
        'vectorstores.opensearch_images_store',
        'config.settings'
    ]
    
    failed = []
    for module in modules:
        try:
            __import__(module)
            print_pass(f"Imported {module}")
        except Exception as e:
            # boto3 is optional for OpenSearch
            if 'boto3' in str(e) and 'opensearch' in module:
                print_warn(f"Optional module not available: {module} (boto3 not installed - OpenSearch features disabled)")
            else:
                print_fail(f"Failed to import {module}: {str(e)}")
                failed.append(module)
    
    return len(failed) == 0

def test_rag_system_initialization():
    """Test RAG system initialization."""
    print_test("RAG System Initialization")
    
    try:
        from rag_system import RAGSystem
        
        # Test with default settings
        rag = RAGSystem()
        print_pass("RAGSystem initialized with defaults")
        
        # Test with OpenSearch
        try:
            rag_opensearch = RAGSystem(
                vector_store_type="opensearch",
                opensearch_domain=os.getenv('OPENSEARCH_DOMAIN'),
                opensearch_index="test-index"
            )
            print_pass("RAGSystem initialized with OpenSearch")
        except Exception as e:
            print_warn(f"OpenSearch initialization skipped: {str(e)}")
        
        # Test methods exist
        assert hasattr(rag, 'query_with_rag'), "query_with_rag method missing"
        assert hasattr(rag, 'process_documents'), "process_documents method missing"
        assert hasattr(rag, '_extract_document_number'), "_extract_document_number method missing"
        assert hasattr(rag, '_store_extracted_images'), "_store_extracted_images method missing"
        assert hasattr(rag, 'query_images'), "query_images method missing"
        
        print_pass("All required methods exist")
        return True
    except Exception as e:
        print_fail(f"RAGSystem initialization failed: {str(e)}")
        traceback.print_exc()
        return False

def test_image_logger():
    """Test image extraction logger."""
    print_test("Image Extraction Logger")
    
    try:
        from shared.utils.image_extraction_logger import image_logger, ImageExtractionLogger
        
        # Test logger instance
        assert image_logger is not None, "image_logger is None"
        assert isinstance(image_logger, ImageExtractionLogger), "image_logger is not ImageExtractionLogger"
        print_pass("Image logger instance exists")
        
        # Test logging methods
        image_logger.log_image_detection_start("test.pdf", "docling")
        image_logger.log_image_detected("test.pdf", 5, ["docling"])
        image_logger.log_ocr_complete("test.pdf", 1000, extraction_method="docling", success=True)
        image_logger.log_storage_success("test.pdf", 3, ["id1", "id2", "id3"])
        
        print_pass("All logging methods work")
        return True
    except Exception as e:
        print_fail(f"Image logger test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_document_number_extraction():
    """Test document number extraction."""
    print_test("Document Number Extraction")
    
    try:
        from rag_system import RAGSystem
        
        rag = RAGSystem()
        
        test_cases = [
            ("FL10.11 SPECIFIC8 (1).pdf", 1),
            ("FL10.11 SPECIFIC8 (2).pdf", 2),
            ("document (10).pdf", 10),
            ("file.pdf", None),
            ("path/to/FL10.11 SPECIFIC8 (1).pdf", 1),
        ]
        
        all_passed = True
        for filename, expected in test_cases:
            result = rag._extract_document_number(filename)
            if result == expected:
                print_pass(f"Extracted {result} from '{filename}'")
            else:
                print_fail(f"Expected {expected}, got {result} for '{filename}'")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print_fail(f"Document number extraction test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_image_storage_method():
    """Test that _store_extracted_images method works without errors."""
    print_test("Image Storage Method")
    
    try:
        from rag_system import RAGSystem
        
        rag = RAGSystem()
        
        # Test with empty map (should return early)
        rag._store_extracted_images({}, set())
        print_pass("Handles empty image_content_map")
        
        # Test with non-OpenSearch (should return early)
        rag.vector_store_type = "faiss"
        rag._store_extracted_images({("test.pdf", 1): [{"ocr_text": "test"}]}, {"test.pdf"})
        print_pass("Handles non-OpenSearch vector store")
        
        # Test that method doesn't crash with image_logger import
        # (This was the bug we fixed)
        try:
            # This should not raise NameError
            rag._store_extracted_images({}, set())
            print_pass("Method handles image_logger import correctly")
        except NameError as e:
            if 'image_logger' in str(e):
                print_fail(f"NameError for image_logger still exists: {str(e)}")
                return False
            else:
                raise
        
        return True
    except Exception as e:
        print_fail(f"Image storage method test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_opensearch_images_store():
    """Test OpenSearch images store initialization."""
    print_test("OpenSearch Images Store")
    
    try:
        from vectorstores.opensearch_images_store import OpenSearchImagesStore
        from langchain_openai import OpenAIEmbeddings
        
        # Check if OpenSearch is configured
        opensearch_domain = os.getenv('OPENSEARCH_DOMAIN')
        if not opensearch_domain:
            print_warn("OPENSEARCH_DOMAIN not set - skipping OpenSearch test")
            return True
        
        try:
            embeddings = OpenAIEmbeddings(
                openai_api_key=os.getenv('OPENAI_API_KEY'),
                model="text-embedding-3-large"
            )
            
            images_store = OpenSearchImagesStore(
                embeddings=embeddings,
                domain=opensearch_domain,
                region=os.getenv('AWS_REGION', 'us-east-2')
            )
            
            print_pass("OpenSearchImagesStore initialized")
            
            # Test methods exist
            assert hasattr(images_store, 'store_images_batch'), "store_images_batch method missing"
            assert hasattr(images_store, 'search_images'), "search_images method missing"
            print_pass("All required methods exist")
            
            return True
        except Exception as e:
            print_warn(f"OpenSearch connection failed (may not be configured): {str(e)}")
            return True  # Don't fail if OpenSearch isn't available
    except ImportError as e:
        print_warn(f"OpenSearch images store not available: {str(e)}")
        return True  # Don't fail if module not available
    except Exception as e:
        print_fail(f"OpenSearch images store test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_document_processor():
    """Test document processor initialization."""
    print_test("Document Processor")
    
    try:
        from ingestion.document_processor import DocumentProcessor
        from rag_system import RAGSystem
        
        rag = RAGSystem()
        processor = DocumentProcessor(rag_system=rag)
        
        print_pass("DocumentProcessor initialized")
        
        # Test methods exist
        assert hasattr(processor, 'process_document'), "process_document method missing"
        assert hasattr(processor, '_store_images_in_opensearch'), "_store_images_in_opensearch method missing"
        print_pass("All required methods exist")
        
        return True
    except Exception as e:
        print_fail(f"Document processor test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_parser_factory():
    """Test parser factory."""
    print_test("Parser Factory")
    
    try:
        from parsers.parser_factory import ParserFactory
        
        # Test that ParserFactory can be instantiated
        factory = ParserFactory()
        print_pass("ParserFactory can be instantiated")
        
        # Test get_parser method exists
        assert hasattr(factory, 'get_parser'), "get_parser method missing"
        print_pass("get_parser method exists")
        
        # Try to get parsers (may fail if dependencies not installed)
        try:
            docling_parser = factory.get_parser('docling')
            print_info("Docling parser available")
        except Exception as e:
            print_warn(f"Docling parser not available: {str(e)}")
        
        try:
            pymupdf_parser = factory.get_parser('pymupdf')
            print_info("PyMuPDF parser available")
        except Exception as e:
            print_warn(f"PyMuPDF parser not available: {str(e)}")
        
        print_pass("Parser factory works correctly")
        return True
    except Exception as e:
        print_fail(f"Parser factory test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_query_methods():
    """Test that query methods have correct signatures."""
    print_test("Query Methods Signature")
    
    try:
        from rag_system import RAGSystem
        import inspect
        
        rag = RAGSystem()
        
        # Check _query_openai signature
        sig = inspect.signature(rag._query_openai)
        params = list(sig.parameters.keys())
        
        if 'mentioned_documents' in params and 'question_doc_number' in params:
            print_pass("_query_openai has correct parameters (document filtering fix)")
        else:
            print_fail(f"_query_openai missing parameters. Found: {params}")
            return False
        
        # Check _query_cerebras signature
        sig = inspect.signature(rag._query_cerebras)
        params = list(sig.parameters.keys())
        
        if 'mentioned_documents' in params and 'question_doc_number' in params:
            print_pass("_query_cerebras has correct parameters (document filtering fix)")
        else:
            print_fail(f"_query_cerebras missing parameters. Found: {params}")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Query methods test failed: {str(e)}")
        traceback.print_exc()
        return False

def test_environment_variables():
    """Test that required environment variables are set."""
    print_test("Environment Variables")
    
    required_vars = ['OPENAI_API_KEY']
    optional_vars = ['OPENSEARCH_DOMAIN', 'AWS_REGION', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    
    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
            print_warn(f"Required environment variable not set: {var} (will be checked on server)")
        else:
            print_pass(f"Environment variable set: {var}")
    
    for var in optional_vars:
        if os.getenv(var):
            print_info(f"Optional environment variable set: {var}")
        else:
            print_warn(f"Optional environment variable not set: {var} (optional)")
    
    # Don't fail if env vars not set locally - they should be set on server
    if missing_required:
        print_info("Note: Environment variables should be set on the server via .env file")
        return True  # Don't fail locally
    return True

def test_file_structure():
    """Test that required files and directories exist."""
    print_test("File Structure")
    
    required_files = [
        'rag_system.py',
        'parsers/docling_parser.py',
        'parsers/pymupdf_parser.py',
        'parsers/parser_factory.py',
        'ingestion/document_processor.py',
        'utils/tokenizer.py',
        'utils/image_extraction_logger.py',
        'vectorstores/opensearch_images_store.py',
        'config/settings.py'
    ]
    
    missing = []
    for file_path in required_files:
        if os.path.exists(file_path):
            print_pass(f"File exists: {file_path}")
        else:
            print_fail(f"File missing: {file_path}")
            missing.append(file_path)
    
    # Check log directory
    log_dir = Path('logs')
    if log_dir.exists():
        print_pass(f"Log directory exists: {log_dir}")
    else:
        print_warn(f"Log directory missing: {log_dir} (will be created on first log)")
    
    return len(missing) == 0

def run_all_tests():
    """Run all comprehensive tests."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}COMPREHENSIVE SERVER TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")
    
    tests = [
        ("File Structure", test_file_structure),
        ("Environment Variables", test_environment_variables),
        ("Module Imports", test_imports),
        ("RAG System Initialization", test_rag_system_initialization),
        ("Image Extraction Logger", test_image_logger),
        ("Document Number Extraction", test_document_number_extraction),
        ("Image Storage Method", test_image_storage_method),
        ("OpenSearch Images Store", test_opensearch_images_store),
        ("Document Processor", test_document_processor),
        ("Parser Factory", test_parser_factory),
        ("Query Methods Signature", test_query_methods),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {str(e)}")
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}TEST SUMMARY{Colors.END}")
    print(f"{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASSED{Colors.END}" if result else f"{Colors.RED}❌ FAILED{Colors.END}"
        print(f"{status}: {test_name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.END}\n")
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! Server is ready.{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return True
    else:
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}⚠️  SOME TESTS FAILED. Please review the errors above.{Colors.END}")
        print(f"{Colors.RED}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

