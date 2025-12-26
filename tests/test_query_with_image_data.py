#!/usr/bin/env python3
"""
Test query endpoint to verify image data is returned
"""
import os
import sys
import requests
import json

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')

def test_query_with_image_question():
    """Test query with image-related question"""
    print("\n" + "="*70)
    print("Testing Query Endpoint with Image Questions")
    print("="*70)
    
    # Test 1: Query about tools/parts (should return image data)
    print("\n📋 Test 1: Query about tools/parts")
    print("   Question: 'What tools are in drawer 1?'")
    
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={
            "question": "What tools are in drawer 1?",
            "k": 10,
            "document_id": None  # Query all documents
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Status: 200")
        print(f"   Answer length: {len(data.get('answer', ''))} chars")
        print(f"   Sources: {len(data.get('sources', []))}")
        print(f"   Citations: {len(data.get('citations', []))}")
        
        # Check if citations have image info
        citations = data.get('citations', [])
        image_citations = [c for c in citations if c.get('image_ref') or c.get('content_type') == 'image']
        print(f"   Citations with images: {len(image_citations)}")
        
        if image_citations:
            print(f"\n   ✅ Found {len(image_citations)} citations with image references!")
            for i, cit in enumerate(image_citations[:3], 1):
                print(f"\n   Image Citation {i}:")
                print(f"   - Source: {cit.get('source')}")
                print(f"   - Page: {cit.get('page')}")
                print(f"   - Image Info: {cit.get('image_info')}")
                print(f"   - Content Type: {cit.get('content_type')}")
                print(f"   - Snippet (first 200 chars): {cit.get('snippet', '')[:200]}...")
        else:
            print(f"   ⚠️  No citations with image references found")
        
        # Check answer for image content
        answer = data.get('answer', '')
        if 'drawer' in answer.lower() or 'tool' in answer.lower() or 'part' in answer.lower():
            print(f"\n   ✅ Answer mentions tools/drawers/parts")
        else:
            print(f"\n   ⚠️  Answer doesn't mention tools/drawers/parts")
        
        return data
    else:
        print(f"   ❌ Status: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return None

def test_query_specific_document():
    """Test query with specific document"""
    print("\n📋 Test 2: Query specific document with images")
    print("   Question: 'What is in the tool reorder sheet?'")
    
    # Get document ID
    response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
    if response.status_code == 200:
        docs = response.json().get('documents', [])
        doc_with_images = next((d for d in docs if d.get('image_count', 0) > 0), None)
        
        if doc_with_images:
            doc_id = doc_with_images.get('document_id')
            doc_name = doc_with_images.get('document_name')
            print(f"   Using document: {doc_name} (ID: {doc_id})")
            
            response = requests.post(
                f"{API_BASE_URL}/query",
                json={
                    "question": "What is in the tool reorder sheet?",
                    "k": 10,
                    "document_id": doc_id
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status: 200")
                print(f"   Answer length: {len(data.get('answer', ''))} chars")
                
                citations = data.get('citations', [])
                print(f"   Citations: {len(citations)}")
                
                # Check for image content in citations
                image_citations = [c for c in citations if c.get('image_ref') or c.get('content_type') == 'image']
                print(f"   Citations with images: {len(image_citations)}")
                
                if image_citations:
                    print(f"\n   ✅ Found image citations!")
                    for i, cit in enumerate(image_citations[:2], 1):
                        print(f"\n   Image Citation {i}:")
                        print(f"   - Source: {cit.get('source')}")
                        print(f"   - Image Info: {cit.get('image_info')}")
                        print(f"   - Snippet: {cit.get('snippet', '')[:300]}...")
                
                return data
            else:
                print(f"   ❌ Status: {response.status_code}")
        else:
            print(f"   ⚠️  No document with images found")
    else:
        print(f"   ❌ Failed to get documents")

if __name__ == "__main__":
    test_query_with_image_question()
    test_query_specific_document()



