#!/usr/bin/env python3
"""
Complete End-to-End Test of ARIS RAG API
Tests the full workflow: Upload -> Process -> Query -> Query Images -> Delete
"""
import os
import sys
import requests
import json
import time

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def print_step(step_num, description):
    print(f"\n{'='*70}")
    print(f"STEP {step_num}: {description}")
    print(f"{'='*70}")

def test_request(name, method, url, **kwargs):
    """Make a request and return result"""
    print(f"\n🔍 {name}")
    print(f"   {method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        
        print(f"   Status: {response.status_code}")
        
        try:
            data = response.json()
            print(f"   ✅ Response received")
            if isinstance(data, dict):
                # Print key fields
                if 'document_id' in data:
                    print(f"   📄 Document ID: {data.get('document_id')}")
                if 'status' in data:
                    print(f"   📊 Status: {data.get('status')}")
                if 'chunks_created' in data:
                    print(f"   📦 Chunks: {data.get('chunks_created')}")
                if 'answer' in data:
                    answer_preview = data.get('answer', '')[:200]
                    print(f"   💬 Answer: {answer_preview}...")
                if 'sources' in data:
                    print(f"   📚 Sources: {len(data.get('sources', []))} documents")
                if 'citations' in data:
                    print(f"   📝 Citations: {len(data.get('citations', []))}")
                if 'images' in data:
                    print(f"   🖼️  Images: {data.get('total', 0)} found")
            return {"status": response.status_code, "success": response.status_code < 400, "data": data}
        except:
            print(f"   ✅ Response: {response.text[:200]}")
            return {"status": response.status_code, "success": response.status_code < 400, "text": response.text}
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {"error": str(e), "success": False}

def main():
    print("\n" + "="*70)
    print("ARIS RAG API - COMPLETE END-TO-END TEST")
    print("="*70)
    print(f"Server: {API_BASE_URL}\n")
    
    results = {}
    uploaded_doc_id = None
    uploaded_doc_name = None
    
    # STEP 1: Health Check
    print_step(1, "Health Check")
    results['health'] = test_request("Health Check", "GET", f"{API_BASE_URL}/health")
    if not results['health'].get('success'):
        print("\n❌ Health check failed! Cannot proceed.")
        return 1
    
    # STEP 2: List Documents (Initial State)
    print_step(2, "List Documents (Initial State)")
    results['list_initial'] = test_request("List Documents", "GET", f"{API_BASE_URL}/documents")
    initial_count = 0
    if results['list_initial'].get('success'):
        initial_count = results['list_initial'].get('data', {}).get('total', 0)
        print(f"   📊 Initial document count: {initial_count}")
    
    # STEP 3: Upload Document
    print_step(3, "Upload Document")
    pdf_path = "./FL10.11 SPECIFIC8 (1).pdf"
    if not os.path.exists(pdf_path):
        print(f"   ⚠️  PDF not found: {pdf_path}")
        print("   Creating test document...")
        # Create a simple test file
        test_content = "This is a test document for end-to-end testing.\n" * 50
        pdf_path = "/tmp/test_e2e.txt"
        with open(pdf_path, 'w') as f:
            f.write(test_content)
        parser = 'auto'
    else:
        parser = 'docling'
    
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': (os.path.basename(pdf_path), f, 'application/pdf' if pdf_path.endswith('.pdf') else 'text/plain')}
            data = {'parser': parser}
            response = requests.post(
                f"{API_BASE_URL}/documents",
                files=files,
                data=data,
                timeout=TEST_TIMEOUT
            )
        
        if response.status_code == 201:
            upload_data = response.json()
            uploaded_doc_id = upload_data.get('document_id')
            uploaded_doc_name = upload_data.get('document_name')
            print(f"   ✅ Document uploaded successfully")
            print(f"   📄 Document ID: {uploaded_doc_id}")
            print(f"   📄 Document Name: {uploaded_doc_name}")
            print(f"   📊 Status: {upload_data.get('status')}")
            print(f"   📦 Chunks: {upload_data.get('chunks_created', 0)}")
            print(f"   🖼️  Images: {upload_data.get('image_count', 0)}")
            results['upload'] = {"status": 201, "success": True, "data": upload_data}
            
            # Wait for processing to complete
            if upload_data.get('status') == 'success':
                print(f"\n   ⏳ Waiting 3 seconds for indexing...")
                time.sleep(3)
        else:
            print(f"   ❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            results['upload'] = {"status": response.status_code, "success": False, "data": response.text}
            return 1
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
        results['upload'] = {"error": str(e), "success": False}
        return 1
    
    # STEP 4: Verify Document in List
    print_step(4, "Verify Document in List")
    results['list_after_upload'] = test_request("List Documents", "GET", f"{API_BASE_URL}/documents")
    if results['list_after_upload'].get('success'):
        new_count = results['list_after_upload'].get('data', {}).get('total', 0)
        print(f"   📊 Document count after upload: {new_count}")
        if new_count > initial_count:
            print(f"   ✅ Document count increased (was {initial_count}, now {new_count})")
        else:
            print(f"   ⚠️  Document count did not increase")
    
    # STEP 5: Query Document
    print_step(5, "Query Document")
    query_question = "What is this document about? Give me a summary."
    results['query'] = test_request(
        "Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": query_question,
            "k": 5
        }
    )
    
    if results['query'].get('success'):
        query_data = results['query'].get('data', {})
        answer = query_data.get('answer', '')
        if answer and 'No documents' not in answer:
            print(f"   ✅ Query successful - Answer received")
            print(f"   📝 Answer length: {len(answer)} characters")
            print(f"   📚 Sources: {len(query_data.get('sources', []))}")
            print(f"   📝 Citations: {len(query_data.get('citations', []))}")
        else:
            print(f"   ⚠️  Query returned but answer indicates no documents")
    
    # STEP 6: Query with document_id filter
    if uploaded_doc_id:
        print_step(6, "Query with document_id filter")
        results['query_filtered'] = test_request(
            "Query with document_id",
            "POST",
            f"{API_BASE_URL}/query",
            json={
                "question": "What information is in this specific document?",
                "k": 3,
                "document_id": uploaded_doc_id
            }
        )

        # STEP 6B: Strict per-document query endpoint
        print_step("6B", "Strict per-document query endpoint")
        results['query_strict'] = test_request(
            "Query single document (strict)",
            "POST",
            f"{API_BASE_URL}/documents/{uploaded_doc_id}/query",
            json={
                "question": "What information is in this specific document?",
                "k": 3
            }
        )
    
    # STEP 7: Query Images
    print_step(7, "Query Images")
    if uploaded_doc_name:
        results['query_images'] = test_request(
            "Query Images (Get All)",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": uploaded_doc_name,
                "k": 10
            }
        )
    
    # Also test semantic image search
    results['query_images_search'] = test_request(
        "Query Images (Semantic Search)",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "diagram or chart",
            "k": 5
        }
    )
    
    # STEP 8: Delete Document
    if uploaded_doc_id:
        print_step(8, "Delete Document")
        results['delete'] = test_request(
            "Delete Document",
            "DELETE",
            f"{API_BASE_URL}/documents/{uploaded_doc_id}"
        )
        
        # Verify deletion
        print(f"\n   ⏳ Waiting 2 seconds...")
        time.sleep(2)
        results['list_after_delete'] = test_request("List Documents (After Delete)", "GET", f"{API_BASE_URL}/documents")
        if results['list_after_delete'].get('success'):
            final_count = results['list_after_delete'].get('data', {}).get('total', 0)
            print(f"   📊 Document count after delete: {final_count}")
            if final_count == initial_count:
                print(f"   ✅ Document successfully deleted (count back to {initial_count})")
            else:
                print(f"   ⚠️  Document count mismatch (expected {initial_count}, got {final_count})")
    
    # Final Summary
    print("\n" + "="*70)
    print("END-TO-END TEST SUMMARY")
    print("="*70)
    
    passed = 0
    failed = 0
    warnings = 0
    
    test_steps = {
        'health': '1. Health Check',
        'list_initial': '2. List Documents (Initial)',
        'upload': '3. Upload Document',
        'list_after_upload': '4. Verify Document in List',
        'query': '5. Query Document',
        'query_filtered': '6. Query with document_id',
        'query_images': '7. Query Images (All)',
        'query_images_search': '7. Query Images (Search)',
        'delete': '8. Delete Document',
        'list_after_delete': '8. Verify Deletion'
    }
    
    for key, name in test_steps.items():
        result = results.get(key, {})
        if result.get('skipped'):
            print(f"⏭️  {name}: SKIPPED")
        elif result.get('success'):
            status = result.get('status', 'N/A')
            # Check for expected warnings
            if status == 400 and 'No documents' in str(result.get('data', {})):
                warnings += 1
                print(f"⚠️  {name}: WORKING (Status: {status}) - Expected warning")
            else:
                passed += 1
                print(f"✅ {name}: PASSED (Status: {status})")
        else:
            failed += 1
            status = result.get('status', 'N/A')
            error = result.get('error', 'Unknown error')
            print(f"❌ {name}: FAILED (Status: {status}) - {error}")
    
    print(f"\n📊 Results: {passed} passed, {warnings} warnings, {failed} failed")
    
    # Save results
    with open('END_TO_END_TEST_RESULTS.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Full results saved to: END_TO_END_TEST_RESULTS.json")
    
    if failed > 0:
        print(f"\n❌ End-to-end test failed! {failed} step(s) failed.")
        return 1
    else:
        print(f"\n✅ End-to-end test PASSED! All steps completed successfully.")
        return 0

if __name__ == "__main__":
    sys.exit(main())



