#!/usr/bin/env python3
"""
Comprehensive test suite for image endpoints
"""
import os
import sys
import requests
import json
import time
from datetime import datetime

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def print_test_header(test_name):
    print("\n" + "="*80)
    print(f"  TEST: {test_name}")
    print("="*80)

def print_result(success, message):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")

def test_1_upload_document_with_images():
    """Test 1: Upload document with images"""
    print_test_header("Upload Document with Images")
    
    pdf_path = "./FL10.11 SPECIFIC8 (1).pdf"
    if not os.path.exists(pdf_path):
        print_result(False, f"PDF file not found: {pdf_path}")
        return None
    
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
            data = response.json()
            doc_id = data.get('document_id')
            image_count = data.get('image_count', 0)
            chunks = data.get('chunks_created', 0)
            
            print_result(True, f"Document uploaded: {data.get('document_name')}")
            print(f"   Document ID: {doc_id}")
            print(f"   Images detected: {image_count}")
            print(f"   Chunks created: {chunks}")
            
            if image_count > 0:
                print_result(True, f"Images detected: {image_count}")
                return doc_id, data.get('document_name')
            else:
                print_result(False, "No images detected in document")
                return None, None
        else:
            print_result(False, f"Upload failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return None, None
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return None, None

def test_2_get_all_images(doc_name):
    """Test 2: Get all images from a document"""
    print_test_header("Get All Images from Document")
    
    if not doc_name:
        print_result(False, "No document name provided")
        return False
    
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
            images = data.get('images', [])
            
            print_result(True, f"Retrieved {total} images")
            
            if total > 0:
                print(f"   First image:")
                img = images[0]
                print(f"     - ID: {img.get('image_id')}")
                print(f"     - Source: {img.get('source')}")
                print(f"     - Page: {img.get('page')}")
                print(f"     - OCR length: {len(img.get('ocr_text', ''))} chars")
                print(f"     - OCR preview: {img.get('ocr_text', '')[:150]}...")
                
                # Verify all images have required fields
                all_valid = all(
                    img.get('image_id') and 
                    img.get('source') and 
                    img.get('ocr_text') is not None
                    for img in images
                )
                
                if all_valid:
                    print_result(True, "All images have required fields")
                else:
                    print_result(False, "Some images missing required fields")
                
                return True
            else:
                print_result(False, "No images returned")
                return False
        else:
            print_result(False, f"Request failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_3_semantic_search_images():
    """Test 3: Semantic search in images"""
    print_test_header("Semantic Search in Images")
    
    test_queries = [
        "drawer tools",
        "part numbers",
        "tool reorder sheet",
        "socket wrench"
    ]
    
    all_passed = True
    
    for query in test_queries:
        try:
            response = requests.post(
                f"{API_BASE_URL}/query/images",
                json={
                    "question": query,
                    "k": 10
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                print(f"   Query: '{query}' -> {total} results")
                
                if total > 0:
                    img = data['images'][0]
                    print(f"     Top result: {img.get('source')}, Page {img.get('page')}")
            else:
                print_result(False, f"Query '{query}' failed: {response.status_code}")
                all_passed = False
        except Exception as e:
            print_result(False, f"Query '{query}' error: {str(e)}")
            all_passed = False
    
    print_result(all_passed, "Semantic search tests")
    return all_passed

def test_4_query_with_image_questions(doc_id):
    """Test 4: Query with image-related questions via regular endpoint"""
    print_test_header("Query with Image Questions (Regular Endpoint)")
    
    test_questions = [
        "What tools are in drawer 1?",
        "What part numbers are in the tool reorder sheet?",
        "What is in drawer 2?",
        "List all tools mentioned in images"
    ]
    
    all_passed = True
    
    for question in test_questions:
        try:
            request_data = {
                "question": question,
                "k": 10
            }
            
            if doc_id:
                request_data["document_id"] = doc_id
            
            response = requests.post(
                f"{API_BASE_URL}/query",
                json=request_data,
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                citations = data.get('citations', [])
                image_citations = [c for c in citations if c.get('image_ref') or c.get('content_type') == 'image']
                
                print(f"   Question: '{question}'")
                print(f"     Answer length: {len(answer)} chars")
                print(f"     Total citations: {len(citations)}")
                print(f"     Image citations: {len(image_citations)}")
                
                if image_citations:
                    print_result(True, f"Found {len(image_citations)} image citations")
                    for cit in image_citations[:2]:
                        print(f"       - {cit.get('source')}, Page {cit.get('page')}, {cit.get('image_info')}")
                else:
                    print(f"     ⚠️  No image citations (may still use image content in answer)")
            else:
                print_result(False, f"Query failed: {response.status_code}")
                all_passed = False
        except Exception as e:
            print_result(False, f"Query error: {str(e)}")
            all_passed = False
    
    print_result(all_passed, "Image question queries")
    return all_passed

def test_5_verify_image_ocr_content(doc_name):
    """Test 5: Verify image OCR content is accessible"""
    print_test_header("Verify Image OCR Content")
    
    if not doc_name:
        print_result(False, "No document name provided")
        return False
    
    try:
        # Get all images
        response = requests.post(
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 20
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            
            if not images:
                print_result(False, "No images to verify")
                return False
            
            # Check OCR content quality
            ocr_lengths = [len(img.get('ocr_text', '')) for img in images]
            avg_length = sum(ocr_lengths) / len(ocr_lengths) if ocr_lengths else 0
            min_length = min(ocr_lengths) if ocr_lengths else 0
            max_length = max(ocr_lengths) if ocr_lengths else 0
            
            print(f"   Total images checked: {len(images)}")
            print(f"   OCR text lengths:")
            print(f"     - Average: {avg_length:.0f} chars")
            print(f"     - Min: {min_length} chars")
            print(f"     - Max: {max_length} chars")
            
            # Check for specific content patterns
            has_tools = any('tool' in img.get('ocr_text', '').lower() for img in images)
            has_drawers = any('drawer' in img.get('ocr_text', '').lower() for img in images)
            has_part_numbers = any(any(c.isdigit() for c in img.get('ocr_text', '')[:100]) for img in images)
            
            print(f"   Content patterns found:")
            print(f"     - Tools: {'✅' if has_tools else '❌'}")
            print(f"     - Drawers: {'✅' if has_drawers else '❌'}")
            print(f"     - Part numbers: {'✅' if has_part_numbers else '❌'}")
            
            # Verify at least some OCR content exists
            has_content = avg_length > 50
            print_result(has_content, f"OCR content quality (avg {avg_length:.0f} chars)")
            
            return has_content and (has_tools or has_drawers or has_part_numbers)
        else:
            print_result(False, f"Request failed: {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_6_image_metadata_verification(doc_name):
    """Test 6: Verify image metadata is complete"""
    print_test_header("Verify Image Metadata")
    
    if not doc_name:
        print_result(False, "No document name provided")
        return False
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 10
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            
            required_fields = ['image_id', 'source', 'image_number', 'ocr_text']
            optional_fields = ['page', 'metadata', 'score']
            
            all_valid = True
            for img in images:
                missing_required = [f for f in required_fields if f not in img or img[f] is None]
                if missing_required:
                    print_result(False, f"Image {img.get('image_id', 'unknown')} missing: {missing_required}")
                    all_valid = False
            
            if all_valid:
                print_result(True, f"All {len(images)} images have required metadata")
                print(f"   Required fields: {', '.join(required_fields)}")
                print(f"   Optional fields: {', '.join(optional_fields)}")
            
            return all_valid
        else:
            print_result(False, f"Request failed: {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def test_7_filter_by_source():
    """Test 7: Test filtering images by source"""
    print_test_header("Filter Images by Source")
    
    # Get list of documents
    try:
        response = requests.get(f"{API_BASE_URL}/documents", timeout=30)
        if response.status_code == 200:
            docs = response.json().get('documents', [])
            doc_with_images = next((d for d in docs if d.get('image_count', 0) > 0), None)
            
            if doc_with_images:
                doc_name = doc_with_images.get('document_name')
                
                # Test with source filter
                response = requests.post(
                    f"{API_BASE_URL}/query/images",
                    json={
                        "question": "",
                        "source": doc_name,
                        "k": 10
                    },
                    timeout=60
                )
                
                if response.status_code == 200:
                    data = response.json()
                    images = data.get('images', [])
                    
                    # Verify all images are from the specified source
                    all_match = all(
                        img.get('source') == doc_name or 
                        os.path.basename(img.get('source', '')) == os.path.basename(doc_name)
                        for img in images
                    )
                    
                    if all_match:
                        print_result(True, f"All {len(images)} images match source filter: {doc_name}")
                    else:
                        print_result(False, "Some images don't match source filter")
                    
                    return all_match
                else:
                    print_result(False, f"Request failed: {response.status_code}")
                    return False
            else:
                print_result(False, "No document with images found")
                return False
        else:
            print_result(False, f"Failed to get documents: {response.status_code}")
            return False
    except Exception as e:
        print_result(False, f"Error: {str(e)}")
        return False

def main():
    print("\n" + "="*80)
    print("  COMPREHENSIVE IMAGE API TEST SUITE")
    print("="*80)
    print(f"Server: {API_BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Test 1: Upload document
    doc_id, doc_name = test_1_upload_document_with_images()
    results['upload'] = doc_id is not None
    
    if doc_id:
        # Wait for processing
        print("\n⏳ Waiting 10 seconds for image processing...")
        time.sleep(10)
        
        # Test 2: Get all images
        results['get_all_images'] = test_2_get_all_images(doc_name)
        
        # Test 3: Semantic search
        results['semantic_search'] = test_3_semantic_search_images()
        
        # Test 4: Query with image questions
        results['image_queries'] = test_4_query_with_image_questions(doc_id)
        
        # Test 5: Verify OCR content
        results['ocr_content'] = test_5_verify_image_ocr_content(doc_name)
        
        # Test 6: Metadata verification
        results['metadata'] = test_6_image_metadata_verification(doc_name)
        
        # Test 7: Source filtering
        results['source_filter'] = test_7_filter_by_source()
    else:
        print("\n⚠️  Skipping image tests - document upload failed")
        results['get_all_images'] = False
        results['semantic_search'] = False
        results['image_queries'] = False
        results['ocr_content'] = False
        results['metadata'] = False
        results['source_filter'] = False
    
    # Summary
    print("\n" + "="*80)
    print("  TEST SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    print(f"Success rate: {(passed_tests/total_tests*100):.1f}%")
    
    # Save results
    with open('IMAGE_TEST_RESULTS.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'server': API_BASE_URL,
            'results': results,
            'summary': {
                'total': total_tests,
                'passed': passed_tests,
                'failed': total_tests - passed_tests,
                'success_rate': f"{(passed_tests/total_tests*100):.1f}%"
            }
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: IMAGE_TEST_RESULTS.json")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if passed_tests == total_tests:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed")

if __name__ == "__main__":
    main()



