#!/usr/bin/env python3
"""
In-depth system verification test
Tests all endpoints, checks for errors, and verifies fixes
"""
import os
import sys
import requests
import json
import time
from typing import Dict, Any, List

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def find_document_file() -> str:
    """Find the test document"""
    possible_paths = [
        "FL10.11 SPECIFIC8 (1).pdf",
        "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf",
        os.path.join(os.path.dirname(__file__), "FL10.11 SPECIFIC8 (1).pdf")
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def test_health():
    """Test health endpoint"""
    print("\n" + "="*80)
    print("TEST: Health Check")
    print("="*80)
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✅ Health check passed: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_upload_and_query():
    """Test upload and query with document_id"""
    print("\n" + "="*80)
    print("TEST: Upload Document and Query with document_id")
    print("="*80)
    
    # Upload document
    file_path = find_document_file()
    if not file_path:
        print("❌ Test document not found")
        return False
    
    print(f"📄 Uploading: {os.path.basename(file_path)}")
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
        data = {'parser': 'docling'}
        response = requests.post(
            f"{API_BASE_URL}/documents",
            files=files,
            data=data,
            timeout=TEST_TIMEOUT
        )
    
    if response.status_code != 201:
        print(f"❌ Upload failed: {response.status_code} - {response.text}")
        return False
    
    upload_result = response.json()
    document_id = upload_result.get('document_id')
    document_name = upload_result.get('document_name')
    print(f"✅ Document uploaded: {document_id}")
    print(f"   Name: {document_name}")
    print(f"   Chunks: {upload_result.get('chunks_created', 0)}")
    print(f"   Images: {upload_result.get('images_detected', False)}")
    
    # Wait for processing
    print("⏳ Waiting 5 seconds for processing...")
    time.sleep(5)
    
    # Update document name
    print(f"\n📝 Updating document name...")
    update_response = requests.put(
        f"{API_BASE_URL}/documents/{document_id}",
        json={"document_name": f"{document_name} - Updated Test"},
        timeout=30
    )
    
    if update_response.status_code != 200:
        print(f"❌ Update failed: {update_response.status_code} - {update_response.text}")
        return False
    
    updated_doc = update_response.json()
    new_name = updated_doc.get('document_name')
    print(f"✅ Document updated: {new_name}")
    
    # Query with document_id (should work even after name update)
    print(f"\n🔍 Querying with document_id={document_id}...")
    query_response = requests.post(
        f"{API_BASE_URL}/query",
        json={
            "question": "What is this document about?",
            "k": 5,
            "document_id": document_id
        },
        timeout=60
    )
    
    if query_response.status_code != 200:
        print(f"❌ Query failed: {query_response.status_code} - {query_response.text}")
        return False
    
    query_result = query_response.json()
    answer = query_result.get('answer', '')
    print(f"✅ Query successful")
    print(f"   Answer length: {len(answer)} chars")
    print(f"   Answer preview: {answer[:100]}...")
    
    if "No indexes found" in answer:
        print(f"⚠️  WARNING: Query returned 'No indexes found' - document_index_map may not be updated correctly")
        return False
    
    # Get document images
    print(f"\n🖼️  Getting images for document...")
    images_response = requests.get(
        f"{API_BASE_URL}/documents/{document_id}/images?limit=5",
        timeout=30
    )
    
    if images_response.status_code != 200:
        print(f"❌ Get images failed: {images_response.status_code} - {images_response.text}")
        return False
    
    images_result = images_response.json()
    images = images_result.get('images', [])
    print(f"✅ Found {len(images)} images")
    
    if len(images) > 0:
        print(f"   First image: {images[0].get('image_id', 'N/A')}")
        print(f"   OCR preview: {images[0].get('ocr_text', '')[:100]}...")
    
    return True

def test_image_semantic_search():
    """Test semantic image search"""
    print("\n" + "="*80)
    print("TEST: Semantic Image Search")
    print("="*80)
    
    # Try semantic search with specific queries
    queries = [
        "FILLING HANDLER",
        "Standard Work",
        "Batch Change"
    ]
    
    for query in queries:
        print(f"\n🔍 Searching for: '{query}'")
        response = requests.post(
            f"{API_BASE_URL}/query/images",
            json={
                "question": query,
                "k": 5
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Search failed: {response.status_code} - {response.text}")
            continue
        
        result = response.json()
        images = result.get('images', [])
        print(f"   Found {len(images)} images")
        
        if len(images) > 0:
            print(f"   ✅ Semantic search working!")
            print(f"   First result: {images[0].get('image_id', 'N/A')}")
            return True
    
    print("⚠️  No images found for any query - semantic search may need tuning")
    return False

def main():
    """Run all tests"""
    print("="*80)
    print("IN-DEPTH SYSTEM VERIFICATION TEST")
    print("="*80)
    print(f"API URL: {API_BASE_URL}")
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health()))
    
    # Test 2: Upload and query with document_id
    results.append(("Upload and Query", test_upload_and_query()))
    
    # Test 3: Semantic image search
    results.append(("Semantic Image Search", test_image_semantic_search()))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("⚠️  Some tests failed - check logs above")
        return 1

if __name__ == "__main__":
    sys.exit(main())

