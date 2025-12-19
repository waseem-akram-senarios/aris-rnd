#!/usr/bin/env python3
"""
Test script to diagnose image OCR extraction issues.
"""
import requests
import sys
import json

API_BASE = "http://44.221.84.58:8500"
DOC_ID = "b0b01b35-ccbb-4e52-9db6-2690e531289b"

def test_image_extraction():
    """Test image extraction with diagnostics."""
    print("="*80)
    print("IMAGE OCR EXTRACTION DIAGNOSTICS")
    print("="*80)
    
    # Step 1: Check document status
    print("\n📋 Step 1: Checking document status...")
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code == 200:
            docs = response.json().get('documents', [])
            doc = next((d for d in docs if d.get('document_id') == DOC_ID), None)
            if doc:
                print(f"   ✅ Document found: {doc.get('document_name')}")
                print(f"   - Images detected: {doc.get('images_detected', False)}")
                print(f"   - Image count: {doc.get('image_count', 0)}")
                print(f"   - Images stored: {doc.get('images_stored', 0)}")
                print(f"   - Storage status: {doc.get('images_storage_status', 'unknown')}")
            else:
                print(f"   ❌ Document {DOC_ID} not found")
                return
        else:
            print(f"   ❌ Error getting documents: {response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Step 2: Check current images
    print("\n📋 Step 2: Checking stored images...")
    try:
        response = requests.get(f"{API_BASE}/documents/{DOC_ID}/images/all?limit=10", timeout=60)
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            print(f"   Total images stored: {total}")
            if total == 0:
                print("   ⚠️  No images stored - need to extract and store")
            else:
                print(f"   ✅ {total} images already stored")
        else:
            print(f"   ⚠️  Error: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Step 3: Test page 4
    print("\n📋 Step 3: Testing page 4 retrieval...")
    try:
        response = requests.get(f"{API_BASE}/documents/{DOC_ID}/pages/4", timeout=60)
        if response.status_code == 200:
            data = response.json()
            print(f"   Total images on page 4: {data.get('total_images', 0)}")
            print(f"   Total OCR text length: {data.get('total_ocr_text_length', 0)}")
            if data.get('images'):
                print(f"   ✅ Found {len(data['images'])} images with OCR")
                for img in data['images'][:3]:  # Show first 3
                    print(f"      - Image {img.get('image_number')}: {len(img.get('ocr_text', ''))} chars")
            else:
                print("   ❌ No images found on page 4")
        else:
            print(f"   ⚠️  Error: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n" + "="*80)
    print("DIAGNOSIS COMPLETE")
    print("="*80)
    print("\n💡 Next Steps:")
    print("   1. If images_stored = 0, upload PDF file to /store/images endpoint")
    print("   2. Check server logs for detailed OCR extraction diagnostics")
    print("   3. Verify Docling OCR models are installed: docling download-models")
    print("   4. If extraction fails, the endpoint will now create fallback entries from text")

if __name__ == "__main__":
    test_image_extraction()
