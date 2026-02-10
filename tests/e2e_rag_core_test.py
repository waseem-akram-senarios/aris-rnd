import requests
import json
import time

BASE_URL = "http://44.221.84.58:8500"
DOC_NAME = "VUORMAR(spa).pdf"

def test_api_feature(name, payload):
    print(f"\n🚀 Testing API Feature: {name}")
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/query", json=payload, timeout=60)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', '')
            citations = result.get('citations', [])
            
            print(f"✅ Success ({duration:.2f}s)")
            print(f"   Answer: {answer[:100]}...")
            print(f"   Citations: {len(citations)}")
            if citations:
                print(f"   Sample Source: {citations[0].get('source')} (Page {citations[0].get('page')})")
            return True
        else:
            print(f"❌ Failed: HTTP {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("🧪 End-to-End Core RAG Feature Testing (API)")
    
    features = [
        {
            "name": "Single Document Retrieval (active_sources)",
            "payload": {
                "question": "What is the contact email?",
                "active_sources": [DOC_NAME],
                "k": 3
            }
        },
        {
            "name": "Global Retrieval (All Documents)",
            "payload": {
                "question": "What is the contact email of Vuormar?",
                "k": 3
            }
        },
        {
            "name": "Cross-Language Accuracy (English query on Spanish doc)",
            "payload": {
                "question": "Tell me about the motor power and contact information.",
                "active_sources": [DOC_NAME],
                "auto_translate": True,
                "k": 5
            }
        }
    ]
    
    all_passed = True
    for feature in features:
        if not test_api_feature(feature['name'], feature['payload']):
            all_passed = False
            
    if all_passed:
        print("\n✨ ALL CORE API FEATURES PASSED ✨")
    else:
        print("\n⚠️ SOME API FEATURES FAILED ⚠️")

if __name__ == "__main__":
    main()
