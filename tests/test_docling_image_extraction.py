#!/usr/bin/env python3
"""
Test Docling Image Extraction
Verifies that Docling is actually extracting OCR text from images in PDFs
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, '.')

from parsers.docling_parser import DoclingParser

def test_image_extraction(file_path: str):
    """Test if Docling extracts text from images"""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"\n{'='*70}")
    print(f"Testing Docling Image Extraction")
    print(f"File: {os.path.basename(file_path)}")
    print(f"{'='*70}\n")
    
    try:
        parser = DoclingParser()
        
        print("Step 1: Parsing document with Docling...")
        result = parser.parse(file_path)
        
        print(f"\n✅ Parsing completed")
        print(f"   Pages: {result.pages}")
        print(f"   Images detected: {result.images_detected}")
        print(f"   Image count: {result.image_count}")
        print(f"   Text length: {len(result.text):,} characters")
        print(f"   Confidence: {result.confidence}")
        print(f"   Extraction percentage: {result.extraction_percentage:.1%}")
        
        # Check for image markers
        marker_count = result.text.count('<!-- image -->')
        print(f"\n📷 Image Markers:")
        print(f"   Markers found: {marker_count}")
        print(f"   Expected: {result.image_count}")
        if result.image_count > 0:
            coverage = (marker_count / result.image_count * 100) if result.image_count > 0 else 0
            print(f"   Coverage: {coverage:.1f}%")
        
        # Extract text around image markers to see OCR content
        print(f"\n📝 OCR Text from Images:")
        if marker_count > 0:
            parts = result.text.split('<!-- image -->')
            for i, part in enumerate(parts[1:6], 1):  # Show first 5 images
                # Get text after marker (OCR content)
                ocr_text = part.strip()[:500]  # First 500 chars
                if ocr_text:
                    print(f"\n   Image {i} OCR text (first 500 chars):")
                    print(f"   {ocr_text[:200]}...")
                    print(f"   Length: {len(part.strip())} characters")
                else:
                    print(f"\n   Image {i}: No OCR text found after marker")
        else:
            print("   ⚠️  No image markers found in text")
        
        # Check for specific keywords that should be in images
        print(f"\n🔍 Searching for common tool/item keywords in OCR text:")
        keywords = ['mallet', 'wrench', 'socket', 'drawer', 'tool', 'part', 'quantity']
        found_keywords = {}
        text_lower = result.text.lower()
        for keyword in keywords:
            count = text_lower.count(keyword)
            if count > 0:
                found_keywords[keyword] = count
                print(f"   ✅ '{keyword}': found {count} time(s)")
        
        if not found_keywords:
            print("   ⚠️  No common tool/item keywords found in text")
        
        # Check if text looks like it came from images
        print(f"\n📊 Text Analysis:")
        # Look for patterns typical of OCR from tool lists
        has_part_numbers = bool(__import__('re').search(r'\b\d{5,}\b', result.text))
        has_drawer_refs = bool(__import__('re').search(r'DRAWER\s+\d+', result.text, __import__('re').IGNORECASE))
        has_tool_sizes = bool(__import__('re').search(r'\d+/\d+"', result.text) or __import__('re').search(r'\d+MM', result.text))
        
        print(f"   Contains part numbers (5+ digits): {'✅ Yes' if has_part_numbers else '❌ No'}")
        print(f"   Contains drawer references: {'✅ Yes' if has_drawer_refs else '❌ No'}")
        print(f"   Contains tool sizes: {'✅ Yes' if has_tool_sizes else '❌ No'}")
        
        # Summary
        print(f"\n{'='*70}")
        print("Summary:")
        if result.images_detected and result.image_count > 0:
            if marker_count > 0:
                print(f"✅ Images detected: {result.image_count}")
                print(f"✅ Image markers inserted: {marker_count}")
                if len(result.text) > 1000:
                    print(f"✅ Substantial text extracted: {len(result.text):,} characters")
                    print(f"✅ OCR appears to be working")
                else:
                    print(f"⚠️  Limited text extracted: {len(result.text):,} characters")
                    print(f"⚠️  OCR may not have extracted much content from images")
            else:
                print(f"⚠️  Images detected: {result.image_count}")
                print(f"❌ No image markers found - markers may not be inserted")
        else:
            print(f"❌ No images detected in document")
        
        return True
        
    except Exception as e:
        import traceback
        print(f"\n❌ Error during testing:")
        print(f"   {str(e)}")
        print(f"\nFull traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test with FL10.11 SPECIFIC8 (1).pdf if it exists
    test_file = "FL10.11 SPECIFIC8 (1).pdf"
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    if not os.path.exists(test_file):
        print(f"❌ Test file not found: {test_file}")
        print(f"\nUsage: python3 test_docling_image_extraction.py [path_to_pdf]")
        sys.exit(1)
    
    success = test_image_extraction(test_file)
    sys.exit(0 if success else 1)

