#!/usr/bin/env python3
"""
Example script showing how to query images from the API
"""
import requests
import json

API_BASE_URL = "http://44.221.84.58:8500"

def example_1_get_all_images():
    """Example 1: Get all images from a document"""
    print("\n" + "="*70)
    print("Example 1: Get All Images from a Document")
    print("="*70)
    
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "",
            "source": "FL10.11 SPECIFIC8 (1).pdf",
            "k": 20
        },
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Found {data['total']} images")
        
        for i, img in enumerate(data['images'][:3], 1):  # Show first 3
            print(f"\n  Image {i}:")
            print(f"    ID: {img['image_id']}")
            print(f"    Source: {img['source']}")
            print(f"    Image Number: {img['image_number']}")
            print(f"    Page: {img['page']}")
            print(f"    OCR Text (first 200 chars): {img['ocr_text'][:200]}...")
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   {response.text[:200]}")

def example_2_semantic_search():
    """Example 2: Semantic search in images"""
    print("\n" + "="*70)
    print("Example 2: Semantic Search in Images")
    print("="*70)
    
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "drawer tools part numbers",
            "k": 10
        },
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Found {data['total']} matching images")
        
        for i, img in enumerate(data['images'][:3], 1):  # Show first 3
            print(f"\n  Match {i}:")
            print(f"    Source: {img['source']}")
            print(f"    Page: {img['page']}")
            print(f"    Score: {img.get('score', 'N/A')}")
            print(f"    OCR Preview: {img['ocr_text'][:300]}...")
    else:
        print(f"❌ Error: {response.status_code}")

def example_3_search_specific_tool():
    """Example 3: Search for specific tools"""
    print("\n" + "="*70)
    print("Example 3: Search for Specific Tools")
    print("="*70)
    
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "wire stripper socket wrench",
            "k": 5
        },
        timeout=60
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Found {data['total']} images with tools")
        
        for img in data['images']:
            print(f"\n  Tool found in {img['source']}:")
            print(f"    Page: {img['page']}")
            # Check for specific tools in OCR
            ocr_lower = img['ocr_text'].lower()
            tools_found = []
            if 'wire stripper' in ocr_lower:
                tools_found.append('Wire Stripper')
            if 'socket' in ocr_lower:
                tools_found.append('Socket')
            if 'wrench' in ocr_lower:
                tools_found.append('Wrench')
            
            if tools_found:
                print(f"    Tools: {', '.join(tools_found)}")
            print(f"    OCR Preview: {img['ocr_text'][:400]}...")
    else:
        print(f"❌ Error: {response.status_code}")

def example_4_query_via_regular_endpoint():
    """Example 4: Query images via regular query endpoint"""
    print("\n" + "="*70)
    print("Example 4: Query Images via Regular Query Endpoint")
    print("="*70)
    
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={
            "question": "What tools are in drawer 1?",
            "k": 10
        },
        timeout=120
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"\n✅ Query successful")
        print(f"   Answer: {data['answer'][:200]}...")
        print(f"   Citations: {len(data['citations'])}")
        
        # Find citations with images
        image_citations = [c for c in data['citations'] if c.get('image_ref')]
        print(f"   Citations with images: {len(image_citations)}")
        
        if image_citations:
            print(f"\n   Image Citations:")
            for cit in image_citations[:2]:
                print(f"     - {cit['source']}, Page {cit['page']}")
                print(f"       Image Info: {cit.get('image_info')}")
                print(f"       Snippet: {cit['snippet'][:150]}...")
    else:
        print(f"❌ Error: {response.status_code}")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("HOW TO QUERY IMAGES - EXAMPLES")
    print("="*70)
    
    # Run examples
    example_1_get_all_images()
    example_2_semantic_search()
    example_3_search_specific_tool()
    example_4_query_via_regular_endpoint()
    
    print("\n" + "="*70)
    print("✅ All examples completed!")
    print("="*70)



