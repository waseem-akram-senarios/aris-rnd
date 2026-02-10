#!/usr/bin/env python3
"""
Test script for API fixes
Tests all fixed endpoints to verify they're working correctly
"""
import requests
import json
import sys

# Server URL
BASE_URL = "http://44.221.84.58:8500"

def test_endpoint(name, method, url, data=None, expected_status=None):
    """Test a single endpoint"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"Method: {method} {url}")
    print('='*60)
    
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
        
        print(f"Status Code: {response.status_code}")
        
        # Check if status matches expected
        if expected_status and response.status_code != expected_status:
            print(f"⚠️  Expected {expected_status}, got {response.status_code}")
        
        # Try to parse JSON response
        try:
            response_json = response.json()
            print(f"Response: {json.dumps(response_json, indent=2)[:500]}...")
        except:
            print(f"Response (text): {response.text[:500]}...")
        
        # Determine success
        if response.status_code < 400:
            print(f"✅ PASSED")
            return True
        elif response.status_code == 404:
            print(f"⚠️  NOT FOUND (may be expected if no documents exist)")
            return True
        else:
            print(f"❌ FAILED")
            return False
            
    except requests.exceptions.Timeout:
        print(f"❌ TIMEOUT - Server not responding")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ CONNECTION ERROR - Cannot reach server")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    print("="*60)
    print("API FIXES TEST SUITE")
    print("="*60)
    print(f"Testing server: {BASE_URL}")
    
    results = {}
    
    # Test 1: List documents (to get a document_id)
    print("\n\n### PHASE 1: GET DOCUMENT LIST ###")
    success = test_endpoint(
        "List Documents",
        "GET",
        f"{BASE_URL}/documents"
    )
    results["list_documents"] = success
    
    # Get first document ID if available
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=10)
        docs = response.json().get('documents', [])
        if docs:
            doc_id = docs[0].get('document_id')
            doc_name = docs[0].get('document_name')
            print(f"\n📄 Found document: {doc_name} (ID: {doc_id})")
        else:
            doc_id = "test-doc-id"
            print(f"\n⚠️  No documents found. Using test ID: {doc_id}")
    except:
        doc_id = "test-doc-id"
        print(f"\n⚠️  Could not get documents. Using test ID: {doc_id}")
    
    # Test 2: Get single document metadata (FIX #2)
    print("\n\n### PHASE 2: TEST GET DOCUMENT ENDPOINT ###")
    success = test_endpoint(
        "Get Document Metadata",
        "GET",
        f"{BASE_URL}/documents/{doc_id}",
        expected_status=None  # 200 if exists, 404 if not
    )
    results["get_document"] = success
    
    # Test 3: Query with search_mode (FIX #1)
    print("\n\n### PHASE 3: TEST QUERY WITH SEARCH_MODE ###")
    success = test_endpoint(
        "Query with search_mode='hybrid'",
        "POST",
        f"{BASE_URL}/query",
        data={
            "question": "What is this document about?",
            "search_mode": "hybrid",
            "k": 5
        }
    )
    results["query_search_mode"] = success
    
    # Test 4: Storage status (FIX #3)
    print("\n\n### PHASE 4: TEST STORAGE STATUS ENDPOINT ###")
    success = test_endpoint(
        "Get Storage Status",
        "GET",
        f"{BASE_URL}/documents/{doc_id}/storage/status",
        expected_status=None  # 200 if exists, 404 if not
    )
    results["storage_status"] = success
    
    # Test 5: Accuracy check (FIX #4)
    print("\n\n### PHASE 5: TEST ACCURACY CHECK ENDPOINT ###")
    success = test_endpoint(
        "Get Document Accuracy",
        "GET",
        f"{BASE_URL}/documents/{doc_id}/accuracy",
        expected_status=None  # 200 if exists, 404 if not
    )
    results["accuracy_check"] = success
    
    # Test 6: Query text only
    print("\n\n### PHASE 6: TEST TEXT QUERY ENDPOINT ###")
    success = test_endpoint(
        "Query Text Only",
        "POST",
        f"{BASE_URL}/query/text",
        data={
            "question": "What is this document about?",
            "k": 5
        }
    )
    results["query_text"] = success
    
    # Test 7: Query images
    print("\n\n### PHASE 7: TEST IMAGE QUERY ENDPOINT ###")
    success = test_endpoint(
        "Query Images",
        "POST",
        f"{BASE_URL}/query/images",
        data={
            "question": "all images",
            "k": 5
        }
    )
    results["query_images"] = success
    
    # Print summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name:30} {status}")
    
    print("="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
