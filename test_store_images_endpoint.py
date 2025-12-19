#!/usr/bin/env python3
"""
Test script for /store/images endpoint
Tests both with and without file upload
"""
import requests
import json
import sys
import os
from pathlib import Path

API_BASE = "http://44.221.84.58:8500"

def test_without_file(doc_id):
    """Test endpoint without file upload"""
    print("\n" + "="*80)
    print("TEST 1: Store Images Without File Upload (Check Existing)")
    print("="*80)
    
    url = f"{API_BASE}/documents/{doc_id}/store/images"
    print(f"URL: {url}")
    print("Method: POST (no file)")
    
    try:
        response = requests.post(url, timeout=60)
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS - Images already stored")
            print(f"   Images Stored: {data.get('images_stored', 0)}")
            print(f"   Total OCR Length: {data.get('total_ocr_text_length', 0):,} chars")
            print(f"   Status: {data.get('status')}")
            print(f"   Reprocessed: {data.get('reprocessed', False)}")
            return True
        elif response.status_code == 404:
            error = response.json()
            print("⚠️  Images not stored yet")
            print(f"   Error: {error.get('detail', 'Unknown error')}")
            return False
        else:
            print(f"❌ Unexpected status code")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def test_with_file(doc_id, pdf_path):
    """Test endpoint with file upload"""
    print("\n" + "="*80)
    print("TEST 2: Store Images With File Upload (Re-process)")
    print("="*80)
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF file not found: {pdf_path}")
        return False
    
    url = f"{API_BASE}/documents/{doc_id}/store/images"
    print(f"URL: {url}")
    print(f"File: {pdf_path}")
    print("Method: POST (with file upload)")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            print("Uploading file and processing...")
            response = requests.post(url, files=files, timeout=300)
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ SUCCESS - Document re-processed and images stored")
            print(f"   Images Stored: {data.get('images_stored', 0)}")
            print(f"   Total OCR Length: {data.get('total_ocr_text_length', 0):,} chars")
            print(f"   Status: {data.get('status')}")
            print(f"   Reprocessed: {data.get('reprocessed', False)}")
            print(f"   Extraction Method: {data.get('extraction_method', 'N/A')}")
            print(f"   Message: {data.get('message', '')[:100]}")
            return True
        else:
            error = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            print(f"❌ Error: {error}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_images_stored(doc_id):
    """Verify images are accessible after storage"""
    print("\n" + "="*80)
    print("TEST 3: Verify Images Are Stored and Accessible")
    print("="*80)
    
    try:
        # Get all images
        url = f"{API_BASE}/documents/{doc_id}/images/all?limit=10"
        response = requests.get(url, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            images_with_ocr = data.get('images_with_ocr', 0)
            
            print(f"✅ Images accessible")
            print(f"   Total Images: {total}")
            print(f"   Images with OCR: {images_with_ocr}")
            
            if total > 0:
                # Try to get images from page 1
                page_url = f"{API_BASE}/documents/{doc_id}/pages/1"
                page_response = requests.get(page_url, timeout=60)
                
                if page_response.status_code == 200:
                    page_data = page_response.json()
                    page_images = page_data.get('total_images', 0)
                    print(f"   Images on Page 1: {page_images}")
                
                return True
            else:
                print("⚠️  No images found in storage")
                return False
        else:
            print(f"❌ Error getting images: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    """Run all tests"""
    print("="*80)
    print("STORE IMAGES ENDPOINT TESTING")
    print("="*80)
    
    # Get document ID
    print("\n📋 Getting document ID...")
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code == 200:
            docs = response.json().get('documents', [])
            if not docs:
                print("❌ No documents found")
                return 1
            
            # Find document with images detected
            doc_id = None
            doc_name = None
            for doc in docs:
                if doc.get('images_detected') and doc.get('image_count', 0) > 0:
                    doc_id = doc.get('document_id')
                    doc_name = doc.get('document_name')
                    if doc_id:
                        break
            
            if not doc_id:
                print("⚠️  No document with images found")
                # Use first document anyway
                doc_id = docs[0].get('document_id') or docs[0].get('document_name', '')
                doc_name = docs[0].get('document_name', '')
            
            print(f"✅ Using Document ID: {doc_id}")
            print(f"   Document Name: {doc_name}")
        else:
            print(f"❌ Failed to get documents: {response.status_code}")
            return 1
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
        return 1
    
    # Find PDF file
    pdf_file = None
    if doc_name:
        # Try to find PDF file
        for ext in ['.pdf', '.PDF']:
            potential_file = doc_name.replace(' ', '_')
            if os.path.exists(potential_file):
                pdf_file = potential_file
                break
        
        # Try common locations
        if not pdf_file:
            for path in ['.', '..', '../..']:
                for file in Path(path).glob('*.pdf'):
                    if doc_name.lower() in file.name.lower() or file.name.lower() in doc_name.lower():
                        pdf_file = str(file)
                        break
                if pdf_file:
                    break
    
    if not pdf_file:
        print(f"\n⚠️  PDF file not found for: {doc_name}")
        print("   Will test without file upload only")
        pdf_file = None
    
    # Run tests
    results = []
    
    # Test 1: Without file
    results.append(("Without File Upload", test_without_file(doc_id)))
    
    # Test 2: With file (if available)
    if pdf_file:
        results.append(("With File Upload", test_with_file(doc_id, pdf_file)))
        
        # Test 3: Verify storage
        if results[-1][1]:  # If file upload succeeded
            results.append(("Verify Images Stored", verify_images_stored(doc_id)))
    else:
        print("\n⚠️  Skipping file upload test (PDF file not found)")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        icon = "✅" if result else "❌"
        print(f"{icon} {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
