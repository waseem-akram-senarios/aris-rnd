import httpx
import time
import os
import sys

GATEWAY_URL = "http://localhost:8500"
INGESTION_URL = "http://localhost:8501"
RETRIEVAL_URL = "http://localhost:8502"

# Create dummy file if it doesn't exist
if not os.path.exists("test_doc.txt"):
    with open("test_doc.txt", "w") as f:
        f.write("This is a test document for ARIS microservices verification. The secret code is ARIS-2026-FIXED.")

def test_health():
    print("--- [Health Checks] ---")
    for name, url in [("Gateway", GATEWAY_URL), ("Ingestion", INGESTION_URL), ("Retrieval", RETRIEVAL_URL)]:
        try:
            resp = httpx.get(f"{url}/health", timeout=10.0)
            print(f"{name}: {resp.status_code} - {resp.json()}")
        except Exception as e:
            print(f"{name}: FAILED - {e}")

def test_upload():
    print("\n--- [Document Upload] ---")
    with open("test_doc.txt", "rb") as f:
        files = {"file": ("test_doc.txt", f)}
        try:
            resp = httpx.post(f"{GATEWAY_URL}/documents", files=files, timeout=30.0)
            print(f"Status: {resp.status_code}")
            print(f"Result: {resp.json()}")
            return resp.json().get("document_id")
        except Exception as e:
            print(f"Upload FAILED: {e}")
            return None

def test_query():
    print("\n--- [RAG Query] ---")
    payload = {
        "question": "What is the secret code in the test document?",
        "k": 3
    }
    try:
        resp = httpx.post(f"{GATEWAY_URL}/query", json=payload, timeout=60.0)
        print(f"Status: {resp.status_code}")
        print(f"Answer: {resp.json().get('answer')}")
        print(f"Sources: {resp.json().get('sources')}")
    except Exception as e:
        print(f"Query FAILED: {e}")

if __name__ == "__main__":
    test_health()
    doc_id = test_upload()
    if doc_id:
        print("\nWaiting for background processing (10s)...")
        time.sleep(10)
        test_query()
    else:
        print("Skipping query due to upload failure.")
