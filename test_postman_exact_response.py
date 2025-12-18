#!/usr/bin/env python3
"""
Show exact response format that Postman should receive
"""
import requests
import json

API_BASE_URL = "http://44.221.84.58:8500"

print("="*70)
print("EXACT POSTMAN RESPONSE FORMAT")
print("="*70)

# Test Query
print("\n📋 Query Request:")
print("POST /query")
print("Body: {\"question\": \"What is this document about?\", \"k\": 5}")

response = requests.post(
    f"{API_BASE_URL}/query",
    json={
        "question": "What is this document about?",
        "k": 5
    },
    timeout=120
)

print(f"\n📊 Response Status: {response.status_code}")
print(f"📄 Response Headers: {dict(response.headers)}")

if response.status_code == 200:
    data = response.json()
    
    print("\n" + "="*70)
    print("COMPLETE RESPONSE (as Postman should see it):")
    print("="*70)
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    print("\n" + "="*70)
    print("FIELD VERIFICATION:")
    print("="*70)
    
    # Check each field
    fields_to_check = [
        ("answer", str, "Should be a string"),
        ("sources", list, "Should be a list of strings"),
        ("citations", list, "Should be a list of citation objects"),
        ("num_chunks_used", int, "Should be an integer"),
        ("response_time", (int, float), "Should be a number"),
        ("context_tokens", int, "Should be an integer"),
        ("response_tokens", int, "Should be an integer"),
        ("total_tokens", int, "Should be an integer"),
    ]
    
    for field, expected_type, description in fields_to_check:
        value = data.get(field)
        is_correct_type = isinstance(value, expected_type) if not isinstance(expected_type, tuple) else isinstance(value, expected_type)
        is_null = value is None
        
        status = "✅" if (is_correct_type and not is_null) else "❌"
        print(f"{status} {field}: {type(value).__name__} = {value if not isinstance(value, (list, dict)) else f'{len(value)} items'}")
        if is_null:
            print(f"   ⚠️  WARNING: {field} is NULL!")
        elif not is_correct_type:
            print(f"   ⚠️  WARNING: {field} has wrong type (expected {expected_type})")
    
    # Check citations
    if data.get('citations'):
        print(f"\n📑 Citation Fields (first citation):")
        cit = data['citations'][0]
        citation_fields = [
            ("id", int),
            ("source", str),
            ("page", (int, type(None))),
            ("snippet", str),
            ("full_text", str),
            ("source_location", str),
            ("content_type", str),
            ("image_ref", (dict, type(None))),
            ("image_info", (str, type(None))),
        ]
        
        for field, expected_type in citation_fields:
            value = cit.get(field)
            is_correct_type = isinstance(value, expected_type) if not isinstance(expected_type, tuple) else any(isinstance(value, t) for t in expected_type)
            is_null = value is None
            
            status = "✅" if (is_correct_type) else "❌"
            null_note = " (NULL is OK for optional fields)" if is_null and field in ['image_ref', 'image_info', 'page'] else ""
            print(f"{status} {field}: {type(value).__name__} = {str(value)[:50] if value is not None else 'null'}{null_note}")
else:
    print(f"\n❌ ERROR: {response.status_code}")
    print(response.text)

# Test Image Query
print("\n\n" + "="*70)
print("IMAGE QUERY RESPONSE")
print("="*70)

response = requests.post(
    f"{API_BASE_URL}/query/images",
    json={
        "question": "",
        "source": "FL10.11 SPECIFIC8 (1).pdf",
        "k": 3
    },
    timeout=60
)

if response.status_code == 200:
    data = response.json()
    print(f"\n📊 Response Status: {response.status_code}")
    print(f"\n📄 Complete Response:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    print(f"\n✅ Fields:")
    print(f"  - total: {data.get('total')} ({type(data.get('total')).__name__})")
    print(f"  - images: {len(data.get('images', []))} items")
    
    if data.get('images'):
        img = data['images'][0]
        print(f"\n📷 First Image Fields:")
        for key, value in img.items():
            print(f"  - {key}: {type(value).__name__} = {str(value)[:100] if not isinstance(value, dict) else 'dict'}")
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)

