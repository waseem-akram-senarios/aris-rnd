#!/usr/bin/env python3
"""
Test Get Page Information Endpoint
Tests GET /documents/{id}/pages/{page_number} to get all information from a specific page
"""
import requests
import json
import sys

API_BASE_URL = "http://44.221.84.58:8500"

def test_page_information(doc_id, page_number):
    """Test getting all information from a specific page"""
    print("="*70)
    print(f"TEST: GET /documents/{{id}}/pages/{{page_number}}")
    print("="*70)
    print(f"\nDocument ID: {doc_id}")
    print(f"Page Number: {page_number}")
    print(f"Endpoint: {API_BASE_URL}/documents/{doc_id}/pages/{page_number}")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/documents/{doc_id}/pages/{page_number}",
            timeout=60
        )
        
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n✅ SUCCESS! Retrieved all information from page")
            print("\n" + "="*70)
            print("PAGE INFORMATION SUMMARY")
            print("="*70)
            print(f"Document ID: {data.get('document_id')}")
            print(f"Document Name: {data.get('document_name')}")
            print(f"Page Number: {data.get('page_number')}")
            print(f"Text Index: {data.get('text_index')}")
            print(f"Images Index: {data.get('images_index')}")
            print(f"\nText Chunks: {data.get('total_text_chunks', 0)}")
            print(f"Total Text Length: {data.get('total_text_length', 0):,} characters")
            print(f"\nImages: {data.get('total_images', 0)}")
            print(f"Total OCR Text: {data.get('total_ocr_text_length', 0):,} characters")
            
            # Show text chunks
            text_chunks = data.get('text_chunks', [])
            if text_chunks:
                print("\n" + "="*70)
                print("TEXT CHUNKS FROM PAGE")
                print("="*70)
                for i, chunk in enumerate(text_chunks[:5], 1):  # Show first 5
                    print(f"\nChunk {i}:")
                    print(f"  Chunk Index: {chunk.get('chunk_index')}")
                    print(f"  Page: {chunk.get('page')}")
                    print(f"  Source: {chunk.get('source')}")
                    print(f"  Text Length: {len(chunk.get('text', '')):,} characters")
                    print(f"  Text Preview: {chunk.get('text', '')[:200]}...")
                if len(text_chunks) > 5:
                    print(f"\n... and {len(text_chunks) - 5} more text chunks")
            else:
                print("\n⚠️  No text chunks found for this page")
            
            # Show images
            images = data.get('images', [])
            if images:
                print("\n" + "="*70)
                print("IMAGES FROM PAGE")
                print("="*70)
                for i, img in enumerate(images, 1):
                    print(f"\nImage {i}:")
                    print(f"  Image ID: {img.get('image_id')}")
                    print(f"  Image Number: {img.get('image_number')}")
                    print(f"  Page: {img.get('page')}")
                    print(f"  OCR Text Length: {img.get('ocr_text_length', 0):,} characters")
                    print(f"  Extraction Method: {img.get('extraction_method', 'N/A')}")
                    print(f"  OCR Preview: {img.get('ocr_text', '')[:200]}...")
                    
                    metadata = img.get('metadata', {})
                    if metadata:
                        if 'drawer_references' in metadata:
                            print(f"  Drawer References: {metadata.get('drawer_references')}")
                        if 'part_numbers' in metadata:
                            part_nums = metadata.get('part_numbers', [])[:5]
                            print(f"  Part Numbers: {part_nums}")
                        if 'tools_found' in metadata:
                            print(f"  Tools Found: {metadata.get('tools_found')}")
            else:
                print("\n⚠️  No images found for this page")
            
            # Summary
            print("\n" + "="*70)
            print("PAGE CONTENT SUMMARY")
            print("="*70)
            total_text = data.get('total_text_length', 0)
            total_ocr = data.get('total_ocr_text_length', 0)
            total_content = total_text + total_ocr
            
            print(f"Text Content: {total_text:,} characters")
            print(f"Image OCR Content: {total_ocr:,} characters")
            print(f"Total Page Content: {total_content:,} characters")
            print(f"Text Chunks: {len(text_chunks)}")
            print(f"Images: {len(images)}")
            
            if total_content > 0:
                print(f"\n✅ Page {page_number} has complete information!")
                print(f"✅ Total content: {total_content:,} characters")
            else:
                print(f"\n⚠️  Page {page_number} has no content")
            
            return True
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Use document ID from previous test
    doc_id = "2bac8df5-931a-4d5a-9074-c8eaa7d6247e"
    page_num = 1
    
    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
    if len(sys.argv) > 2:
        page_num = int(sys.argv[2])
    
    print(f"\nTesting page information retrieval...")
    print(f"Document: {doc_id}")
    print(f"Page: {page_num}\n")
    
    success = test_page_information(doc_id, page_num)
    sys.exit(0 if success else 1)
