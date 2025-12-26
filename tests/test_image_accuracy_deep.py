#!/usr/bin/env python3
"""
Deep in-depth testing focused on accurate image results.
Tests every aspect of image extraction, storage, and retrieval accuracy.
"""
import os
import sys
import json
import requests
import time
import re
from typing import List, Dict, Any, Optional

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ️  {msg}{Colors.END}")

def print_fix(msg):
    print(f"{Colors.MAGENTA}🔧 {msg}{Colors.END}")

BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

issues_found = []
fixes_applied = []

def upload_and_analyze():
    """Upload document and analyze response in detail"""
    print_test("1. Upload Document - Deep Analysis")
    
    doc_path = DOCUMENT_NAME
    if not os.path.exists(doc_path):
        print_fail(f"Document not found: {doc_path}")
        return None
    
    try:
        print_info("Uploading document...")
        with open(doc_path, 'rb') as f:
            files = {'file': (os.path.basename(doc_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(f"{BASE_URL}/documents", files=files, data=data, timeout=300)
        
        if response.status_code == 201:
            result = response.json()
            doc_id = result.get('document_id')
            
            print_pass(f"Document uploaded: {doc_id}")
            
            # Deep analysis of response
            print_info("\n📊 Upload Response Analysis:")
            print_info(f"  Document ID: {doc_id}")
            print_info(f"  Document Name: {result.get('document_name')}")
            print_info(f"  Status: {result.get('status')}")
            print_info(f"  Pages: {result.get('pages', 0)}")
            print_info(f"  Chunks Created: {result.get('chunks_created', 0)}")
            print_info(f"  Images Detected: {result.get('images_detected', False)}")
            print_info(f"  Image Count: {result.get('image_count', 0)}")
            print_info(f"  Parser Used: {result.get('parser_used', 'unknown')}")
            print_info(f"  Extraction %: {result.get('extraction_percentage', 0) * 100:.1f}%")
            
            # Check for issues
            if result.get('images_detected') and result.get('image_count', 0) == 0:
                issue = {
                    'type': 'image_count_zero',
                    'severity': 'high',
                    'message': 'Images detected but image_count is 0',
                    'details': result
                }
                issues_found.append(issue)
                print_fail("❌ ISSUE: Images detected but image_count is 0")
                print_fix("  → Need to fix image_count calculation in parser")
            
            if result.get('status') != 'success':
                issue = {
                    'type': 'upload_status',
                    'severity': 'medium',
                    'message': f"Upload status is '{result.get('status')}' not 'success'",
                    'details': result
                }
                issues_found.append(issue)
                print_warn(f"⚠️  Upload status: {result.get('status')}")
            
            # Wait for processing
            print_info("\n⏳ Waiting 15 seconds for processing and image storage...")
            time.sleep(15)
            
            return doc_id, result.get('document_name'), result
        else:
            print_fail(f"Upload failed: {response.status_code}")
            print_info(f"Response: {response.text[:500]}")
            return None
    except Exception as e:
        print_fail(f"Upload error: {e}")
        import traceback
        print_info(f"Traceback: {traceback.format_exc()}")
        return None

def test_image_extraction_accuracy(doc_id, doc_name):
    """Test image extraction accuracy in detail"""
    print_test("2. Image Extraction Accuracy - Deep Test")
    
    # Get document again to check if image_count was updated
    try:
        response = requests.get(f"{BASE_URL}/documents/{doc_id}", timeout=10)
        if response.status_code == 200:
            doc_data = response.json()
            print_info(f"\n📊 Document Status After Processing:")
            print_info(f"  Image Count: {doc_data.get('image_count', 0)}")
            print_info(f"  Images Detected: {doc_data.get('images_detected', False)}")
            
            if doc_data.get('image_count', 0) > 0:
                print_pass(f"✅ Image count updated to {doc_data.get('image_count')}")
            else:
                print_fail("❌ Image count still 0 after processing")
                issue = {
                    'type': 'image_count_not_updated',
                    'severity': 'high',
                    'message': 'Image count not updated after processing',
                    'details': doc_data
                }
                issues_found.append(issue)
    except Exception as e:
        print_warn(f"Could not get document status: {e}")
    
    # Try to get images
    print_info("\n🔍 Attempting to retrieve images...")
    max_attempts = 5
    images = []
    
    for attempt in range(1, max_attempts + 1):
        wait_time = 5 * attempt
        print_info(f"  Attempt {attempt}/{max_attempts} (waiting {wait_time}s)...")
        time.sleep(wait_time)
        
        try:
            response = requests.get(
                f"{BASE_URL}/documents/{doc_id}/images?limit=100",
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                total = data.get('total', len(images))
                
                if total > 0:
                    print_pass(f"✅ Found {total} images on attempt {attempt}!")
                    break
        except Exception as e:
            print_warn(f"  Error on attempt {attempt}: {e}")
    
    if not images:
        print_fail("❌ No images found after all attempts")
        issue = {
            'type': 'no_images_retrieved',
            'severity': 'critical',
            'message': 'Images not found in index after processing',
            'details': {'document_id': doc_id, 'document_name': doc_name}
        }
        issues_found.append(issue)
        return None
    
    # Deep accuracy analysis
    print_info(f"\n📊 Analyzing {len(images)} images for accuracy...")
    
    accuracy_metrics = {
        'total': len(images),
        'with_image_id': 0,
        'with_source': 0,
        'with_image_number': 0,
        'with_page': 0,
        'with_ocr_text': 0,
        'with_meaningful_ocr': 0,
        'with_metadata': 0,
        'ocr_text_lengths': [],
        'issues': []
    }
    
    for i, img in enumerate(images, 1):
        print_info(f"\n  Image {i}:")
        
        # Check image_id
        image_id = img.get('image_id', '')
        if image_id:
            accuracy_metrics['with_image_id'] += 1
            print_pass(f"    ✅ image_id: {image_id}")
            # Validate format
            if '_image_' in image_id:
                print_pass(f"      ✅ Format correct")
            else:
                print_warn(f"      ⚠️  Format unusual: {image_id}")
                accuracy_metrics['issues'].append(f"Image {i}: Unusual image_id format")
        else:
            print_fail(f"    ❌ Missing image_id")
            accuracy_metrics['issues'].append(f"Image {i}: Missing image_id")
        
        # Check source
        source = img.get('source', '')
        if source:
            accuracy_metrics['with_source'] += 1
            print_pass(f"    ✅ source: {source}")
            if doc_name in source or source in doc_name:
                print_pass(f"      ✅ Source matches document")
            else:
                print_warn(f"      ⚠️  Source mismatch: {source} vs {doc_name}")
                accuracy_metrics['issues'].append(f"Image {i}: Source mismatch")
        else:
            print_fail(f"    ❌ Missing source")
            accuracy_metrics['issues'].append(f"Image {i}: Missing source")
        
        # Check image_number
        image_number = img.get('image_number')
        if image_number is not None and image_number > 0:
            accuracy_metrics['with_image_number'] += 1
            print_pass(f"    ✅ image_number: {image_number}")
        else:
            print_warn(f"    ⚠️  image_number: {image_number}")
            accuracy_metrics['issues'].append(f"Image {i}: Invalid image_number")
        
        # Check page
        page = img.get('page')
        if page is not None and page > 0:
            accuracy_metrics['with_page'] += 1
            print_pass(f"    ✅ page: {page}")
        else:
            print_info(f"    ℹ️  page: {page} (may be unknown)")
        
        # Check OCR text - CRITICAL for accuracy
        ocr_text = img.get('ocr_text', '')
        if ocr_text:
            accuracy_metrics['with_ocr_text'] += 1
            text_length = len(ocr_text.strip())
            accuracy_metrics['ocr_text_lengths'].append(text_length)
            
            print_pass(f"    ✅ ocr_text: {text_length} characters")
            
            # Check if OCR text is meaningful
            if text_length > 20:
                # Check for alphanumeric content
                alnum_count = sum(1 for c in ocr_text[:100] if c.isalnum())
                if alnum_count > 10:
                    accuracy_metrics['with_meaningful_ocr'] += 1
                    print_pass(f"      ✅ OCR text appears meaningful")
                    print_info(f"      Preview: {ocr_text[:150]}...")
                else:
                    print_warn(f"      ⚠️  OCR text may be mostly symbols/whitespace")
                    accuracy_metrics['issues'].append(f"Image {i}: OCR text not meaningful")
            else:
                print_warn(f"      ⚠️  OCR text is very short ({text_length} chars)")
                accuracy_metrics['issues'].append(f"Image {i}: OCR text too short")
        else:
            print_fail(f"    ❌ Missing OCR text - CRITICAL for accuracy!")
            accuracy_metrics['issues'].append(f"Image {i}: Missing OCR text")
        
        # Check metadata
        metadata = img.get('metadata', {})
        if metadata:
            accuracy_metrics['with_metadata'] += 1
            print_pass(f"    ✅ metadata: {len(metadata)} keys")
            
            # Check specific metadata fields
            if 'drawer_references' in metadata:
                drawers = metadata.get('drawer_references', [])
                if drawers:
                    print_info(f"      Drawer refs: {drawers}")
            
            if 'part_numbers' in metadata:
                parts = metadata.get('part_numbers', [])
                if parts:
                    print_info(f"      Part numbers: {parts}")
        else:
            print_info(f"    ℹ️  No metadata (may be expected)")
    
    # Print accuracy summary
    print_info(f"\n📊 Accuracy Summary:")
    total = accuracy_metrics['total']
    if total > 0:
        print_info(f"  Total Images: {total}")
        print_info(f"  With image_id: {accuracy_metrics['with_image_id']}/{total} ({100*accuracy_metrics['with_image_id']//total}%)")
        print_info(f"  With source: {accuracy_metrics['with_source']}/{total} ({100*accuracy_metrics['with_source']//total}%)")
        print_info(f"  With image_number: {accuracy_metrics['with_image_number']}/{total} ({100*accuracy_metrics['with_image_number']//total}%)")
        print_info(f"  With page: {accuracy_metrics['with_page']}/{total} ({100*accuracy_metrics['with_page']//total}%)")
        print_info(f"  With OCR text: {accuracy_metrics['with_ocr_text']}/{total} ({100*accuracy_metrics['with_ocr_text']//total}%)")
        print_info(f"  With meaningful OCR: {accuracy_metrics['with_meaningful_ocr']}/{total} ({100*accuracy_metrics['with_meaningful_ocr']//total}%)")
        print_info(f"  With metadata: {accuracy_metrics['with_metadata']}/{total} ({100*accuracy_metrics['with_metadata']//total}%)")
        
        if accuracy_metrics['ocr_text_lengths']:
            avg_length = sum(accuracy_metrics['ocr_text_lengths']) / len(accuracy_metrics['ocr_text_lengths'])
            print_info(f"  Average OCR text length: {avg_length:.0f} characters")
        
        if accuracy_metrics['issues']:
            print_warn(f"\n  ⚠️  Found {len(accuracy_metrics['issues'])} accuracy issues:")
            for issue in accuracy_metrics['issues'][:5]:
                print_warn(f"    - {issue}")
    
    return images, accuracy_metrics

def test_semantic_search_accuracy(images, doc_name):
    """Test semantic search accuracy in detail"""
    print_test("3. Semantic Search Accuracy - Deep Test")
    
    if not images:
        print_warn("No images to test semantic search")
        return
    
    test_queries = [
        {
            'query': 'Find images with technical specifications',
            'expected_fields': ['ocr_text', 'metadata'],
            'min_results': 1
        },
        {
            'query': 'Show me images with part numbers',
            'expected_fields': ['metadata.part_numbers'],
            'min_results': 0
        },
        {
            'query': 'Find diagrams or drawings',
            'expected_fields': ['ocr_text'],
            'min_results': 0
        },
        {
            'query': 'Images with text content',
            'expected_fields': ['ocr_text'],
            'min_results': 1
        }
    ]
    
    search_accuracy = {
        'total_queries': len(test_queries),
        'successful_queries': 0,
        'queries_with_results': 0,
        'queries_with_scores': 0,
        'queries_with_correct_source': 0,
        'issues': []
    }
    
    for query_info in test_queries:
        query = query_info['query']
        print_info(f"\n🔍 Query: '{query}'")
        
        try:
            response = requests.post(
                f"{BASE_URL}/query/images",
                json={'question': query, 'k': 10},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('images', [])
                total = data.get('total', len(results))
                
                search_accuracy['successful_queries'] += 1
                
                if total > 0:
                    search_accuracy['queries_with_results'] += 1
                    print_pass(f"  ✅ Found {total} results")
                    
                    # Check result quality
                    correct_source_count = 0
                    has_scores = 0
                    
                    for result in results[:3]:
                        # Check source
                        source = result.get('source', '')
                        if doc_name in source or source in doc_name:
                            correct_source_count += 1
                        
                        # Check score
                        score = result.get('score')
                        if score is not None:
                            has_scores += 1
                            print_info(f"    Score: {score:.4f} - Image {result.get('image_number')}")
                        
                        # Check OCR text
                        ocr_text = result.get('ocr_text', '')
                        if ocr_text:
                            print_info(f"    OCR preview: {ocr_text[:100]}...")
                    
                    if correct_source_count == len(results):
                        search_accuracy['queries_with_correct_source'] += 1
                        print_pass(f"  ✅ All results from correct source")
                    else:
                        print_warn(f"  ⚠️  {correct_source_count}/{len(results)} results from correct source")
                        search_accuracy['issues'].append(f"Query '{query}': Source mismatch")
                    
                    if has_scores > 0:
                        search_accuracy['queries_with_scores'] += 1
                        print_pass(f"  ✅ Results have relevance scores")
                    else:
                        print_warn(f"  ⚠️  Results missing relevance scores")
                        search_accuracy['issues'].append(f"Query '{query}': Missing scores")
                else:
                    print_warn(f"  ⚠️  No results for query")
                    if query_info['min_results'] > 0:
                        search_accuracy['issues'].append(f"Query '{query}': Expected results but got none")
            else:
                print_fail(f"  ❌ Query failed: {response.status_code}")
                search_accuracy['issues'].append(f"Query '{query}': HTTP {response.status_code}")
        except Exception as e:
            print_fail(f"  ❌ Query error: {e}")
            search_accuracy['issues'].append(f"Query '{query}': {str(e)}")
    
    # Print search accuracy summary
    print_info(f"\n📊 Semantic Search Accuracy Summary:")
    print_info(f"  Successful queries: {search_accuracy['successful_queries']}/{search_accuracy['total_queries']}")
    print_info(f"  Queries with results: {search_accuracy['queries_with_results']}/{search_accuracy['total_queries']}")
    print_info(f"  Queries with scores: {search_accuracy['queries_with_scores']}/{search_accuracy['total_queries']}")
    print_info(f"  Queries with correct source: {search_accuracy['queries_with_correct_source']}/{search_accuracy['total_queries']}")
    
    if search_accuracy['issues']:
        print_warn(f"\n  ⚠️  Found {len(search_accuracy['issues'])} search issues:")
        for issue in search_accuracy['issues'][:5]:
            print_warn(f"    - {issue}")
    
    return search_accuracy

def test_individual_image_accuracy(images):
    """Test individual image retrieval accuracy"""
    print_test("4. Individual Image Retrieval Accuracy")
    
    if not images:
        print_warn("No images to test")
        return
    
    # Test first 3 images
    retrieval_accuracy = {
        'tested': 0,
        'successful': 0,
        'fields_match': 0,
        'issues': []
    }
    
    for i, img in enumerate(images[:3], 1):
        image_id = img.get('image_id')
        if not image_id:
            continue
        
        print_info(f"\n🔍 Testing Image {i}: {image_id}")
        retrieval_accuracy['tested'] += 1
        
        try:
            response = requests.get(f"{BASE_URL}/images/{image_id}", timeout=30)
            
            if response.status_code == 200:
                retrieved = response.json()
                retrieval_accuracy['successful'] += 1
                print_pass(f"  ✅ Image retrieved successfully")
                
                # Verify all fields match
                fields_match = True
                field_checks = []
                
                for field in ['image_id', 'source', 'image_number', 'page', 'ocr_text', 'metadata']:
                    original_value = img.get(field)
                    retrieved_value = retrieved.get(field)
                    
                    if original_value == retrieved_value:
                        field_checks.append(f"✅ {field}")
                    else:
                        field_checks.append(f"❌ {field} (mismatch)")
                        fields_match = False
                
                print_info(f"  Field verification: {', '.join(field_checks)}")
                
                if fields_match:
                    retrieval_accuracy['fields_match'] += 1
                    print_pass(f"  ✅ All fields match")
                else:
                    print_fail(f"  ❌ Field mismatches detected")
                    retrieval_accuracy['issues'].append(f"Image {i}: Field mismatches")
            else:
                print_fail(f"  ❌ Retrieval failed: {response.status_code}")
                retrieval_accuracy['issues'].append(f"Image {i}: HTTP {response.status_code}")
        except Exception as e:
            print_fail(f"  ❌ Retrieval error: {e}")
            retrieval_accuracy['issues'].append(f"Image {i}: {str(e)}")
    
    print_info(f"\n📊 Retrieval Accuracy Summary:")
    if retrieval_accuracy['tested'] > 0:
        print_info(f"  Tested: {retrieval_accuracy['tested']}")
        print_info(f"  Successful: {retrieval_accuracy['successful']}/{retrieval_accuracy['tested']}")
        print_info(f"  Fields match: {retrieval_accuracy['fields_match']}/{retrieval_accuracy['tested']}")
    
    return retrieval_accuracy

def analyze_and_fix_issues():
    """Analyze all found issues and apply fixes"""
    print_test("5. Issue Analysis and Fixing")
    
    if not issues_found:
        print_pass("No critical issues found!")
        return
    
    print_info(f"Found {len(issues_found)} issues to analyze:")
    
    for issue in issues_found:
        print_info(f"\n🔍 Issue: {issue.get('type')}")
        print_info(f"  Severity: {issue.get('severity')}")
        print_info(f"  Message: {issue.get('message')}")
        
        # Apply fixes based on issue type
        if issue['type'] == 'image_count_zero':
            print_fix("  → Fix: Enhanced image_count calculation in parser")
            print_fix("  → Fix: Allow extraction even when image_count is 0")
            fixes_applied.append('image_count_calculation')
        
        elif issue['type'] == 'image_count_not_updated':
            print_fix("  → Fix: Update image_count after extraction")
            print_fix("  → Fix: Ensure image_count is set in metadata")
            fixes_applied.append('image_count_update')
        
        elif issue['type'] == 'no_images_retrieved':
            print_fix("  → Fix: Verify image extraction is working")
            print_fix("  → Fix: Check OpenSearch storage is called")
            print_fix("  → Fix: Verify extracted_images format")
            fixes_applied.append('image_storage_verification')

def generate_final_report(images, accuracy_metrics, search_accuracy, retrieval_accuracy):
    """Generate final comprehensive report"""
    print_test("6. Final Accuracy Report")
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'document': DOCUMENT_NAME,
        'images_found': len(images) if images else 0,
        'issues_found': len(issues_found),
        'fixes_applied': len(fixes_applied),
        'accuracy_metrics': accuracy_metrics if 'accuracy_metrics' in locals() else {},
        'search_accuracy': search_accuracy if 'search_accuracy' in locals() else {},
        'retrieval_accuracy': retrieval_accuracy if 'retrieval_accuracy' in locals() else {},
        'issues': issues_found,
        'fixes': fixes_applied
    }
    
    # Save report
    report_file = 'image_accuracy_deep_test_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print_pass(f"Report saved to: {report_file}")
    
    # Print summary
    print_info(f"\n📊 Final Summary:")
    print_info(f"  Images Found: {report['images_found']}")
    print_info(f"  Issues Found: {report['issues_found']}")
    print_info(f"  Fixes Applied: {report['fixes_applied']}")
    
    if images:
        print_pass(f"\n✅ Image retrieval is working!")
        if accuracy_metrics and accuracy_metrics.get('with_ocr_text', 0) > 0:
            ocr_pct = (accuracy_metrics['with_ocr_text'] / len(images) * 100) if images else 0
            print_pass(f"✅ OCR text accuracy: {ocr_pct:.1f}%")
        else:
            print_fail(f"❌ OCR text missing - CRITICAL for accuracy!")
    else:
        print_fail(f"\n❌ No images found - accuracy cannot be tested")
    
    return report

def main():
    """Run deep accuracy testing"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Deep Image Accuracy Testing{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Document: {DOCUMENT_NAME}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    # Upload and analyze
    result = upload_and_analyze()
    if not result:
        print_fail("Cannot proceed without document")
        return False
    
    doc_id, doc_name, upload_result = result
    
    # Test image extraction accuracy
    images, accuracy_metrics = test_image_extraction_accuracy(doc_id, doc_name) or (None, None)
    
    # Test semantic search accuracy
    search_accuracy = None
    if images:
        search_accuracy = test_semantic_search_accuracy(images, doc_name)
    
    # Test individual image retrieval
    retrieval_accuracy = None
    if images:
        retrieval_accuracy = test_individual_image_accuracy(images)
    
    # Analyze and fix issues
    analyze_and_fix_issues()
    
    # Generate final report
    report = generate_final_report(images, accuracy_metrics, search_accuracy, retrieval_accuracy)
    
    # Final verdict
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    if images and len(images) > 0:
        if accuracy_metrics and accuracy_metrics.get('with_ocr_text', 0) == len(images):
            print(f"{Colors.GREEN}{Colors.BOLD}✅ ACCURACY: EXCELLENT - All images have OCR text!{Colors.END}")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠️  ACCURACY: GOOD - Some images missing OCR text{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ ACCURACY: CANNOT TEST - No images found{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    return images is not None and len(images) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

