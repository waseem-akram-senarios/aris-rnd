#!/usr/bin/env python3
"""
Extract and Save Image Information from Docling
Shows exactly how Docling extracts information from images and how RAG processes it
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')

from parsers.docling_parser import DoclingParser

def extract_image_information(file_path: str, output_dir: str = "extracted_image_info"):
    """Extract all image information and save to files"""
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    print(f"\n{'='*70}")
    print(f"Extracting Image Information from Docling")
    print(f"File: {os.path.basename(file_path)}")
    print(f"{'='*70}\n")
    
    try:
        parser = DoclingParser()
        
        print("Step 1: Parsing document with Docling...")
        result = parser.parse(file_path)
        
        print(f"✅ Parsing completed")
        print(f"   Pages: {result.pages}")
        print(f"   Images detected: {result.images_detected}")
        print(f"   Image count: {result.image_count}")
        print(f"   Text length: {len(result.text):,} characters")
        
        # Save full extracted text
        full_text_file = os.path.join(output_dir, f"{base_name}_full_text_{timestamp}.txt")
        with open(full_text_file, 'w', encoding='utf-8') as f:
            f.write(result.text)
        print(f"\n✅ Saved full extracted text to: {full_text_file}")
        
        # Extract image-specific information
        image_info = {
            'document': os.path.basename(file_path),
            'timestamp': timestamp,
            'pages': result.pages,
            'images_detected': result.images_detected,
            'image_count': result.image_count,
            'total_text_length': len(result.text),
            'marker_count': result.text.count('<!-- image -->'),
            'marker_coverage': (result.text.count('<!-- image -->') / result.image_count * 100) if result.image_count > 0 else 0,
            'images': []
        }
        
        # Split text by image markers to extract individual image content
        parts = result.text.split('<!-- image -->')
        print(f"\nStep 2: Extracting content from each image...")
        print(f"   Found {len(parts) - 1} image marker(s)")
        
        for i, part in enumerate(parts[1:], 1):
            # Get text after marker (OCR content from image)
            ocr_text = part.strip()
            
            # Get context before (if any)
            before_text = parts[i-1].strip() if i > 0 else ''
            
            image_data = {
                'image_number': i,
                'ocr_text_length': len(ocr_text),
                'ocr_text': ocr_text[:5000],  # First 5000 chars
                'ocr_text_full_length': len(ocr_text),
                'context_before_length': len(before_text),
                'context_before': before_text[-500:] if before_text else '',  # Last 500 chars
            }
            
            # Check for common patterns
            import re
            image_data['has_part_numbers'] = bool(re.search(r'\b\d{5,}\b', ocr_text))
            image_data['has_drawer_refs'] = bool(re.search(r'DRAWER\s+\d+', ocr_text, re.IGNORECASE))
            image_data['has_tool_names'] = bool(re.search(r'\b(wrench|socket|ratchet|mallet|hammer|tool)\b', ocr_text, re.IGNORECASE))
            
            # Extract specific tool/item names found
            tool_keywords = ['mallet', 'wrench', 'socket', 'ratchet', 'extension', 'allen', 'snips', 'cutter', 'hammer']
            found_tools = [tool for tool in tool_keywords if tool in ocr_text.lower()]
            image_data['tools_found'] = found_tools
            
            # Extract part numbers
            part_numbers = re.findall(r'\b\d{5,}\b', ocr_text)
            image_data['part_numbers'] = list(set(part_numbers))[:20]  # First 20 unique
            
            # Extract drawer references
            drawer_refs = re.findall(r'DRAWER\s+(\d+)', ocr_text, re.IGNORECASE)
            image_data['drawer_references'] = list(set(drawer_refs))
            
            image_info['images'].append(image_data)
            
            # Save individual image content to separate file
            image_file = os.path.join(output_dir, f"{base_name}_image_{i:02d}_{timestamp}.txt")
            with open(image_file, 'w', encoding='utf-8') as f:
                f.write(f"Image {i} - OCR Content\n")
                f.write("="*70 + "\n\n")
                f.write(f"OCR Text Length: {len(ocr_text):,} characters\n")
                f.write(f"Has Part Numbers: {image_data['has_part_numbers']}\n")
                f.write(f"Has Drawer References: {image_data['has_drawer_refs']}\n")
                f.write(f"Tools Found: {', '.join(found_tools) if found_tools else 'None'}\n")
                f.write(f"Part Numbers: {', '.join(image_data['part_numbers'][:10]) if image_data['part_numbers'] else 'None'}\n")
                f.write(f"Drawer References: {', '.join(image_data['drawer_references']) if image_data['drawer_references'] else 'None'}\n")
                f.write("\n" + "="*70 + "\n")
                f.write("FULL OCR TEXT:\n")
                f.write("="*70 + "\n\n")
                f.write(ocr_text)
            
            if i <= 5:  # Show first 5
                print(f"   Image {i}: {len(ocr_text):,} chars, Tools: {len(found_tools)}, Part numbers: {len(image_data['part_numbers'])}")
        
        # Save summary JSON
        summary_file = os.path.join(output_dir, f"{base_name}_summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(image_info, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved summary JSON to: {summary_file}")
        
        # Create a readable summary report
        report_file = os.path.join(output_dir, f"{base_name}_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("DOCLING IMAGE EXTRACTION REPORT\n")
            f.write("="*70 + "\n\n")
            f.write(f"Document: {os.path.basename(file_path)}\n")
            f.write(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"\nDocument Statistics:\n")
            f.write(f"  Pages: {result.pages}\n")
            f.write(f"  Images Detected: {result.image_count}\n")
            f.write(f"  Image Markers: {image_info['marker_count']}\n")
            f.write(f"  Marker Coverage: {image_info['marker_coverage']:.1f}%\n")
            f.write(f"  Total Text Extracted: {len(result.text):,} characters\n")
            f.write(f"\n" + "="*70 + "\n")
            f.write("IMAGE-BY-IMAGE BREAKDOWN\n")
            f.write("="*70 + "\n\n")
            
            for img in image_info['images']:
                f.write(f"Image {img['image_number']}:\n")
                f.write(f"  OCR Text Length: {img['ocr_text_length']:,} characters\n")
                f.write(f"  Has Part Numbers: {img['has_part_numbers']}\n")
                f.write(f"  Has Drawer References: {img['has_drawer_refs']}\n")
                f.write(f"  Tools Found: {', '.join(img['tools_found']) if img['tools_found'] else 'None'}\n")
                if img['part_numbers']:
                    f.write(f"  Part Numbers: {', '.join(img['part_numbers'][:10])}\n")
                if img['drawer_references']:
                    f.write(f"  Drawer References: {', '.join(img['drawer_references'])}\n")
                f.write(f"  Preview (first 200 chars): {img['ocr_text'][:200]}...\n")
                f.write("\n")
            
            # Search for specific items
            f.write("\n" + "="*70 + "\n")
            f.write("SEARCH RESULTS FOR COMMON TOOLS/ITEMS\n")
            f.write("="*70 + "\n\n")
            
            search_terms = ['mallet', 'wrench', 'socket', 'ratchet', 'drawer']
            for term in search_terms:
                count = result.text.lower().count(term)
                if count > 0:
                    f.write(f"'{term}': Found {count} time(s)\n")
                    # Find which images contain it
                    containing_images = []
                    for img in image_info['images']:
                        if term in img['ocr_text'].lower():
                            containing_images.append(img['image_number'])
                    if containing_images:
                        f.write(f"  Found in images: {containing_images}\n")
                else:
                    f.write(f"'{term}': Not found\n")
                f.write("\n")
        
        print(f"✅ Saved detailed report to: {report_file}")
        
        # Show summary
        print(f"\n{'='*70}")
        print("EXTRACTION SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Total images processed: {len(image_info['images'])}")
        print(f"✅ Marker coverage: {image_info['marker_coverage']:.1f}%")
        print(f"✅ Total OCR text: {sum(img['ocr_text_length'] for img in image_info['images']):,} characters")
        
        # Check for mallet specifically
        mallet_found = False
        mallet_images = []
        for img in image_info['images']:
            if 'mallet' in img['ocr_text'].lower():
                mallet_found = True
                mallet_images.append(img['image_number'])
        
        print(f"\n🔍 'Mallet' search:")
        if mallet_found:
            print(f"   ✅ Found in images: {mallet_images}")
        else:
            print(f"   ❌ Not found in marked image sections")
            # Check full text
            if 'mallet' in result.text.lower():
                print(f"   ⚠️  But found in full text (may be in unmarked section)")
        
        print(f"\n📁 All files saved to: {output_dir}/")
        print(f"   - Full text: {os.path.basename(full_text_file)}")
        print(f"   - Summary JSON: {os.path.basename(summary_file)}")
        print(f"   - Report: {os.path.basename(report_file)}")
        print(f"   - Individual images: {base_name}_image_XX_{timestamp}.txt")
        
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_file = "FL10.11 SPECIFIC8 (1).pdf"
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        sys.exit(1)
    
    extract_image_information(test_file)

