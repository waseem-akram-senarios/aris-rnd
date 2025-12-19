#!/usr/bin/env python3
"""
Postman Endpoint Testing Script
Simulates Postman requests to test all endpoints
"""
import sys
import requests
import json
from typing import Dict, Any, Optional
from datetime import datetime

API_BASE = "http://44.221.84.58:8500"

# Test results
results = {
    'timestamp': datetime.now().isoformat(),
    'endpoints': []
}

def test_endpoint(name: str, method: str, url: str, headers: Dict = None, 
                 data: Dict = None, files: Dict = None, expected_status: int = 200) -> Dict:
    """Test a single endpoint"""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")
    print(f"Method: {method}")
    print(f"URL: {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, data=data, files=files, timeout=300)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            return {'status': 'SKIP', 'error': f'Unsupported method: {method}'}
        
        result = {
            'name': name,
            'method': method,
            'url': url,
            'status_code': response.status_code,
            'status': 'PASS' if response.status_code == expected_status else 'FAIL',
            'response_time': response.elapsed.total_seconds()
        }
        
        # Try to parse JSON response
        try:
            result['response'] = response.json()
            result['response_size'] = len(json.dumps(result['response']))
        except:
            result['response'] = response.text[:500]
            result['response_size'] = len(response.text)
        
        # Status message
        if response.status_code == 200:
            print(f"✅ Status: {response.status_code} - SUCCESS")
            print(f"⏱️  Response Time: {result['response_time']:.2f}s")
        elif response.status_code == 404:
            print(f"⚠️  Status: {response.status_code} - NOT FOUND (needs deployment)")
            result['status'] = 'NEEDS_DEPLOYMENT'
        else:
            print(f"❌ Status: {response.status_code} - ERROR")
            result['status'] = 'FAIL'
        
        # Show response preview
        if isinstance(result['response'], dict):
            print(f"📄 Response Preview:")
            for key in list(result['response'].keys())[:5]:
                value = result['response'][key]
                if isinstance(value, (str, int, float, bool)):
                    print(f"   {key}: {value}")
                elif isinstance(value, list):
                    print(f"   {key}: [{len(value)} items]")
                else:
                    print(f"   {key}: {type(value).__name__}")
        else:
            print(f"📄 Response: {result['response'][:200]}")
        
        return result
        
    except requests.exceptions.Timeout:
        print(f"⏱️  TIMEOUT - Request took too long")
        return {
            'name': name,
            'status': 'TIMEOUT',
            'error': 'Request timeout'
        }
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {
            'name': name,
            'status': 'ERROR',
            'error': str(e)
        }

def main():
    """Run all Postman endpoint tests"""
    print("="*80)
    print("POSTMAN ENDPOINT TESTING")
    print("Simulating Postman Extension Requests")
    print("="*80)
    
    # Test 1: Health Check
    result1 = test_endpoint(
        "Health Check",
        "GET",
        f"{API_BASE}/health"
    )
    results['endpoints'].append(result1)
    
    # Test 2: Get All Documents
    result2 = test_endpoint(
        "Get All Documents",
        "GET",
        f"{API_BASE}/documents",
        headers={"Accept": "application/json"}
    )
    results['endpoints'].append(result2)
    
    # Get document ID from response
    doc_id = None
    doc_name = None
    if result2.get('status') == 'PASS' and isinstance(result2.get('response'), dict):
        documents = result2['response'].get('documents', [])
        if documents:
            doc_id = documents[0].get('document_id')
            doc_name = documents[0].get('document_name')
            print(f"\n📋 Found Document ID: {doc_id}")
            print(f"📄 Document Name: {doc_name}")
    
    if not doc_id:
        print("\n⚠️  No document ID found. Some tests will be skipped.")
        print("   Upload a document first or use an existing document ID.")
    else:
        # Test 3: Quick Accuracy Check
        result3 = test_endpoint(
            "Quick Accuracy Check",
            "GET",
            f"{API_BASE}/documents/{doc_id}/accuracy",
            headers={"Accept": "application/json"}
        )
        results['endpoints'].append(result3)
        
        # Test 4: Get All Images
        result4 = test_endpoint(
            "Get All Images",
            "GET",
            f"{API_BASE}/documents/{doc_id}/images/all",
            headers={"Accept": "application/json"}
        )
        results['endpoints'].append(result4)
        
        # Test 5: Get Page Information
        result5 = test_endpoint(
            "Get Page Information (Page 1)",
            "GET",
            f"{API_BASE}/documents/{doc_id}/pages/1",
            headers={"Accept": "application/json"}
        )
        results['endpoints'].append(result5)
        
        # Test 6: Query Text Only
        result6 = test_endpoint(
            "Query Text Only",
            "POST",
            f"{API_BASE}/query/text",
            headers={"Content-Type": "application/json"},
            data={
                "question": "What is in this document?",
                "k": 5,
                "document_id": doc_id,
                "use_mmr": True
            }
        )
        results['endpoints'].append(result6)
        
        # Test 7: Query Images Only
        result7 = test_endpoint(
            "Query Images Only",
            "POST",
            f"{API_BASE}/query/images",
            headers={"Content-Type": "application/json"},
            data={
                "question": "tools and equipment",
                "k": 5,
                "source": doc_name
            }
        )
        results['endpoints'].append(result7)
        
        # Test 8: Full Verification (if PDF available)
        import os
        from pathlib import Path
        
        pdf_file = None
        for pdf in Path('.').glob('*.pdf'):
            if pdf.name == doc_name or (doc_name and doc_name in pdf.name):
                pdf_file = str(pdf)
                break
        
        if not pdf_file:
            for pdf in Path('.').glob('*.pdf'):
                pdf_file = str(pdf)
                break
        
        if pdf_file and os.path.exists(pdf_file):
            print(f"\n📄 Found PDF file: {pdf_file}")
            print("⚠️  Full Verification test will take 5-10 minutes...")
            
            with open(pdf_file, 'rb') as f:
                result8 = test_endpoint(
                    "Full Verification",
                    "POST",
                    f"{API_BASE}/documents/{doc_id}/verify",
                    data={"auto_fix": "false"},
                    files={"file": (os.path.basename(pdf_file), f, "application/pdf")},
                    expected_status=200
                )
                results['endpoints'].append(result8)
        else:
            print(f"\n⚠️  PDF file not found. Skipping Full Verification test.")
            results['endpoints'].append({
                'name': 'Full Verification',
                'status': 'SKIP',
                'reason': 'PDF file not found'
            })
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for r in results['endpoints'] if r.get('status') == 'PASS')
    failed = sum(1 for r in results['endpoints'] if r.get('status') == 'FAIL')
    needs_deployment = sum(1 for r in results['endpoints'] if r.get('status') == 'NEEDS_DEPLOYMENT')
    skipped = sum(1 for r in results['endpoints'] if r.get('status') in ['SKIP', 'TIMEOUT', 'ERROR'])
    
    print(f"\nTotal Tests: {len(results['endpoints'])}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Needs Deployment: {needs_deployment}")
    print(f"⏭️  Skipped: {skipped}")
    
    print(f"\n{'='*80}")
    print("DETAILED RESULTS")
    print(f"{'='*80}")
    
    for endpoint in results['endpoints']:
        status_icon = {
            'PASS': '✅',
            'FAIL': '❌',
            'NEEDS_DEPLOYMENT': '⚠️',
            'SKIP': '⏭️',
            'TIMEOUT': '⏱️',
            'ERROR': '❌'
        }.get(endpoint.get('status', 'UNKNOWN'), '❓')
        
        print(f"\n{status_icon} {endpoint.get('name', 'Unknown')}")
        print(f"   Status Code: {endpoint.get('status_code', 'N/A')}")
        print(f"   Response Time: {endpoint.get('response_time', 0):.2f}s" if endpoint.get('response_time') else "")
        
        if endpoint.get('status') == 'NEEDS_DEPLOYMENT':
            print(f"   ⚠️  This endpoint needs to be deployed")
        elif endpoint.get('error'):
            print(f"   Error: {endpoint.get('error')}")
    
    # Save results
    report_file = f"postman_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Test results saved to: {report_file}")
    
    # Recommendations
    if needs_deployment > 0:
        print(f"\n{'='*80}")
        print("RECOMMENDATIONS")
        print(f"{'='*80}")
        print("⚠️  Some endpoints need deployment:")
        print("   1. Run: ./scripts/deploy-api-updates.sh")
        print("   2. Wait 10-15 seconds")
        print("   3. Re-run this test")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
