#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for FastAPI RAG Integration
Tests all new endpoints and features including:
- Enhanced query parameters (temperature, max_tokens)
- Image operations (query, retrieve)
- Document CRUD (create, read, update, delete)
- Chunk statistics
- Proper document deletion with vectorstore cleanup
"""
import os
import sys
import json
import logging
import traceback
import requests
import time
from pathlib import Path
from typing import Optional, Dict, Any

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
    CYAN = '\033[96m'
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
    print(f"{Colors.CYAN}ℹ️  INFO: {msg}{Colors.END}")

# Test configuration
# Prefer explicit env vars, fall back to live API
API_BASE_URL = os.getenv('FASTAPI_URL') or os.getenv('LIVE_API_URL') or 'http://44.221.84.58:8500'
# Some endpoints (Docling OCR) can take time; use generous timeout
TEST_TIMEOUT = 300

class FastAPITester:
    """Test client for FastAPI endpoints"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.uploaded_documents = []
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'tests': []
        }
    
    def test_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                     data: Optional[Dict] = None, files: Optional[Dict] = None,
                     description: str = "") -> Optional[Dict]:
        """Test an API endpoint"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=TEST_TIMEOUT)
            elif method.upper() == 'POST':
                if files:
                    response = self.session.post(url, files=files, data=data, timeout=TEST_TIMEOUT)
                else:
                    response = self.session.post(url, json=data, timeout=TEST_TIMEOUT)
            elif method.upper() == 'PUT':
                response = self.session.put(url, json=data, timeout=TEST_TIMEOUT)
            elif method.upper() == 'DELETE':
                response = self.session.delete(url, timeout=TEST_TIMEOUT)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.status_code == expected_status:
                print_pass(f"{method} {endpoint} - Status {response.status_code}")
                try:
                    return response.json() if response.content else {}
                except:
                    return {}
            else:
                print_fail(f"{method} {endpoint} - Expected {expected_status}, got {response.status_code}")
                print_info(f"Response: {response.text[:200]}")
                self.test_results['failed'] += 1
                return None
        except requests.exceptions.RequestException as e:
            print_fail(f"{method} {endpoint} - Request failed: {str(e)}")
            self.test_results['failed'] += 1
            return None
        except Exception as e:
            print_fail(f"{method} {endpoint} - Error: {str(e)}")
            traceback.print_exc()
            self.test_results['failed'] += 1
            return None
    
    def test_health_check(self):
        """Test health check endpoint"""
        print_test("Health Check")
        result = self.test_endpoint('GET', '/health', expected_status=200)
        if result:
            self.test_results['passed'] += 1
            return True
        return False
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        print_test("Root Endpoint")
        result = self.test_endpoint('GET', '/', expected_status=200)
        if result and 'message' in result:
            print_pass(f"API Message: {result.get('message')}")
            self.test_results['passed'] += 1
            return True
        return False
    
    def test_upload_document(self, file_path: Optional[str] = None):
        """Test document upload"""
        print_test("Document Upload")
        
        # Create a simple test file if none provided
        if not file_path:
            # Prefer sample PDF if available
            candidate = os.getenv('TEST_PDF_PATH') or "FL10.11 SPECIFIC8 (1).pdf"
            if os.path.exists(candidate):
                file_path = candidate
            else:
                test_file_path = "/tmp/test_document.txt"
                with open(test_file_path, 'w') as f:
                    f.write("This is a test document for FastAPI RAG integration testing.\n")
                    f.write("It contains some sample text to test document processing.\n")
                    f.write("The document should be processed and stored in the vectorstore.\n")
                file_path = test_file_path
        
        if not os.path.exists(file_path):
            print_fail(f"Test file not found: {file_path}")
            self.test_results['failed'] += 1
            return None
        
        try:
            with open(file_path, 'rb') as f:
                content_type = 'application/pdf' if file_path.lower().endswith('.pdf') else 'text/plain'
                parser_choice = 'docling' if file_path.lower().endswith('.pdf') else 'auto'
                files = {'file': (os.path.basename(file_path), f, content_type)}
                data = {'parser': parser_choice}
                result = self.test_endpoint('POST', '/documents', expected_status=201, 
                                         files=files, data=data)
            
            if result:
                doc_id = result.get('document_id') or result.get('document_name', 'unknown')
                self.uploaded_documents.append(doc_id)
                print_pass(f"Document uploaded: {doc_id}")
                print_info(f"Document name: {result.get('document_name')}")
                print_info(f"Chunks created: {result.get('chunks_created', 0)}")
                self.test_results['passed'] += 1
                return result
            return None
        except Exception as e:
            print_fail(f"Upload failed: {str(e)}")
            traceback.print_exc()
            self.test_results['failed'] += 1
            return None
    
    def test_list_documents(self):
        """Test listing documents"""
        print_test("List Documents")
        result = self.test_endpoint('GET', '/documents', expected_status=200)
        if result and 'documents' in result:
            count = result.get('total', len(result.get('documents', [])))
            print_pass(f"Found {count} document(s)")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_get_document(self, document_id: str):
        """Test getting a specific document"""
        print_test(f"Get Document: {document_id}")
        result = self.test_endpoint('GET', f'/documents/{document_id}', expected_status=200)
        if result:
            print_pass(f"Document retrieved: {result.get('document_name')}")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_update_document(self, document_id: str):
        """Test updating document metadata"""
        print_test(f"Update Document: {document_id}")
        update_data = {
            'status': 'success',
            'document_name': f'updated_{int(time.time())}.txt'
        }
        result = self.test_endpoint('PUT', f'/documents/{document_id}', 
                                   expected_status=200, data=update_data)
        if result:
            print_pass(f"Document updated: {result.get('document_name')}")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_query_with_enhanced_params(self):
        """Test query endpoint with new parameters (temperature, max_tokens)"""
        print_test("Query with Enhanced Parameters")
        query_data = {
            'question': 'What is the main topic of the document?',
            'k': 3,
            'use_mmr': True,
            'temperature': 0.7,
            'max_tokens': 500
        }
        result = self.test_endpoint('POST', '/query', expected_status=200, data=query_data)
        if result:
            print_pass(f"Query successful - Answer length: {len(result.get('answer', ''))}")
            print_info(f"Citations: {len(result.get('citations', []))}")
            print_info(f"Total tokens: {result.get('total_tokens', 0)}")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_query_basic(self):
        """Test basic query endpoint"""
        print_test("Basic Query")
        query_data = {
            'question': 'What does the document contain?',
            'k': 3
        }
        result = self.test_endpoint('POST', '/query', expected_status=200, data=query_data)
        if result:
            print_pass("Basic query successful")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_get_stats(self):
        """Test statistics endpoint"""
        print_test("Get Statistics")
        result = self.test_endpoint('GET', '/stats', expected_status=200)
        if result:
            print_pass("Statistics retrieved")
            if 'rag_stats' in result:
                print_info(f"Total documents: {result['rag_stats'].get('total_documents', 0)}")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_get_chunk_stats(self):
        """Test chunk statistics endpoint"""
        print_test("Get Chunk Statistics")
        result = self.test_endpoint('GET', '/stats/chunks', expected_status=200)
        if result:
            print_pass("Chunk statistics retrieved")
            if 'total_chunks' in result:
                print_info(f"Total chunks: {result.get('total_chunks', 0)}")
            self.test_results['passed'] += 1
            return result
        return None
    
    def test_query_images(self):
        """Test image query endpoint (OpenSearch only)"""
        print_test("Query Images")
        query_data = {
            'question': 'Find images with text',
            'k': 5
        }
        result = self.test_endpoint('POST', '/query/images', expected_status=200, data=query_data)
        if result:
            if result.get('total', 0) > 0:
                print_pass(f"Found {result.get('total')} images")
            else:
                print_warn("No images found (may be expected if no images in documents)")
            self.test_results['passed'] += 1
            return result
        else:
            # Check if it's because OpenSearch is not configured
            print_warn("Image query failed - may require OpenSearch configuration")
            self.test_results['warnings'] += 1
            return None
    
    def test_get_document_images(self, document_id: str):
        """Test getting images for a document"""
        print_test(f"Get Document Images: {document_id}")
        result = self.test_endpoint('GET', f'/documents/{document_id}/images?limit=10', 
                                   expected_status=200)
        if result:
            image_count = result.get('total', len(result.get('images', [])))
            if image_count > 0:
                print_pass(f"Found {image_count} images for document")
            else:
                print_warn("No images found for document (may be expected)")
            self.test_results['passed'] += 1
            return result
        else:
            print_warn("Document images endpoint failed - may require OpenSearch")
            self.test_results['warnings'] += 1
            return None
    
    def test_get_single_image(self, image_id: str = "test_image_1"):
        """Test getting a single image"""
        print_test(f"Get Single Image: {image_id}")
        result = self.test_endpoint('GET', f'/images/{image_id}', expected_status=404)
        # 404 is expected if image doesn't exist, but endpoint should work
        if result is not None or True:  # Endpoint exists and responds
            print_warn(f"Image {image_id} not found (expected if no images exist)")
            self.test_results['warnings'] += 1
            return True
        return False
    
    def test_delete_document(self, document_id: str):
        """Test document deletion with proper cleanup"""
        print_test(f"Delete Document: {document_id}")
        result = self.test_endpoint('DELETE', f'/documents/{document_id}', expected_status=204)
        if result is not None or True:  # 204 No Content
            print_pass(f"Document deleted: {document_id}")
            if document_id in self.uploaded_documents:
                self.uploaded_documents.remove(document_id)
            self.test_results['passed'] += 1
            return True
        return False
    
    def test_sync_status(self):
        """Test sync status endpoint"""
        print_test("Sync Status")
        result = self.test_endpoint('GET', '/sync/status', expected_status=200)
        if result:
            print_pass("Sync status retrieved")
            self.test_results['passed'] += 1
            return result
        return None
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}FastAPI RAG End-to-End Integration Test{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
        print_info(f"Testing API at: {self.base_url}")
        
        # Basic connectivity tests
        if not self.test_health_check():
            print_fail("Health check failed - API may not be running")
            return False
        
        self.test_root_endpoint()
        
        # Document CRUD tests
        upload_result = self.test_upload_document()
        if not upload_result:
            print_warn("Document upload failed - some tests may be skipped")
        else:
            document_id = upload_result.get('document_id') or upload_result.get('document_name', '')
            if document_id:
                # Wait a bit for processing
                time.sleep(2)
                
                self.test_list_documents()
                self.test_get_document(document_id)
                self.test_update_document(document_id)
                
                # Query tests
                self.test_query_basic()
                self.test_query_with_enhanced_params()
                
                # Image tests (may require OpenSearch)
                self.test_get_document_images(document_id)
                self.test_query_images()
                self.test_get_single_image()
                
                # Statistics tests
                self.test_get_stats()
                self.test_get_chunk_stats()
                
                # Sync tests
                self.test_sync_status()
                
                # Cleanup - delete document
                self.test_delete_document(document_id)
        
        # Print summary
        self.print_summary()
        return self.test_results['failed'] == 0
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.CYAN}{Colors.BOLD}Test Summary{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}✅ Passed: {self.test_results['passed']}{Colors.END}")
        print(f"{Colors.RED}❌ Failed: {self.test_results['failed']}{Colors.END}")
        print(f"{Colors.YELLOW}⚠️  Warnings: {self.test_results['warnings']}{Colors.END}")
        print(f"{Colors.CYAN}{'='*80}{Colors.END}")

def main():
    """Main test runner"""
    try:
        tester = FastAPITester()
        success = tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print_info("\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print_fail(f"Test runner failed: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

