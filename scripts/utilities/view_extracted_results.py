#!/usr/bin/env python3
"""
View All Extracted OCR Results
Shows complete information extracted from images by Docling
"""

import os
import json
import glob
from pathlib import Path

def view_extracted_results():
    """Display all extracted results"""
    
    results_dir = "extracted_image_info_server"
    
    if not os.path.exists(results_dir):
        print(f"❌ Results directory not found: {results_dir}")
        print("   Run test_ocr_on_server.sh first to extract results")
        return
    
    print(f"\n{'='*70}")
    print(f"COMPLETE OCR EXTRACTION RESULTS")
    print(f"{'='*70}\n")
    
    # Find all files
    full_text_files = glob.glob(f"{results_dir}/*_FULL_TEXT_*.txt")
    report_files = glob.glob(f"{results_dir}/*_OCR_REPORT_*.txt")
    json_files = glob.glob(f"{results_dir}/*_SUMMARY_*.json")
    image_files = sorted(glob.glob(f"{results_dir}/*_IMAGE_*.txt"))
    
    # Show summary from JSON
    if json_files:
        with open(json_files[0], 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        print("📊 EXTRACTION SUMMARY:")
        print("-"*70)
        print(f"Document: {summary['document']}")
        print(f"Pages: {summary['pages']}")
        print(f"Images Detected: {summary['images_detected']}")
        print(f"Markers Inserted: {summary['markers_inserted']} ({summary['marker_coverage_pct']:.1f}%)")
        print(f"Total Text: {summary['total_text_chars']:,} characters")
        print(f"Total OCR Text: {summary['total_ocr_chars']:,} characters")
        print(f"Images with Content: {summary['images_with_content']}")
        print(f"'Mallet' Found: {'✅ Yes' if summary['mallet_found'] else '❌ No'}")
        print()
    
    # Show all images
    print(f"{'='*70}")
    print(f"ALL EXTRACTED IMAGES ({len(image_files)} images)")
    print(f"{'='*70}\n")
    
    for img_file in image_files:
        with open(img_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract image number from filename
        img_num = img_file.split('_IMAGE_')[1].split('_')[0] if '_IMAGE_' in img_file else '?'
        
        # Get OCR text length
        if "OCR Text Length:" in content:
            length_line = [l for l in content.split('\n') if 'OCR Text Length:' in l][0]
            length = length_line.split(':')[1].strip().split()[0]
        else:
            length = "unknown"
        
        # Check for tools
        tools_found = []
        tool_keywords = ['mallet', 'wrench', 'socket', 'ratchet', 'extension', 'allen', 'snips', 'cutter', 'hammer']
        content_lower = content.lower()
        for tool in tool_keywords:
            if tool in content_lower:
                tools_found.append(tool)
        
        # Check for drawers
        import re
        drawers = re.findall(r'Drawer\s+(\d+)', content, re.IGNORECASE)
        drawers = list(set(drawers))
        
        # Check for part numbers
        part_numbers = re.findall(r'\b\d{5,}\b', content)
        part_numbers = list(set(part_numbers))[:10]
        
        print(f"Image {img_num}:")
        print(f"  File: {os.path.basename(img_file)}")
        print(f"  OCR Length: {length} characters")
        if tools_found:
            print(f"  Tools Found: {', '.join(tools_found)}")
        if drawers:
            print(f"  Drawers: {', '.join(drawers)}")
        if part_numbers:
            print(f"  Part Numbers: {', '.join(part_numbers)}")
        
        # Show preview
        if "FULL OCR TEXT FROM IMAGE:" in content:
            ocr_section = content.split("FULL OCR TEXT FROM IMAGE:")[1].split("---")[0].strip()
            preview = ocr_section[:200].replace('\n', ' ')
            print(f"  Preview: {preview}...")
        print()
    
    # Show full text file info
    if full_text_files:
        full_text_file = full_text_files[0]
        file_size = os.path.getsize(full_text_file)
        print(f"{'='*70}")
        print(f"FULL EXTRACTED TEXT FILE")
        print(f"{'='*70}")
        print(f"File: {os.path.basename(full_text_file)}")
        print(f"Size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"Location: {full_text_file}")
        print()
        print("To view full text:")
        print(f"  cat {full_text_file}")
        print(f"  less {full_text_file}")
        print()
    
    # Show report file
    if report_files:
        print(f"{'='*70}")
        print(f"DETAILED REPORT")
        print(f"{'='*70}")
        print(f"File: {os.path.basename(report_files[0])}")
        print(f"Location: {report_files[0]}")
        print()
        print("To view report:")
        print(f"  cat {report_files[0]}")
        print()
    
    # Search results
    print(f"{'='*70}")
    print(f"SEARCH RESULTS IN EXTRACTED TEXT")
    print(f"{'='*70}\n")
    
    if full_text_files:
        with open(full_text_files[0], 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        search_terms = ['mallet', 'wrench', 'socket', 'ratchet', 'drawer', 'tool']
        for term in search_terms:
            count = full_text.lower().count(term)
            if count > 0:
                print(f"'{term}': {count} occurrence(s)")
                # Show first occurrence context
                idx = full_text.lower().find(term)
                if idx >= 0:
                    context = full_text[max(0, idx-100):idx+200]
                    print(f"  First occurrence: ...{context}...")
            else:
                print(f"'{term}': Not found")
            print()
    
    print(f"{'='*70}")
    print("FILES LOCATION")
    print(f"{'='*70}")
    print(f"All files are in: {os.path.abspath(results_dir)}/")
    print()
    print("Quick access commands:")
    print(f"  cd {results_dir}")
    print(f"  ls -lh")
    print(f"  cat *_FULL_TEXT_*.txt | less")
    print(f"  grep -i 'mallet\|wrench\|socket' *_FULL_TEXT_*.txt")

if __name__ == "__main__":
    view_extracted_results()

