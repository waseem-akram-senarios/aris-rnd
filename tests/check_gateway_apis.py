import requests
import json
import time

GATEWAY_URL = "http://44.221.84.58:8500"

def check_endpoint(name, method, path, data=None):
    url = f"{GATEWAY_URL}{path}"
    print(f"Testing {name}: {method} {url}...")
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        
        status = response.status_code
        print(f"  [Status: {status}]")
        if status == 200:
            print(f"  [OK]")
            # Truncated output
            content = response.json()
            print(f"  [Data: {str(content)[:100]}...]")
            return True
        else:
            print(f"  [FAILED: {status}] {response.text}")
            return False
    except Exception as e:
        print(f"  [ERROR: {str(e)}]")
        return False

def main():
    endpoints = [
        ("Root", "GET", "/"),
        ("Health", "GET", "/health"),
        ("List Documents", "GET", "/documents"),
        ("System Stats", "GET", "/stats"),
        ("Chunk Stats", "GET", "/stats/chunks"),
        ("Sync Status", "GET", "/sync/status"),
    ]
    
    results = []
    for name, method, path in endpoints:
        results.append(check_endpoint(name, method, path))
    
    # Try one more: Query if documents exist
    try:
        response = requests.get(f"{GATEWAY_URL}/documents")
        docs = response.json()
        if docs and len(docs) > 0:
            doc_id = docs[0]['document_id']
            print(f"Found document {doc_id}, testing Get Document...")
            results.append(check_endpoint("Get Document", "GET", f"/documents/{doc_id}"))
            
            # Simple query test
            query_data = {
                "question": "What is this document about?",
                "search_mode": "hybrid"
            }
            results.append(check_endpoint("Query RAG", "POST", "/query/rag", query_data))
    except:
        pass

    success_count = sum(1 for r in results if r)
    print(f"\nSummary: {success_count}/{len(results)} endpoints verified.")

if __name__ == "__main__":
    main()
