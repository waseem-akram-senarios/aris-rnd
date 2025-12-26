#!/usr/bin/env python3
"""
Complete endpoint verification with PDF upload test
"""
import os
import sys
import requests
import json

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def test_endpoint(name, method, url, **kwargs):
    """Test endpoint and return result"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}")
    print(f"{method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        
        print(f"Status: {response.status_code}")
        
        try:
            data = response.json()
            print(f"Response:\n{json.dumps(data, indent=2)}")
            return {"status": response.status_code, "success": response.status_code < 400, "data": data}
        except:
            print(f"Response: {response.text}")
            return {"status": response.status_code, "success": response.status_code < 400, "text": response.text}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"error": str(e), "success": False}

def main():
    print("\n" + "="*70)
    print("COMPLETE ENDPOINT VERIFICATION")
    print("="*70)
    print(f"Server: {API_BASE_URL}\n")
    
    results = {}
    
    # 1. Health
    results['health'] = test_endpoint("GET /health", "GET", f"{API_BASE_URL}/health")
    
    # 2. Root
    results['root'] = test_endpoint("GET /", "GET", f"{API_BASE_URL}/")
    
    # 3. List Documents
    results['list'] = test_endpoint("GET /documents", "GET", f"{API_BASE_URL}/documents")
    
    # 4. Upload PDF if available
    pdf_path = None
    for path in ["./FL10.11 SPECIFIC8 (1).pdf", "./test.pdf", "./sample.pdf"]:
        if os.path.exists(path):
            pdf_path = path
            break
    
    if pdf_path:
        print(f"\n{'='*70}")
        print(f"Uploading PDF: {pdf_path}")
        print(f"{'='*70}")
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
                data = {'parser': 'docling'}
                response = requests.post(
                    f"{API_BASE_URL}/documents",
                    files=files,
                    data=data,
                    timeout=TEST_TIMEOUT
                )
            
            print(f"Status: {response.status_code}")
            if response.status_code == 201:
                upload_data = response.json()
                print(f"Response:\n{json.dumps(upload_data, indent=2)}")
                doc_id = upload_data.get('document_id')
                results['upload'] = {"status": 201, "success": True, "data": upload_data, "doc_id": doc_id}
                
                # Wait a bit for processing
                import time
                print("\n⏳ Waiting 5 seconds for document processing...")
                time.sleep(5)
                
                # 5. Query after upload
                results['query_after_upload'] = test_endpoint(
                    "POST /query (after upload)",
                    "POST",
                    f"{API_BASE_URL}/query",
                    json={"question": "What is this document about?", "k": 3}
                )
            else:
                print(f"Response: {response.text}")
                results['upload'] = {"status": response.status_code, "success": False, "data": response.text}
        except Exception as e:
            print(f"❌ Error: {e}")
            results['upload'] = {"error": str(e), "success": False}
    else:
        print("\n⚠️  No PDF file found for upload test")
        results['upload'] = {"skipped": True}
    
    # 6. Query Images
    results['query_images'] = test_endpoint(
        "POST /query/images",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={"question": "test", "k": 5}
    )
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for r in results.values() if r.get('success'))
    failed = sum(1 for r in results.values() if r.get('success') == False and not r.get('skipped'))
    skipped = sum(1 for r in results.values() if r.get('skipped'))
    
    for name, result in results.items():
        if result.get('skipped'):
            print(f"⏭️  {name}: SKIPPED")
        elif result.get('success'):
            print(f"✅ {name}: PASSED (Status: {result.get('status')})")
        else:
            print(f"❌ {name}: FAILED")
            if result.get('error'):
                print(f"   Error: {result['error']}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    # Save results
    with open('COMPLETE_ENDPOINT_VERIFICATION.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())



