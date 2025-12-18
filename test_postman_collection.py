#!/usr/bin/env python3
"""
Test all endpoints from Postman collection to verify they work correctly
"""
import os
import sys
import requests
import json
import time
from datetime import datetime

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def print_test(test_name):
    print(f"\n{'='*70}")
    print(f"  TEST: {test_name}")
    print(f"{'='*70}")

def test_result(success, message, details=None):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")
    if details:
        print(f"   {details}")
    return success

# Test results
results = {}
doc_id = None
doc_name = None

# Test 1: Health Check
print_test("1. Health Check")
try:
    response = requests.get(f"{API_BASE_URL}/health", timeout=10)
    results['health'] = test_result(
        response.status_code == 200,
        f"Health check returned {response.status_code}",
        response.json() if response.status_code == 200 else response.text[:200]
    )
except Exception as e:
    results['health'] = test_result(False, f"Error: {str(e)}")

# Test 2: Root - API Info
print_test("2. Root - API Info")
try:
    response = requests.get(f"{API_BASE_URL}/", timeout=10)
    results['root'] = test_result(
        response.status_code == 200,
        f"Root endpoint returned {response.status_code}",
        response.json() if response.status_code == 200 else response.text[:200]
    )
except Exception as e:
    results['root'] = test_result(False, f"Error: {str(e)}")

# Test 3: List All Documents
print_test("3. List All Documents")
try:
    response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
    if response.status_code == 200:
        data = response.json()
        docs = data.get('documents', [])
        results['list_documents'] = test_result(
            True,
            f"Retrieved {len(docs)} documents",
            f"Total: {data.get('total', 0)}"
        )
        # Get first document with images if available
        doc_with_images = next((d for d in docs if d.get('image_count', 0) > 0), None)
        if doc_with_images:
            doc_name = doc_with_images.get('document_name')
            doc_id = doc_with_images.get('document_id')
    else:
        results['list_documents'] = test_result(False, f"Status: {response.status_code}")
except Exception as e:
    results['list_documents'] = test_result(False, f"Error: {str(e)}")

# Test 4: Upload Document
print_test("4. Upload Document")
pdf_path = "./FL10.11 SPECIFIC8 (1).pdf"
if os.path.exists(pdf_path):
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=TEST_TIMEOUT
            )
        
        if response.status_code == 201:
            upload_data = response.json()
            doc_id = upload_data.get('document_id')
            doc_name = upload_data.get('document_name')
            results['upload'] = test_result(
                True,
                f"Document uploaded: {doc_name}",
                f"ID: {doc_id}, Images: {upload_data.get('image_count', 0)}, Chunks: {upload_data.get('chunks_created', 0)}"
            )
            # Wait for processing
            print("   ⏳ Waiting 10 seconds for processing...")
            time.sleep(10)
        else:
            results['upload'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
    except Exception as e:
        results['upload'] = test_result(False, f"Error: {str(e)}")
else:
    results['upload'] = test_result(False, f"PDF file not found: {pdf_path}")

# Test 5: Delete Document (will test with uploaded doc)
if doc_id:
    print_test("5. Delete Document (will test later)")
    # We'll test delete at the end
    pass

# Test 6: Query Documents (Basic)
print_test("6. Query Documents (Basic)")
try:
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={
            "question": "What is the main topic of the document?",
            "k": 6,
            "use_mmr": True
        },
        timeout=120
    )
    if response.status_code == 200:
        data = response.json()
        results['query_basic'] = test_result(
            True,
            f"Query successful",
            f"Answer: {len(data.get('answer', ''))} chars, Citations: {len(data.get('citations', []))}"
        )
    else:
        results['query_basic'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
except Exception as e:
    results['query_basic'] = test_result(False, f"Error: {str(e)}")

# Test 7: Query Specific Document
if doc_id:
    print_test("7. Query Specific Document")
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "question": "What information is in this document?",
                "k": 6,
                "use_mmr": True,
                "document_id": doc_id
            },
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            results['query_specific'] = test_result(
                True,
                f"Query successful",
                f"Answer: {len(data.get('answer', ''))} chars, Citations: {len(data.get('citations', []))}"
            )
        else:
            results['query_specific'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
    except Exception as e:
        results['query_specific'] = test_result(False, f"Error: {str(e)}")
else:
    results['query_specific'] = test_result(False, "No document_id available")

# Test 8: Query with Image Questions
if doc_id:
    print_test("8. Query with Image Questions")
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={
                "question": "What tools are in drawer 1?",
                "k": 10,
                "document_id": doc_id
            },
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            citations = data.get('citations', [])
            image_citations = [c for c in citations if c.get('image_ref') or c.get('content_type') == 'image']
            results['query_images'] = test_result(
                True,
                f"Query successful",
                f"Answer: {len(data.get('answer', ''))} chars, Image citations: {len(image_citations)}"
            )
        else:
            results['query_images'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
    except Exception as e:
        results['query_images'] = test_result(False, f"Error: {str(e)}")
else:
    results['query_images'] = test_result(False, "No document_id available")

# Test 9: Query with Enhanced Parameters
print_test("9. Query with Enhanced Parameters")
try:
    response = requests.post(
        f"{API_BASE_URL}/query",
        json={
            "question": "What is the main topic of the document?",
            "k": 6,
            "use_mmr": True,
            "use_hybrid_search": True,
            "semantic_weight": 0.7,
            "search_mode": "hybrid",
            "use_agentic_rag": False,
            "temperature": 0.7,
            "max_tokens": 1000
        },
        timeout=120
    )
    if response.status_code == 200:
        data = response.json()
        results['query_enhanced'] = test_result(
            True,
            f"Query successful",
            f"Answer: {len(data.get('answer', ''))} chars, Citations: {len(data.get('citations', []))}"
        )
    else:
        results['query_enhanced'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
except Exception as e:
    results['query_enhanced'] = test_result(False, f"Error: {str(e)}")

# Test 10: Get All Images from Document
if doc_name:
    print_test("10. Get All Images from Document")
    try:
        response = requests.post(
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 50
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            results['get_all_images'] = test_result(
                True,
                f"Retrieved {total} images",
                f"First image OCR length: {len(data.get('images', [{}])[0].get('ocr_text', '')) if data.get('images') else 0} chars"
            )
        else:
            results['get_all_images'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
    except Exception as e:
        results['get_all_images'] = test_result(False, f"Error: {str(e)}")
else:
    results['get_all_images'] = test_result(False, "No document name available")

# Test 11: Search Images by Content
print_test("11. Search Images by Content")
try:
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "drawer tools part numbers",
            "k": 10
        },
        timeout=60
    )
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        results['search_images'] = test_result(
            True,
            f"Search successful",
            f"Found {total} matching images"
        )
    else:
        results['search_images'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
except Exception as e:
    results['search_images'] = test_result(False, f"Error: {str(e)}")

# Test 12: Search Images in Specific Document
if doc_name:
    print_test("12. Search Images in Specific Document")
    try:
        response = requests.post(
            f"{API_BASE_URL}/query/images",
            json={
                "question": "tool reorder sheet",
                "source": doc_name,
                "k": 5
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            results['search_images_specific'] = test_result(
                True,
                f"Search successful",
                f"Found {total} matching images in {doc_name}"
            )
        else:
            results['search_images_specific'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
    except Exception as e:
        results['search_images_specific'] = test_result(False, f"Error: {str(e)}")
else:
    results['search_images_specific'] = test_result(False, "No document name available")

# Test 13: Search for Specific Tools
print_test("13. Search for Specific Tools")
try:
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "wire stripper socket wrench",
            "k": 5
        },
        timeout=60
    )
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        results['search_tools'] = test_result(
            True,
            f"Search successful",
            f"Found {total} images with tools"
        )
    else:
        results['search_tools'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
except Exception as e:
    results['search_tools'] = test_result(False, f"Error: {str(e)}")

# Test 14: Search for Part Numbers
print_test("14. Search for Part Numbers")
try:
    response = requests.post(
        f"{API_BASE_URL}/query/images",
        json={
            "question": "part number 65300077",
            "k": 5
        },
        timeout=60
    )
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        results['search_part_numbers'] = test_result(
            True,
            f"Search successful",
            f"Found {total} images with part numbers"
        )
    else:
        results['search_part_numbers'] = test_result(False, f"Status: {response.status_code}", response.text[:200])
except Exception as e:
    results['search_part_numbers'] = test_result(False, f"Error: {str(e)}")

# Test 15: Delete Document (cleanup)
if doc_id:
    print_test("15. Delete Document (Cleanup)")
    try:
        response = requests.delete(
            f"{API_BASE_URL}/documents/{doc_id}",
            timeout=60
        )
        results['delete'] = test_result(
            response.status_code == 204,
            f"Delete returned {response.status_code}",
            "Document deleted successfully" if response.status_code == 204 else response.text[:200]
        )
    except Exception as e:
        results['delete'] = test_result(False, f"Error: {str(e)}")
else:
    results['delete'] = test_result(False, "No document_id available for deletion")

# Summary
print("\n" + "="*70)
print("  TEST SUMMARY")
print("="*70)

total_tests = len(results)
passed_tests = sum(1 for v in results.values() if v)
failed_tests = total_tests - passed_tests

for test_name, passed in results.items():
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {test_name}")

print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
print(f"Success rate: {(passed_tests/total_tests*100):.1f}%")

# Save results
with open('POSTMAN_COLLECTION_TEST_RESULTS.json', 'w') as f:
    json.dump({
        'timestamp': datetime.now().isoformat(),
        'server': API_BASE_URL,
        'results': results,
        'summary': {
            'total': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': f"{(passed_tests/total_tests*100):.1f}%"
        }
    }, f, indent=2)

print(f"\n💾 Results saved to: POSTMAN_COLLECTION_TEST_RESULTS.json")

if passed_tests == total_tests:
    print("\n✅ ALL POSTMAN COLLECTION ENDPOINTS WORKING!")
else:
    print(f"\n⚠️  {failed_tests} endpoint(s) need attention")

