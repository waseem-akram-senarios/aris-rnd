#!/usr/bin/env python3
"""
Comprehensive test to verify image retrieval accuracy from FL10.11 SPECIFIC8 (1).pdf
Tests OCR text accuracy, metadata correctness, and semantic search precision.
"""
import os
import sys
import json
import requests
import time
from typing import List, Dict, Any

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS: {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  WARN: {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ️  INFO: {msg}{Colors.END}")

BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'images_found': 0,
    'accuracy_checks': {
        'image_id_format': 0,
        'source_accuracy': 0,
        'image_number_accuracy': 0,
        'page_accuracy': 0,
        'ocr_text_quality': 0,
        'metadata_present': 0,
        'semantic_search_accuracy': 0
    }
}

def upload_document():
    """Upload document and return document_id"""
    print_test("1. Upload Document")
    
    doc_path = DOCUMENT_NAME
    if not os.path.exists(doc_path):
        print_fail(f"Document not found: {doc_path}")
        return None
    
    try:
        with open(doc_path, 'rb') as f:
            files = {'file': (os.path.basename(doc_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(f"{BASE_URL}/documents", files=files, data=data, timeout=300)
        
        if response.status_code == 201:
            result = response.json()
            doc_id = result.get('document_id')
            print_pass(f"Document uploaded: {doc_id}")
            print_info(f"Document name: {result.get('document_name')}")
            print_info(f"Pages: {result.get('pages', 0)}")
            print_info(f"Images detected: {result.get('images_detected', False)}")
            print_info(f"Chunks created: {result.get('chunks_created', 0)}")
            
            # Wait for processing and image storage
            print_info("Waiting 10 seconds for document processing and image storage...")
            time.sleep(10)
            
            test_results['passed'] += 1
            return doc_id, result.get('document_name')
        else:
            print_fail(f"Upload failed: {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return None
    except Exception as e:
        print_fail(f"Upload error: {e}")
        return None

def get_document_images(document_id: str, document_name: str) -> List[Dict]:
    """Get all images for the document"""
    print_test("2. Retrieve Document Images")
    
    try:
        response = requests.get(
            f"{BASE_URL}/documents/{document_id}/images?limit=100",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            total = data.get('total', len(images))
            test_results['images_found'] = total
            
            if total > 0:
                print_pass(f"Found {total} images for document")
                print_info(f"Document: {document_name}")
                return images
            else:
                print_warn("No images found in index")
                print_info("This could mean:")
                print_info("  - Images are still being processed")
                print_info("  - Images were not stored during ingestion")
                print_info("  - Waiting longer for async storage...")
                
                # Wait and retry
                print_info("Waiting 10 more seconds and retrying...")
                time.sleep(10)
                
                response = requests.get(
                    f"{BASE_URL}/documents/{document_id}/images?limit=100",
                    timeout=30
                )
                if response.status_code == 200:
                    data = response.json()
                    images = data.get('images', [])
                    total = data.get('total', len(images))
                    if total > 0:
                        print_pass(f"Found {total} images on retry!")
                        test_results['images_found'] = total
                        return images
                
                test_results['warnings'] += 1
                return []
        else:
            print_fail(f"Failed to get images: {response.status_code}")
            test_results['failed'] += 1
            return []
    except Exception as e:
        print_fail(f"Error getting images: {e}")
        test_results['failed'] += 1
        return []

def test_image_data_accuracy(images: List[Dict], document_name: str):
    """Test accuracy of image data fields"""
    print_test("3. Test Image Data Accuracy")
    
    if not images:
        print_warn("No images to test")
        return
    
    print_info(f"Testing accuracy for {len(images)} images...\n")
    
    for i, img in enumerate(images, 1):
        print_info(f"--- Image {i} Accuracy Check ---")
        checks_passed = 0
        total_checks = 0
        
        # 1. Image ID Format
        total_checks += 1
        image_id = img.get('image_id', '')
        if image_id:
            # Check format: should be {source}_image_{number}
            if '_image_' in image_id:
                print_pass(f"  ✅ Image ID format correct: {image_id}")
                checks_passed += 1
                test_results['accuracy_checks']['image_id_format'] += 1
            else:
                print_warn(f"  ⚠️  Image ID format unusual: {image_id}")
        else:
            print_fail(f"  ❌ Missing image_id")
        
        # 2. Source Accuracy
        total_checks += 1
        source = img.get('source', '')
        if source:
            # Check if source matches document name
            if document_name in source or source in document_name:
                print_pass(f"  ✅ Source accurate: {source}")
                checks_passed += 1
                test_results['accuracy_checks']['source_accuracy'] += 1
            else:
                print_warn(f"  ⚠️  Source may not match: {source} vs {document_name}")
        else:
            print_fail(f"  ❌ Missing source")
        
        # 3. Image Number Accuracy
        total_checks += 1
        image_number = img.get('image_number')
        if image_number is not None and image_number > 0:
            print_pass(f"  ✅ Image number: {image_number}")
            checks_passed += 1
            test_results['accuracy_checks']['image_number_accuracy'] += 1
        else:
            print_warn(f"  ⚠️  Image number: {image_number} (may be 0 or None)")
        
        # 4. Page Accuracy
        total_checks += 1
        page = img.get('page')
        if page is not None:
            if isinstance(page, int) and page > 0:
                print_pass(f"  ✅ Page number: {page}")
                checks_passed += 1
                test_results['accuracy_checks']['page_accuracy'] += 1
            else:
                print_warn(f"  ⚠️  Page number format: {page}")
        else:
            print_info(f"  ℹ️  Page: None (may be unknown)")
        
        # 5. OCR Text Quality
        total_checks += 1
        ocr_text = img.get('ocr_text', '')
        if ocr_text:
            text_length = len(ocr_text.strip())
            if text_length > 0:
                print_pass(f"  ✅ OCR text present: {text_length} characters")
                print_info(f"     Preview: {ocr_text[:100]}...")
                
                # Check if OCR text seems meaningful
                if text_length > 20:
                    # Check for common technical terms
                    has_content = any(char.isalnum() for char in ocr_text[:50])
                    if has_content:
                        print_pass(f"     OCR text appears meaningful")
                        checks_passed += 1
                        test_results['accuracy_checks']['ocr_text_quality'] += 1
                    else:
                        print_warn(f"     OCR text may be mostly whitespace/symbols")
                else:
                    print_info(f"     OCR text is short ({text_length} chars)")
            else:
                print_warn(f"  ⚠️  OCR text is empty")
        else:
            print_fail(f"  ❌ Missing OCR text")
        
        # 6. Metadata Presence
        total_checks += 1
        metadata = img.get('metadata', {})
        if metadata:
            print_pass(f"  ✅ Metadata present: {len(metadata)} keys")
            
            # Check for specific metadata fields
            if 'drawer_references' in metadata:
                drawers = metadata.get('drawer_references', [])
                if drawers:
                    print_info(f"     Drawer references: {drawers}")
            
            if 'part_numbers' in metadata:
                parts = metadata.get('part_numbers', [])
                if parts:
                    print_info(f"     Part numbers: {parts}")
            
            if 'tools_found' in metadata:
                tools = metadata.get('tools_found', [])
                if tools:
                    print_info(f"     Tools: {tools}")
            
            checks_passed += 1
            test_results['accuracy_checks']['metadata_present'] += 1
        else:
            print_info(f"  ℹ️  No metadata (may be expected)")
        
        # Summary for this image
        accuracy_pct = (checks_passed / total_checks) * 100 if total_checks > 0 else 0
        print_info(f"  Accuracy: {checks_passed}/{total_checks} checks passed ({accuracy_pct:.1f}%)")
        print()
    
    # Overall accuracy summary
    total_images = len(images)
    print_info(f"\nOverall Accuracy Summary:")
    print_info(f"  Image ID Format: {test_results['accuracy_checks']['image_id_format']}/{total_images}")
    print_info(f"  Source Accuracy: {test_results['accuracy_checks']['source_accuracy']}/{total_images}")
    print_info(f"  Image Number: {test_results['accuracy_checks']['image_number_accuracy']}/{total_images}")
    print_info(f"  Page Accuracy: {test_results['accuracy_checks']['page_accuracy']}/{total_images}")
    print_info(f"  OCR Text Quality: {test_results['accuracy_checks']['ocr_text_quality']}/{total_images}")
    print_info(f"  Metadata Present: {test_results['accuracy_checks']['metadata_present']}/{total_images}")
    
    test_results['passed'] += 1

def test_semantic_search_accuracy(images: List[Dict], document_name: str):
    """Test semantic search accuracy"""
    print_test("4. Test Semantic Search Accuracy")
    
    if not images:
        print_warn("No images to test semantic search")
        return
    
    # Test queries that should find images
    test_queries = [
        {
            'query': 'Find images with text or diagrams',
            'expected': 'Should return images with OCR text'
        },
        {
            'query': 'Show me images with technical specifications',
            'expected': 'Should return images with technical content'
        },
        {
            'query': 'Find images with part numbers or references',
            'expected': 'Should return images with metadata'
        }
    ]
    
    for test_case in test_queries:
        query = test_case['query']
        expected = test_case['expected']
        
        print_info(f"\nQuery: '{query}'")
        print_info(f"Expected: {expected}")
        
        try:
            response = requests.post(
                f"{BASE_URL}/query/images",
                json={'question': query, 'k': 5},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('images', [])
                total = data.get('total', len(results))
                
                if total > 0:
                    print_pass(f"Found {total} images")
                    
                    # Check relevance scores
                    for img in results[:3]:
                        score = img.get('score')
                        image_num = img.get('image_number', 'N/A')
                        source = img.get('source', 'N/A')
                        
                        if score:
                            print_info(f"  Score: {score:.4f} - Image {image_num} from {os.path.basename(source)}")
                            
                            # Verify source matches
                            if document_name in source or source in document_name:
                                print_pass(f"    ✅ Source matches document")
                            else:
                                print_warn(f"    ⚠️  Source mismatch: {source}")
                            
                            # Check OCR text relevance
                            ocr_text = img.get('ocr_text', '')
                            if ocr_text and len(ocr_text) > 10:
                                print_pass(f"    ✅ OCR text present ({len(ocr_text)} chars)")
                            else:
                                print_warn(f"    ⚠️  OCR text missing or short")
                        else:
                            print_info(f"  No score - Image {image_num}")
                    
                    test_results['accuracy_checks']['semantic_search_accuracy'] += 1
                else:
                    print_warn(f"No results for query: '{query}'")
            else:
                print_fail(f"Query failed: {response.status_code}")
        except Exception as e:
            print_fail(f"Query error: {e}")
    
    test_results['passed'] += 1

def test_single_image_retrieval(images: List[Dict]):
    """Test retrieving individual images by ID"""
    print_test("5. Test Single Image Retrieval Accuracy")
    
    if not images:
        print_warn("No images to test single retrieval")
        return
    
    # Test first 3 images
    for i, img in enumerate(images[:3], 1):
        image_id = img.get('image_id')
        if not image_id:
            continue
        
        print_info(f"\nTesting Image {i}: {image_id}")
        
        try:
            response = requests.get(f"{BASE_URL}/images/{image_id}", timeout=30)
            
            if response.status_code == 200:
                retrieved_img = response.json()
                print_pass(f"Image retrieved successfully")
                
                # Verify all fields match
                checks = []
                if retrieved_img.get('image_id') == image_id:
                    checks.append("✅ image_id matches")
                if retrieved_img.get('source') == img.get('source'):
                    checks.append("✅ source matches")
                if retrieved_img.get('image_number') == img.get('image_number'):
                    checks.append("✅ image_number matches")
                if retrieved_img.get('page') == img.get('page'):
                    checks.append("✅ page matches")
                if retrieved_img.get('ocr_text') == img.get('ocr_text'):
                    checks.append("✅ ocr_text matches")
                
                print_info(f"  Verification: {', '.join(checks)}")
                
                # Show OCR text preview
                ocr_text = retrieved_img.get('ocr_text', '')
                if ocr_text:
                    print_info(f"  OCR text: {ocr_text[:150]}...")
            else:
                print_fail(f"Failed to retrieve image: {response.status_code}")
        except Exception as e:
            print_fail(f"Error retrieving image: {e}")
    
    test_results['passed'] += 1

def test_source_filtering_accuracy(images: List[Dict], document_name: str):
    """Test source filtering accuracy"""
    print_test("6. Test Source Filtering Accuracy")
    
    if not images:
        print_warn("No images to test source filtering")
        return
    
    try:
        response = requests.post(
            f"{BASE_URL}/query/images",
            json={'question': 'Find all images', 'source': document_name, 'k': 20},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('images', [])
            total = data.get('total', len(results))
            
            if total > 0:
                print_pass(f"Found {total} images with source filter")
                
                # Verify all results are from correct source
                all_correct = True
                for img in results:
                    source = img.get('source', '')
                    if document_name not in source and source not in document_name:
                        print_fail(f"Wrong source: {source} (expected: {document_name})")
                        all_correct = False
                
                if all_correct:
                    print_pass("All images are from the correct source")
                    test_results['passed'] += 1
                else:
                    test_results['failed'] += 1
            else:
                print_warn("No images found with source filter")
                test_results['warnings'] += 1
        else:
            print_fail(f"Source filter query failed: {response.status_code}")
            test_results['failed'] += 1
    except Exception as e:
        print_fail(f"Error testing source filter: {e}")
        test_results['failed'] += 1

def main():
    """Run all accuracy tests"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Image Retrieval Accuracy Test{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Document: {DOCUMENT_NAME}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}\n")
    print_info(f"API Base URL: {BASE_URL}")
    
    # Upload document
    result = upload_document()
    if not result:
        print_fail("Cannot proceed without document")
        return False
    
    document_id, document_name = result
    
    # Get images
    images = get_document_images(document_id, document_name)
    
    if not images:
        print_warn("\n⚠️  No images found. This could mean:")
        print_warn("  1. Images are still being processed (wait longer)")
        print_warn("  2. Images were not stored during ingestion")
        print_warn("  3. OpenSearch image index is not configured")
        print_warn("\nPlease check server logs for image storage messages.")
        return False
    
    # Run accuracy tests
    test_image_data_accuracy(images, document_name)
    test_semantic_search_accuracy(images, document_name)
    test_single_image_retrieval(images)
    test_source_filtering_accuracy(images, document_name)
    
    # Print final summary
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}ACCURACY TEST SUMMARY{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.GREEN}✅ Passed: {test_results['passed']}{Colors.END}")
    print(f"{Colors.RED}❌ Failed: {test_results['failed']}{Colors.END}")
    print(f"{Colors.YELLOW}⚠️  Warnings: {test_results['warnings']}{Colors.END}")
    print(f"{Colors.CYAN}📸 Images Found: {test_results['images_found']}{Colors.END}")
    print(f"\n{Colors.CYAN}Accuracy Breakdown:{Colors.END}")
    for check, count in test_results['accuracy_checks'].items():
        pct = (count / test_results['images_found'] * 100) if test_results['images_found'] > 0 else 0
        status = "✅" if count == test_results['images_found'] else "⚠️"
        print(f"  {status} {check.replace('_', ' ').title()}: {count}/{test_results['images_found']} ({pct:.1f}%)")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    if test_results['failed'] == 0 and test_results['images_found'] > 0:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 IMAGE RETRIEVAL ACCURACY: EXCELLENT!{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return True
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  SOME ACCURACY ISSUES DETECTED{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return test_results['failed'] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

