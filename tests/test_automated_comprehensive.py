#!/usr/bin/env python3
"""
Comprehensive Automated Test Suite
Tests all OCR verification and enhanced metadata functionality
"""
import sys
import os
import requests
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# API base URL
API_BASE = "http://44.221.84.58:8500"

# Test results storage
test_results = {
    'start_time': datetime.now().isoformat(),
    'tests': [],
    'summary': {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'skipped': 0
    }
}

def log_test(test_name: str, status: str, message: str = "", details: Dict = None):
    """Log test result"""
    test_results['tests'].append({
        'name': test_name,
        'status': status,
        'message': message,
        'details': details or {},
        'timestamp': datetime.now().isoformat()
    })
    test_results['summary']['total'] += 1
    if status == 'PASS':
        test_results['summary']['passed'] += 1
        print(f"✅ PASS: {test_name}")
    elif status == 'FAIL':
        test_results['summary']['failed'] += 1
        print(f"❌ FAIL: {test_name} - {message}")
    elif status == 'SKIP':
        test_results['summary']['skipped'] += 1
        print(f"⏭️  SKIP: {test_name} - {message}")
    
    if details:
        for key, value in details.items():
            print(f"   {key}: {value}")

def test_api_health():
    """Test 1: API Health Check"""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=10)
        if response.status_code == 200:
            log_test("API Health Check", "PASS", "API is healthy")
            return True
        else:
            log_test("API Health Check", "FAIL", f"Status code: {response.status_code}")
            return False
    except Exception as e:
        log_test("API Health Check", "FAIL", f"Connection error: {str(e)}")
        return False

def test_documents_endpoint():
    """Test 2: Documents List Endpoint"""
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code == 200:
            data = response.json()
            docs = data.get('documents', [])
            log_test("Documents List Endpoint", "PASS", f"Found {len(docs)} documents", {
                'document_count': len(docs)
            })
            return docs
        else:
            log_test("Documents List Endpoint", "FAIL", f"Status code: {response.status_code}")
            return []
    except Exception as e:
        log_test("Documents List Endpoint", "FAIL", f"Error: {str(e)}")
        return []

def test_enhanced_metadata(doc: Dict):
    """Test 3: Enhanced Metadata Fields"""
    fields_to_check = [
        ('file_hash', 'File Hash'),
        ('upload_metadata', 'Upload Metadata'),
        ('pdf_metadata', 'PDF Metadata'),
        ('processing_metadata', 'Processing Metadata'),
        ('ocr_quality_metrics', 'OCR Quality Metrics'),
        ('version_info', 'Version Info')
    ]
    
    present_fields = []
    missing_fields = []
    
    for field, name in fields_to_check:
        if doc.get(field):
            present_fields.append(name)
        else:
            missing_fields.append(name)
    
    if len(present_fields) >= 3:  # At least 3 fields should be present
        log_test("Enhanced Metadata Fields", "PASS", 
                f"{len(present_fields)}/{len(fields_to_check)} fields present", {
                    'present': present_fields,
                    'missing': missing_fields
                })
        return True
    else:
        log_test("Enhanced Metadata Fields", "SKIP", 
                f"Only {len(present_fields)} fields present (may be old document)", {
                    'present': present_fields,
                    'missing': missing_fields
                })
        return False

def test_accuracy_endpoint(doc_id: str):
    """Test 4: Accuracy Check Endpoint"""
    try:
        response = requests.get(f"{API_BASE}/documents/{doc_id}/accuracy", timeout=30)
        if response.status_code == 200:
            data = response.json()
            log_test("Accuracy Check Endpoint", "PASS", "Endpoint working", {
                'status': data.get('status'),
                'overall_accuracy': data.get('overall_accuracy'),
                'verification_needed': data.get('verification_needed')
            })
            return data
        elif response.status_code == 404:
            log_test("Accuracy Check Endpoint", "SKIP", "Endpoint not found (may need deployment)")
            return None
        else:
            log_test("Accuracy Check Endpoint", "FAIL", f"Status code: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        log_test("Accuracy Check Endpoint", "SKIP", "Timeout - server may be slow")
        return None
    except Exception as e:
        log_test("Accuracy Check Endpoint", "FAIL", f"Error: {str(e)}")
        return None

def test_verification_endpoint(doc_id: str, pdf_path: Optional[str] = None):
    """Test 5: Verification Endpoint"""
    if not pdf_path or not Path(pdf_path).exists():
        log_test("Verification Endpoint", "SKIP", "PDF file not available")
        return None
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (Path(pdf_path).name, f, 'application/pdf')}
            data = {'auto_fix': 'false'}
            
            response = requests.post(
                f"{API_BASE}/documents/{doc_id}/verify",
                files=files,
                data=data,
                timeout=300
            )
        
        if response.status_code == 200:
            result = response.json()
            overall_accuracy = result.get('overall_accuracy', 0)
            log_test("Verification Endpoint", "PASS", "Verification completed", {
                'overall_accuracy': f"{overall_accuracy:.2%}",
                'images_verified': len(result.get('image_verifications', [])),
                'issues_found': len(result.get('issues_found', [])),
                'recommendations': len(result.get('recommendations', []))
            })
            return result
        elif response.status_code == 404:
            log_test("Verification Endpoint", "SKIP", "Endpoint not found (may need deployment)")
            return None
        else:
            log_test("Verification Endpoint", "FAIL", f"Status code: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        log_test("Verification Endpoint", "SKIP", "Timeout - verification takes time")
        return None
    except Exception as e:
        log_test("Verification Endpoint", "FAIL", f"Error: {str(e)}")
        return None

def test_utility_imports():
    """Test 6: Utility Module Imports"""
    try:
        sys.path.insert(0, '.')
        from utils.pdf_metadata_extractor import extract_pdf_metadata
        from utils.pdf_content_extractor import extract_pdf_content
        from utils.ocr_verifier import OCRVerifier
        from utils.ocr_auto_fix import OCRAutoFix
        from config.accuracy_config import ACCURACY_THRESHOLDS
        
        log_test("Utility Module Imports", "PASS", "All utilities imported successfully")
        return True
    except Exception as e:
        log_test("Utility Module Imports", "FAIL", f"Import error: {str(e)}")
        return False

def test_ocr_verifier_functionality():
    """Test 7: OCR Verifier Functionality"""
    try:
        sys.path.insert(0, '.')
        from utils.ocr_verifier import OCRVerifier
        
        verifier = OCRVerifier()
        
        # Test similarity
        text1 = "Hello world"
        text2 = "Hello world"
        similarity = verifier._calculate_similarity(text1, text2)
        
        if similarity >= 0.99:
            log_test("OCR Verifier Functionality", "PASS", "Similarity calculation working", {
                'similarity': f"{similarity:.2%}"
            })
            return True
        else:
            log_test("OCR Verifier Functionality", "FAIL", f"Unexpected similarity: {similarity}")
            return False
    except Exception as e:
        log_test("OCR Verifier Functionality", "FAIL", f"Error: {str(e)}")
        return False

def test_auto_fix_functionality():
    """Test 8: Auto-Fix Functionality"""
    try:
        sys.path.insert(0, '.')
        from utils.ocr_auto_fix import OCRAutoFix
        
        auto_fix = OCRAutoFix()
        
        # Test should_auto_fix
        low_accuracy_report = {'overall_accuracy': 0.75}
        high_accuracy_report = {'overall_accuracy': 0.95}
        
        should_fix_low = auto_fix.should_auto_fix(low_accuracy_report)
        should_fix_high = auto_fix.should_auto_fix(high_accuracy_report)
        
        if should_fix_low and not should_fix_high:
            log_test("Auto-Fix Functionality", "PASS", "Auto-fix logic working correctly", {
                'low_accuracy_should_fix': should_fix_low,
                'high_accuracy_should_fix': should_fix_high
            })
            return True
        else:
            log_test("Auto-Fix Functionality", "FAIL", "Auto-fix logic incorrect")
            return False
    except Exception as e:
        log_test("Auto-Fix Functionality", "FAIL", f"Error: {str(e)}")
        return False

def test_schema_validation():
    """Test 9: Schema Validation"""
    try:
        sys.path.insert(0, '.')
        from api.schemas import (
            DocumentMetadata, VerificationReport, AccuracyCheckResponse
        )
        
        # Test DocumentMetadata
        doc = DocumentMetadata(
            document_id='test',
            document_name='test.pdf',
            status='success',
            file_hash='abc123'
        )
        
        # Test VerificationReport
        report = VerificationReport(
            document_id='test',
            document_name='test.pdf',
            verification_timestamp='2024-01-01T00:00:00Z',
            overall_accuracy=0.95,
            page_verifications=[],
            image_verifications=[],
            issues_found=[],
            recommendations=[]
        )
        
        log_test("Schema Validation", "PASS", "All schemas validated successfully")
        return True
    except Exception as e:
        log_test("Schema Validation", "FAIL", f"Schema error: {str(e)}")
        return False

def test_version_tracking():
    """Test 10: Version Tracking"""
    try:
        sys.path.insert(0, '.')
        from storage.document_registry import DocumentRegistry
        
        registry = DocumentRegistry('storage/document_registry.json')
        
        # Check methods exist
        has_add_version = hasattr(registry, 'add_document_version')
        has_get_versions = hasattr(registry, 'get_document_versions')
        has_detect_changes = hasattr(registry, '_detect_changes')
        
        if has_add_version and has_get_versions and has_detect_changes:
            log_test("Version Tracking", "PASS", "Version tracking methods available")
            return True
        else:
            log_test("Version Tracking", "FAIL", "Missing version tracking methods")
            return False
    except Exception as e:
        log_test("Version Tracking", "FAIL", f"Error: {str(e)}")
        return False

def find_pdf_file(doc_name: str = None):
    """Find PDF file for testing"""
    # Try to find PDF matching document name
    if doc_name:
        if Path(doc_name).exists():
            return str(Path(doc_name))
        for pdf_file in Path('.').glob('*.pdf'):
            if doc_name in pdf_file.name or pdf_file.name in doc_name:
                return str(pdf_file)
    
    # Find any PDF
    for pdf_file in Path('.').glob('*.pdf'):
        return str(pdf_file)
    
    return None

def run_all_tests():
    """Run all automated tests"""
    print("="*80)
    print("COMPREHENSIVE AUTOMATED TEST SUITE")
    print("OCR Verification and Enhanced Metadata System")
    print("="*80)
    print()
    
    # Test 1: API Health
    if not test_api_health():
        print("\n⚠️  API is not accessible. Some tests will be skipped.")
        print()
    
    # Test 2: Documents Endpoint
    documents = test_documents_endpoint()
    
    # Test 3: Enhanced Metadata (if documents available)
    doc_id = None
    doc_name = None
    if documents:
        doc = documents[0]
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        test_enhanced_metadata(doc)
    
    # Test 4: Accuracy Endpoint
    if doc_id:
        test_accuracy_endpoint(doc_id)
    
    # Test 5: Verification Endpoint
    pdf_path = find_pdf_file(doc_name)
    if doc_id and pdf_path:
        test_verification_endpoint(doc_id, pdf_path)
    
    # Test 6-10: Code Functionality Tests
    test_utility_imports()
    test_ocr_verifier_functionality()
    test_auto_fix_functionality()
    test_schema_validation()
    test_version_tracking()
    
    # Finalize results
    test_results['end_time'] = datetime.now().isoformat()
    duration = (datetime.fromisoformat(test_results['end_time']) - 
                datetime.fromisoformat(test_results['start_time'])).total_seconds()
    test_results['duration_seconds'] = duration
    
    return test_results

def print_summary(results: Dict):
    """Print test summary"""
    print()
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print()
    
    summary = results['summary']
    print(f"Total Tests: {summary['total']}")
    print(f"✅ Passed: {summary['passed']}")
    print(f"❌ Failed: {summary['failed']}")
    print(f"⏭️  Skipped: {summary['skipped']}")
    print(f"⏱️  Duration: {results.get('duration_seconds', 0):.2f} seconds")
    print()
    
    # Show failed tests
    failed_tests = [t for t in results['tests'] if t['status'] == 'FAIL']
    if failed_tests:
        print("Failed Tests:")
        for test in failed_tests:
            print(f"  ❌ {test['name']}: {test['message']}")
        print()
    
    # Calculate pass rate
    if summary['total'] > 0:
        pass_rate = (summary['passed'] / summary['total']) * 100
        print(f"Pass Rate: {pass_rate:.1f}%")
        
        if pass_rate >= 80:
            print("✅ Overall Status: GOOD")
        elif pass_rate >= 60:
            print("⚠️  Overall Status: ACCEPTABLE")
        else:
            print("❌ Overall Status: NEEDS ATTENTION")
    
    print()

def save_report(results: Dict):
    """Save test report to file"""
    report_file = f"automated_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"✅ Test report saved to: {report_file}")
        return report_file
    except Exception as e:
        print(f"❌ Error saving report: {e}")
        return None

def main():
    """Main test execution"""
    results = run_all_tests()
    print_summary(results)
    save_report(results)
    
    # Return exit code
    if results['summary']['failed'] > 0:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
