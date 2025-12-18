#!/usr/bin/env python3
"""
Comprehensive test of all endpoints with full response verification
"""
import os
import sys
import requests
import json
import tempfile
from typing import Dict, Any

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 120

def print_header(text: str):
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")

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
            print(f"   Response: {json.dumps(data, indent=2)[:1000]}...")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "data": data
            }
        except:
            print(f"   Response: {response.text[:500]}")
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "text": response.text[:500]
            }
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {"error": str(e), "success": False}

def main():
    """Test all endpoints comprehensively"""
    print_header("ARIS RAG API - Complete Endpoint Test with Responses")
    print(f"Server: {API_BASE_URL}")
    
    results = {}
    uploaded_doc_id = None
    
    # 1. Health Check
    print_header("1. GET /health")
    results['health'] = test_endpoint("Health Check", "GET", f"{API_BASE_URL}/health")
    
    # 2. Root
    print_header("2. GET /")
    results['root'] = test_endpoint("Root", "GET", f"{API_BASE_URL}/")
    
    # 3. List Documents
    print_header("3. GET /documents")
    results['list_documents'] = test_endpoint("List Documents", "GET", f"{API_BASE_URL}/documents")
    
    # Get document info
    doc_id = None
    doc_name = None
    if results['list_documents'].get('success') and results['list_documents'].get('data'):
        docs = results['list_documents']['data'].get('documents', [])
        if docs:
            doc = docs[0]
            doc_id = doc.get('document_id')
            doc_name = doc.get('document_name')
            print(f"\n   📄 Found document: {doc_name} (ID: {doc_id})")
    
    # 4. Upload Document
    print_header("4. POST /documents")
    test_content = "This is a test document for endpoint verification.\n" * 20
    test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    test_file.write(test_content)
    test_file.close()
    
    try:
        with open(test_file.name, 'rb') as f:
            files = {'file': ('test_endpoint_verification.txt', f, 'text/plain')}
            data = {'parser': 'auto'}
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=TEST_TIMEOUT
            )
        
        if response.status_code == 201:
            result_data = response.json()
            uploaded_doc_id = result_data.get('document_id')
            print(f"   ✅ Document uploaded: {result_data.get('document_name')} (ID: {uploaded_doc_id})")
            print(f"   Response: {json.dumps(result_data, indent=2)[:500]}...")
            results['upload_document'] = {
                "status": response.status_code,
                "success": True,
                "data": result_data
            }
        else:
            print(f"   ❌ Status: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            results['upload_document'] = {
                "status": response.status_code,
                "success": False,
                "data": response.text
            }
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['upload_document'] = {"error": str(e), "success": False}
    finally:
        os.unlink(test_file.name)
    
    # 5. Query Documents
    print_header("5. POST /query")
    results['query'] = test_endpoint(
        "Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": "What is this document about?",
            "k": 3
        }
    )
    
    # 6. Query with document_id
    if uploaded_doc_id:
        print_header("6. POST /query (with document_id)")
        results['query_with_doc_id'] = test_endpoint(
            "Query with document_id",
            "POST",
            f"{API_BASE_URL}/query",
            json={
                "question": "test",
                "k": 3,
                "document_id": uploaded_doc_id
            }
        )
    else:
        print_header("6. POST /query (with document_id)")
        print("   ⏭️  Skipped - No document uploaded")
        results['query_with_doc_id'] = {"skipped": True}
    
    # 7. Query Images - Get all
    if doc_name:
        print_header("7. POST /query/images (Get All)")
        results['query_images_all'] = test_endpoint(
            "Query Images (All)",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 10
            }
        )
    else:
        print_header("7. POST /query/images (Get All)")
        print("   ⏭️  Skipped - No document name available")
        results['query_images_all'] = {"skipped": True}
    
    # 8. Query Images - Search
    print_header("8. POST /query/images (Semantic Search)")
    results['query_images_search'] = test_endpoint(
        "Query Images (Search)",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "diagram or chart",
            "k": 5
        }
    )
    
    # 9. Delete Document
    if uploaded_doc_id:
        print_header("9. DELETE /documents/{id}")
        results['delete_document'] = test_endpoint(
            "Delete Document",
            "DELETE",
            f"{API_BASE_URL}/documents/{uploaded_doc_id}"
        )
    else:
        print_header("9. DELETE /documents/{id}")
        print("   ⏭️  Skipped - No document uploaded to delete")
        results['delete_document'] = {"skipped": True}
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = 0
    failed = 0
    skipped = 0
    warnings = 0
    
    endpoint_names = {
        'health': 'GET /health',
        'root': 'GET /',
        'list_documents': 'GET /documents',
        'upload_document': 'POST /documents',
        'query': 'POST /query',
        'query_with_doc_id': 'POST /query (with document_id)',
        'query_images_all': 'POST /query/images (all)',
        'query_images_search': 'POST /query/images (search)',
        'delete_document': 'DELETE /documents/{id}'
    }
    
    for key, name in endpoint_names.items():
        result = results.get(key, {})
        if result.get('skipped'):
            skipped += 1
            print(f"⏭️  {name}: SKIPPED")
        elif result.get('success'):
            status = result.get('status', 'N/A')
            # Check for expected errors
            if status == 400 and 'No documents' in str(result.get('data', {})):
                warnings += 1
                print(f"⚠️  {name}: WORKING (Status: {status}) - Expected: No documents")
            elif status == 400 and 'Vectorstore not available' in str(result.get('data', {})):
                warnings += 1
                print(f"⚠️  {name}: WORKING (Status: {status}) - Expected: No vectorstore")
            else:
                passed += 1
                print(f"✅ {name}: WORKING (Status: {status})")
        else:
            failed += 1
            status = result.get('status', 'N/A')
            error = result.get('error', 'Unknown error')
            print(f"❌ {name}: FAILED (Status: {status}) - {error}")
    
    print(f"\n📊 Results: {passed} passed, {warnings} warnings, {failed} failed, {skipped} skipped")
    
    # Save results
    output_file = 'ENDPOINT_TEST_WITH_RESPONSES.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Full results saved to: {output_file}")
    
    # Final verdict
    if failed > 0:
        print(f"\n❌ Some endpoints failed! Check the errors above.")
        return failed
    else:
        print(f"\n✅ All endpoints working correctly!")
        if warnings > 0:
            print(f"   (Some expected warnings - this is normal)")
        return 0

if __name__ == "__main__":
    sys.exit(main())

