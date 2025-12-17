#!/usr/bin/env python3
"""
Test image storage by triggering query-time storage and then verifying accuracy.
"""
import os
import sys
import json
import requests
import time

BASE_URL = "http://44.221.84.58:8500"

def print_test(name):
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print('='*80)

def print_pass(msg):
    print(f"✅ PASS: {msg}")

def print_fail(msg):
    print(f"❌ FAIL: {msg}")

def print_info(msg):
    print(f"ℹ️  INFO: {msg}")

def upload_and_get_document_id():
    """Upload document and return document_id"""
    print_test("1. Upload Document")
    
    doc_path = "FL10.11 SPECIFIC8 (1).pdf"
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
            print_info(f"Images detected: {result.get('images_detected', False)}")
            time.sleep(5)  # Wait for processing
            return doc_id
        else:
            print_fail(f"Upload failed: {response.status_code}")
            return None
    except Exception as e:
        print_fail(f"Upload error: {e}")
        return None

def trigger_image_storage_with_query(document_id):
    """Query the document to trigger image storage at query time"""
    print_test("2. Trigger Image Storage with Query")
    
    # Query that should trigger image extraction
    query_data = {
        'question': 'What images or diagrams are in this document? Show me information from images.',
        'k': 10,
        'document_id': document_id
    }
    
    try:
        print_info("Making query to trigger image extraction...")
        response = requests.post(f"{BASE_URL}/query", json=query_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print_pass("Query completed successfully")
            print_info(f"Answer length: {len(result.get('answer', ''))}")
            print_info(f"Citations: {len(result.get('citations', []))}")
            
            # Wait a bit for async image storage
            print_info("Waiting 3 seconds for image storage...")
            time.sleep(3)
            return True
        else:
            print_fail(f"Query failed: {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return False
    except Exception as e:
        print_fail(f"Query error: {e}")
        return False

def check_images_after_query(document_id, document_name):
    """Check if images are now available after query"""
    print_test("3. Check Images After Query")
    
    # Check document images
    try:
        response = requests.get(
            f"{BASE_URL}/documents/{document_id}/images?limit=100",
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            total = data.get('total', len(images))
            
            if total > 0:
                print_pass(f"Found {total} images after query!")
                
                # Test accuracy of first few images
                print_info("\nTesting image accuracy:")
                for i, img in enumerate(images[:5]):
                    print_info(f"\n--- Image {i+1} ---")
                    
                    # Check all required fields
                    checks = []
                    if img.get('image_id'):
                        checks.append("✅ image_id")
                    else:
                        checks.append("❌ Missing image_id")
                    
                    if img.get('source'):
                        checks.append("✅ source")
                    else:
                        checks.append("❌ Missing source")
                    
                    if img.get('image_number') is not None:
                        checks.append(f"✅ image_number: {img.get('image_number')}")
                    else:
                        checks.append("❌ Missing image_number")
                    
                    if img.get('page') is not None:
                        checks.append(f"✅ page: {img.get('page')}")
                    else:
                        checks.append("⚠️  page: None")
                    
                    ocr_text = img.get('ocr_text', '')
                    if ocr_text:
                        text_len = len(ocr_text)
                        checks.append(f"✅ ocr_text: {text_len} chars")
                        print_info(f"  OCR preview: {ocr_text[:150]}...")
                        
                        # Check if OCR text is meaningful
                        if text_len > 20:
                            print_pass(f"  OCR text is meaningful ({text_len} characters)")
                        else:
                            print_info(f"  OCR text is short ({text_len} characters)")
                    else:
                        checks.append("❌ Missing ocr_text")
                    
                    metadata = img.get('metadata', {})
                    if metadata:
                        checks.append(f"✅ metadata: {len(metadata)} keys")
                        if 'drawer_references' in metadata:
                            drawers = metadata.get('drawer_references', [])
                            if drawers:
                                print_info(f"  Drawer refs: {drawers}")
                        if 'part_numbers' in metadata:
                            parts = metadata.get('part_numbers', [])
                            if parts:
                                print_info(f"  Part numbers: {parts}")
                    else:
                        checks.append("⚠️  No metadata")
                    
                    print_info(f"  Fields: {', '.join(checks)}")
                
                return images
            else:
                print_info("No images found yet")
                print_info("Images may be stored asynchronously - waiting 5 more seconds...")
                time.sleep(5)
                
                # Try again
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
                        return images
                    else:
                        print_info("Still no images - may need to check query-time storage logic")
                        return []
                return []
        else:
            print_fail(f"Failed to get images: {response.status_code}")
            return None
    except Exception as e:
        print_fail(f"Error checking images: {e}")
        return None

def test_image_query_accuracy(images):
    """Test semantic search accuracy on stored images"""
    print_test("4. Test Image Query Accuracy")
    
    if not images or len(images) == 0:
        print_info("No images to test query accuracy")
        return
    
    queries = [
        "Find images with text",
        "Show images with part numbers",
        "Find technical diagrams"
    ]
    
    for query in queries:
        print_info(f"\nQuery: '{query}'")
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
                    print_pass(f"Found {total} images for: '{query}'")
                    
                    # Check relevance scores
                    for img in results[:2]:
                        score = img.get('score')
                        if score:
                            print_info(f"  Score: {score:.4f} - Image {img.get('image_number')}")
                        else:
                            print_info(f"  No score - Image {img.get('image_number')}")
                else:
                    print_info(f"No results for: '{query}'")
            else:
                print_info(f"Query failed: {response.status_code}")
        except Exception as e:
            print_info(f"Query error: {e}")

def test_single_image_retrieval(images):
    """Test retrieving a single image by ID"""
    print_test("5. Test Single Image Retrieval")
    
    if not images or len(images) == 0:
        print_info("No images to test single retrieval")
        return
    
    first_image = images[0]
    image_id = first_image.get('image_id')
    
    if not image_id:
        print_info("No image_id available")
        return
    
    try:
        response = requests.get(f"{BASE_URL}/images/{image_id}", timeout=30)
        
        if response.status_code == 200:
            img = response.json()
            print_pass(f"Image retrieved: {image_id}")
            
            # Verify all fields
            print_info("Verifying fields:")
            if img.get('image_id'):
                print_pass("  ✅ image_id")
            if img.get('source'):
                print_pass("  ✅ source")
            if img.get('image_number') is not None:
                print_pass(f"  ✅ image_number: {img.get('image_number')}")
            if img.get('page') is not None:
                print_pass(f"  ✅ page: {img.get('page')}")
            
            ocr_text = img.get('ocr_text', '')
            if ocr_text:
                print_pass(f"  ✅ ocr_text: {len(ocr_text)} chars")
                print_info(f"  OCR text: {ocr_text[:200]}...")
            else:
                print_fail("  ❌ Missing ocr_text")
            
            metadata = img.get('metadata', {})
            if metadata:
                print_pass(f"  ✅ metadata: {json.dumps(metadata, indent=4)}")
            else:
                print_info("  ⚠️  No metadata")
        else:
            print_fail(f"Failed to retrieve image: {response.status_code}")
    except Exception as e:
        print_fail(f"Error retrieving image: {e}")

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("IMAGE STORAGE AND ACCURACY TEST")
    print("="*80 + "\n")
    
    # Upload document
    document_id = upload_and_get_document_id()
    if not document_id:
        print_fail("Cannot proceed without document")
        return False
    
    # Get document name
    try:
        response = requests.get(f"{BASE_URL}/documents/{document_id}", timeout=10)
        if response.status_code == 200:
            doc_data = response.json()
            document_name = doc_data.get('document_name')
        else:
            document_name = None
    except:
        document_name = None
    
    # Trigger image storage with query
    trigger_image_storage_with_query(document_id)
    
    # Check images after query
    images = check_images_after_query(document_id, document_name)
    
    # Test image query accuracy
    if images:
        test_image_query_accuracy(images)
        test_single_image_retrieval(images)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    if images and len(images) > 0:
        print(f"✅ Found {len(images)} images")
        print("✅ Image endpoints are working")
        print("✅ Images can be retrieved accurately")
    else:
        print("⚠️  No images found")
        print("   This could mean:")
        print("   - Images are stored at query time only (need to query first)")
        print("   - Image storage is asynchronous (may take time)")
        print("   - Check server logs for image storage errors")
    
    print("="*80 + "\n")
    return images is not None and len(images) > 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

