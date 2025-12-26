#!/usr/bin/env python3
"""
Detailed test of all API endpoints with full response verification
"""
import os
import sys
import requests
import json
from typing import Dict, Any

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 60

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_endpoint(name: str, method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Test an endpoint and return detailed results"""
    print(f"\n🔍 Testing: {name}")
    print(f"   {method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        else:
            return {"error": f"Unsupported method: {method}", "success": False}
        
        print(f"   Status: {response.status_code}")
        
        try:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "data": data
            }
        except:
            print(f"   Response: {response.text}")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "text": response.text
            }
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {"error": str(e), "success": False}

def main():
    """Test all endpoints in detail"""
    print_section("ARIS RAG API - Endpoint Verification")
    print(f"Server: {API_BASE_URL}")
    print(f"Time: {os.popen('date').read().strip()}")
    
    results = {}
    
    # 1. Health Check
    print_section("1. Health Check Endpoint")
    results['health'] = test_endpoint(
        "Health Check",
        "GET",
        f"{API_BASE_URL}/health"
    )
    
    # 2. Root
    print_section("2. Root Endpoint")
    results['root'] = test_endpoint(
        "Root",
        "GET",
        f"{API_BASE_URL}/"
    )
    
    # 3. List Documents
    print_section("3. List Documents Endpoint")
    results['list_documents'] = test_endpoint(
        "List Documents",
        "GET",
        f"{API_BASE_URL}/documents"
    )
    
    # Get document info for further tests
    doc_id = None
    doc_name = None
    if results['list_documents'].get('success') and results['list_documents'].get('data'):
        docs = results['list_documents']['data'].get('documents', [])
        if docs:
            doc = docs[0]
            doc_id = doc.get('document_id')
            doc_name = doc.get('document_name')
            print(f"\n   📄 Found document: {doc_name} (ID: {doc_id})")
    
    # 4. Query Documents
    print_section("4. Query Documents Endpoint")
    results['query'] = test_endpoint(
        "Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": "What is this document about?",
            "k": 3
        }
    )
    
    # 5. Query with document_id (if available)
    if doc_id:
        print_section("5. Query Documents (with document_id filter)")
        results['query_with_doc_id'] = test_endpoint(
            "Query with document_id",
            "POST",
            f"{API_BASE_URL}/query",
            json={
                "question": "test",
                "k": 3,
                "document_id": doc_id
            }
        )
    else:
        print_section("5. Query Documents (with document_id filter)")
        print("   ⏭️  Skipped - No document_id available")
        results['query_with_doc_id'] = {"skipped": True}
    
    # 6. Query Images - Get all for document
    if doc_name:
        print_section("6. Query Images (Get All for Document)")
        results['query_images_all'] = test_endpoint(
            "Query Images - All",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 10
            }
        )
    else:
        print_section("6. Query Images (Get All for Document)")
        print("   ⏭️  Skipped - No document name available")
        results['query_images_all'] = {"skipped": True}
    
    # 7. Query Images - Semantic Search
    print_section("7. Query Images (Semantic Search)")
    results['query_images_search'] = test_endpoint(
        "Query Images - Search",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "diagram or chart",
            "k": 5
        }
    )
    
    # Summary
    print_section("TEST SUMMARY")
    
    passed = 0
    failed = 0
    skipped = 0
    warnings = 0
    
    for name, result in results.items():
        if result.get('skipped'):
            skipped += 1
            print(f"⏭️  {name}: SKIPPED")
        elif result.get('success'):
            status = result.get('status', 'N/A')
            # Check if it's an expected error (like no documents)
            if status == 400 and 'No documents' in str(result.get('data', {})):
                warnings += 1
                print(f"⚠️  {name}: PASSED (Status: {status}) - Expected: No documents available")
            else:
                passed += 1
                print(f"✅ {name}: PASSED (Status: {status})")
        else:
            failed += 1
            print(f"❌ {name}: FAILED")
            if result.get('error'):
                print(f"   Error: {result['error']}")
            elif result.get('status'):
                print(f"   Status: {result['status']}")
    
    print(f"\n📊 Results: {passed} passed, {warnings} warnings, {failed} failed, {skipped} skipped")
    
    # Save detailed results
    output_file = 'ENDPOINT_VERIFICATION_RESULTS.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    # Final verdict
    if failed > 0:
        print("\n❌ Some endpoints failed!")
        sys.exit(1)
    elif warnings > 0:
        print("\n⚠️  All endpoints working, but some have expected warnings (e.g., no documents)")
        sys.exit(0)
    else:
        print("\n✅ All endpoints working perfectly!")
        sys.exit(0)

if __name__ == "__main__":
    main()

