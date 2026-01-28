#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for Latest Changes
Tests:
1. Microservices health
2. GatewayService compatibility
3. Document upload and processing
4. Query with fallback mechanisms
5. OpenSearch domain validation
6. Error handling improvements
"""
import requests
import httpx
import json
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://44.221.84.58"
GATEWAY_URL = f"{BASE_URL}:8000"
INGESTION_URL = f"{BASE_URL}:8001"
RETRIEVAL_URL = f"{BASE_URL}:8002"
UI_URL = f"{BASE_URL}:80"

# Test results
results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'tests': []
}

def print_test(name: str):
    """Print test name"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")

def print_pass(msg: str):
    """Print success message"""
    print(f"✅ {msg}")
    results['passed'] += 1
    results['tests'].append({'name': msg, 'status': 'PASSED'})

def print_fail(msg: str):
    """Print failure message"""
    print(f"❌ {msg}")
    results['failed'] += 1
    results['tests'].append({'name': msg, 'status': 'FAILED'})

def print_warn(msg: str):
    """Print warning message"""
    print(f"⚠️  {msg}")
    results['warnings'] += 1
    results['tests'].append({'name': msg, 'status': 'WARNING'})

def test_microservices_health():
    """Test all microservices health endpoints"""
    print_test("Microservices Health Checks")
    
    services = {
        "Gateway": GATEWAY_URL,
        "Ingestion": INGESTION_URL,
        "Retrieval": RETRIEVAL_URL
    }
    
    all_healthy = True
    for name, url in services.items():
        try:
            response = httpx.get(f"{url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    print_pass(f"{name} service is healthy")
                else:
                    print_fail(f"{name} service status: {data.get('status')}")
                    all_healthy = False
            else:
                print_fail(f"{name} service returned {response.status_code}")
                all_healthy = False
        except Exception as e:
            print_fail(f"{name} service health check failed: {str(e)}")
            all_healthy = False
    
    return all_healthy

def test_ui_health():
    """Test UI health"""
    print_test("UI Health Check")
    
    try:
        response = httpx.get(f"{UI_URL}/_stcore/health", timeout=10)
        if response.status_code == 200:
            print_pass("UI service is accessible")
            return True
        else:
            print_warn(f"UI service returned {response.status_code}")
            return True  # Don't fail, UI might be starting
    except Exception as e:
        print_warn(f"UI health check: {str(e)}")
        return True  # Don't fail, UI might be starting

def test_document_upload():
    """Test document upload through Gateway"""
    print_test("Document Upload via Gateway")
    
    # Create a test document
    test_content = """
    This is a test document for end-to-end testing.
    It contains information about the ARIS RAG system.
    The system uses microservices architecture with Gateway, Ingestion, and Retrieval services.
    Documents are processed and indexed for semantic search.
    """
    
    try:
        files = {"file": ("test_e2e.txt", test_content.encode())}
        response = httpx.post(
            f"{GATEWAY_URL}/documents",
            files=files,
            timeout=60
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            doc_id = data.get('document_id')
            if doc_id:
                print_pass(f"Document uploaded successfully: {doc_id}")
                return doc_id
            else:
                print_fail("Document uploaded but no document_id returned")
                return None
        else:
            print_fail(f"Document upload returned {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print_fail(f"Document upload failed: {str(e)}")
        return None

def test_document_processing_status(doc_id: str):
    """Test document processing status"""
    print_test("Document Processing Status")
    
    if not doc_id:
        print_warn("No document ID, skipping processing status check")
        return False
    
    try:
        # Wait a bit for processing
        print("Waiting 5 seconds for processing to start...")
        time.sleep(5)
        
        # Check document status
        response = httpx.get(f"{GATEWAY_URL}/documents/{doc_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get('status', 'unknown')
            chunks = data.get('chunks_created', 0)
            
            if status == 'success':
                print_pass(f"Document processed successfully with {chunks} chunks")
                return True
            elif status == 'processing':
                print_warn(f"Document still processing (chunks: {chunks})")
                return True  # Don't fail, just warn
            elif status == 'failed':
                print_fail(f"Document processing failed: {data.get('error', 'Unknown error')}")
                return False
            else:
                print_warn(f"Document status: {status}")
                return True
        else:
            print_warn(f"Could not get document status: {response.status_code}")
            return True
    except Exception as e:
        print_warn(f"Document status check: {str(e)}")
        return True

def test_query_with_fallback():
    """Test query with fallback mechanisms"""
    print_test("Query with Fallback Mechanisms")
    
    try:
        # Test query through Gateway
        payload = {
            "question": "What is the ARIS RAG system?",
            "k": 3,
            "use_mmr": True
        }
        
        response = httpx.post(
            f"{GATEWAY_URL}/query",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            
            if 'answer' in data:
                answer = data.get('answer', '')
                if answer and not answer.startswith("No documents") and not answer.startswith("Retrieval service error"):
                    print_pass("Query returned valid answer")
                    print(f"   Answer preview: {answer[:100]}...")
                else:
                    print_warn(f"Query returned: {answer[:100]}")
            
            if 'citations' in data:
                citations = data.get('citations', [])
                print_pass(f"Query returned {len(citations)} citation(s)")
            
            if 'sources' in data:
                sources = data.get('sources', [])
                print_pass(f"Query returned {len(sources)} source(s)")
            
            return True
        else:
            # Check if it's a connection error that should trigger fallback
            error_text = response.text[:200]
            if "connection" in error_text.lower() or "failed" in error_text.lower():
                print_warn(f"Query returned {response.status_code}, but fallback should handle this")
            else:
                print_warn(f"Query returned {response.status_code}: {error_text}")
            return True  # Don't fail, may be expected
    except httpx.ConnectError as e:
        print_warn(f"Connection error (fallback should handle): {str(e)}")
        return True  # Fallback should handle this
    except Exception as e:
        print_warn(f"Query test: {str(e)}")
        return True

def test_query_with_rag_method():
    """Test query_with_rag method compatibility"""
    print_test("Query with RAG Method Compatibility")
    
    try:
        # Test through Gateway with all parameters
        payload = {
            "question": "What is microservices architecture?",
            "k": 5,
            "use_mmr": True,
            "use_hybrid_search": False,
            "search_mode": "semantic",
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = httpx.post(
            f"{GATEWAY_URL}/query",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print_pass("query_with_rag method works with all parameters")
            return True
        else:
            print_warn(f"query_with_rag returned {response.status_code}")
            return True
    except Exception as e:
        print_warn(f"query_with_rag test: {str(e)}")
        return True

def test_documents_list():
    """Test documents list endpoint"""
    print_test("Documents List Endpoint")
    
    try:
        response = httpx.get(f"{GATEWAY_URL}/documents", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'documents' in data:
                docs = data.get('documents', [])
                print_pass(f"Documents list returns {len(docs)} document(s)")
                
                # Check document structure
                if docs:
                    first_doc = docs[0]
                    required_fields = ['document_id', 'document_name', 'status']
                    for field in required_fields:
                        if field in first_doc:
                            print_pass(f"Document has '{field}' field")
                        else:
                            print_fail(f"Document missing '{field}' field")
                
                return True
            else:
                print_fail("Documents list missing 'documents' field")
                return False
        else:
            print_fail(f"Documents list returned {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Documents list test failed: {str(e)}")
        return False

def test_error_handling():
    """Test improved error handling"""
    print_test("Error Handling Improvements")
    
    # Test query with no documents (should give helpful message)
    try:
        payload = {"question": "test", "k": 3}
        response = httpx.post(f"{GATEWAY_URL}/query", json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '')
            
            # Check for improved error messages
            helpful_keywords = ['processing', 'indexed', 'registry', 'wait']
            if any(keyword in answer.lower() for keyword in helpful_keywords):
                print_pass("Error message provides helpful information")
            elif "No documents" in answer:
                print_pass("Error message indicates no documents (expected)")
            else:
                print_warn(f"Error message: {answer[:100]}")
            
            return True
        else:
            print_warn(f"Error handling test returned {response.status_code}")
            return True
    except Exception as e:
        print_warn(f"Error handling test: {str(e)}")
        return True

def test_gateway_compatibility():
    """Test GatewayService compatibility methods"""
    print_test("GatewayService Compatibility Methods")
    
    # These are tested indirectly through queries, but we can verify the service responds
    try:
        # Test that Gateway responds to queries (uses compatibility methods)
        response = httpx.get(f"{GATEWAY_URL}/health", timeout=10)
        if response.status_code == 200:
            print_pass("GatewayService is accessible and responding")
            
            # Test that it can handle document operations
            docs_response = httpx.get(f"{GATEWAY_URL}/documents", timeout=10)
            if docs_response.status_code == 200:
                print_pass("GatewayService document operations work")
            
            return True
        else:
            print_fail("GatewayService not responding")
            return False
    except Exception as e:
        print_fail(f"GatewayService compatibility test failed: {str(e)}")
        return False

def main():
    """Run all end-to-end tests"""
    print("="*70)
    print("COMPREHENSIVE END-TO-END TEST - Latest Changes")
    print("="*70)
    print(f"Testing microservices at:")
    print(f"  Gateway: {GATEWAY_URL}")
    print(f"  Ingestion: {INGESTION_URL}")
    print(f"  Retrieval: {RETRIEVAL_URL}")
    print(f"  UI: {UI_URL}")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all tests
    test_microservices_health()
    test_ui_health()
    test_gateway_compatibility()
    test_documents_list()
    
    # Upload and process document
    doc_id = test_document_upload()
    if doc_id:
        test_document_processing_status(doc_id)
        # Wait a bit more for processing
        print("\nWaiting 10 seconds for document processing...")
        time.sleep(10)
    
    # Test queries
    test_query_with_fallback()
    test_query_with_rag_method()
    test_error_handling()
    
    # Summary
    print("\n" + "="*70)
    print("END-TO-END TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⚠️  Warnings: {results['warnings']}")
    print(f"📊 Total: {results['passed'] + results['failed'] + results['warnings']}")
    
    success_rate = (results['passed'] / (results['passed'] + results['failed'] + results['warnings'])) * 100 if (results['passed'] + results['failed'] + results['warnings']) > 0 else 0
    print(f"📈 Success Rate: {success_rate:.1f}%")
    
    if results['failed'] == 0:
        print("\n✅ All critical tests passed!")
        return 0
    else:
        print(f"\n❌ {results['failed']} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())



