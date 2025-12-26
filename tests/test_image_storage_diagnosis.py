#!/usr/bin/env python3
"""
Diagnostic script to check image storage configuration and verify images are being stored.
"""
import os
import sys
import requests
import json

BASE_URL = "http://44.221.84.58:8500"

def check_vectorstore_type():
    """Check what vector store type is being used"""
    print("="*80)
    print("1. Checking Vector Store Type")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rag_stats = data.get('rag_stats', {})
            vector_store_type = rag_stats.get('vector_store_type', 'unknown')
            print(f"✅ Vector Store Type: {vector_store_type}")
            
            if vector_store_type.lower() == 'opensearch':
                print("✅ OpenSearch is configured - images should be stored")
                return True
            else:
                print(f"⚠️  Vector store is {vector_store_type} - images are only stored with OpenSearch")
                print("   Images will only be stored at query time, not during ingestion")
                return False
        else:
            print(f"❌ Failed to get stats: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error checking vector store: {e}")
        return None

def check_opensearch_config():
    """Check OpenSearch configuration"""
    print("\n" + "="*80)
    print("2. Checking OpenSearch Configuration")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=10)
        if response.status_code == 200:
            data = response.json()
            rag_stats = data.get('rag_stats', {})
            
            opensearch_domain = rag_stats.get('opensearch_domain', 'Not configured')
            opensearch_index = rag_stats.get('opensearch_index', 'Not configured')
            
            print(f"OpenSearch Domain: {opensearch_domain}")
            print(f"OpenSearch Index: {opensearch_index}")
            
            if opensearch_domain != 'Not configured':
                print("✅ OpenSearch domain is configured")
            else:
                print("⚠️  OpenSearch domain is not configured")
            
            return opensearch_domain != 'Not configured'
        else:
            print(f"❌ Failed to get stats: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking OpenSearch config: {e}")
        return False

def check_image_index():
    """Check if images index exists and has data"""
    print("\n" + "="*80)
    print("3. Checking Image Index Status")
    print("="*80)
    
    # Try to query images to see if index exists
    try:
        response = requests.post(
            f"{BASE_URL}/query/images",
            json={'question': 'test', 'k': 1},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            print(f"✅ Image query endpoint works")
            print(f"   Images in index: {total}")
            
            if total > 0:
                print("✅ Images are stored in the index")
                return True
            else:
                print("⚠️  No images found in index")
                print("   This could mean:")
                print("   - Images haven't been stored yet")
                print("   - Images are stored at query time only")
                print("   - Document processing didn't extract images properly")
                return False
        elif response.status_code == 400:
            error = response.json().get('detail', 'Unknown error')
            print(f"⚠️  Image query failed: {error}")
            if 'OpenSearch' in error:
                print("   This means OpenSearch is not configured for image storage")
            return False
        else:
            print(f"❌ Image query failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error checking image index: {e}")
        return False

def check_document_images(document_id):
    """Check if a specific document has images stored"""
    print("\n" + "="*80)
    print(f"4. Checking Images for Document: {document_id}")
    print("="*80)
    
    try:
        response = requests.get(
            f"{BASE_URL}/documents/{document_id}/images?limit=10",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            total = data.get('total', len(images))
            
            print(f"✅ Document images endpoint works")
            print(f"   Images found: {total}")
            
            if total > 0:
                print("✅ Images are stored for this document")
                print(f"\nFirst image details:")
                if images:
                    img = images[0]
                    print(f"  Image ID: {img.get('image_id')}")
                    print(f"  Image Number: {img.get('image_number')}")
                    print(f"  Page: {img.get('page')}")
                    print(f"  OCR Text Length: {len(img.get('ocr_text', ''))}")
                    print(f"  Source: {img.get('source')}")
                    return True
            else:
                print("⚠️  No images stored for this document")
                return False
        else:
            print(f"❌ Failed to get document images: {response.status_code}")
            if response.status_code == 404:
                print("   Document not found")
            return False
    except Exception as e:
        print(f"❌ Error checking document images: {e}")
        return False

def main():
    """Run diagnostics"""
    print("\n" + "="*80)
    print("IMAGE STORAGE DIAGNOSTICS")
    print("="*80 + "\n")
    
    # Check vector store type
    is_opensearch = check_vectorstore_type()
    
    # Check OpenSearch config
    if is_opensearch:
        check_opensearch_config()
    
    # Check image index
    check_image_index()
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSIS SUMMARY")
    print("="*80)
    
    if not is_opensearch:
        print("\n⚠️  ISSUE FOUND:")
        print("   Vector store is not OpenSearch.")
        print("   Images are only stored when using OpenSearch vector store.")
        print("\n   Solutions:")
        print("   1. Configure OpenSearch as the vector store type")
        print("   2. Images will be stored at query time (if OpenSearch is used)")
        print("   3. For full image storage, use OpenSearch vector store")
    else:
        print("\n✅ OpenSearch is configured")
        print("   If images are not found:")
        print("   1. Images may be stored at query time only")
        print("   2. Check if document processing extracted images properly")
        print("   3. Verify extracted_images format in parser output")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()

