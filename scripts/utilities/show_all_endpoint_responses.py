#!/usr/bin/env python3
"""
Show full responses from all API endpoints
"""
import os
import sys
import requests
import json
import tempfile

API_BASE_URL = os.getenv('FASTAPI_URL', 'http://44.221.84.58:8500')
TEST_TIMEOUT = 300

def print_section(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def show_response(name, method, url, **kwargs):
    """Show full endpoint response"""
    print_section(f"{name} - {method} {url}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'POST':
            response = requests.post(url, timeout=TEST_TIMEOUT, **kwargs)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, timeout=TEST_TIMEOUT, **kwargs)
        
        print(f"\n📊 Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}\n")
        
        try:
            data = response.json()
            print("📄 Response Body (JSON):")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except:
            print("📄 Response Body (Text):")
            print(response.text)
        
        return {"status": response.status_code, "data": data if 'data' in locals() else response.text}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {"error": str(e)}

def main():
    print("\n" + "="*80)
    print("  ARIS RAG API - ALL ENDPOINT RESPONSES")
    print("="*80)
    print(f"Server: {API_BASE_URL}\n")
    
    responses = {}
    uploaded_doc_id = None
    
    # 1. Health Check
    responses['health'] = show_response(
        "1. Health Check",
        "GET",
        f"{API_BASE_URL}/health"
    )
    
    # 2. Root
    responses['root'] = show_response(
        "2. Root Endpoint",
        "GET",
        f"{API_BASE_URL}/"
    )
    
    # 3. List Documents
    responses['list_documents'] = show_response(
        "3. List Documents",
        "GET",
        f"{API_BASE_URL}/documents"
    )
    
    # Get document info for further tests
    doc_id = None
    doc_name = None
    if responses['list_documents'].get('data') and isinstance(responses['list_documents']['data'], dict):
        docs = responses['list_documents']['data'].get('documents', [])
        if docs:
            doc = docs[0]
            doc_id = doc.get('document_id')
            doc_name = doc.get('document_name')
    
    # 4. Upload Document
    print_section("4. Upload Document - POST /documents")
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
            
            print(f"\n📊 Status Code: {response.status_code}")
            print(f"📋 Headers: {dict(response.headers)}\n")
            
            if response.status_code == 201:
                upload_data = response.json()
                uploaded_doc_id = upload_data.get('document_id')
                print("📄 Response Body (JSON):")
                print(json.dumps(upload_data, indent=2, ensure_ascii=False))
                responses['upload'] = {"status": 201, "data": upload_data}
            else:
                print("📄 Response Body (Text):")
                print(response.text)
                responses['upload'] = {"status": response.status_code, "data": response.text}
        except Exception as e:
            print(f"❌ Error: {e}")
            responses['upload'] = {"error": str(e)}
    else:
        print("⚠️  PDF file not found, skipping upload test")
        responses['upload'] = {"skipped": True}
    
    # 5. Query Documents
    responses['query'] = show_response(
        "5. Query Documents",
        "POST",
        f"{API_BASE_URL}/query",
        json={
            "question": "What is this document about?",
            "k": 5
        }
    )
    
    # 6. Query with document_id
    if uploaded_doc_id:
        responses['query_filtered'] = show_response(
            "6. Query with document_id filter",
            "POST",
            f"{API_BASE_URL}/query",
            json={
                "question": "test query",
                "k": 3,
                "document_id": uploaded_doc_id
            }
        )
    else:
        print_section("6. Query with document_id filter - SKIPPED")
        print("No document uploaded, skipping filtered query test")
        responses['query_filtered'] = {"skipped": True}
    
    # 7. Query Images - Get All
    if doc_name:
        responses['query_images_all'] = show_response(
            "7. Query Images (Get All)",
            "POST",
            f"{API_BASE_URL}/query/images",
            json={
                "question": "",
                "source": doc_name,
                "k": 10
            }
        )
    else:
        print_section("7. Query Images (Get All) - SKIPPED")
        print("No document name available, skipping image query test")
        responses['query_images_all'] = {"skipped": True}
    
    # 8. Query Images - Semantic Search
    responses['query_images_search'] = show_response(
        "8. Query Images (Semantic Search)",
        "POST",
        f"{API_BASE_URL}/query/images",
        json={
            "question": "diagram or chart",
            "k": 5
        }
    )
    
    # 9. Delete Document
    if uploaded_doc_id:
        responses['delete'] = show_response(
            "9. Delete Document",
            "DELETE",
            f"{API_BASE_URL}/documents/{uploaded_doc_id}"
        )
    else:
        print_section("9. Delete Document - SKIPPED")
        print("No document uploaded, skipping delete test")
        responses['delete'] = {"skipped": True}
    
    # Save all responses to file
    output_file = 'ALL_ENDPOINT_RESPONSES.json'
    with open(output_file, 'w') as f:
        json.dump(responses, f, indent=2, ensure_ascii=False, default=str)
    
    print("\n" + "="*80)
    print("  SUMMARY")
    print("="*80)
    print(f"\n✅ All endpoint responses displayed above")
    print(f"💾 Full responses saved to: {output_file}")
    print(f"\n📊 Total endpoints tested: {len([r for r in responses.values() if not r.get('skipped')])}")

if __name__ == "__main__":
    main()



