#!/usr/bin/env python3
"""
Debug script to check why images aren't being stored.
Tests the full pipeline from upload to storage.
"""
import os
import sys
import requests
import time

BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

def print_test(name):
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print('='*80)

def print_pass(msg):
    print(f"✅ {msg}")

def print_fail(msg):
    print(f"❌ {msg}")

def print_info(msg):
    print(f"ℹ️  {msg}")

def check_server_logs_hint():
    """Provide instructions for checking server logs"""
    print_test("Server Logs Check")
    print_info("To debug image storage, check server logs for:")
    print_info("  1. '✅ Stored X images in OpenSearch' - Success message")
    print_info("  2. '⚠️ Failed to store images' - Error message")
    print_info("  3. 'OpenSearch domain not configured' - Config issue")
    print_info("  4. 'Extracted X individual images' - Parser extraction")
    print()
    print_info("To check logs on server:")
    print_info("  docker logs aris-rag-app | grep -i image")
    print_info("  docker logs aris-rag-app | grep -i opensearch")

def upload_and_check():
    """Upload document and check response"""
    print_test("1. Upload Document and Check Response")
    
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
            print_info(f"Images detected: {result.get('images_detected', False)}")
            print_info(f"Image count: {result.get('image_count', 0)}")
            print_info(f"Pages: {result.get('pages', 0)}")
            
            # Wait for processing
            print_info("Waiting 15 seconds for processing...")
            time.sleep(15)
            
            return doc_id, result.get('document_name')
        else:
            print_fail(f"Upload failed: {response.status_code}")
            return None
    except Exception as e:
        print_fail(f"Upload error: {e}")
        return None

def check_images_multiple_times(document_id, document_name, max_attempts=5):
    """Check for images multiple times with increasing wait"""
    print_test("2. Check Images (Multiple Attempts)")
    
    for attempt in range(1, max_attempts + 1):
        wait_time = 5 * attempt  # 5, 10, 15, 20, 25 seconds
        print_info(f"\nAttempt {attempt}/{max_attempts} (waiting {wait_time}s)...")
        time.sleep(wait_time)
        
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
                    print_pass(f"Found {total} images on attempt {attempt}!")
                    return images
                else:
                    print_info(f"No images yet (attempt {attempt})")
            else:
                print_info(f"Request failed: {response.status_code}")
        except Exception as e:
            print_info(f"Error: {e}")
    
    print_fail("No images found after all attempts")
    return []

def test_query_to_trigger_storage(document_id):
    """Make a query that might trigger image storage"""
    print_test("3. Query Document to Trigger Image Storage")
    
    query_data = {
        'question': 'What images, diagrams, or technical drawings are in this document? Show me information from any images.',
        'k': 10,
        'document_id': document_id
    }
    
    try:
        print_info("Making query to trigger image extraction...")
        response = requests.post(f"{BASE_URL}/query", json=query_data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print_pass("Query completed")
            print_info(f"Answer length: {len(result.get('answer', ''))}")
            print_info(f"Citations: {len(result.get('citations', []))}")
            
            # Wait for async storage
            print_info("Waiting 10 seconds for async image storage...")
            time.sleep(10)
            return True
        else:
            print_fail(f"Query failed: {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Query error: {e}")
        return False

def verify_image_endpoints():
    """Verify image endpoints are working"""
    print_test("4. Verify Image Endpoints")
    
    # Test query images endpoint
    try:
        response = requests.post(
            f"{BASE_URL}/query/images",
            json={'question': 'test', 'k': 1},
            timeout=10
        )
        
        if response.status_code == 200:
            print_pass("Image query endpoint works")
            data = response.json()
            print_info(f"Images in index: {data.get('total', 0)}")
        elif response.status_code == 400:
            error = response.json().get('detail', '')
            print_info(f"Image query endpoint: {error}")
            if 'OpenSearch' in error:
                print_fail("OpenSearch not configured for image storage")
        else:
            print_info(f"Image query endpoint: {response.status_code}")
    except Exception as e:
        print_info(f"Image query endpoint error: {e}")

def main():
    """Run debug tests"""
    print("\n" + "="*80)
    print("IMAGE STORAGE DEBUG TEST")
    print("="*80 + "\n")
    
    # Check server logs hint
    check_server_logs_hint()
    
    # Verify endpoints
    verify_image_endpoints()
    
    # Upload document
    result = upload_and_check()
    if not result:
        print_fail("Cannot proceed without document")
        return
    
    document_id, document_name = result
    
    # Check images multiple times
    images = check_images_multiple_times(document_id, document_name)
    
    # If no images, try query to trigger storage
    if not images:
        print_info("\nNo images found during ingestion. Trying query-time storage...")
        test_query_to_trigger_storage(document_id)
        
        # Check again after query
        print_info("\nChecking again after query...")
        images = check_images_multiple_times(document_id, document_name, max_attempts=3)
    
    # Final summary
    print("\n" + "="*80)
    print("DEBUG SUMMARY")
    print("="*80)
    
    if images:
        print_pass(f"✅ Images found: {len(images)}")
        print_info("Image storage is working!")
    else:
        print_fail("❌ No images found")
        print_info("\nPossible issues:")
        print_info("  1. Images not extracted by parser (check parser logs)")
        print_info("  2. OpenSearch connection issue (check OpenSearch domain)")
        print_info("  3. Image storage failing silently (check server logs)")
        print_info("  4. Images stored but not queryable (check index name)")
        print_info("\nNext steps:")
        print_info("  1. Check server logs: docker logs aris-rag-app | grep -i image")
        print_info("  2. Verify OpenSearch domain is accessible")
        print_info("  3. Check if extracted_images format matches expected format")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

