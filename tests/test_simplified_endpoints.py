#!/usr/bin/env python3
"""
Test all simplified API endpoints
"""
import os
import sys
import requests
import json
from typing import Dict, Any

# API base URL
API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 60

def test_endpoint(name: str, method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Test an endpoint and return results"""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    print(f"{method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        else:
            return {"error": f"Unsupported method: {method}"}
        
        print(f"Status: {response.status_code}")
        
        try:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)[:500]}...")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "data": data
            }
        except:
            print(f"Response: {response.text[:500]}")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "text": response.text[:500]
            }
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"error": str(e), "success": False}

def main():
    """Test all endpoints"""
    print("="*60)
    print("Testing Simplified ARIS RAG API Endpoints")
    print("="*60)
    print(f"API URL: {API_BASE_URL}")
    
    results = {}
    
    # 1. Health Check
    results['health'] = test_endpoint(
        "Health Check",
        "GET",
        f"{API_BASE_URL}/health"
    )
    
    # 2. Root
    results['root'] = test_endpoint(
        "Root Endpoint",
        "GET",
        f"{API_BASE_URL}/"
    )
    
    # 3. List Documents
    results['list_documents'] = test_endpoint(
        "List Documents",
        "GET",
        f"{API_BASE_URL}/documents"
    )
    
    # 4. Query (simple)
    results['query'] = test_endpoint(
        "Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": "test query",
            "k": 3
        }
    )
    
    # 5. Query Images (empty question to get all)
    # First, get a document name if available
    doc_name = None
    if results['list_documents'].get('success') and results['list_documents'].get('data'):
        docs = results['list_documents']['data'].get('documents', [])
        if docs:
            doc_name = docs[0].get('document_name')
            print(f"\nUsing document: {doc_name} for image query test")
    
    if doc_name:
        results['query_images_all'] = test_endpoint(
            "Query Images (All for document)",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 10
            }
        )
        
        results['query_images_search'] = test_endpoint(
            "Query Images (Semantic Search)",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "test",
                "k": 5
            }
        )
    else:
        print("\n⚠️ No documents found - skipping image query tests")
        results['query_images_all'] = {"skipped": True}
        results['query_images_search'] = {"skipped": True}
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results.items():
        if result.get('skipped'):
            skipped += 1
            print(f"⏭️  {name}: SKIPPED")
        elif result.get('success'):
            passed += 1
            print(f"✅ {name}: PASSED (Status: {result.get('status')})")
        else:
            failed += 1
            print(f"❌ {name}: FAILED")
            if result.get('error'):
                print(f"   Error: {result['error']}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    # Save results
    with open('ENDPOINT_TEST_RESULTS.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: ENDPOINT_TEST_RESULTS.json")
    
    if failed > 0:
        print("\n❌ Some tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()

