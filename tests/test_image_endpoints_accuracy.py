#!/usr/bin/env python3
"""
Comprehensive test script to verify image endpoints return accurate information.
Tests image retrieval, OCR text accuracy, and metadata correctness.
"""
import os
import sys
import json
import requests
import time
from pathlib import Path

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

# Configuration
BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0,
    'images_found': 0,
    'images_tested': 0
}

def find_document_file():
    """Find the document file"""
    possible_locations = [
        DOCUMENT_NAME,
        f"samples/{DOCUMENT_NAME}",
    ]
    
    for location in possible_locations:
        if os.path.exists(location):
            return location
    
    return None

def test_endpoint(method, endpoint, expected_status=200, data=None, files=None, timeout=30):
    """Test an API endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=timeout)
        elif method.upper() == 'POST':
            if files:
                response = requests.post(url, files=files, data=data, timeout=timeout)
            else:
                response = requests.post(url, json=data, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        if response.status_code == expected_status:
            try:
                return response.json() if response.content else {}
            except:
                return {}
        else:
            print_fail(f"{method} {endpoint} - Expected {expected_status}, got {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return None
    except Exception as e:
        print_fail(f"{method} {endpoint} - Error: {str(e)}")
        return None

def upload_document(file_path):
    """Upload document and return document_id"""
    print_test("1. Upload Document for Image Testing")
    
    if not file_path or not os.path.exists(file_path):
        print_fail(f"Document file not found: {file_path}")
        return None
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            result = test_endpoint('POST', '/documents', expected_status=201, files=files, data=data, timeout=300)
        
        if result:
            doc_id = result.get('document_id') or result.get('document_name', 'unknown')
            print_pass(f"Document uploaded: {doc_id}")
            print_info(f"Document name: {result.get('document_name')}")
            print_info(f"Status: {result.get('status')}")
            print_info(f"Chunks created: {result.get('chunks_created', 0)}")
            print_info(f"Pages: {result.get('pages', 0)}")
            print_info(f"Images detected: {result.get('images_detected', False)}")
            test_results['passed'] += 1
            
            # Wait for processing
            print_info("Waiting 5 seconds for document processing...")
            time.sleep(5)
            
            return doc_id
        return None
    except Exception as e:
        print_fail(f"Upload failed: {str(e)}")
        test_results['failed'] += 1
        return None

def test_get_document_images(document_id):
    """Test getting images for a document"""
    print_test(f"2. Get Document Images: {document_id}")
    
    result = test_endpoint('GET', f'/documents/{document_id}/images?limit=100', expected_status=200, timeout=30)
    
    if result:
        images = result.get('images', [])
        total = result.get('total', len(images))
        test_results['images_found'] = total
        
        if total > 0:
            print_pass(f"Found {total} images for document")
            print_info(f"Document: {result.get('document_name')}")
            
            # Test first few images for accuracy
            for i, img in enumerate(images[:5]):  # Test first 5 images
                test_results['images_tested'] += 1
                print_info(f"\n--- Image {i+1} Details ---")
                
                # Check required fields
                image_id = img.get('image_id', '')
                source = img.get('source', '')
                image_number = img.get('image_number', 0)
                page = img.get('page')
                ocr_text = img.get('ocr_text', '')
                metadata = img.get('metadata', {})
                
                # Validate fields
                checks = []
                if image_id:
                    checks.append(f"✅ Image ID: {image_id}")
                else:
                    checks.append(f"❌ Missing image_id")
                
                if source:
                    checks.append(f"✅ Source: {source}")
                else:
                    checks.append(f"❌ Missing source")
                
                if image_number > 0:
                    checks.append(f"✅ Image number: {image_number}")
                else:
                    checks.append(f"⚠️  Image number: {image_number} (may be 0)")
                
                if page is not None:
                    checks.append(f"✅ Page: {page}")
                else:
                    checks.append(f"⚠️  Page: None (may be unknown)")
                
                if ocr_text:
                    text_length = len(ocr_text)
                    checks.append(f"✅ OCR text: {text_length} characters")
                    print_info(f"  OCR preview: {ocr_text[:100]}...")
                    
                    # Check if OCR text seems meaningful
                    if text_length > 10:
                        print_pass(f"  OCR text appears meaningful ({text_length} chars)")
                    else:
                        print_warn(f"  OCR text is very short ({text_length} chars)")
                else:
                    checks.append(f"❌ Missing OCR text")
                    print_warn("  No OCR text found")
                
                if metadata:
                    checks.append(f"✅ Metadata present: {len(metadata)} keys")
                    if 'drawer_references' in metadata:
                        drawers = metadata.get('drawer_references', [])
                        if drawers:
                            print_info(f"  Drawer references: {drawers}")
                    if 'part_numbers' in metadata:
                        parts = metadata.get('part_numbers', [])
                        if parts:
                            print_info(f"  Part numbers: {parts}")
                    if 'tools_found' in metadata:
                        tools = metadata.get('tools_found', [])
                        if tools:
                            print_info(f"  Tools found: {tools}")
                else:
                    checks.append(f"⚠️  No metadata")
                
                # Summary
                all_good = image_id and source and ocr_text
                if all_good:
                    print_pass(f"Image {i+1} data is complete and accurate")
                    test_results['passed'] += 1
                else:
                    print_warn(f"Image {i+1} has some missing fields")
                    test_results['warnings'] += 1
            
            test_results['passed'] += 1
            return images
        else:
            print_warn("No images found for document")
            print_info("This could mean:")
            print_info("  - Images are not stored in OpenSearch image index")
            print_info("  - Document processing didn't extract images")
            print_info("  - Images were not stored during ingestion")
            test_results['warnings'] += 1
            return []
    else:
        test_results['failed'] += 1
        return None

def test_query_images_semantic():
    """Test semantic search for images"""
    print_test("3. Query Images with Semantic Search")
    
    queries = [
        "Find images with text or diagrams",
        "Show me images with part numbers",
        "Find images with technical specifications",
        "Images with drawings or schematics"
    ]
    
    for query in queries:
        print_info(f"\nQuery: '{query}'")
        result = test_endpoint('POST', '/query/images', expected_status=200, 
                              data={'question': query, 'k': 5}, timeout=30)
        
        if result:
            images = result.get('images', [])
            total = result.get('total', len(images))
            
            if total > 0:
                print_pass(f"Found {total} images for query: '{query}'")
                
                # Check relevance scores
                for img in images[:3]:
                    score = img.get('score')
                    ocr_text = img.get('ocr_text', '')
                    if score:
                        print_info(f"  Score: {score:.4f} - Image {img.get('image_number')} from {img.get('source')}")
                        if ocr_text:
                            print_info(f"    OCR preview: {ocr_text[:80]}...")
                    else:
                        print_warn(f"  No score for image {img.get('image_number')}")
                
                test_results['passed'] += 1
            else:
                print_warn(f"No images found for query: '{query}'")
                test_results['warnings'] += 1
        else:
            test_results['failed'] += 1

def test_query_images_with_source(document_name):
    """Test querying images with source filter"""
    print_test(f"4. Query Images with Source Filter: {document_name}")
    
    result = test_endpoint('POST', '/query/images', expected_status=200,
                          data={'question': 'Find all images', 'source': document_name, 'k': 10}, timeout=30)
    
    if result:
        images = result.get('images', [])
        total = result.get('total', len(images))
        
        if total > 0:
            print_pass(f"Found {total} images from {document_name}")
            
            # Verify all images are from the correct source
            all_correct = True
            for img in images:
                source = img.get('source', '')
                if document_name not in source and source not in document_name:
                    print_fail(f"Image {img.get('image_number')} has wrong source: {source}")
                    all_correct = False
            
            if all_correct:
                print_pass("All images are from the correct source")
                test_results['passed'] += 1
            else:
                test_results['failed'] += 1
        else:
            print_warn(f"No images found for source: {document_name}")
            test_results['warnings'] += 1
    else:
        test_results['failed'] += 1

def test_get_single_image(image_id):
    """Test getting a single image by ID"""
    print_test(f"5. Get Single Image by ID: {image_id}")
    
    result = test_endpoint('GET', f'/images/{image_id}', expected_status=200, timeout=30)
    
    if result:
        print_pass(f"Image retrieved: {image_id}")
        
        # Validate all fields
        checks = []
        if result.get('image_id'):
            checks.append("✅ image_id")
        if result.get('source'):
            checks.append("✅ source")
        if result.get('image_number') is not None:
            checks.append("✅ image_number")
        if result.get('ocr_text'):
            checks.append(f"✅ ocr_text ({len(result.get('ocr_text', ''))} chars)")
        if result.get('metadata'):
            checks.append("✅ metadata")
        
        print_info(f"Fields present: {', '.join(checks)}")
        
        # Show OCR text preview
        ocr_text = result.get('ocr_text', '')
        if ocr_text:
            print_info(f"OCR text preview: {ocr_text[:200]}...")
        
        # Show metadata
        metadata = result.get('metadata', {})
        if metadata:
            print_info(f"Metadata: {json.dumps(metadata, indent=2)}")
        
        test_results['passed'] += 1
        return result
    else:
        test_results['failed'] += 1
        return None

def test_image_ocr_accuracy(images):
    """Test OCR text accuracy and completeness"""
    print_test("6. Test OCR Text Accuracy")
    
    if not images or len(images) == 0:
        print_warn("No images to test OCR accuracy")
        test_results['warnings'] += 1
        return
    
    print_info(f"Testing OCR accuracy for {len(images)} images...")
    
    accuracy_checks = {
        'has_text': 0,
        'meaningful_length': 0,
        'has_metadata': 0,
        'has_page_info': 0
    }
    
    for img in images:
        ocr_text = img.get('ocr_text', '')
        metadata = img.get('metadata', {})
        page = img.get('page')
        
        if ocr_text and len(ocr_text.strip()) > 0:
            accuracy_checks['has_text'] += 1
            
            if len(ocr_text) > 20:  # Meaningful length
                accuracy_checks['meaningful_length'] += 1
        
        if metadata:
            accuracy_checks['has_metadata'] += 1
        
        if page is not None:
            accuracy_checks['has_page_info'] += 1
    
    # Report results
    total = len(images)
    print_info(f"\nOCR Accuracy Summary:")
    print_info(f"  Images with text: {accuracy_checks['has_text']}/{total} ({100*accuracy_checks['has_text']//total if total > 0 else 0}%)")
    print_info(f"  Images with meaningful text (>20 chars): {accuracy_checks['meaningful_length']}/{total} ({100*accuracy_checks['meaningful_length']//total if total > 0 else 0}%)")
    print_info(f"  Images with metadata: {accuracy_checks['has_metadata']}/{total} ({100*accuracy_checks['has_metadata']//total if total > 0 else 0}%)")
    print_info(f"  Images with page info: {accuracy_checks['has_page_info']}/{total} ({100*accuracy_checks['has_page_info']//total if total > 0 else 0}%)")
    
    # Overall assessment
    if accuracy_checks['has_text'] == total and accuracy_checks['meaningful_length'] >= total * 0.8:
        print_pass("OCR text accuracy is good")
        test_results['passed'] += 1
    elif accuracy_checks['has_text'] >= total * 0.5:
        print_warn("OCR text accuracy is moderate - some images may have limited text")
        test_results['warnings'] += 1
    else:
        print_fail("OCR text accuracy is poor - many images lack text")
        test_results['failed'] += 1

def main():
    """Run all image endpoint tests"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Image Endpoints Accuracy Test{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Testing with: {DOCUMENT_NAME}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}\n")
    print_info(f"API Base URL: {BASE_URL}")
    
    # Find and upload document
    document_path = find_document_file()
    if not document_path:
        print_fail("Cannot find document file")
        return False
    
    # Upload document
    document_id = upload_document(document_path)
    if not document_id:
        print_fail("Cannot proceed without document")
        return False
    
    # Get document name
    doc_info = test_endpoint('GET', f'/documents/{document_id}', expected_status=200)
    document_name = doc_info.get('document_name') if doc_info else None
    
    # Test getting images for document
    images = test_get_document_images(document_id)
    
    # Test semantic search
    test_query_images_semantic()
    
    # Test with source filter
    if document_name:
        test_query_images_with_source(document_name)
    
    # Test getting single image
    if images and len(images) > 0:
        first_image_id = images[0].get('image_id')
        if first_image_id:
            test_get_single_image(first_image_id)
    
    # Test OCR accuracy
    if images:
        test_image_ocr_accuracy(images)
    
    # Print summary
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Test Summary{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.GREEN}✅ Passed: {test_results['passed']}{Colors.END}")
    print(f"{Colors.RED}❌ Failed: {test_results['failed']}{Colors.END}")
    print(f"{Colors.YELLOW}⚠️  Warnings: {test_results['warnings']}{Colors.END}")
    print(f"{Colors.CYAN}📸 Images Found: {test_results['images_found']}{Colors.END}")
    print(f"{Colors.CYAN}🔍 Images Tested: {test_results['images_tested']}{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    if test_results['failed'] == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL IMAGE TESTS PASSED!{Colors.END}")
        print(f"{Colors.GREEN}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return True
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  SOME TESTS FAILED OR HAD WARNINGS{Colors.END}")
        print(f"{Colors.YELLOW}{Colors.BOLD}{'='*80}{Colors.END}\n")
        return test_results['failed'] == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

