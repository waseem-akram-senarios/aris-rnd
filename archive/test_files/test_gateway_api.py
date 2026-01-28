#!/usr/bin/env python3
"""
Comprehensive test script for ARIS RAG Gateway API endpoints
Tests all Gateway service endpoints
"""
import requests
import json
import sys
import os
from typing import Dict, List, Optional
from pathlib import Path

# Server configuration
BASE_URL = "http://44.221.84.58"
GATEWAY_URL = f"{BASE_URL}:8500"

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

class TestResult:
    def __init__(self, name: str, success: bool, message: str = "", data: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.message = message
        self.data = data

def print_header(text: str):
    print(f"\n{BLUE}{'='*70}{NC}")
    print(f"{BLUE}{text:^70}{NC}")
    print(f"{BLUE}{'='*70}{NC}\n")

def print_test(name: str, success: bool, message: str = ""):
    status = f"{GREEN}✓ PASS{NC}" if success else f"{RED}✗ FAIL{NC}"
    print(f"{status} {name}")
    if message:
        print(f"    {message}")

def test_endpoint(method: str, url: str, name: str, **kwargs) -> TestResult:
    """Test a single endpoint"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, timeout=60, **kwargs)
        else:
            return TestResult(name, False, f"Unsupported method: {method}")
        
        success = response.status_code in [200, 201, 202]
        message = f"Status: {response.status_code}"
        
        try:
            data = response.json() if response.content else {}
            if data:
                message += f" | Response: {json.dumps(data, indent=2)[:200]}"
        except:
            data = {"raw_response": response.text[:200]}
        
        return TestResult(name, success, message, data)
    except requests.exceptions.Timeout:
        return TestResult(name, False, "Request timed out")
    except requests.exceptions.ConnectionError:
        return TestResult(name, False, "Connection error - service may be down")
    except Exception as e:
        return TestResult(name, False, f"Error: {str(e)}")

def test_gateway_health():
    """Test Gateway health endpoint"""
    print_header("Gateway Health Check")
    result = test_endpoint("GET", f"{GATEWAY_URL}/health", "GET /health")
    print_test(result.name, result.success, result.message)
    
    if result.success and result.data:
        status = result.data.get("status", "unknown")
        service = result.data.get("service", "unknown")
        print(f"    Service: {service}")
        print(f"    Status: {status}")
        if "registry_accessible" in result.data:
            print(f"    Registry Accessible: {result.data.get('registry_accessible')}")
        if "registry_document_count" in result.data:
            print(f"    Document Count: {result.data.get('registry_document_count')}")
    
    return result

def test_list_documents():
    """Test list documents endpoint"""
    print_header("List Documents")
    result = test_endpoint("GET", f"{GATEWAY_URL}/documents", "GET /documents")
    print_test(result.name, result.success, result.message)
    
    if result.success and result.data:
        total = result.data.get("total", 0)
        documents = result.data.get("documents", [])
        print(f"    Total Documents: {total}")
        if documents:
            print(f"    Sample Documents:")
            for doc in documents[:3]:  # Show first 3
                doc_name = doc.get("document_name", "Unknown")
                doc_id = doc.get("document_id", "N/A")
                status = doc.get("status", "unknown")
                print(f"      - {doc_name} (ID: {doc_id[:8]}..., Status: {status})")
    
    return result

def test_upload_document():
    """Test upload document endpoint"""
    print_header("Upload Document")
    
    # Create a test document
    test_content = b"This is a test document for API testing.\nIt contains some sample text."
    test_filename = "test_api_document.txt"
    
    try:
        files = {"file": (test_filename, test_content, "text/plain")}
        result = test_endpoint("POST", f"{GATEWAY_URL}/documents", 
                              "POST /documents", files=files)
        print_test(result.name, result.success, result.message)
        
        if result.success and result.data:
            doc_id = result.data.get("document_id")
            doc_name = result.data.get("document_name")
            status = result.data.get("status")
            print(f"    Document ID: {doc_id}")
            print(f"    Document Name: {doc_name}")
            print(f"    Status: {status}")
            return result, doc_id
        else:
            return result, None
    except Exception as e:
        result = TestResult("POST /documents", False, f"Error: {str(e)}")
        print_test(result.name, result.success, result.message)
        return result, None

def test_get_document(document_id: Optional[str] = None):
    """Test get document endpoint"""
    print_header("Get Document")
    
    # Always use an existing document from the list (not the newly uploaded one)
    list_result = test_endpoint("GET", f"{GATEWAY_URL}/documents", "GET /documents")
    if list_result.success and list_result.data:
        documents = list_result.data.get("documents", [])
        # Find a document with status "success" (already processed)
        existing_doc = None
        for doc in documents:
            if doc.get("status") == "success":
                existing_doc = doc
                break
        
        if existing_doc:
            document_id = existing_doc.get("document_id")
            print(f"    Using existing document: {existing_doc.get('document_name', 'Unknown')}")
        elif documents:
            # Use first document even if not success
            document_id = documents[0].get("document_id")
            print(f"    Using document: {documents[0].get('document_name', 'Unknown')} (may still be processing)")
        else:
            result = TestResult("GET /documents/{document_id}", False, 
                               "No documents available to test")
            print_test(result.name, result.success, result.message)
            return result
    else:
        result = TestResult("GET /documents/{document_id}", False, 
                           "Could not retrieve document list")
        print_test(result.name, result.success, result.message)
        return result
    
    if document_id:
        result = test_endpoint("GET", f"{GATEWAY_URL}/documents/{document_id}", 
                              f"GET /documents/{document_id[:8]}...")
        print_test(result.name, result.success, result.message)
        
        if result.success and result.data:
            doc_name = result.data.get("document_name", "Unknown")
            status = result.data.get("status", "unknown")
            chunks = result.data.get("chunks_created", 0)
            print(f"    Document Name: {doc_name}")
            print(f"    Status: {status}")
            print(f"    Chunks Created: {chunks}")
        elif not result.success:
            # Document might still be processing
            print(f"    {YELLOW}Note: Document may still be processing (this is normal for newly uploaded documents){NC}")
    else:
        result = TestResult("GET /documents/{document_id}", False, 
                           "No document ID available")
        print_test(result.name, result.success, result.message)
    
    return result

def test_query_rag():
    """Test query RAG endpoint"""
    print_header("Query RAG")
    
    query_payload = {
        "question": "What is this document about?",
        "k": 3,
        "use_mmr": True
    }
    
    result = test_endpoint("POST", f"{GATEWAY_URL}/query", 
                          "POST /query", json=query_payload)
    print_test(result.name, result.success, result.message)
    
    if result.success and result.data:
        answer = result.data.get("answer", "")
        citations = result.data.get("citations", [])
        sources = result.data.get("sources", [])
        num_chunks = result.data.get("num_chunks_used", 0)
        
        print(f"    Answer Preview: {answer[:100]}..." if len(answer) > 100 else f"    Answer: {answer}")
        print(f"    Citations: {len(citations)}")
        print(f"    Sources: {len(sources)}")
        print(f"    Chunks Used: {num_chunks}")
        
        if citations:
            print(f"    Sample Citation:")
            first_citation = citations[0]
            print(f"      - Source: {first_citation.get('source', 'Unknown')}")
            print(f"      - Page: {first_citation.get('page', 'N/A')}")
            snippet = first_citation.get('snippet', '')[:100]
            print(f"      - Snippet: {snippet}...")
    
    return result

def test_sync_status():
    """Test sync status endpoint"""
    print_header("Sync Status")
    result = test_endpoint("GET", f"{GATEWAY_URL}/sync/status", "GET /sync/status")
    print_test(result.name, result.success, result.message)
    
    if result.success and result.data:
        registry_synced = result.data.get("registry_synced", False)
        index_map_synced = result.data.get("index_map_synced", False)
        last_sync = result.data.get("last_sync_time", "N/A")
        
        print(f"    Registry Synced: {registry_synced}")
        print(f"    Index Map Synced: {index_map_synced}")
        print(f"    Last Sync Time: {last_sync}")
    
    return result

def main():
    """Run all Gateway API tests"""
    print(f"\n{CYAN}╔════════════════════════════════════════════════════════════╗{NC}")
    print(f"{CYAN}║     ARIS RAG Gateway API Test Suite                    ║{NC}")
    print(f"{CYAN}╚════════════════════════════════════════════════════════════╝{NC}")
    print(f"\nTesting Gateway at: {GATEWAY_URL}\n")
    
    all_results = []
    
    # Test 1: Health Check
    health_result = test_gateway_health()
    all_results.append(health_result)
    
    if not health_result.success:
        print(f"\n{RED}⚠️  Gateway health check failed. Some tests may not work.{NC}\n")
    
    # Test 2: List Documents
    list_result = test_list_documents()
    all_results.append(list_result)
    
    # Test 3: Upload Document
    upload_result, uploaded_doc_id = test_upload_document()
    all_results.append(upload_result)
    
    # Test 4: Get Document (use existing document, not newly uploaded one)
    get_result = test_get_document()
    all_results.append(get_result)
    
    # Test 5: Query RAG
    query_result = test_query_rag()
    all_results.append(query_result)
    
    # Test 6: Sync Status
    sync_result = test_sync_status()
    all_results.append(sync_result)
    
    # Summary
    print_header("Test Summary")
    total = len(all_results)
    passed = sum(1 for r in all_results if r.success)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{NC}")
    print(f"{RED}Failed: {failed}{NC}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    # List failed tests
    if failed > 0:
        print(f"\n{RED}Failed Tests:{NC}")
        for result in all_results:
            if not result.success:
                print(f"  - {result.name}: {result.message}")
    
    # Exit code
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()



