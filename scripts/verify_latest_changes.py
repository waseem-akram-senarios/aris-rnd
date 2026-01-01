import requests
import time
import json
import sys

BASE_URL = "http://44.221.84.58:8000"

def test_health():
    print("🔍 Testing Microservices Health...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Gateway: {response.json()}")
        
        # Check ingestion via gateway redirect or direct if needed
        # But gateway healthy usually means registry is accessible.
    except Exception as e:
        print(f"❌ Health Check Failed: {e}")

def test_ingestion(file_path):
    print(f"📤 Testing Ingestion for: {file_path}")
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{BASE_URL}/ingest", files=files)
            
        if response.status_code == 200:
            job = response.json()
            doc_id = job.get('document_id')
            print(f"✅ Ingestion started: {doc_id}")
            
            # Poll for status
            while True:
                status_resp = requests.get(f"{BASE_URL}/ingest/status/{doc_id}")
                status = status_resp.json()
                print(f"⏳ Status: {status.get('status')} | Progress: {status.get('progress')*100:.1f}% | {status.get('detailed_message')}")
                
                if status.get('status') == 'success':
                    print("🎉 Ingestion SUCCESS!")
                    print(f"📝 Metadata: {json.dumps(status.get('metadata', {}), indent=2)}")
                    return doc_id
                elif status.get('status') == 'failed':
                    print(f"❌ Ingestion FAILED: {status.get('error')}")
                    return None
                
                time.sleep(2)
        else:
            print(f"❌ Ingestion Request Failed: {response.text}")
    except Exception as e:
        print(f"❌ Ingestion Error: {e}")
    return None

def test_query(doc_id, question):
    print(f"❓ Testing Query: '{question}'")
    try:
        payload = {
            "query": question,
            "active_sources": [doc_id] if doc_id else None,
            "stream": False
        }
        response = requests.post(f"{BASE_URL}/query", json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Answer: {result.get('answer')[:200]}...")
            print("📜 Citations:")
            for cit in result.get('citations', []):
                print(f"   - [{cit.get('source')}] Page {cit.get('page')} | S3: {cit.get('s3_url')}")
                if cit.get('s3_preview_url'):
                    print(f"     🔗 Preview: {cit.get('s3_preview_url')[:50]}...")
        else:
            print(f"❌ Query Failed: {response.text}")
    except Exception as e:
        print(f"❌ Query Error: {e}")

if __name__ == "__main__":
    test_health()
    # Use a small test file if possible, or try the audi one if already on server
    # For local test, we need a file.
    test_file = "temp-archive/test_upload.txt"
    with open(test_file, 'w') as f:
        f.write("This is a test document for ARIS S3 integration verification. " * 100)
    
    doc_id = test_ingestion(test_file)
    if doc_id:
        test_query(doc_id, "What is this document about?")
