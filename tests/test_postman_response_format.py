#!/usr/bin/env python3
"""
Test query endpoint to show exact response format that Postman should receive
"""
import requests
import json

API_BASE_URL = "http://44.221.84.58:8500"

print("="*70)
print("Testing Query Endpoint - Response Format")
print("="*70)

# Test 1: Basic Query
print("\n1. Basic Query:")
print("-" * 70)
response = requests.post(
    f"{API_BASE_URL}/query",
    json={
        "question": "What is this document about?",
        "k": 5
    },
    timeout=120
)

if response.status_code == 200:
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"\nResponse Structure:")
    print(f"  - answer: {type(data.get('answer'))} (length: {len(data.get('answer', ''))})")
    print(f"  - sources: {type(data.get('sources'))} (count: {len(data.get('sources', []))})")
    print(f"  - citations: {type(data.get('citations'))} (count: {len(data.get('citations', []))})")
    print(f"  - num_chunks_used: {data.get('num_chunks_used')}")
    print(f"  - response_time: {data.get('response_time')}")
    print(f"  - context_tokens: {data.get('context_tokens')}")
    print(f"  - response_tokens: {data.get('response_tokens')}")
    print(f"  - total_tokens: {data.get('total_tokens')}")
    
    print(f"\nFirst Citation Structure:")
    if data.get('citations'):
        cit = data.get('citations')[0]
        print(f"  - id: {cit.get('id')} ({type(cit.get('id'))})")
        print(f"  - source: {cit.get('source')} ({type(cit.get('source'))})")
        print(f"  - page: {cit.get('page')} ({type(cit.get('page'))})")
        print(f"  - snippet: {type(cit.get('snippet'))} (length: {len(cit.get('snippet', ''))})")
        print(f"  - full_text: {type(cit.get('full_text'))} (length: {len(cit.get('full_text', ''))})")
        print(f"  - source_location: {cit.get('source_location')} ({type(cit.get('source_location'))})")
        print(f"  - content_type: {cit.get('content_type')} ({type(cit.get('content_type'))})")
        print(f"  - image_ref: {cit.get('image_ref')} ({type(cit.get('image_ref'))})")
        print(f"  - image_info: {cit.get('image_info')} ({type(cit.get('image_info'))})")
    
    print(f"\nFull Response (first 1000 chars):")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])
else:
    print(f"Error: {response.status_code}")
    print(response.text)

# Test 2: Query with document_id
print("\n\n" + "="*70)
print("2. Query with document_id:")
print("-" * 70)

# Get a document_id
docs_response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
if docs_response.status_code == 200:
    docs = docs_response.json().get('documents', [])
    doc_with_id = next((d for d in docs if d.get('document_id')), None)
    
    if doc_with_id:
        doc_id = doc_with_id.get('document_id')
        print(f"Using document_id: {doc_id}")
        
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "question": "What information is in this document?",
                "k": 5,
                "document_id": doc_id
            },
            timeout=120
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {response.status_code}")
            print(f"Answer length: {len(data.get('answer', ''))}")
            print(f"Citations: {len(data.get('citations', []))}")
            print(f"Sources: {data.get('sources', [])}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    else:
        print("No document with ID found")

# Test 3: Image Query
print("\n\n" + "="*70)
print("3. Image Query:")
print("-" * 70)

response = requests.post(
    f"{API_BASE_URL}/query/images",
    json={
        "question": "",
        "source": "FL10.11 SPECIFIC8 (1).pdf",
        "k": 5
    },
    timeout=60
)

if response.status_code == 200:
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Total: {data.get('total')}")
    print(f"Images: {len(data.get('images', []))}")
    
    if data.get('images'):
        img = data.get('images')[0]
        print(f"\nFirst Image Structure:")
        print(f"  - image_id: {img.get('image_id')} ({type(img.get('image_id'))})")
        print(f"  - source: {img.get('source')} ({type(img.get('source'))})")
        print(f"  - image_number: {img.get('image_number')} ({type(img.get('image_number'))})")
        print(f"  - page: {img.get('page')} ({type(img.get('page'))})")
        print(f"  - ocr_text: {type(img.get('ocr_text'))} (length: {len(img.get('ocr_text', ''))})")
        print(f"  - metadata: {type(img.get('metadata'))}")
        print(f"  - score: {img.get('score')} ({type(img.get('score'))})")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

print("\n" + "="*70)
print("✅ Response format verification complete")
print("="*70)



