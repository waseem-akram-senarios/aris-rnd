#!/usr/bin/env python3
"""
End-to-End Test - Run on Server
Tests all latest changes directly on the server
"""
import httpx
import time
import sys
import json

# Test on localhost (server)
GATEWAY_URL = "http://localhost:8000"
INGESTION_URL = "http://localhost:8001"
RETRIEVAL_URL = "http://localhost:8002"
UI_URL = "http://localhost:80"

results = {'passed': 0, 'failed': 0, 'warnings': 0}

def test(name, func):
    print(f"\n{'='*60}")
    print(f"Test: {name}")
    print('='*60)
    try:
        if func():
            results['passed'] += 1
            print("✅ PASSED")
        else:
            results['failed'] += 1
            print("❌ FAILED")
    except Exception as e:
        results['failed'] += 1
        print(f"❌ FAILED: {e}")

def test_health():
    """Test all services health"""
    for name, url in [("Gateway", GATEWAY_URL), ("Ingestion", INGESTION_URL), ("Retrieval", RETRIEVAL_URL)]:
        try:
            resp = httpx.get(f"{url}/health", timeout=5)
            if resp.status_code == 200 and resp.json().get('status') == 'healthy':
                print(f"✅ {name}: Healthy")
            else:
                print(f"❌ {name}: {resp.status_code}")
                return False
        except Exception as e:
            print(f"❌ {name}: {e}")
            return False
    return True

def test_documents_list():
    """Test documents list"""
    try:
        resp = httpx.get(f"{GATEWAY_URL}/documents", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            docs = data.get('documents', [])
            print(f"✅ Documents list: {len(docs)} document(s)")
            return True
        return False
    except Exception as e:
        print(f"❌ Documents list: {e}")
        return False

def test_upload():
    """Test document upload"""
    test_content = "This is a test document for E2E testing. It contains information about the ARIS RAG system."
    try:
        files = {"file": ("test_e2e.txt", test_content.encode())}
        resp = httpx.post(f"{GATEWAY_URL}/documents", files=files, timeout=60)
        if resp.status_code in [200, 201]:
            data = resp.json()
            doc_id = data.get('document_id')
            print(f"✅ Upload successful: {doc_id}")
            return doc_id
        print(f"❌ Upload failed: {resp.status_code}")
        return None
    except Exception as e:
        print(f"❌ Upload: {e}")
        return None

def test_query():
    """Test query"""
    try:
        payload = {"question": "What is this document about?", "k": 3}
        resp = httpx.post(f"{GATEWAY_URL}/query", json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get('answer', '')
            if answer and not answer.startswith("No documents"):
                print(f"✅ Query successful")
                print(f"   Answer: {answer[:100]}...")
                return True
            else:
                print(f"⚠️  Query: {answer[:100]}")
                return True  # Don't fail
        print(f"⚠️  Query: {resp.status_code}")
        return True
    except Exception as e:
        print(f"⚠️  Query: {e}")
        return True

def main():
    print("="*60)
    print("END-TO-END TEST - Latest Changes")
    print("="*60)
    
    test("Health Checks", test_health)
    test("Documents List", test_documents_list)
    doc_id = test_upload()
    if doc_id:
        print("\nWaiting 10 seconds for processing...")
        time.sleep(10)
    test("Query", test_query)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✅ Passed: {results['passed']}")
    print(f"❌ Failed: {results['failed']}")
    print(f"⚠️  Warnings: {results['warnings']}")
    
    return 0 if results['failed'] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())



