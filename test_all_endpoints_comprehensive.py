#!/usr/bin/env python3
"""
Comprehensive test of ALL 7 API endpoints
"""
import os
import sys
import requests
import json
import tempfile
from typing import Dict, Any, Optional

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 120

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}  {text}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}")

def print_test(name: str, method: str, url: str):
    print(f"\n{Colors.YELLOW}🔍 {name}{Colors.NC}")
    print(f"   {method} {url}")

def print_result(success: bool, status: int, message: str = ""):
    if success:
        print(f"   {Colors.GREEN}✅ Status: {status} - {message}{Colors.NC}")
    else:
        print(f"   {Colors.RED}❌ Status: {status} - {message}{Colors.NC}")

def test_endpoint(name: str, method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Test an endpoint and return results"""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        else:
            return {"error": f"Unsupported method: {method}", "success": False}
        
        try:
            data = response.json()
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "data": data
            }
        except:
            return {
                "status": response.status_code,
                "success": response.status_code < 400,
                "text": response.text
            }
    except Exception as e:
        return {"error": str(e), "success": False}

def main():
    """Test all 7 endpoints comprehensively"""
    print_header("ARIS RAG API - Comprehensive Endpoint Test")
    print(f"Server: {API_BASE_URL}")
    
    results = {}
    uploaded_doc_id = None
    
    # 1. Health Check
    print_header("1. GET /health - Health Check")
    print_test("Health Check", "GET", f"{API_BASE_URL}/health")
    results['health'] = test_endpoint("Health", "GET", f"{API_BASE_URL}/health")
    print_result(results['health']['success'], results['health'].get('status', 0), 
                "Health check" if results['health']['success'] else results['health'].get('error', 'Failed'))
    
    # 2. Root
    print_header("2. GET / - Root Endpoint")
    print_test("Root", "GET", f"{API_BASE_URL}/")
    results['root'] = test_endpoint("Root", "GET", f"{API_BASE_URL}/")
    print_result(results['root']['success'], results['root'].get('status', 0),
                "API info returned" if results['root']['success'] else results['root'].get('error', 'Failed'))
    
    # 3. List Documents
    print_header("3. GET /documents - List Documents")
    print_test("List Documents", "GET", f"{API_BASE_URL}/documents")
    results['list_documents'] = test_endpoint("List Documents", "GET", f"{API_BASE_URL}/documents")
    if results['list_documents']['success']:
        docs = results['list_documents'].get('data', {}).get('documents', [])
        print_result(True, results['list_documents'].get('status', 0), 
                    f"Found {len(docs)} document(s)")
    else:
        print_result(False, results['list_documents'].get('status', 0),
                    results['list_documents'].get('error', 'Failed'))
    
    # 4. Upload Document
    print_header("4. POST /documents - Upload Document")
    print_test("Upload Document", "POST", f"{API_BASE_URL}/documents")
    
    # Create a test document
    test_content = "This is a test document for API endpoint verification.\n" * 10
    test_file = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    test_file.write(test_content)
    test_file.close()
    
    try:
        with open(test_file.name, 'rb') as f:
            files = {'file': ('test_api_verification.txt', f, 'text/plain')}
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
            print_result(True, response.status_code, 
                        f"Document uploaded: {result_data.get('document_name')} (ID: {uploaded_doc_id})")
            results['upload_document'] = {
                "status": response.status_code,
                "success": True,
                "data": result_data
            }
        else:
            print_result(False, response.status_code, response.text[:100])
            results['upload_document'] = {
                "status": response.status_code,
                "success": False,
                "data": response.text
            }
    except Exception as e:
        print_result(False, 0, str(e))
        results['upload_document'] = {"error": str(e), "success": False}
    finally:
        os.unlink(test_file.name)
    
    # 5. Query Documents
    print_header("5. POST /query - Query Documents")
    print_test("Query Documents", "POST", f"{API_BASE_URL}/query")
    results['query'] = test_endpoint(
        "Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": "What is this document about?",
            "k": 3
        }
    )
    if results['query']['success']:
        answer = results['query'].get('data', {}).get('answer', '')[:100]
        print_result(True, results['query'].get('status', 0), f"Query successful - Answer: {answer}...")
    else:
        error_detail = results['query'].get('data', {}).get('detail', results['query'].get('error', 'Unknown error'))
        print_result(False, results['query'].get('status', 0), error_detail)
    
    # 6. Query with document_id (if we uploaded one)
    if uploaded_doc_id:
        print_header("6. POST /query - Query with document_id filter")
        print_test("Query with document_id", "POST", f"{API_BASE_URL}/query")
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
        if results['query_with_doc_id']['success']:
            print_result(True, results['query_with_doc_id'].get('status', 0), "Filtered query successful")
        else:
            error_detail = results['query_with_doc_id'].get('data', {}).get('detail', 'Unknown error')
            print_result(False, results['query_with_doc_id'].get('status', 0), error_detail)
    else:
        print_header("6. POST /query - Query with document_id filter")
        print("   ⏭️  Skipped - No document uploaded")
        results['query_with_doc_id'] = {"skipped": True}
    
    # 7. Query Images - Get all
    print_header("7. POST /query/images - Query Images (Get All)")
    print_test("Query Images (All)", "POST", f"{API_BASE_URL}/query/images")
    
    # Get document name for image query
    doc_name = None
    if results['list_documents'].get('success'):
        docs = results['list_documents'].get('data', {}).get('documents', [])
        if docs:
            doc_name = docs[0].get('document_name')
    
    if doc_name:
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
        if results['query_images_all']['success']:
            total = results['query_images_all'].get('data', {}).get('total', 0)
            print_result(True, results['query_images_all'].get('status', 0), 
                        f"Found {total} image(s)")
        else:
            print_result(False, results['query_images_all'].get('status', 0),
                        results['query_images_all'].get('error', 'Failed'))
    else:
        print("   ⏭️  Skipped - No document name available")
        results['query_images_all'] = {"skipped": True}
    
    # 8. Query Images - Semantic Search
    print_header("8. POST /query/images - Query Images (Semantic Search)")
    print_test("Query Images (Search)", "POST", f"{API_BASE_URL}/query/images")
    results['query_images_search'] = test_endpoint(
        "Query Images (Search)",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "diagram or chart",
            "k": 5
        }
    )
    if results['query_images_search']['success']:
        total = results['query_images_search'].get('data', {}).get('total', 0)
        print_result(True, results['query_images_search'].get('status', 0),
                    f"Found {total} image(s)")
    else:
        print_result(False, results['query_images_search'].get('status', 0),
                    results['query_images_search'].get('error', 'Failed'))
    
    # 9. Delete Document (if we uploaded one)
    if uploaded_doc_id:
        print_header("9. DELETE /documents/{id} - Delete Document")
        print_test("Delete Document", "DELETE", f"{API_BASE_URL}/documents/{uploaded_doc_id}")
        results['delete_document'] = test_endpoint(
            "Delete Document",
            "DELETE",
            f"{API_BASE_URL}/documents/{uploaded_doc_id}"
        )
        if results['delete_document'].get('status') == 204:
            print_result(True, 204, "Document deleted successfully")
        else:
            print_result(False, results['delete_document'].get('status', 0),
                        results['delete_document'].get('error', 'Failed'))
    else:
        print_header("9. DELETE /documents/{id} - Delete Document")
        print("   ⏭️  Skipped - No document uploaded to delete")
        results['delete_document'] = {"skipped": True}
    
    # Final Summary
    print_header("FINAL SUMMARY")
    
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
            # Check for expected errors (like no documents)
            if status == 400 and 'No documents' in str(result.get('data', {})):
                warnings += 1
                print(f"⚠️  {name}: WORKING (Status: {status}) - Expected: No documents")
            else:
                passed += 1
                print(f"{Colors.GREEN}✅ {name}: WORKING (Status: {status}){Colors.NC}")
        else:
            failed += 1
            status = result.get('status', 'N/A')
            error = result.get('error', 'Unknown error')
            print(f"{Colors.RED}❌ {name}: FAILED (Status: {status}) - {error}{Colors.NC}")
    
    print(f"\n{Colors.BLUE}📊 Results:{Colors.NC}")
    print(f"   {Colors.GREEN}✅ Passed: {passed}{Colors.NC}")
    print(f"   {Colors.YELLOW}⚠️  Warnings: {warnings}{Colors.NC}")
    print(f"   {Colors.RED}❌ Failed: {failed}{Colors.NC}")
    print(f"   ⏭️  Skipped: {skipped}")
    
    # Save results
    output_file = 'COMPREHENSIVE_ENDPOINT_TEST_RESULTS.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Final verdict
    if failed > 0:
        print(f"\n{Colors.RED}❌ Some endpoints failed!{Colors.NC}")
        sys.exit(1)
    else:
        print(f"\n{Colors.GREEN}✅ All endpoints are working correctly!{Colors.NC}")
        if warnings > 0:
            print(f"{Colors.YELLOW}   (Some expected warnings about no documents - this is normal){Colors.NC}")
        sys.exit(0)

if __name__ == "__main__":
    main()

