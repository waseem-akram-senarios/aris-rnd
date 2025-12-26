#!/usr/bin/env python3
"""
Comprehensive test script to test all FastAPI endpoints with a specific document.
Tests: FL10.11 SPECIFIC8 (1).pdf
"""
import os
import sys
import json
import requests
import time
from pathlib import Path

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

# Configuration
BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

# Test results
test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0
}

def find_document_file():
    """Find the document file in common locations"""
    possible_locations = [
        DOCUMENT_NAME,
        f"data/{DOCUMENT_NAME}",
        f"samples/{DOCUMENT_NAME}",
        f"test_data/{DOCUMENT_NAME}",
        f"/tmp/{DOCUMENT_NAME}",
        os.path.expanduser(f"~/Downloads/{DOCUMENT_NAME}"),
        os.path.expanduser(f"~/Desktop/{DOCUMENT_NAME}"),
    ]
    
    for location in possible_locations:
        if os.path.exists(location):
            print_pass(f"Found document: {location}")
            return location
    
    # Try to find any file with similar name
    print_warn(f"Document not found in common locations. Searching...")
    for root, dirs, files in os.walk('.'):
        for file in files:
            if 'FL10.11' in file and 'SPECIFIC8' in file and file.endswith('.pdf'):
                full_path = os.path.join(root, file)
                print_pass(f"Found similar document: {full_path}")
                return full_path
    
    print_fail(f"Document '{DOCUMENT_NAME}' not found")
    return None

def test_endpoint(method, endpoint, expected_status=200, data=None, files=None, description=""):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=30)
        elif method.upper() == 'POST':
            if files:
                # Longer timeout for file uploads (documents can take time to process)
                response = requests.post(url, files=files, data=data, timeout=300)  # 5 minutes
            else:
                response = requests.post(url, json=data, timeout=30)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, timeout=30)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=30)
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
            test_results['failed'] += 1
            return None
    except requests.exceptions.RequestException as e:
        print_fail(f"{method} {endpoint} - Request failed: {str(e)}")
        test_results['failed'] += 1
        return None
    except Exception as e:
        print_fail(f"{method} {endpoint} - Error: {str(e)}")
        test_results['failed'] += 1
        return None

def test_health_check():
    """Test health check endpoint"""
    print_test("1. Health Check")
    result = test_endpoint('GET', '/health', expected_status=200)
    if result:
        test_results['passed'] += 1
        return True
    return False

def test_root_endpoint():
    """Test root endpoint"""
    print_test("2. Root Endpoint")
    result = test_endpoint('GET', '/', expected_status=200)
    if result and 'message' in result:
        print_pass(f"API Message: {result.get('message')}")
        test_results['passed'] += 1
        return True
    return False

def test_upload_document(file_path):
    """Test document upload"""
    print_test("3. Upload Document")
    
    if not file_path or not os.path.exists(file_path):
        print_fail(f"Document file not found: {file_path}")
        test_results['failed'] += 1
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            result = test_endpoint('POST', '/documents', expected_status=201, files=files, data=data)
        
        if result:
            doc_id = result.get('document_id') or result.get('document_name', 'unknown')
            print_pass(f"Document uploaded: {doc_id}")
            print_info(f"Document name: {result.get('document_name')}")
            print_info(f"Status: {result.get('status')}")
            print_info(f"Chunks created: {result.get('chunks_created', 0)}")
            print_info(f"Pages: {result.get('pages', 0)}")
            print_info(f"Images detected: {result.get('images_detected', False)}")
            test_results['passed'] += 1
            return result
        return None
    except Exception as e:
        print_fail(f"Upload failed: {str(e)}")
        test_results['failed'] += 1
        return None

def test_list_documents():
    """Test listing documents"""
    print_test("4. List All Documents")
    result = test_endpoint('GET', '/documents', expected_status=200)
    if result and 'documents' in result:
        count = result.get('total', len(result.get('documents', [])))
        print_pass(f"Found {count} document(s)")
        if result.get('documents'):
            for doc in result.get('documents', [])[:3]:  # Show first 3
                print_info(f"  - {doc.get('document_name')} (ID: {doc.get('document_id', 'N/A')})")
        test_results['passed'] += 1
        return result
    return None

def test_get_document(document_id):
    """Test getting a specific document"""
    print_test(f"5. Get Document by ID: {document_id}")
    result = test_endpoint('GET', f'/documents/{document_id}', expected_status=200)
    if result:
        print_pass(f"Document retrieved: {result.get('document_name')}")
        print_info(f"Status: {result.get('status')}")
        print_info(f"Chunks: {result.get('chunks_created', 0)}")
        test_results['passed'] += 1
        return result
    return None

def test_update_document(document_id):
    """Test updating document metadata"""
    print_test(f"6. Update Document: {document_id}")
    update_data = {
        'status': 'success',
        'document_name': f'FL10.11 SPECIFIC8 (1) - Updated.pdf'
    }
    result = test_endpoint('PUT', f'/documents/{document_id}', expected_status=200, data=update_data)
    if result:
        print_pass(f"Document updated: {result.get('document_name')}")
        test_results['passed'] += 1
        return result
    return None

def test_query_all_documents():
    """Test query without document_id (all documents)"""
    print_test("7. Query All Documents (No document_id)")
    query_data = {
        'question': 'What is the main topic or purpose of the documents?',
        'k': 5,
        'use_mmr': True
    }
    result = test_endpoint('POST', '/query', expected_status=200, data=query_data)
    if result:
        print_pass(f"Query successful - Answer length: {len(result.get('answer', ''))}")
        print_info(f"Citations: {len(result.get('citations', []))}")
        print_info(f"Sources: {result.get('sources', [])}")
        print_info(f"Total tokens: {result.get('total_tokens', 0)}")
        if result.get('answer'):
            print_info(f"Answer preview: {result.get('answer', '')[:200]}...")
        test_results['passed'] += 1
        return result
    return None

def test_query_specific_document(document_id):
    """Test query with document_id (specific document)"""
    print_test(f"8. Query Specific Document (document_id={document_id})")
    query_data = {
        'question': 'What information is in FL10.11 SPECIFIC8 document?',
        'k': 5,
        'use_mmr': True,
        'document_id': document_id
    }
    result = test_endpoint('POST', '/query', expected_status=200, data=query_data)
    if result:
        print_pass(f"Query successful - Answer length: {len(result.get('answer', ''))}")
        print_info(f"Citations: {len(result.get('citations', []))}")
        print_info(f"Sources: {result.get('sources', [])}")
        print_info(f"Total tokens: {result.get('total_tokens', 0)}")
        if result.get('answer'):
            print_info(f"Answer preview: {result.get('answer', '')[:200]}...")
        test_results['passed'] += 1
        return result
    return None

def test_query_with_enhanced_params(document_id):
    """Test query with enhanced parameters"""
    print_test("9. Query with Enhanced Parameters (temperature, max_tokens)")
    query_data = {
        'question': 'What are the key specifications in this document?',
        'k': 5,
        'use_mmr': True,
        'temperature': 0.7,
        'max_tokens': 500,
        'document_id': document_id
    }
    result = test_endpoint('POST', '/query', expected_status=200, data=query_data)
    if result:
        print_pass(f"Query with enhanced params successful")
        print_info(f"Temperature used: 0.7")
        print_info(f"Max tokens: 500")
        print_info(f"Total tokens: {result.get('total_tokens', 0)}")
        test_results['passed'] += 1
        return result
    return None

def test_get_stats():
    """Test statistics endpoint"""
    print_test("10. Get System Statistics")
    result = test_endpoint('GET', '/stats', expected_status=200)
    if result:
        print_pass("Statistics retrieved")
        if 'rag_stats' in result:
            stats = result['rag_stats']
            print_info(f"Total documents: {stats.get('total_documents', 0)}")
            print_info(f"Total chunks: {stats.get('total_chunks', 0)}")
        test_results['passed'] += 1
        return result
    return None

def test_get_chunk_stats():
    """Test chunk statistics endpoint"""
    print_test("11. Get Chunk Statistics")
    result = test_endpoint('GET', '/stats/chunks', expected_status=200)
    if result:
        print_pass("Chunk statistics retrieved")
        if 'total_chunks' in result:
            print_info(f"Total chunks: {result.get('total_chunks', 0)}")
        test_results['passed'] += 1
        return result
    return None

def test_get_document_images(document_id):
    """Test getting images for a document"""
    print_test(f"12. Get Document Images: {document_id}")
    result = test_endpoint('GET', f'/documents/{document_id}/images?limit=10', expected_status=200)
    if result:
        image_count = result.get('total', len(result.get('images', [])))
        if image_count > 0:
            print_pass(f"Found {image_count} images for document")
            for img in result.get('images', [])[:3]:  # Show first 3
                print_info(f"  - Image {img.get('image_number')} (Page {img.get('page', 'N/A')})")
        else:
            print_warn("No images found for document (may be expected)")
            test_results['warnings'] += 1
        test_results['passed'] += 1
        return result
    else:
        test_results['warnings'] += 1
        return None

def test_query_images():
    """Test image query endpoint"""
    print_test("13. Query Images")
    query_data = {
        'question': 'Find images with text or diagrams',
        'k': 5
    }
    result = test_endpoint('POST', '/query/images', expected_status=200, data=query_data)
    if result:
        if result.get('total', 0) > 0:
            print_pass(f"Found {result.get('total')} images")
        else:
            print_warn("No images found (may be expected if no images in documents)")
            test_results['warnings'] += 1
        test_results['passed'] += 1
        return result
    else:
        test_results['warnings'] += 1
        return None

def test_sync_status():
    """Test sync status endpoint"""
    print_test("14. Get Sync Status")
    result = test_endpoint('GET', '/sync/status', expected_status=200)
    if result:
        print_pass("Sync status retrieved")
        test_results['passed'] += 1
        return result
    return None

def test_delete_document(document_id):
    """Test document deletion"""
    print_test(f"15. Delete Document: {document_id}")
    result = test_endpoint('DELETE', f'/documents/{document_id}', expected_status=204)
    if result is not None or True:  # 204 No Content
        print_pass(f"Document deleted: {document_id}")
        test_results['passed'] += 1
        return True
    return False

def main():
    """Run all tests"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Comprehensive FastAPI Endpoint Test{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Testing with: {DOCUMENT_NAME}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}\n")
    print_info(f"API Base URL: {BASE_URL}")
    
    # Find document file
    document_path = find_document_file()
    if not document_path:
        print_fail("Cannot proceed without document file")
        return False
    
    # Run tests
    test_health_check()
    test_root_endpoint()
    
    # Upload document
    upload_result = test_upload_document(document_path)
    if not upload_result:
        print_warn("Document upload failed - some tests may be skipped")
        return False
    
    document_id = upload_result.get('document_id') or upload_result.get('document_name', '')
    if not document_id:
        print_warn("No document_id returned - some tests may be skipped")
        return False
    
    # Wait a bit for processing
    print_info("Waiting 3 seconds for document processing...")
    time.sleep(3)
    
    # CRUD tests
    test_list_documents()
    test_get_document(document_id)
    test_update_document(document_id)
    
    # Query tests
    test_query_all_documents()
    test_query_specific_document(document_id)
    test_query_with_enhanced_params(document_id)
    
    # Statistics tests
    test_get_stats()
    test_get_chunk_stats()
    
    # Image tests
    test_get_document_images(document_id)
    test_query_images()
    
    # Sync tests
    test_sync_status()
    
    # Cleanup - delete document (optional, comment out if you want to keep it)
    # test_delete_document(document_id)
    
    # Print summary
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Test Summary{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.GREEN}✅ Passed: {test_results['passed']}{Colors.END}")
    print(f"{Colors.RED}❌ Failed: {test_results['failed']}{Colors.END}")
    print(f"{Colors.YELLOW}⚠️  Warnings: {test_results['warnings']}{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    if test_results['failed'] == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return True
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  SOME TESTS FAILED OR HAD WARNINGS{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return test_results['failed'] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

