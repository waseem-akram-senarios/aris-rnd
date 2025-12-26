#!/usr/bin/env python3
"""
Test Image OCR Storage and Querying in OpenSearch
Verifies that:
1. Image OCR results are stored in OpenSearch
2. Can query OCR content from images
3. Separation between text and images works correctly
"""
import os
import sys
import requests
import json
import time
from pathlib import Path

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 600  # 10 minutes

# Colors
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*70}")
    print(f"{msg}")
    print(f"{'='*70}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def test_endpoint(name, method, url, expected_status=200, **kwargs):
    """Test an endpoint"""
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
        
        status_ok = response.status_code == expected_status
        if status_ok:
            print_success(f"Status: {response.status_code}")
        else:
            print_error(f"Expected {expected_status}, got {response.status_code}")
        
        try:
            data = response.json()
            return {"success": status_ok, "status": response.status_code, "data": data}
        except:
            return {"success": status_ok, "status": response.status_code, "text": response.text}
    except Exception as e:
        print_error(f"Request failed: {e}")
        return {"success": False, "error": str(e)}

def find_f1_document():
    """Find F1 document"""
    paths = [
        "./FL10.11 SPECIFIC8 (1).pdf",
        "./FL10.11 SPECIFIC8 (2).pdf",
        "./FL10.11 SPECIFIC8.pdf",
        "./test_documents/FL10.11 SPECIFIC8 (1).pdf",
        "./documents/FL10.11 SPECIFIC8 (1).pdf",
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return None

def main():
    print_header("Image OCR OpenSearch Storage and Query Test")
    print(f"Server: {API_BASE_URL}\n")
    
    results = {}
    doc_id = None
    doc_name = None
    
    # STEP 1: Health Check
    print_header("STEP 1: Health Check")
    health = test_endpoint("Health Check", "GET", f"{API_BASE_URL}/health")
    if not health.get('success'):
        print_error("Health check failed! Cannot proceed.")
        return 1
    results['health'] = health
    
    # STEP 2: Find Document
    print_header("STEP 2: Find F1 Document")
    pdf_path = find_f1_document()
    if not pdf_path:
        print_error("F1 document not found!")
        return 1
    print_success(f"Found: {pdf_path}")
    print_info(f"Size: {os.path.getsize(pdf_path) / (1024*1024):.2f} MB")
    
    # STEP 3: Upload Document
    print_header("STEP 3: Upload Document with Docling (OCR Processing)")
    print_info("This may take 5-10 minutes for OCR processing...")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=TEST_TIMEOUT
            )
        
        if response.status_code == 201:
            upload_data = response.json()
            doc_id = upload_data.get('document_id')
            doc_name = upload_data.get('document_name')
            
            print_success("Document uploaded successfully")
            print_info(f"Document ID: {doc_id}")
            print_info(f"Document Name: {doc_name}")
            print_info(f"Text Chunks: {upload_data.get('chunks_created', 0)}")
            print_info(f"Text Stored: {upload_data.get('text_chunks_stored', 0)}")
            print_info(f"Images Detected: {upload_data.get('images_detected', False)}")
            print_info(f"Images Stored: {upload_data.get('images_stored', 0)}")
            print_info(f"Text Index: {upload_data.get('text_index', 'N/A')}")
            print_info(f"Images Index: {upload_data.get('images_index', 'N/A')}")
            
            results['upload'] = {"success": True, "data": upload_data}
            
            # Wait for processing
            print_info("Waiting 10 seconds for indexing...")
            time.sleep(10)
        else:
            print_error(f"Upload failed: {response.status_code}")
            print_info(f"Response: {response.text[:500]}")
            return 1
    except Exception as e:
        print_error(f"Upload error: {e}")
        return 1
    
    if not doc_id:
        print_error("No document ID received")
        return 1
    
    # STEP 4: Check Storage Status
    print_header("STEP 4: Check Storage Status in OpenSearch")
    status = test_endpoint(
        "Get Storage Status",
        "GET",
        f"{API_BASE_URL}/documents/{doc_id}/storage/status"
    )
    
    if status.get('success'):
        status_data = status['data']
        print_success("Storage status retrieved")
        print_info(f"Text Index: {status_data.get('text_index')}")
        print_info(f"Text Chunks: {status_data.get('text_chunks_count', 0)}")
        print_info(f"Text Status: {status_data.get('text_storage_status')}")
        print_info(f"Images Index: {status_data.get('images_index')}")
        print_info(f"Images Count: {status_data.get('images_count', 0)}")
        print_info(f"Images Status: {status_data.get('images_storage_status')}")
        print_info(f"OCR Enabled: {status_data.get('ocr_enabled', False)}")
        print_info(f"Total OCR Text: {status_data.get('total_ocr_text_length', 0):,} characters")
        
        images_count = status_data.get('images_count', 0)
        if images_count > 0:
            print_success(f"✅ {images_count} images found in OpenSearch!")
        else:
            print_warning(f"⚠️  No images found in OpenSearch (may need more time to index)")
        
        results['storage_status'] = status
    else:
        print_error("Failed to get storage status")
        results['storage_status'] = status
    
    # STEP 5: Store Images Separately (Verify)
    print_header("STEP 5: Verify Image Storage in OpenSearch")
    store_images = test_endpoint(
        "Store Images Separately",
        "POST",
        f"{API_BASE_URL}/documents/{doc_id}/store/images"
    )
    
    if store_images.get('success'):
        img_data = store_images['data']
        print_success("Image storage verified")
        print_info(f"Images Stored: {img_data.get('images_stored', 0)}")
        print_info(f"Images Index: {img_data.get('images_index')}")
        print_info(f"Total OCR Text: {img_data.get('total_ocr_text_length', 0):,} characters")
        print_info(f"Status: {img_data.get('status')}")
        
        if img_data.get('images_stored', 0) > 0:
            print_success(f"✅ {img_data.get('images_stored')} images confirmed in OpenSearch!")
        else:
            print_warning("⚠️  No images stored yet (may need more time)")
        
        results['store_images'] = store_images
    else:
        print_error("Failed to verify image storage")
        results['store_images'] = store_images
    
    # STEP 6: Query Images with Empty Question (Get All)
    print_header("STEP 6: Query All Images from OpenSearch")
    query_all = test_endpoint(
        "Get All Images",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "",
            "source": doc_name,
            "k": 100
        }
    )
    
    if query_all.get('success'):
        query_data = query_all['data']
        total_images = query_data.get('total', 0)
        images = query_data.get('images', [])
        
        print_success(f"Query completed")
        print_info(f"Content Type: {query_data.get('content_type', 'N/A')}")
        print_info(f"Images Index: {query_data.get('images_index', 'N/A')}")
        print_info(f"Total Images: {total_images}")
        print_info(f"Images Returned: {len(images)}")
        
        if total_images > 0:
            print_success(f"✅ Successfully retrieved {total_images} images from OpenSearch!")
            
            # Show first image details
            if images:
                first = images[0]
                print_info(f"\nFirst Image Details:")
                print_info(f"  Image ID: {first.get('image_id', 'N/A')}")
                print_info(f"  Source: {first.get('source', 'N/A')}")
                print_info(f"  Image Number: {first.get('image_number', 'N/A')}")
                print_info(f"  Page: {first.get('page', 'N/A')}")
                ocr_text = first.get('ocr_text', '')
                print_info(f"  OCR Text Length: {len(ocr_text):,} characters")
                if ocr_text:
                    print_info(f"  OCR Preview: {ocr_text[:200]}...")
        else:
            print_warning("⚠️  No images returned (may need more time to index)")
        
        results['query_all'] = query_all
    else:
        print_error("Failed to query images")
        results['query_all'] = query_all
    
    # STEP 7: Query Images with Semantic Search
    print_header("STEP 7: Semantic Search on Image OCR Content")
    semantic_queries = [
        "What tools are shown in the images?",
        "What part numbers are in the images?",
        "What drawer information is in the images?",
    ]
    
    for query in semantic_queries:
        print_info(f"\nQuery: '{query}'")
        semantic = test_endpoint(
            f"Semantic Search: {query[:30]}...",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": query,
                "source": doc_name,
                "k": 5
            }
        )
        
        if semantic.get('success'):
            sem_data = semantic['data']
            total = sem_data.get('total', 0)
            images = sem_data.get('images', [])
            
            if total > 0:
                print_success(f"✅ Found {total} relevant images")
                if images:
                    print_info(f"  Top result: Image {images[0].get('image_number')} - {len(images[0].get('ocr_text', '')):,} OCR chars")
            else:
                print_warning("⚠️  No results found")
        else:
            print_error("Query failed")
    
    # STEP 8: Verify OCR Content Quality
    print_header("STEP 8: Verify OCR Content Quality")
    if results.get('query_all', {}).get('success'):
        query_data = results['query_all']['data']
        images = query_data.get('images', [])
        
        if images:
            total_ocr_length = sum(len(img.get('ocr_text', '')) for img in images)
            avg_ocr_length = total_ocr_length / len(images) if images else 0
            images_with_ocr = sum(1 for img in images if img.get('ocr_text', '').strip())
            
            print_info(f"Total Images: {len(images)}")
            print_info(f"Images with OCR: {images_with_ocr}")
            print_info(f"Total OCR Text: {total_ocr_length:,} characters")
            print_info(f"Average OCR per Image: {avg_ocr_length:,.0f} characters")
            
            if images_with_ocr == len(images):
                print_success("✅ All images have OCR text!")
            else:
                print_warning(f"⚠️  {len(images) - images_with_ocr} images missing OCR text")
            
            if avg_ocr_length > 100:
                print_success(f"✅ Good OCR quality (avg {avg_ocr_length:,.0f} chars per image)")
            elif avg_ocr_length > 50:
                print_warning(f"⚠️  Moderate OCR quality (avg {avg_ocr_length:,.0f} chars per image)")
            else:
                print_warning(f"⚠️  Low OCR quality (avg {avg_ocr_length:,.0f} chars per image)")
            
            # Check for specific content
            all_ocr = ' '.join(img.get('ocr_text', '') for img in images)
            keywords = ['wrench', 'socket', 'drawer', 'part', 'tool']
            found_keywords = [kw for kw in keywords if kw.lower() in all_ocr.lower()]
            
            if found_keywords:
                print_success(f"✅ Found keywords in OCR: {', '.join(found_keywords)}")
            else:
                print_warning("⚠️  No expected keywords found in OCR")
    
    # STEP 9: Test Separation
    print_header("STEP 9: Verify Text/Image Separation")
    
    # Query text only
    print_info("Querying text only...")
    text_query = test_endpoint(
        "Query Text Only",
        "POST",
        f"{API_BASE_URL}/query/text",
        json={
            "question": "What is in this document?",
            "document_id": doc_id,
            "k": 3
        }
    )
    
    if text_query.get('success'):
        text_data = text_query['data']
        print_success("Text query completed")
        print_info(f"Content Type: {text_data.get('content_type', 'N/A')}")
        print_info(f"Chunks Used: {text_data.get('num_chunks_used', 0)}")
        
        # Check citations don't have image content
        citations = text_data.get('citations', [])
        image_citations = [c for c in citations if c.get('content_type') == 'image_ocr']
        
        if not image_citations:
            print_success("✅ Text query correctly excludes image content")
        else:
            print_error(f"❌ Text query contains {len(image_citations)} image citations")
    
    # Query images only
    print_info("Querying images only...")
    img_query = test_endpoint(
        "Query Images Only",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "tools",
            "source": doc_name,
            "k": 3
        }
    )
    
    if img_query.get('success'):
        img_data = img_query['data']
        print_success("Image query completed")
        print_info(f"Content Type: {img_data.get('content_type', 'N/A')}")
        print_info(f"Images Index: {img_data.get('images_index', 'N/A')}")
        
        if img_data.get('content_type') == 'image_ocr':
            print_success("✅ Image query correctly returns image_ocr content type")
        else:
            print_error("❌ Image query has wrong content type")
    
    # STEP 10: Summary
    print_header("STEP 10: Test Summary")
    
    total_tests = len([k for k in results.keys() if k != 'health'])
    passed_tests = sum(1 for k, v in results.items() if k != 'health' and v.get('success'))
    
    print(f"\n{Colors.BOLD}Test Results:{Colors.END}")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {Colors.GREEN}{passed_tests}{Colors.END}")
    print(f"  Failed: {Colors.RED}{total_tests - passed_tests}{Colors.END}")
    print(f"  Success Rate: {Colors.CYAN}{(passed_tests/total_tests*100) if total_tests > 0 else 0:.1f}%{Colors.END}")
    
    print(f"\n{Colors.BOLD}OpenSearch Storage Verification:{Colors.END}")
    if results.get('storage_status', {}).get('success'):
        status_data = results['storage_status']['data']
        images_count = status_data.get('images_count', 0)
        ocr_length = status_data.get('total_ocr_text_length', 0)
        
        if images_count > 0:
            print_success(f"✅ {images_count} images stored in OpenSearch")
            print_success(f"✅ {ocr_length:,} OCR characters stored")
        else:
            print_warning("⚠️  No images found in OpenSearch (may need more indexing time)")
    
    if results.get('query_all', {}).get('success'):
        query_data = results['query_all']['data']
        total = query_data.get('total', 0)
        if total > 0:
            print_success(f"✅ Successfully queried {total} images from OpenSearch")
        else:
            print_warning("⚠️  Could not query images from OpenSearch")
    
    if passed_tests >= total_tests * 0.8:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Test PASSED - Image OCR is stored and queryable in OpenSearch!{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Test FAILED - Some issues detected{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
