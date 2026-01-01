#!/usr/bin/env python3
"""
Side-by-side OCR Accuracy Comparison Test
Compares OCR extracted directly from PDF images vs OCR stored in API/OpenSearch
"""
import sys
import os
import requests
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# API base URL
API_BASE = "http://44.221.84.58:8500"

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("⚠️  PyMuPDF not available - cannot extract images directly from PDF")

try:
    from docling.document_converter import DocumentConverter
    HAS_DOCLING = True
except ImportError:
    HAS_DOCLING = False
    print("⚠️  Docling not available - using alternative OCR extraction")


def extract_ocr_from_pdf_images(pdf_path: str) -> Dict[str, Any]:
    """
    Extract OCR text directly from PDF images using Docling.
    This gives us the 'ground truth' OCR from the actual document.
    """
    print(f"\n{'='*80}")
    print("STEP 1: Extracting OCR directly from PDF images")
    print(f"{'='*80}")
    
    result = {
        'pdf_path': pdf_path,
        'images': [],
        'total_images': 0,
        'extraction_method': 'docling',
        'extraction_timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    
    if not HAS_DOCLING:
        print("❌ Docling not available - cannot extract OCR from PDF")
        return result
    
    try:
        converter = DocumentConverter()
        print(f"📄 Processing PDF: {pdf_path}")
        
        # Convert document
        doc = converter.convert(pdf_path)
        
        # Extract images with OCR
        images_data = []
        image_counter = 0
        
        # Get document structure - try multiple approaches
        # Method 1: Check if doc has content attribute
        if hasattr(doc, 'content'):
            for item in doc.content:
                item_type = getattr(item, 'type', None) or getattr(item, '__class__', {}).__name__.lower()
                
                # Check if it's an image
                if 'image' in str(item_type).lower() or hasattr(item, 'image'):
                    image_counter += 1
                    ocr_text = ""
                    
                    # Try multiple ways to get OCR text
                    if hasattr(item, 'text'):
                        ocr_text = str(item.text)
                    elif hasattr(item, 'content'):
                        content = item.content
                        if isinstance(content, str):
                            ocr_text = content
                        elif isinstance(content, list):
                            ocr_text = " ".join(str(c) for c in content if c)
                    elif hasattr(item, 'ocr_text'):
                        ocr_text = str(item.ocr_text)
                    
                    # Get page number
                    page_num = (getattr(item, 'page', None) or 
                               getattr(item, 'page_number', None) or 
                               getattr(item, 'page_num', None) or 0)
                    
                    images_data.append({
                        'image_number': image_counter,
                        'page': page_num,
                        'ocr_text': ocr_text,
                        'ocr_text_length': len(ocr_text),
                        'source': 'direct_pdf_extraction'
                    })
        
        # Method 2: Try to extract from document text with image markers
        # This is a fallback - extract text that might contain image OCR
        if not images_data and hasattr(doc, 'document'):
            # Try to get text content and look for image markers
            doc_text = ""
            if hasattr(doc.document, 'export_to_markdown'):
                doc_text = doc.document.export_to_markdown()
            elif hasattr(doc, 'export_to_markdown'):
                doc_text = doc.export_to_markdown()
            
            # Look for image markers and extract text between them
            if '<!-- image -->' in doc_text or '<image>' in doc_text.lower():
                # Split by image markers
                parts = doc_text.split('<!-- image -->')
                for i, part in enumerate(parts[1:], 1):  # Skip first part (before first image)
                    ocr_text = part.strip()
                    if ocr_text:
                        images_data.append({
                            'image_number': i,
                            'page': 0,  # Page unknown
                            'ocr_text': ocr_text,
                            'ocr_text_length': len(ocr_text),
                            'source': 'direct_pdf_extraction_markers'
                        })
        
        result['images'] = images_data
        result['total_images'] = len(images_data)
        
        print(f"✅ Extracted {len(images_data)} images with OCR from PDF")
        for img in images_data[:5]:  # Show first 5
            print(f"  Image {img['image_number']} (Page {img['page']}): {img['ocr_text_length']} chars")
        
    except Exception as e:
        print(f"❌ Error extracting OCR from PDF: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


def get_stored_ocr_from_api(document_id: str) -> Dict[str, Any]:
    """
    Get stored OCR from API/OpenSearch.
    This is what the API has stored.
    """
    print(f"\n{'='*80}")
    print("STEP 2: Retrieving stored OCR from API")
    print(f"{'='*80}")
    
    result = {
        'document_id': document_id,
        'images': [],
        'total_images': 0,
        'source': 'api_stored'
    }
    
    try:
        # Get all images for this document
        response = requests.get(
            f"{API_BASE}/documents/{document_id}/images/all",
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get images: {response.status_code}")
            print(response.text[:500])
            return result
        
        data = response.json()
        images = data.get('images', [])
        
        result['images'] = images
        result['total_images'] = len(images)
        result['document_name'] = data.get('document_name', '')
        
        print(f"✅ Retrieved {len(images)} stored images from API")
        for img in images[:5]:  # Show first 5
            print(f"  Image {img.get('image_number', 'N/A')} (Page {img.get('page', 'N/A')}): "
                  f"{img.get('ocr_text_length', 0)} chars")
        
    except Exception as e:
        print(f"❌ Error retrieving stored OCR: {e}")
        import traceback
        traceback.print_exc()
        result['error'] = str(e)
    
    return result


def compare_ocr_side_by_side(
    direct_ocr: Dict[str, Any],
    stored_ocr: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Compare OCR from direct PDF extraction vs stored OCR from API.
    """
    print(f"\n{'='*80}")
    print("STEP 3: Side-by-Side OCR Comparison")
    print(f"{'='*80}")
    
    comparison = {
        'total_direct_images': len(direct_ocr.get('images', [])),
        'total_stored_images': len(stored_ocr.get('images', [])),
        'matched_images': 0,
        'comparisons': [],
        'overall_accuracy': 0.0,
        'average_accuracy': 0.0
    }
    
    # Create lookup by page and image number
    stored_by_page = {}
    for img in stored_ocr.get('images', []):
        page = img.get('page', 0)
        img_num = img.get('image_number', 0)
        if page not in stored_by_page:
            stored_by_page[page] = {}
        stored_by_page[page][img_num] = img
    
    # Compare each direct OCR image with stored OCR
    from shared.utils.ocr_verifier import OCRVerifier
    verifier = OCRVerifier()
    
    accuracies = []
    
    for direct_img in direct_ocr.get('images', []):
        page = direct_img.get('page', 0)
        img_num = direct_img.get('image_number', 0)
        direct_text = direct_img.get('ocr_text', '')
        
        # Find matching stored image
        stored_img = stored_by_page.get(page, {}).get(img_num)
        
        if stored_img:
            stored_text = stored_img.get('ocr_text', '')
            
            # Calculate similarity
            similarity = verifier._calculate_similarity(
                verifier._normalize_text(direct_text),
                verifier._normalize_text(stored_text)
            )
            
            char_accuracy = verifier._character_accuracy(
                verifier._normalize_text(direct_text),
                verifier._normalize_text(stored_text)
            )
            
            accuracies.append(similarity)
            comparison['matched_images'] += 1
            
            comp_result = {
                'image_number': img_num,
                'page': page,
                'direct_ocr_length': len(direct_text),
                'stored_ocr_length': len(stored_text),
                'similarity': similarity,
                'character_accuracy': char_accuracy,
                'direct_ocr_preview': direct_text[:200] + ('...' if len(direct_text) > 200 else ''),
                'stored_ocr_preview': stored_text[:200] + ('...' if len(stored_text) > 200 else ''),
                'direct_ocr_full': direct_text,
                'stored_ocr_full': stored_text
            }
            
            comparison['comparisons'].append(comp_result)
        else:
            # No matching stored image
            comp_result = {
                'image_number': img_num,
                'page': page,
                'direct_ocr_length': len(direct_text),
                'stored_ocr_length': 0,
                'similarity': 0.0,
                'character_accuracy': 0.0,
                'status': 'not_found_in_stored',
                'direct_ocr_preview': direct_text[:200] + ('...' if len(direct_text) > 200 else ''),
                'stored_ocr_preview': 'NOT FOUND IN STORED OCR',
                'direct_ocr_full': direct_text,
                'stored_ocr_full': ''
            }
            comparison['comparisons'].append(comp_result)
    
    # Calculate overall accuracy
    if accuracies:
        comparison['average_accuracy'] = sum(accuracies) / len(accuracies)
        comparison['overall_accuracy'] = comparison['average_accuracy']
    
    return comparison


def print_comparison_report(comparison: Dict[str, Any]):
    """
    Print a detailed side-by-side comparison report.
    """
    print(f"\n{'='*80}")
    print("OCR ACCURACY COMPARISON REPORT")
    print(f"{'='*80}")
    
    print(f"\n📊 Summary:")
    print(f"  Direct PDF Images: {comparison['total_direct_images']}")
    print(f"  Stored API Images: {comparison['total_stored_images']}")
    print(f"  Matched Images: {comparison['matched_images']}")
    print(f"  Overall Accuracy: {comparison['overall_accuracy']:.2%}")
    print(f"  Average Accuracy: {comparison['average_accuracy']:.2%}")
    
    print(f"\n{'='*80}")
    print("DETAILED SIDE-BY-SIDE COMPARISON")
    print(f"{'='*80}")
    
    for i, comp in enumerate(comparison.get('comparisons', []), 1):
        print(f"\n{'─'*80}")
        print(f"IMAGE {comp.get('image_number', 'N/A')} - Page {comp.get('page', 'N/A')}")
        print(f"{'─'*80}")
        
        print(f"\n📏 Length Comparison:")
        print(f"  Direct OCR: {comp.get('direct_ocr_length', 0):,} characters")
        print(f"  Stored OCR: {comp.get('stored_ocr_length', 0):,} characters")
        print(f"  Difference: {abs(comp.get('direct_ocr_length', 0) - comp.get('stored_ocr_length', 0)):,} characters")
        
        print(f"\n📊 Accuracy Metrics:")
        print(f"  Similarity: {comp.get('similarity', 0):.2%}")
        print(f"  Character Accuracy: {comp.get('character_accuracy', 0):.2%}")
        
        status = comp.get('status', 'matched')
        if status == 'not_found_in_stored':
            print(f"  ⚠️  Status: NOT FOUND IN STORED OCR")
        elif comp.get('similarity', 0) >= 0.90:
            print(f"  ✅ Status: EXCELLENT MATCH")
        elif comp.get('similarity', 0) >= 0.85:
            print(f"  ⚠️  Status: GOOD MATCH (needs review)")
        else:
            print(f"  ❌ Status: POOR MATCH (needs attention)")
        
        print(f"\n📄 Direct OCR (from PDF):")
        print(f"  {'─'*76}")
        direct_preview = comp.get('direct_ocr_preview', '')
        if direct_preview:
            # Print in chunks to avoid overwhelming output
            direct_lines = direct_preview.split('\n')
            lines = direct_lines[:10]  # First 10 lines
            for line in lines:
                print(f"  {line[:76]}")
            if len(direct_lines) > 10:
                remaining = len(direct_lines) - 10
                print(f"  ... ({remaining} more lines)")
        else:
            print(f"  (empty)")
        
        print(f"\n💾 Stored OCR (from API):")
        print(f"  {'─'*76}")
        stored_preview = comp.get('stored_ocr_preview', '')
        if stored_preview:
            stored_lines = stored_preview.split('\n')
            lines = stored_lines[:10]  # First 10 lines
            for line in lines:
                print(f"  {line[:76]}")
            if len(stored_lines) > 10:
                remaining = len(stored_lines) - 10
                print(f"  ... ({remaining} more lines)")
        else:
            print(f"  (empty)")
        
        # Show differences if significant
        if comp.get('similarity', 0) < 0.95 and comp.get('direct_ocr_length', 0) > 0:
            print(f"\n🔍 Key Differences:")
            direct_words = set(comp.get('direct_ocr_full', '').lower().split())
            stored_words = set(comp.get('stored_ocr_full', '').lower().split())
            missing = direct_words - stored_words
            extra = stored_words - direct_words
            
            if missing:
                print(f"  Missing in stored: {list(missing)[:10]}")
            if extra:
                print(f"  Extra in stored: {list(extra)[:10]}")


def save_comparison_report(comparison: Dict[str, Any], output_file: str = "ocr_comparison_report.json"):
    """
    Save comparison report to JSON file.
    """
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Comparison report saved to: {output_file}")
    except Exception as e:
        print(f"\n❌ Error saving report: {e}")


def main():
    """Main test function"""
    print("="*80)
    print("OCR ACCURACY COMPARISON TEST")
    print("Side-by-Side: Direct PDF OCR vs API Stored OCR")
    print("="*80)
    
    # Step 1: Get document ID
    print("\n📋 Step 0: Getting document information...")
    try:
        response = requests.get(f"{API_BASE}/documents", timeout=30)
        if response.status_code != 200:
            print(f"❌ Failed to get documents: {response.status_code}")
            return 1
        
        documents = response.json().get('documents', [])
        if not documents:
            print("❌ No documents found. Please upload a document first.")
            return 1
        
        # Use first document
        doc = documents[0]
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        
        print(f"✅ Found document: {doc_name}")
        print(f"   Document ID: {doc_id}")
        
        # Find PDF file
        pdf_path = None
        for pdf_file in Path('.').glob('*.pdf'):
            if pdf_file.name == doc_name or pdf_file.name in doc_name:
                pdf_path = str(pdf_file)
                break
        
        if not pdf_path:
            # Try to find any PDF
            for pdf_file in Path('.').glob('*.pdf'):
                pdf_path = str(pdf_file)
                break
        
        if not pdf_path:
            print(f"❌ PDF file not found locally: {doc_name}")
            print("   Please ensure the PDF file is in the current directory")
            return 1
        
        print(f"✅ Found PDF file: {pdf_path}")
        
    except Exception as e:
        print(f"❌ Error getting document info: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Step 2: Extract OCR directly from PDF
    direct_ocr = extract_ocr_from_pdf_images(pdf_path)
    
    if not direct_ocr.get('images'):
        print("⚠️  No images extracted from PDF. Cannot compare.")
        return 1
    
    # Step 3: Get stored OCR from API
    stored_ocr = get_stored_ocr_from_api(doc_id)
    
    if not stored_ocr.get('images'):
        print("⚠️  No stored images found in API. Cannot compare.")
        return 1
    
    # Step 4: Compare side-by-side
    comparison = compare_ocr_side_by_side(direct_ocr, stored_ocr)
    
    # Step 5: Print report
    print_comparison_report(comparison)
    
    # Step 6: Save report
    save_comparison_report(comparison)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Direct OCR Images: {comparison['total_direct_images']}")
    print(f"✅ Stored OCR Images: {comparison['total_stored_images']}")
    print(f"✅ Matched: {comparison['matched_images']}")
    print(f"📊 Overall Accuracy: {comparison['overall_accuracy']:.2%}")
    
    if comparison['overall_accuracy'] >= 0.90:
        print(f"\n✅ EXCELLENT: OCR accuracy is very high!")
    elif comparison['overall_accuracy'] >= 0.85:
        print(f"\n⚠️  GOOD: OCR accuracy is acceptable but could be improved")
    else:
        print(f"\n❌ NEEDS ATTENTION: OCR accuracy is below threshold")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
