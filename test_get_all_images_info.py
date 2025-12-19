#!/usr/bin/env python3
"""
Test Get All Images Information Endpoint
Tests the new GET /documents/{id}/images/all endpoint
"""
import requests
import json
import sys

API_BASE_URL = "http://44.221.84.58:8500"

def test_get_all_images(doc_id):
    """Test getting all image information"""
    print("="*70)
    print("TEST: GET /documents/{id}/images/all")
    print("="*70)
    print(f"\nDocument ID: {doc_id}")
    print(f"Endpoint: {API_BASE_URL}/documents/{doc_id}/images/all")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/documents/{doc_id}/images/all?limit=100",
            timeout=60
        )
        
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            print("\n✅ SUCCESS! Retrieved all image information")
            print("\n" + "="*70)
            print("SUMMARY")
            print("="*70)
            print(f"Document ID: {data.get('document_id')}")
            print(f"Document Name: {data.get('document_name')}")
            print(f"Total Images: {data.get('total', 0)}")
            print(f"Images Index: {data.get('images_index')}")
            print(f"Total OCR Text: {data.get('total_ocr_text_length', 0):,} characters")
            print(f"Average OCR Length: {data.get('average_ocr_length', 0):,.0f} characters")
            print(f"Images with OCR: {data.get('images_with_ocr', 0)}")
            
            images = data.get('images', [])
            if images:
                print(f"\n✅ Retrieved {len(images)} images with COMPLETE information!")
                
                print("\n" + "="*70)
                print("DETAILED IMAGE INFORMATION")
                print("="*70)
                
                for i, img in enumerate(images[:5], 1):  # Show first 5
                    print(f"\n--- Image {i} ---")
                    print(f"Image ID: {img.get('image_id')}")
                    print(f"Image Number: {img.get('image_number')}")
                    print(f"Page: {img.get('page', 'N/A')}")
                    print(f"Source: {img.get('source')}")
                    print(f"OCR Text Length: {img.get('ocr_text_length', 0):,} characters")
                    print(f"Extraction Method: {img.get('extraction_method', 'N/A')}")
                    print(f"Extraction Timestamp: {img.get('extraction_timestamp', 'N/A')}")
                    print(f"Marker Detected: {img.get('marker_detected', 'N/A')}")
                    
                    ocr_text = img.get('ocr_text', '')
                    if ocr_text:
                        print(f"\nOCR Text (first 500 chars):")
                        print(f"{ocr_text[:500]}...")
                    
                    metadata = img.get('metadata', {})
                    if metadata:
                        print(f"\nMetadata Keys: {list(metadata.keys())[:10]}")
                        if 'drawer_references' in metadata:
                            print(f"Drawer References: {metadata.get('drawer_references')}")
                        if 'part_numbers' in metadata:
                            part_nums = metadata.get('part_numbers', [])[:5]
                            print(f"Part Numbers (sample): {part_nums}")
                        if 'tools_found' in metadata:
                            print(f"Tools Found: {metadata.get('tools_found')}")
                
                if len(images) > 5:
                    print(f"\n... and {len(images) - 5} more images")
                
                # Analyze OCR content
                print("\n" + "="*70)
                print("OCR CONTENT ANALYSIS")
                print("="*70)
                
                all_ocr = ' '.join(img.get('ocr_text', '') for img in images)
                keywords = ['wrench', 'socket', 'drawer', 'part', 'tool', 'quantity', 'mallet', 'ratchet']
                found_keywords = [kw for kw in keywords if kw.lower() in all_ocr.lower()]
                
                print(f"Total OCR Characters: {len(all_ocr):,}")
                print(f"Keywords Found: {found_keywords}")
                
                # Count occurrences
                for keyword in found_keywords:
                    count = all_ocr.lower().count(keyword.lower())
                    print(f"  - '{keyword}': {count} occurrences")
                
                print("\n✅ VERIFICATION: All image information successfully retrieved!")
                return True
            else:
                print("⚠️  No images returned")
                return False
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    # Use document ID from previous test
    doc_id = "2bac8df5-931a-4d5a-9074-c8eaa7d6247e"
    
    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
    
    success = test_get_all_images(doc_id)
    sys.exit(0 if success else 1)
