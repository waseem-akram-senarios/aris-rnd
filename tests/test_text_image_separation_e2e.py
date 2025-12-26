#!/usr/bin/env python3
"""
End-to-End Test for Separate Text and Image OCR Endpoints
Tests the complete workflow with F1 document:
1. Upload document with Docling
2. Check storage status (text vs images separation)
3. Store text separately
4. Store images separately
5. Query text only
6. Query images only
7. Verify separation works correctly
"""
import os
import sys
import requests
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, '.')

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 600  # 10 minutes for document processing

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, description):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*70}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def test_request(name, method, url, expected_status=200, **kwargs):
    """Make a request and return result"""
    print(f"\n🔍 {name}")
    print(f"   {method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            if 'files' in kwargs:
                response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
            else:
                response = requests.post(url, timeout=TEST_TIMEOUT, json=kwargs.get('json'), **{k: v for k, v in kwargs.items() if k != 'json'})
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        
        print(f"   Status: {response.status_code}")
        
        try:
            data = response.json()
            if response.status_code == expected_status:
                print_success(f"Response received (Status: {response.status_code})")
                return {"status": response.status_code, "success": True, "data": data}
            else:
                print_error(f"Expected {expected_status}, got {response.status_code}")
                print_info(f"Response: {json.dumps(data, indent=2)[:500]}")
                return {"status": response.status_code, "success": False, "data": data}
        except:
            print_info(f"Response: {response.text[:200]}")
            if response.status_code == expected_status:
                return {"status": response.status_code, "success": True, "text": response.text}
            else:
                return {"status": response.status_code, "success": False, "text": response.text}
    except Exception as e:
        print_error(f"Request failed: {e}")
        return {"error": str(e), "success": False}

def find_f1_document():
    """Find F1 document in common locations"""
    possible_paths = [
        "./FL10.11 SPECIFIC8 (1).pdf",
        "./FL10.11 SPECIFIC8 (2).pdf",
        "./FL10.11 SPECIFIC8.pdf",
        "./FL10.11.pdf",
        "./F1.pdf",
        "./test_documents/FL10.11 SPECIFIC8 (1).pdf",
        "./documents/FL10.11 SPECIFIC8 (1).pdf",
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    return None

def main():
    print("\n" + "="*70)
    print(f"{Colors.BOLD}ARIS RAG API - TEXT/IMAGE SEPARATION END-TO-END TEST{Colors.END}")
    print("="*70)
    print(f"Server: {API_BASE_URL}\n")
    
    results = {}
    uploaded_doc_id = None
    uploaded_doc_name = None
    
    # STEP 1: Health Check
    print_step(1, "Health Check")
    results['health'] = test_request("Health Check", "GET", f"{API_BASE_URL}/health", expected_status=200)
    if not results['health'].get('success'):
        print_error("Health check failed! Cannot proceed.")
        return 1
    
    # STEP 2: Find F1 Document
    print_step(2, "Find F1 Document")
    pdf_path = find_f1_document()
    if not pdf_path:
        print_error("F1 document not found!")
        print_info("Please ensure FL10.11 SPECIFIC8 (1).pdf is in the current directory or test_documents/")
        return 1
    
    print_success(f"Found document: {pdf_path}")
    file_size = os.path.getsize(pdf_path) / (1024 * 1024)  # MB
    print_info(f"File size: {file_size:.2f} MB")
    
    # STEP 3: Upload Document with Docling
    print_step(3, "Upload Document with Docling Parser")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            
            print_info("Uploading document (this may take 5-10 minutes for OCR processing)...")
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=TEST_TIMEOUT
            )
        
        if response.status_code == 201:
            upload_data = response.json()
            uploaded_doc_id = upload_data.get('document_id')
            uploaded_doc_name = upload_data.get('document_name')
            
            print_success("Document uploaded successfully")
            print_info(f"Document ID: {uploaded_doc_id}")
            print_info(f"Document Name: {uploaded_doc_name}")
            print_info(f"Status: {upload_data.get('status')}")
            print_info(f"Text Chunks: {upload_data.get('chunks_created', 0)}")
            print_info(f"Text Stored: {upload_data.get('text_chunks_stored', 0)}")
            print_info(f"Images Detected: {upload_data.get('images_detected', False)}")
            print_info(f"Images Stored: {upload_data.get('images_stored', 0)}")
            print_info(f"Text Index: {upload_data.get('text_index', 'N/A')}")
            print_info(f"Images Index: {upload_data.get('images_index', 'N/A')}")
            print_info(f"Text Storage Status: {upload_data.get('text_storage_status', 'N/A')}")
            print_info(f"Images Storage Status: {upload_data.get('images_storage_status', 'N/A')}")
            
            results['upload'] = {"status": 201, "success": True, "data": upload_data}
            
            # Wait for processing to complete
            if upload_data.get('status') == 'success':
                print_info("Waiting 5 seconds for indexing to complete...")
                time.sleep(5)
        else:
            print_error(f"Upload failed: {response.status_code}")
            print_info(f"Response: {response.text[:500]}")
            results['upload'] = {"status": response.status_code, "success": False, "data": response.text}
            return 1
    except Exception as e:
        print_error(f"Upload error: {e}")
        results['upload'] = {"error": str(e), "success": False}
        return 1
    
    if not uploaded_doc_id:
        print_error("No document ID received. Cannot continue.")
        return 1
    
    # STEP 4: Check Storage Status
    print_step(4, "Check Storage Status (Text vs Images Separation)")
    results['storage_status'] = test_request(
        "Get Storage Status",
        "GET",
        f"{API_BASE_URL}/documents/{uploaded_doc_id}/storage/status",
        expected_status=200
    )
    
    if results['storage_status'].get('success'):
        status_data = results['storage_status']['data']
        print_success("Storage status retrieved")
        print_info(f"Text Index: {status_data.get('text_index')}")
        print_info(f"Text Chunks: {status_data.get('text_chunks_count', 0)}")
        print_info(f"Text Status: {status_data.get('text_storage_status')}")
        print_info(f"Images Index: {status_data.get('images_index')}")
        print_info(f"Images Count: {status_data.get('images_count', 0)}")
        print_info(f"Images Status: {status_data.get('images_storage_status')}")
        print_info(f"OCR Enabled: {status_data.get('ocr_enabled', False)}")
        print_info(f"Total OCR Text Length: {status_data.get('total_ocr_text_length', 0):,} characters")
    
    # STEP 5: Store Text Separately
    print_step(5, "Store Text Content Separately")
    results['store_text'] = test_request(
        "Store Text Separately",
        "POST",
        f"{API_BASE_URL}/documents/{uploaded_doc_id}/store/text",
        expected_status=200
    )
    
    if results['store_text'].get('success'):
        text_data = results['store_text']['data']
        print_success("Text storage verified")
        print_info(f"Text Chunks Stored: {text_data.get('text_chunks_stored', 0)}")
        print_info(f"Text Index: {text_data.get('text_index')}")
        print_info(f"Status: {text_data.get('status')}")
        print_info(f"Message: {text_data.get('message')}")
    
    # STEP 6: Store Images Separately
    print_step(6, "Store Image OCR Content Separately")
    results['store_images'] = test_request(
        "Store Images Separately",
        "POST",
        f"{API_BASE_URL}/documents/{uploaded_doc_id}/store/images",
        expected_status=200
    )
    
    if results['store_images'].get('success'):
        images_data = results['store_images']['data']
        print_success("Image OCR storage verified")
        print_info(f"Images Stored: {images_data.get('images_stored', 0)}")
        print_info(f"Images Index: {images_data.get('images_index')}")
        print_info(f"Total OCR Text Length: {images_data.get('total_ocr_text_length', 0):,} characters")
        print_info(f"Status: {images_data.get('status')}")
        print_info(f"Message: {images_data.get('message')}")
    
    # STEP 7: Query Text Only
    print_step(7, "Query Text Content Only (Excludes Images)")
    results['query_text'] = test_request(
        "Query Text Only",
        "POST",
        f"{API_BASE_URL}/query/text",
        expected_status=200,
        json={
            "question": "What tools and parts are mentioned in this document?",
            "k": 5,
            "document_id": uploaded_doc_id
        }
    )
    
    if results['query_text'].get('success'):
        query_data = results['query_text']['data']
        print_success("Text query completed")
        print_info(f"Content Type: {query_data.get('content_type', 'N/A')}")
        print_info(f"Chunks Used: {query_data.get('num_chunks_used', 0)}")
        print_info(f"Total Text Chunks: {query_data.get('total_text_chunks', 0)}")
        print_info(f"Response Time: {query_data.get('response_time', 0):.2f}s")
        print_info(f"Answer Preview: {query_data.get('answer', '')[:200]}...")
        print_info(f"Sources: {len(query_data.get('sources', []))} documents")
        print_info(f"Citations: {len(query_data.get('citations', []))} citations")
    
    # STEP 8: Query Images Only
    print_step(8, "Query Image OCR Content Only (Excludes Text)")
    results['query_images'] = test_request(
        "Query Images Only",
        "POST",
        f"{API_BASE_URL}/query/images",
        expected_status=200,
        json={
            "question": "What tools and parts are shown in the images?",
            "source": uploaded_doc_name,
            "k": 5
        }
    )
    
    if results['query_images'].get('success'):
        images_query_data = results['query_images']['data']
        print_success("Image query completed")
        print_info(f"Content Type: {images_query_data.get('content_type', 'N/A')}")
        print_info(f"Images Index: {images_query_data.get('images_index', 'N/A')}")
        print_info(f"Total Images: {images_query_data.get('total', 0)}")
        print_info(f"Images Returned: {len(images_query_data.get('images', []))}")
        
        if images_query_data.get('images'):
            first_image = images_query_data['images'][0]
            print_info(f"First Image OCR Preview: {first_image.get('ocr_text', '')[:200]}...")
            print_info(f"First Image Source: {first_image.get('source', 'N/A')}")
            print_info(f"First Image Number: {first_image.get('image_number', 'N/A')}")
    
    # STEP 9: Verify Separation
    print_step(9, "Verify Text and Image Separation")
    
    # Check that text query doesn't return image content
    text_query_has_images = False
    if results['query_text'].get('success'):
        query_data = results['query_text']['data']
        citations = query_data.get('citations', [])
        for citation in citations:
            if citation.get('content_type') == 'image_ocr':
                text_query_has_images = True
                break
    
    # Check that image query doesn't return regular text
    image_query_has_text = False
    if results['query_images'].get('success'):
        images_data = results['query_images']['data']
        if images_data.get('content_type') != 'image_ocr':
            image_query_has_text = True
    
    if not text_query_has_images:
        print_success("✅ Text query correctly excludes image content")
    else:
        print_error("❌ Text query contains image content (separation failed)")
    
    if not image_query_has_text:
        print_success("✅ Image query correctly excludes regular text")
    else:
        print_error("❌ Image query contains regular text (separation failed)")
    
    # STEP 10: Summary
    print_step(10, "Test Summary")
    
    total_tests = len([k for k in results.keys() if k != 'health'])
    passed_tests = sum(1 for k, v in results.items() if k != 'health' and v.get('success'))
    
    print(f"\n{Colors.BOLD}Test Results:{Colors.END}")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
    print(f"  Failed: {Colors.RED}{total_tests - passed_tests}{Colors.END}")
    print(f"  Success Rate: {Colors.CYAN}{(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%{Colors.END}")
    
    print(f"\n{Colors.BOLD}Key Metrics:{Colors.END}")
    if results.get('upload', {}).get('success'):
        upload_data = results['upload']['data']
        print(f"  Text Chunks: {upload_data.get('text_chunks_stored', 0)}")
        print(f"  Images: {upload_data.get('images_stored', 0)}")
        print(f"  Text Index: {upload_data.get('text_index', 'N/A')}")
        print(f"  Images Index: {upload_data.get('images_index', 'N/A')}")
    
    if results.get('query_text', {}).get('success'):
        query_data = results['query_text']['data']
        print(f"  Text Query Chunks: {query_data.get('num_chunks_used', 0)}")
        print(f"  Text Query Time: {query_data.get('response_time', 0):.2f}s")
    
    if results.get('query_images', {}).get('success'):
        images_data = results['query_images']['data']
        print(f"  Image Query Results: {images_data.get('total', 0)}")
    
    if passed_tests == total_tests:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All tests passed!{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
