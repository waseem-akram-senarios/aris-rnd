#!/usr/bin/env python3
"""
Test script for OCR verification functionality.
Tests that OCR verification compares PDF content with stored OCR correctly.
"""
import sys
import os
import requests
import json
from pathlib import Path

# API base URL
API_BASE = "http://44.221.84.58:8500"

def upload_test_document():
    """Upload a test document and return document ID"""
    print("📤 Uploading test document...")
    
    # Find a test PDF
    test_pdf = None
    for pdf_file in Path(".").glob("*.pdf"):
        test_pdf = pdf_file
        break
    
    if not test_pdf:
        print("❌ No PDF file found for testing")
        return None
    
    with open(test_pdf, 'rb') as f:
        files = {'file': (test_pdf.name, f, 'application/pdf')}
        data = {'parser': 'docling'}
        
        response = requests.post(f"{API_BASE}/documents", files=files, data=data, timeout=300)
    
    if response.status_code != 201:
        print(f"❌ Upload failed: {response.status_code}")
        return None
    
    result = response.json()
    doc_id = result.get('document_id')
    print(f"✅ Document uploaded: {doc_id}")
    return doc_id, test_pdf


def test_accuracy_check(doc_id):
    """Test quick accuracy check endpoint"""
    print("\n" + "=" * 80)
    print("TEST: Quick Accuracy Check")
    print("=" * 80)
    
    response = requests.get(f"{API_BASE}/documents/{doc_id}/accuracy", timeout=30)
    
    if response.status_code != 200:
        print(f"❌ Accuracy check failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    print(f"✅ Accuracy Check Response:")
    print(f"  Document ID: {result.get('document_id')}")
    print(f"  Document Name: {result.get('document_name')}")
    print(f"  Overall Accuracy: {result.get('overall_accuracy', 'N/A')}")
    print(f"  OCR Accuracy: {result.get('ocr_accuracy', 'N/A')}")
    print(f"  Status: {result.get('status', 'N/A')}")
    print(f"  Verification Needed: {result.get('verification_needed', 'N/A')}")
    
    return True


def test_verification(doc_id, pdf_path):
    """Test full OCR verification"""
    print("\n" + "=" * 80)
    print("TEST: Full OCR Verification")
    print("=" * 80)
    
    # Upload PDF file for verification
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path.name, f, 'application/pdf')}
        data = {'auto_fix': 'false'}
        
        print(f"📤 Uploading PDF for verification...")
        response = requests.post(
            f"{API_BASE}/documents/{doc_id}/verify",
            files=files,
            data=data,
            timeout=600
        )
    
    if response.status_code != 200:
        print(f"❌ Verification failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    print(f"✅ Verification Report:")
    print(f"  Document ID: {result.get('document_id')}")
    print(f"  Document Name: {result.get('document_name')}")
    print(f"  Verification Timestamp: {result.get('verification_timestamp')}")
    print(f"  Overall Accuracy: {result.get('overall_accuracy', 0):.2%}")
    print(f"  Total Images Verified: {len(result.get('image_verifications', []))}")
    print(f"  Issues Found: {len(result.get('issues_found', []))}")
    print(f"  Recommendations: {len(result.get('recommendations', []))}")
    print(f"  Auto-Fix Applied: {result.get('auto_fix_applied', False)}")
    
    # Show page verifications summary
    page_verifications = result.get('page_verifications', [])
    if page_verifications:
        print(f"\n📄 Page Verifications ({len(page_verifications)} pages):")
        for pv in page_verifications[:5]:  # Show first 5
            page_num = pv.get('page_number')
            img_accuracy = pv.get('images_accuracy', 0)
            issues_count = len(pv.get('issues', []))
            print(f"  Page {page_num}: Images accuracy {img_accuracy:.2%}, {issues_count} issues")
    
    # Show image verifications summary
    image_verifications = result.get('image_verifications', [])
    if image_verifications:
        accurate = sum(1 for iv in image_verifications if iv.get('status') == 'accurate')
        needs_review = sum(1 for iv in image_verifications if iv.get('status') == 'needs_review')
        inaccurate = sum(1 for iv in image_verifications if iv.get('status') == 'inaccurate')
        
        print(f"\n🖼️  Image Verifications:")
        print(f"  Accurate: {accurate}")
        print(f"  Needs Review: {needs_review}")
        print(f"  Inaccurate: {inaccurate}")
        
        # Show sample inaccurate images
        inaccurate_images = [iv for iv in image_verifications if iv.get('status') == 'inaccurate']
        if inaccurate_images:
            print(f"\n⚠️  Sample Inaccurate Images:")
            for iv in inaccurate_images[:3]:
                print(f"  Page {iv.get('page_number')}, Image {iv.get('image_index')}: "
                      f"Accuracy {iv.get('ocr_accuracy', 0):.2%}")
    
    # Show issues
    issues = result.get('issues_found', [])
    if issues:
        print(f"\n⚠️  Issues Found ({len(issues)}):")
        for issue in issues[:5]:
            print(f"  - {issue}")
    
    # Show recommendations
    recommendations = result.get('recommendations', [])
    if recommendations:
        print(f"\n💡 Recommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
    
    return True


def test_verification_with_auto_fix(doc_id, pdf_path):
    """Test verification with auto-fix enabled"""
    print("\n" + "=" * 80)
    print("TEST: Verification with Auto-Fix")
    print("=" * 80)
    
    with open(pdf_path, 'rb') as f:
        files = {'file': (pdf_path.name, f, 'application/pdf')}
        data = {'auto_fix': 'true'}
        
        print(f"📤 Running verification with auto-fix...")
        response = requests.post(
            f"{API_BASE}/documents/{doc_id}/verify",
            files=files,
            data=data,
            timeout=600
        )
    
    if response.status_code != 200:
        print(f"❌ Verification with auto-fix failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    result = response.json()
    auto_fix_applied = result.get('auto_fix_applied', False)
    auto_fix_details = result.get('auto_fix_details')
    
    print(f"✅ Auto-Fix Status: {'Applied' if auto_fix_applied else 'Not Applied'}")
    
    if auto_fix_details:
        print(f"\n🔧 Auto-Fix Details:")
        print(f"  Fix Method: {auto_fix_details.get('fix_method', 'N/A')}")
        print(f"  Images Fixed: {auto_fix_details.get('images_fixed', 0)}")
        print(f"  Accuracy Before: {auto_fix_details.get('accuracy_before', 0):.2%}")
        print(f"  Accuracy After: {auto_fix_details.get('accuracy_after', 0):.2%}")
        
        fix_details = auto_fix_details.get('fix_details', [])
        if fix_details:
            print(f"\n  Fix Details:")
            for detail in fix_details:
                print(f"    - {detail}")
    
    return True


def main():
    """Run all OCR verification tests"""
    print("=" * 80)
    print("OCR VERIFICATION TEST SUITE")
    print("=" * 80)
    
    # Upload test document
    upload_result = upload_test_document()
    if not upload_result:
        print("❌ Could not upload test document")
        return 1
    
    doc_id, pdf_path = upload_result
    
    results = []
    
    # Test 1: Quick accuracy check
    results.append(("Quick Accuracy Check", test_accuracy_check(doc_id)))
    
    # Test 2: Full verification
    results.append(("Full OCR Verification", test_verification(doc_id, pdf_path)))
    
    # Test 3: Verification with auto-fix
    results.append(("Verification with Auto-Fix", test_verification_with_auto_fix(doc_id, pdf_path)))
    
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
