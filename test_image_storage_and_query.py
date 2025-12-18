#!/usr/bin/env python3
"""
Test image storage and query to debug the issue
"""
import os
import sys
import requests
import json

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')

def main():
    print("\n" + "="*70)
    print("Image Storage and Query Debug")
    print("="*70)
    
    # 1. Upload a document with images
    print("\n📤 Step 1: Uploading document with images...")
    pdf_path = "./FL10.11 SPECIFIC8 (1).pdf"
    if not os.path.exists(pdf_path):
        print(f"❌ PDF not found: {pdf_path}")
        return
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=300
            )
        
        if response.status_code == 201:
            upload_data = response.json()
            doc_id = upload_data.get('document_id')
            doc_name = upload_data.get('document_name')
            image_count = upload_data.get('image_count', 0)
            
            print(f"✅ Document uploaded")
            print(f"   Document ID: {doc_id}")
            print(f"   Document Name: {doc_name}")
            print(f"   Images Detected: {image_count}")
            
            if image_count == 0:
                print("⚠️  No images detected in document!")
                return
            
            # Wait for processing
            import time
            print(f"\n⏳ Waiting 10 seconds for image storage...")
            time.sleep(10)
            
            # 2. Try to query images
            print(f"\n🔍 Step 2: Querying images...")
            
            # Try different source formats
            source_variants = [
                doc_name,
                os.path.basename(doc_name),
                doc_name.lower(),
                os.path.basename(doc_name).lower(),
            ]
            
            for source in source_variants:
                print(f"\n   Trying source: '{source}'")
                response = requests.post(
                    f"{API_BASE_URL}/query/images",
                    json={
                        "question": "",
                        "source": source,
                        "k": 20
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    total = data.get('total', 0)
                    print(f"   Status: 200, Images found: {total}")
                    
                    if total > 0:
                        print(f"   ✅ SUCCESS! Found {total} images")
                        images = data.get('images', [])
                        if images:
                            print(f"\n   First image details:")
                            img = images[0]
                            print(f"   - Image ID: {img.get('image_id')}")
                            print(f"   - Source: {img.get('source')}")
                            print(f"   - Image Number: {img.get('image_number')}")
                            print(f"   - OCR Text (first 300 chars):")
                            print(f"     {img.get('ocr_text', '')[:300]}")
                        return True
                else:
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
            
            print("\n❌ No images found with any source variant")
            print("\n🔍 Step 3: Checking if images are in OpenSearch...")
            
            # Try semantic search without source filter
            response = requests.post(
                f"{API_BASE_URL}/query/images",
                json={
                    "question": "drawer tool part number",
                    "k": 20
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                print(f"   Semantic search (no source filter): {total} images found")
                
                if total > 0:
                    print(f"   ✅ Images exist in OpenSearch!")
                    images = data.get('images', [])
                    if images:
                        print(f"\n   Sample image sources:")
                        for img in images[:5]:
                            print(f"   - {img.get('source')} (image {img.get('image_number')})")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

