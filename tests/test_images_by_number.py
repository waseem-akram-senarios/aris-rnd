#!/usr/bin/env python3
"""
Test script for Images by Number endpoints
"""
import requests
import json
import sys

API_BASE = "http://44.221.84.58:8500"

def test_images_summary(doc_id):
    """Test GET /documents/{id}/images"""
    print("\n" + "="*80)
    print("Test 1: Get All Images Summary")
    print("="*80)
    
    url = f"{API_BASE}/documents/{doc_id}/images"
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS")
            print(f"Document: {data.get('document_name')}")
            print(f"Total Images: {data.get('total_images')}")
            print(f"\nFirst 3 Images:")
            for img in data.get('images', [])[:3]:
                print(f"  Image {img['image_number']} (Page {img.get('page', 'N/A')}):")
                print(f"    OCR Length: {img['ocr_text_length']} chars")
                print(f"    OCR Preview: {img['ocr_text'][:100]}...")
            return True
        elif response.status_code == 404:
            print("⚠️  NOT FOUND - Endpoint may need deployment")
            return False
        else:
            print(f"❌ Error: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_image_by_number(doc_id, image_number=0):
    """Test GET /documents/{id}/images/{number}"""
    print("\n" + "="*80)
    print(f"Test 2: Get Image by Number ({image_number})")
    print("="*80)
    
    url = f"{API_BASE}/documents/{doc_id}/images/{image_number}"
    print(f"URL: {url}")
    
    try:
        response = requests.get(url, timeout=60)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ SUCCESS")
            print(f"Image Number: {data.get('image_number')}")
            print(f"Page: {data.get('page', 'N/A')}")
            print(f"OCR Length: {data.get('ocr_text_length')} chars")
            print(f"\nOCR Text:")
            print(f"{data.get('ocr_text', '')[:500]}...")
            if data.get('metadata'):
                print(f"\nMetadata Keys: {list(data['metadata'].keys())[:5]}")
            return True
        elif response.status_code == 404:
            print(f"⚠️  NOT FOUND - Image number {image_number} may not exist")
            print(f"Response: {response.text[:200]}")
            return False
        else:
            print(f"❌ Error: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    """Run tests"""
    print("="*80)
    print("IMAGES BY NUMBER ENDPOINT TESTING")
    print("="*80)
    
    # Get document ID
    print("\n📋 Getting documents...")
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code == 200:
            docs = response.json().get('documents', [])
            if not docs:
                print("❌ No documents found. Upload a document first.")
                return 1
            
            # Try to find document with ID
            doc_id = None
            for doc in docs:
                doc_id = doc.get('document_id') or doc.get('id') or doc.get('_id')
                if doc_id:
                    break
            
            if not doc_id:
                print("⚠️  No document_id found in response.")
                print("   Using first document name as identifier...")
                doc_name = docs[0].get('document_name', '')
                if doc_name:
                    # Try using document name
                    doc_id = doc_name
                    print(f"   Using: {doc_id}")
                else:
                    print("❌ Cannot determine document identifier")
                    return 1
            else:
                print(f"✅ Found Document ID: {doc_id}")
        else:
            print(f"❌ Failed to get documents: {response.status_code}")
            return 1
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
        return 1
    
    # Run tests
    results = []
    
    # Test 1: Summary
    results.append(("Images Summary", test_images_summary(doc_id)))
    
    # Test 2: Specific image
    results.append(("Image by Number (0)", test_image_by_number(doc_id, 0)))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {name}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed < total:
        print("\n⚠️  Some tests failed. This may be because:")
        print("   1. Endpoints need deployment")
        print("   2. Document has no images")
        print("   3. Image number doesn't exist")
        print("\nDeploy: ./scripts/deploy-api-updates.sh")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
