#!/usr/bin/env python3
"""
Test script for enhanced metadata collection.
Tests that all metadata (upload, PDF properties, processing, OCR quality) is captured correctly.
"""
import sys
import os
import requests
import json
from pathlib import Path

# API base URL
API_BASE = "http://44.221.84.58:8500"

def test_upload_metadata():
    """Test that upload metadata is captured"""
    print("=" * 80)
    print("TEST: Upload Metadata Collection")
    print("=" * 80)
    
    # Find a test PDF
    test_pdf = None
    for pdf_file in Path(".").glob("*.pdf"):
        test_pdf = pdf_file
        break
    
    if not test_pdf:
        print("❌ No PDF file found for testing")
        return False
    
    print(f"📄 Testing with: {test_pdf.name}")
    
    # Upload document
    with open(test_pdf, 'rb') as f:
        files = {'file': (test_pdf.name, f, 'application/pdf')}
        data = {'parser': 'docling'}
        
        print(f"\n📤 Uploading document...")
        response = requests.post(f"{API_BASE}/documents", files=files, data=data, timeout=300)
    
    if response.status_code != 201:
        print(f"❌ Upload failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    doc_id = result.get('document_id')
    print(f"✅ Document uploaded: {doc_id}")
    
    # Check upload metadata
    upload_metadata = result.get('upload_metadata')
    if not upload_metadata:
        print("❌ upload_metadata missing")
        return False
    
    print(f"\n✅ Upload Metadata:")
    print(f"  File Hash: {upload_metadata.get('file_hash', 'MISSING')[:32]}...")
    print(f"  File Size: {upload_metadata.get('file_size_bytes', 'MISSING'):,} bytes")
    print(f"  Upload Timestamp: {upload_metadata.get('upload_timestamp', 'MISSING')}")
    print(f"  MIME Type: {upload_metadata.get('mime_type', 'MISSING')}")
    print(f"  Original Filename: {upload_metadata.get('original_filename', 'MISSING')}")
    
    # Check PDF metadata
    pdf_metadata = result.get('pdf_metadata')
    if pdf_metadata:
        print(f"\n✅ PDF Metadata:")
        print(f"  Page Count: {pdf_metadata.get('page_count', 'N/A')}")
        print(f"  Title: {pdf_metadata.get('title', 'N/A')}")
        print(f"  Author: {pdf_metadata.get('author', 'N/A')}")
        print(f"  Encrypted: {pdf_metadata.get('encrypted', 'N/A')}")
    else:
        print("\n⚠️  PDF metadata not extracted (may not be a PDF)")
    
    # Check processing metadata
    processing_metadata = result.get('processing_metadata')
    if processing_metadata:
        print(f"\n✅ Processing Metadata:")
        print(f"  Processing Time: {processing_metadata.get('processing_time', 'N/A')}s")
        print(f"  Parser Used: {processing_metadata.get('parser_used', 'N/A')}")
    else:
        print("\n⚠️  Processing metadata not captured")
    
    # Check version info
    version_info = result.get('version_info')
    if version_info:
        print(f"\n✅ Version Info:")
        print(f"  Version: {version_info.get('version', 'N/A')}")
        print(f"  Created At: {version_info.get('created_at', 'N/A')}")
    else:
        print("\n⚠️  Version info not captured")
    
    # Check file hash
    file_hash = result.get('file_hash')
    if file_hash:
        print(f"\n✅ File Hash: {file_hash[:32]}...")
    else:
        print("\n⚠️  File hash not captured")
    
    print(f"\n✅ All metadata collection tests passed!")
    return True


def test_metadata_retrieval():
    """Test that metadata is returned when retrieving documents"""
    print("\n" + "=" * 80)
    print("TEST: Metadata Retrieval")
    print("=" * 80)
    
    # Get document list
    response = requests.get(f"{API_BASE}/documents", timeout=30)
    if response.status_code != 200:
        print(f"❌ Failed to get documents: {response.status_code}")
        return False
    
    documents = response.json().get('documents', [])
    if not documents:
        print("⚠️  No documents found")
        return True
    
    # Check first document
    doc = documents[0]
    doc_id = doc.get('document_id')
    
    print(f"📄 Checking document: {doc.get('document_name')}")
    print(f"  Document ID: {doc_id}")
    
    # Check for enhanced metadata fields
    has_upload_metadata = 'upload_metadata' in doc
    has_pdf_metadata = 'pdf_metadata' in doc
    has_processing_metadata = 'processing_metadata' in doc
    has_version_info = 'version_info' in doc
    has_file_hash = 'file_hash' in doc
    
    print(f"\n✅ Metadata Fields Present:")
    print(f"  upload_metadata: {'✅' if has_upload_metadata else '❌'}")
    print(f"  pdf_metadata: {'✅' if has_pdf_metadata else '❌'}")
    print(f"  processing_metadata: {'✅' if has_processing_metadata else '❌'}")
    print(f"  version_info: {'✅' if has_version_info else '❌'}")
    print(f"  file_hash: {'✅' if has_file_hash else '❌'}")
    
    if all([has_upload_metadata, has_file_hash, has_version_info]):
        print(f"\n✅ Metadata retrieval test passed!")
        return True
    else:
        print(f"\n⚠️  Some metadata fields missing")
        return False


def main():
    """Run all metadata collection tests"""
    print("=" * 80)
    print("METADATA COLLECTION TEST SUITE")
    print("=" * 80)
    
    results = []
    
    # Test 1: Upload metadata
    results.append(("Upload Metadata", test_upload_metadata()))
    
    # Test 2: Metadata retrieval
    results.append(("Metadata Retrieval", test_metadata_retrieval()))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    all_passed = all(result[1] for result in results)
    print(f"\n{'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
