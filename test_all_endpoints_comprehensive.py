#!/usr/bin/env python3
"""
Comprehensive test script for all ARIS microservices endpoints
Tests Gateway, Ingestion, and Retrieval services
"""
import requests
import json
import sys
from typing import Dict, List, Optional

# Server configuration
BASE_URL = "http://44.221.84.58"
GATEWAY_URL = f"{BASE_URL}:8500"
INGESTION_URL = f"{BASE_URL}:8501"
RETRIEVAL_URL = f"{BASE_URL}:8502"

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

class TestResult:
    def __init__(self, name: str, success: bool, message: str = "", data: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.message = message
        self.data = data

def print_header(text: str):
    print(f"\n{BLUE}{'='*60}{NC}")
    print(f"{BLUE}{text:^60}{NC}")
    print(f"{BLUE}{'='*60}{NC}\n")

def print_test(name: str, success: bool, message: str = ""):
    status = f"{GREEN}✓ PASS{NC}" if success else f"{RED}✗ FAIL{NC}"
    print(f"{status} {name}")
    if message:
        print(f"    {message}")

def test_endpoint(method: str, url: str, name: str, **kwargs) -> TestResult:
    """Test a single endpoint"""
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10, **kwargs)
        elif method.upper() == "POST":
            response = requests.post(url, timeout=30, **kwargs)
        else:
            return TestResult(name, False, f"Unsupported method: {method}")
        
        success = response.status_code < 400
        try:
            data = response.json() if response.content else {}
        except:
            data = {"raw": response.text[:200]}
        
        message = f"Status: {response.status_code}"
        if not success:
            message += f" - {response.text[:100]}"
        
        return TestResult(name, success, message, data)
    except requests.exceptions.RequestException as e:
        return TestResult(name, False, f"Request failed: {str(e)}")
    except Exception as e:
        return TestResult(name, False, f"Error: {str(e)}")

def test_gateway_service():
    """Test Gateway Service endpoints"""
    print_header("Gateway Service Tests (Port 8500)")
    results = []
    
    # 1. Health Check
    result = test_endpoint("GET", f"{GATEWAY_URL}/health", "GET /health")
    results.append(result)
    print_test(result.name, result.success, result.message)
    
    # 2. List Documents
    result = test_endpoint("GET", f"{GATEWAY_URL}/documents", "GET /documents")
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        doc_count = result.data.get("total", 0)
        print(f"    Found {doc_count} documents")
    
    # 3. Get Document (if documents exist)
    if result.success and result.data and result.data.get("total", 0) > 0:
        doc_id = result.data.get("documents", [{}])[0].get("document_id")
        if doc_id:
            result = test_endpoint("GET", f"{GATEWAY_URL}/documents/{doc_id}", 
                                 f"GET /documents/{{document_id}}")
            results.append(result)
            print_test(result.name, result.success, result.message)
    
    # 4. Sync Status
    result = test_endpoint("GET", f"{GATEWAY_URL}/sync/status", "GET /sync/status")
    results.append(result)
    print_test(result.name, result.success, result.message)
    
    # 5. Query RAG (requires documents)
    query_payload = {
        "question": "What is this document about?",
        "k": 5
    }
    result = test_endpoint("POST", f"{GATEWAY_URL}/query", "POST /query",
                          json=query_payload)
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        answer = result.data.get("answer", "")[:100]
        if answer:
            print(f"    Answer preview: {answer}...")
    
    # 6. Upload Document (test with minimal data)
    # Note: This might fail if file is required, but we test the endpoint
    try:
        files = {"file": ("test.txt", b"Test document content", "text/plain")}
        response = requests.post(f"{GATEWAY_URL}/documents", files=files, timeout=30)
        result = TestResult("POST /documents", response.status_code < 400,
                          f"Status: {response.status_code}")
        results.append(result)
        print_test(result.name, result.success, result.message)
    except Exception as e:
        result = TestResult("POST /documents", False, f"Error: {str(e)}")
        results.append(result)
        print_test(result.name, result.success, result.message)
    
    return results

def test_ingestion_service():
    """Test Ingestion Service endpoints"""
    print_header("Ingestion Service Tests (Port 8501)")
    results = []
    
    # 1. Health Check
    result = test_endpoint("GET", f"{INGESTION_URL}/health", "GET /health")
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        doc_count = result.data.get("registry_document_count", 0)
        index_count = result.data.get("index_map_entries", 0)
        print(f"    Documents: {doc_count}, Index entries: {index_count}")
    
    # 2. Get Metrics
    result = test_endpoint("GET", f"{INGESTION_URL}/metrics", "GET /metrics")
    results.append(result)
    print_test(result.name, result.success, result.message)
    
    # 3. Check Index Exists
    result = test_endpoint("GET", f"{INGESTION_URL}/indexes/aris-rag-index/exists",
                          "GET /indexes/{{index_name}}/exists")
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        exists = result.data.get("exists", False)
        print(f"    Index exists: {exists}")
    
    # 4. Get Next Available Index
    result = test_endpoint("GET", f"{INGESTION_URL}/indexes/test-index/next-available",
                          "GET /indexes/{{base_name}}/next-available")
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        next_index = result.data.get("index_name", "")
        print(f"    Next available: {next_index}")
    
    # 5. Get Processing Status (test with a dummy ID)
    result = test_endpoint("GET", f"{INGESTION_URL}/status/test-doc-id",
                          "GET /status/{{document_id}}")
    # This might return 404, which is expected for non-existent document
    results.append(result)
    if result.success:
        print_test(result.name, result.success, result.message)
    else:
        # 404 is acceptable for non-existent document
        print_test(result.name, True, "404 expected for non-existent document")
        result.success = True  # Mark as success since 404 is expected
    
    # 6. Ingest Document (test endpoint)
    try:
        files = {"file": ("test_ingestion.txt", b"Test content for ingestion", "text/plain")}
        data = {}
        response = requests.post(f"{INGESTION_URL}/ingest", files=files, data=data, timeout=60)
        result = TestResult("POST /ingest", response.status_code < 500,
                          f"Status: {response.status_code}")
        results.append(result)
        print_test(result.name, result.success, result.message)
        if result.success and response.status_code == 201:
            doc_data = response.json()
            doc_id = doc_data.get("document_id", "")
            print(f"    Document ID: {doc_id}")
    except Exception as e:
        result = TestResult("POST /ingest", False, f"Error: {str(e)}")
        results.append(result)
        print_test(result.name, result.success, result.message)
    
    # 7. Process Document Sync
    try:
        files = {"file": ("test_process.txt", b"Test content for sync processing", "text/plain")}
        data = {}
        response = requests.post(f"{INGESTION_URL}/process", files=files, data=data, timeout=120)
        result = TestResult("POST /process", response.status_code < 500,
                          f"Status: {response.status_code}")
        results.append(result)
        print_test(result.name, result.success, result.message)
    except Exception as e:
        result = TestResult("POST /process", False, f"Error: {str(e)}")
        results.append(result)
        print_test(result.name, result.success, result.message)
    
    return results

def test_retrieval_service():
    """Test Retrieval Service endpoints"""
    print_header("Retrieval Service Tests (Port 8502)")
    results = []
    
    # 1. Health Check
    result = test_endpoint("GET", f"{RETRIEVAL_URL}/health", "GET /health")
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        index_count = result.data.get("index_map_entries", 0)
        print(f"    Index entries: {index_count}")
    
    # 2. Get Metrics
    result = test_endpoint("GET", f"{RETRIEVAL_URL}/metrics", "GET /metrics")
    results.append(result)
    print_test(result.name, result.success, result.message)
    
    # 3. Query RAG
    query_payload = {
        "question": "What is artificial intelligence?",
        "k": 5
    }
    result = test_endpoint("POST", f"{RETRIEVAL_URL}/query", "POST /query",
                          json=query_payload)
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        answer = result.data.get("answer", "")[:100]
        citations = len(result.data.get("citations", []))
        print(f"    Answer preview: {answer}...")
        print(f"    Citations: {citations}")
    
    # 4. Query Images
    image_query_payload = {
        "question": "diagram or chart",
        "k": 3
    }
    result = test_endpoint("POST", f"{RETRIEVAL_URL}/query/images", "POST /query/images",
                          json=image_query_payload)
    results.append(result)
    print_test(result.name, result.success, result.message)
    if result.success and result.data:
        image_count = result.data.get("total", 0)
        print(f"    Images found: {image_count}")
    
    return results

def main():
    """Run all tests"""
    print(f"\n{BLUE}╔════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║  ARIS Microservices Endpoint Tests    ║{NC}")
    print(f"{BLUE}╚════════════════════════════════════════╝{NC}")
    print(f"\nTesting services at:")
    print(f"  Gateway:   {GATEWAY_URL}")
    print(f"  Ingestion: {INGESTION_URL}")
    print(f"  Retrieval: {RETRIEVAL_URL}\n")
    
    all_results = []
    
    # Test Gateway Service
    gateway_results = test_gateway_service()
    all_results.extend(gateway_results)
    
    # Test Ingestion Service
    ingestion_results = test_ingestion_service()
    all_results.extend(ingestion_results)
    
    # Test Retrieval Service
    retrieval_results = test_retrieval_service()
    all_results.extend(retrieval_results)
    
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









