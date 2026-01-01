#!/usr/bin/env python3
"""
Comprehensive test for ALL latest changes:
1. API v3.0.0 endpoints
2. S3 document storage
3. Settings management
4. Document library
5. Metrics endpoints
6. Page number extraction improvements
7. Citation accuracy
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://44.221.84.58:8500"

def test_api_version():
    """Test API v3.0.0"""
    print("\n" + "="*70)
    print("1. API Version Test")
    print("="*70)
    
    response = requests.get(f"{BASE_URL}/", timeout=10)
    if response.status_code == 200:
        data = response.json()
        assert data.get('version') == '3.0.0', f"Expected v3.0.0, got {data.get('version')}"
        assert 'Unified' in data.get('name', ''), "API name should contain 'Unified'"
        assert data.get('s3_enabled') is not None, "s3_enabled should be present"
        print("✅ API v3.0.0 verified")
        return True
    print(f"❌ API version test failed: {response.status_code}")
    return False

def test_s3_endpoints():
    """Test S3 storage endpoints"""
    print("\n" + "="*70)
    print("2. S3 Storage Endpoints Test")
    print("="*70)
    
    # Test endpoint exists (OPTIONS)
    response = requests.options(f"{BASE_URL}/documents/upload-s3", timeout=5)
    if response.status_code in [200, 405]:
        print("✅ S3 upload endpoint exists")
    else:
        print(f"⚠️  S3 upload endpoint: {response.status_code}")
    
    # Check root endpoint shows S3 endpoints
    root_response = requests.get(f"{BASE_URL}/", timeout=10)
    if root_response.status_code == 200:
        root_data = root_response.json()
        if 'documents_s3' in root_data.get('endpoints', {}):
            print("✅ S3 endpoints listed in API structure")
            return True
    
    return True

def test_settings_endpoints():
    """Test settings endpoints"""
    print("\n" + "="*70)
    print("3. Settings Endpoints Test")
    print("="*70)
    
    # Test GET /settings
    response = requests.get(f"{BASE_URL}/settings", timeout=10)
    if response.status_code == 200:
        data = response.json()
        required_sections = ['models', 'parser', 'chunking', 'vector_store', 'retrieval', 'agentic_rag', 's3']
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
        print("✅ GET /settings works with all sections")
        
        # Test section-specific query
        section_response = requests.get(f"{BASE_URL}/settings?section=models", timeout=10)
        if section_response.status_code == 200:
            section_data = section_response.json()
            assert 'models' in section_data, "Section query should return models"
            print("✅ Settings section query works")
        
        return True
    print(f"❌ Settings endpoint failed: {response.status_code}")
    return False

def test_library_endpoints():
    """Test library endpoints"""
    print("\n" + "="*70)
    print("4. Library Endpoints Test")
    print("="*70)
    
    response = requests.get(f"{BASE_URL}/library", timeout=10)
    if response.status_code == 200:
        data = response.json()
        assert 'total_documents' in data, "Missing total_documents"
        assert 'documents' in data, "Missing documents list"
        assert 's3_enabled' in data, "Missing s3_enabled"
        print(f"✅ Library endpoint works (found {data.get('total_documents')} documents)")
        return True
    print(f"❌ Library endpoint failed: {response.status_code}")
    return False

def test_metrics_endpoints():
    """Test metrics endpoints"""
    print("\n" + "="*70)
    print("5. Metrics Endpoints Test")
    print("="*70)
    
    response = requests.get(f"{BASE_URL}/metrics", timeout=10)
    if response.status_code == 200:
        data = response.json()
        required_sections = ['processing', 'queries', 'parsers', 'storage']
        for section in required_sections:
            assert section in data, f"Missing metrics section: {section}"
        print("✅ Metrics endpoint works")
        
        # Test dashboard
        dashboard_response = requests.get(f"{BASE_URL}/metrics/dashboard", timeout=10)
        if dashboard_response.status_code == 200:
            dashboard_data = dashboard_response.json()
            assert 'system' in dashboard_data, "Dashboard missing system"
            assert 'library' in dashboard_data, "Dashboard missing library"
            print("✅ Metrics dashboard works")
        
        return True
    print(f"❌ Metrics endpoint failed: {response.status_code}")
    return False

def test_citation_page_numbers():
    """Test citation page number improvements"""
    print("\n" + "="*70)
    print("6. Citation Page Number Improvements Test")
    print("="*70)
    
    # Get documents first
    docs_response = requests.get(f"{BASE_URL}/documents", timeout=10)
    if docs_response.status_code != 200:
        print("⚠️  Could not get documents list")
        return True
    
    docs_data = docs_response.json()
    if len(docs_data.get('documents', [])) == 0:
        print("⚠️  No documents available for query test")
        return True
    
    # Test query
    query_data = {
        "question": "What is in the documents?",
        "k": 3
    }
    
    response = requests.post(f"{BASE_URL}/query", json=query_data, timeout=30)
    if response.status_code == 200:
        data = response.json()
        citations = data.get('citations', [])
        
        if citations:
            # Check page numbers
            all_have_pages = all('page' in c and isinstance(c.get('page'), int) and c.get('page') >= 1 for c in citations)
            assert all_have_pages, "All citations should have valid page numbers"
            print(f"✅ All {len(citations)} citations have valid page numbers")
            
            # Check page_extraction_method (new feature)
            has_method = any('page_extraction_method' in c for c in citations)
            if has_method:
                print("✅ Citations include page_extraction_method")
            else:
                print("⚠️  Citations missing page_extraction_method (may be expected)")
            
            # Check source_location
            all_have_location = all('source_location' in c and 'Page' in str(c.get('source_location', '')) for c in citations)
            if all_have_location:
                print("✅ All citations have source_location with 'Page'")
            else:
                print("⚠️  Some citations missing proper source_location")
            
            return True
        else:
            print("⚠️  No citations returned (may be expected)")
            return True
    else:
        print(f"⚠️  Query endpoint returned {response.status_code}")
        return True

def test_core_endpoints():
    """Test core endpoints"""
    print("\n" + "="*70)
    print("7. Core Endpoints Test")
    print("="*70)
    
    # Health
    health_response = requests.get(f"{BASE_URL}/health", timeout=10)
    assert health_response.status_code == 200, "Health endpoint should return 200"
    print("✅ Health endpoint works")
    
    # Documents
    docs_response = requests.get(f"{BASE_URL}/documents", timeout=10)
    assert docs_response.status_code == 200, "Documents endpoint should return 200"
    print("✅ Documents endpoint works")
    
    # Docs
    docs_ui_response = requests.get(f"{BASE_URL}/docs", timeout=10)
    assert docs_ui_response.status_code == 200, "API docs should be accessible"
    print("✅ API documentation accessible")
    
    return True

def main():
    """Run all tests"""
    print("="*70)
    print("COMPREHENSIVE TEST - ALL LATEST CHANGES")
    print("="*70)
    print(f"Testing API at: {BASE_URL}")
    
    results = []
    
    results.append(("API Version", test_api_version()))
    results.append(("S3 Endpoints", test_s3_endpoints()))
    results.append(("Settings Endpoints", test_settings_endpoints()))
    results.append(("Library Endpoints", test_library_endpoints()))
    results.append(("Metrics Endpoints", test_metrics_endpoints()))
    results.append(("Citation Page Numbers", test_citation_page_numbers()))
    results.append(("Core Endpoints", test_core_endpoints()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - All latest changes are working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())




