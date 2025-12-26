#!/usr/bin/env python3
"""
Simple OCR Accuracy Test using Verification Endpoint
Compares stored OCR with PDF content using the built-in verification endpoint
"""
import sys
import requests
import json
from pathlib import Path

# API base URL
API_BASE = "http://44.221.84.58:8500"

def get_document_info():
    """Get first available document"""
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to get documents: {response.status_code}")
            return None, None
        
        documents = response.json().get('documents', [])
        if not documents:
            print("❌ No documents found")
            return None, None
        
        doc = documents[0]
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        
        print(f"✅ Found document: {doc_name}")
        print(f"   Document ID: {doc_id}")
        
        return doc_id, doc_name
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, None


def find_pdf_file(doc_name):
    """Find PDF file matching document name"""
    # Try exact match first
    if Path(doc_name).exists():
        return str(Path(doc_name))
    
    # Try to find any PDF
    for pdf_file in Path('.').glob('*.pdf'):
        if doc_name in pdf_file.name or pdf_file.name in doc_name:
            return str(pdf_file)
    
    # Return first PDF found
    for pdf_file in Path('.').glob('*.pdf'):
        return str(pdf_file)
    
    return None


def test_accuracy_check(doc_id):
    """Test quick accuracy check endpoint"""
    print(f"\n{'='*80}")
    print("STEP 1: Quick Accuracy Check")
    print(f"{'='*80}")
    
    try:
        response = requests.get(f"{API_BASE}/documents/{doc_id}/accuracy", timeout=30)
        if response.status_code != 200:
            print(f"❌ Accuracy check failed: {response.status_code}")
            print(response.text[:500])
            return None
        
        data = response.json()
        print(f"✅ Accuracy Check Results:")
        print(f"  Document: {data.get('document_name')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Overall Accuracy: {data.get('overall_accuracy', 'N/A')}")
        print(f"  OCR Accuracy: {data.get('ocr_accuracy', 'N/A')}")
        print(f"  Verification Needed: {data.get('verification_needed', 'N/A')}")
        
        return data
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_verification(doc_id, pdf_path):
    """Test full verification with PDF upload"""
    print(f"\n{'='*80}")
    print("STEP 2: Full OCR Verification (Side-by-Side Comparison)")
    print(f"{'='*80}")
    
    if not pdf_path or not Path(pdf_path).exists():
        print(f"❌ PDF file not found: {pdf_path}")
        return None
    
    print(f"📄 Uploading PDF for verification: {Path(pdf_path).name}")
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            data = {'auto_fix': 'false'}
            
            response = requests.post(
                f"{API_BASE}/documents/{doc_id}/verify",
                files=files,
                data=data,
                timeout=600
            )
        
        if response.status_code != 200:
            print(f"❌ Verification failed: {response.status_code}")
            print(response.text[:500])
            return None
        
        result = response.json()
        
        print(f"\n✅ Verification Complete!")
        print(f"\n📊 Overall Results:")
        print(f"  Overall Accuracy: {result.get('overall_accuracy', 0):.2%}")
        print(f"  Total Images Verified: {len(result.get('image_verifications', []))}")
        print(f"  Issues Found: {len(result.get('issues_found', []))}")
        
        # Count accuracy status
        image_verifications = result.get('image_verifications', [])
        accurate = sum(1 for iv in image_verifications if iv.get('status') == 'accurate')
        needs_review = sum(1 for iv in image_verifications if iv.get('status') == 'needs_review')
        inaccurate = sum(1 for iv in image_verifications if iv.get('status') == 'inaccurate')
        
        print(f"\n🖼️  Image Status:")
        print(f"  ✅ Accurate: {accurate}")
        print(f"  ⚠️  Needs Review: {needs_review}")
        print(f"  ❌ Inaccurate: {inaccurate}")
        
        # Show sample comparisons
        print(f"\n{'='*80}")
        print("SAMPLE SIDE-BY-SIDE COMPARISONS")
        print(f"{'='*80}")
        
        for i, img_ver in enumerate(image_verifications[:5], 1):  # Show first 5
            print(f"\n{'─'*80}")
            print(f"IMAGE {i} - Page {img_ver.get('page_number', 'N/A')}, Index {img_ver.get('image_index', 'N/A')}")
            print(f"{'─'*80}")
            print(f"📊 Accuracy: {img_ver.get('ocr_accuracy', 0):.2%}")
            print(f"📏 Stored OCR Length: {img_ver.get('stored_ocr_length', 0):,} chars")
            print(f"📏 Verified OCR Length: {img_ver.get('verified_ocr_length', 0):,} chars")
            print(f"📈 Status: {img_ver.get('status', 'unknown')}")
            
            missing = img_ver.get('missing_content', [])
            extra = img_ver.get('extra_content', [])
            
            if missing:
                print(f"\n⚠️  Missing Content ({len(missing)} items):")
                for item in missing[:3]:
                    print(f"  - {item[:100]}")
            
            if extra:
                print(f"\n➕ Extra Content ({len(extra)} items):")
                for item in extra[:3]:
                    print(f"  - {item[:100]}")
        
        # Show issues
        issues = result.get('issues_found', [])
        if issues:
            print(f"\n{'='*80}")
            print(f"ISSUES FOUND ({len(issues)}):")
            print(f"{'='*80}")
            for issue in issues[:10]:
                print(f"  - {issue}")
        
        # Show recommendations
        recommendations = result.get('recommendations', [])
        if recommendations:
            print(f"\n{'='*80}")
            print(f"RECOMMENDATIONS:")
            print(f"{'='*80}")
            for rec in recommendations:
                print(f"  💡 {rec}")
        
        # Save report
        report_file = f"ocr_verification_report_{doc_id[:8]}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Full report saved to: {report_file}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("="*80)
    print("OCR ACCURACY TEST - Side-by-Side Comparison")
    print("="*80)
    
    # Get document
    doc_id, doc_name = get_document_info()
    if not doc_id:
        print("\n❌ Could not get document. Please ensure:")
        print("   1. API is running")
        print("   2. At least one document is uploaded")
        return 1
    
    # Find PDF
    pdf_path = find_pdf_file(doc_name)
    if not pdf_path:
        print(f"\n⚠️  PDF file not found locally: {doc_name}")
        print("   Will test accuracy check endpoint only")
        pdf_path = None
    
    # Test 1: Quick accuracy check
    accuracy_data = test_accuracy_check(doc_id)
    
    # Test 2: Full verification (if PDF available)
    if pdf_path:
        verification_result = test_verification(doc_id, pdf_path)
        
        if verification_result:
            overall_accuracy = verification_result.get('overall_accuracy', 0)
            print(f"\n{'='*80}")
            print("FINAL SUMMARY")
            print(f"{'='*80}")
            print(f"📊 Overall OCR Accuracy: {overall_accuracy:.2%}")
            
            if overall_accuracy >= 0.90:
                print(f"✅ EXCELLENT: OCR accuracy is very high!")
            elif overall_accuracy >= 0.85:
                print(f"⚠️  GOOD: OCR accuracy is acceptable")
            else:
                print(f"❌ NEEDS ATTENTION: OCR accuracy is below threshold")
                print(f"   Consider using auto-fix or re-processing")
    else:
        print(f"\n{'='*80}")
        print("NOTE: Full verification requires PDF file")
        print("   Upload the PDF file to get side-by-side comparison")
        print(f"{'='*80}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
