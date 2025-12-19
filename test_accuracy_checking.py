#!/usr/bin/env python3
"""
Test script for accuracy checking functionality.
Tests accuracy endpoints and verification workflows.
"""
import sys
import requests
from pathlib import Path

# API base URL
API_BASE = "http://44.221.84.58:8500"

def get_document_id():
    """Get first available document ID"""
    response = requests.get(f"{API_BASE}/documents", timeout=30)
    if response.status_code != 200:
        return None
    
    documents = response.json().get('documents', [])
    if not documents:
        return None
    
    return documents[0].get('document_id')


def test_accuracy_endpoint():
    """Test the accuracy check endpoint"""
    print("=" * 80)
    print("TEST: Accuracy Check Endpoint")
    print("=" * 80)
    
    doc_id = get_document_id()
    if not doc_id:
        print("❌ No documents available for testing")
        return False
    
    print(f"📄 Testing with document: {doc_id}")
    
    response = requests.get(f"{API_BASE}/documents/{doc_id}/accuracy", timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Accuracy check failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    
    print(f"\n✅ Accuracy Check Results:")
    print(f"  Document ID: {result.get('document_id')}")
    print(f"  Document Name: {result.get('document_name')}")
    print(f"  Overall Accuracy: {result.get('overall_accuracy', 'N/A')}")
    print(f"  OCR Accuracy: {result.get('ocr_accuracy', 'N/A')}")
    print(f"  Text Accuracy: {result.get('text_accuracy', 'N/A')}")
    print(f"  Status: {result.get('status', 'N/A')}")
    print(f"  Verification Needed: {result.get('verification_needed', 'N/A')}")
    print(f"  Last Verification: {result.get('last_verification', 'N/A')}")
    
    # Validate response structure
    required_fields = ['document_id', 'document_name', 'status', 'verification_needed']
    missing_fields = [field for field in required_fields if field not in result]
    
    if missing_fields:
        print(f"\n❌ Missing required fields: {missing_fields}")
        return False
    
    print(f"\n✅ Accuracy check endpoint test passed!")
    return True


def main():
    """Run accuracy checking tests"""
    print("=" * 80)
    print("ACCURACY CHECKING TEST SUITE")
    print("=" * 80)
    
    results = []
    results.append(("Accuracy Check Endpoint", test_accuracy_endpoint()))
    
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
