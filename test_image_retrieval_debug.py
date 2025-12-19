#!/usr/bin/env python3
"""
Debug script to test image retrieval and see what's stored
"""
import os
import sys
import requests
import json

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')

def test_image_query(doc_name):
    """Test image query with different source formats"""
    print(f"\n{'='*70}")
    print(f"Testing Image Query for: {doc_name}")
    print(f"{'='*70}")
    
    # Try different source formats
    source_variants = [
        doc_name,
        os.path.basename(doc_name),
        doc_name.lower(),
        os.path.basename(doc_name).lower(),
    ]
    
    for source in source_variants:
        print(f"\n🔍 Trying source: '{source}'")
        try:
            response = requests.post(
                f"{API_BASE_URL}/query/images",
                json={
                    "question": "",
                    "source": source,
                    "k": 20
                },
                timeout=60
            )
            
            print(f"   Status: {response.status_code}")
            data = response.json()
            total = data.get('total', 0)
            print(f"   Images found: {total}")
            
            if total > 0:
                print(f"   ✅ SUCCESS! Found {total} images with source: '{source}'")
                # Show first image
                if data.get('images'):
                    first_img = data['images'][0]
                    print(f"\n   First image:")
                    print(f"   - Image ID: {first_img.get('image_id')}")
                    print(f"   - Source: {first_img.get('source')}")
                    print(f"   - Image Number: {first_img.get('image_number')}")
                    print(f"   - OCR Text (first 200 chars): {first_img.get('ocr_text', '')[:200]}")
                return True
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    return False

def main():
    print("\n" + "="*70)
    print("Image Retrieval Debug Test")
    print("="*70)
    
    # Get documents
    print("\n📋 Getting document list...")
    response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
    if response.status_code == 200:
        data = response.json()
        documents = data.get('documents', [])
        print(f"   Found {len(documents)} documents")
        
        # Find document with images
        for doc in documents:
            doc_name = doc.get('document_name')
            image_count = doc.get('image_count', 0)
            print(f"\n   Document: {doc_name}")
            print(f"   Images detected: {image_count}")
            
            if image_count > 0:
                print(f"\n   🖼️  Testing image retrieval for: {doc_name}")
                success = test_image_query(doc_name)
                if success:
                    break
    else:
        print(f"   ❌ Failed to get documents: {response.status_code}")

if __name__ == "__main__":
    main()



