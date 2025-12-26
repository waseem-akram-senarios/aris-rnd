#!/usr/bin/env python3
"""
Test OCR Extraction on Server
Runs comprehensive OCR test and saves all results
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/app' if os.path.exists('/app') else '.')

from parsers.docling_parser import DoclingParser

def test_ocr_extraction(file_path: str):
    """Test OCR extraction and save detailed results"""
    
    output_dir = "/tmp/extracted_image_info"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    print(f"\n{'='*70}")
    print(f"OCR EXTRACTION TEST ON SERVER")
    print(f"File: {os.path.basename(file_path)}")
    print(f"Timestamp: {timestamp}")
    print(f"{'='*70}\n")
    
    try:
        # Step 1: Parse with Docling
        print("Step 1: Parsing document with Docling (OCR enabled)...")
        parser = DoclingParser()
        result = parser.parse(file_path)
        
        print(f"✅ Parsing completed")
        print(f"   Pages: {result.pages}")
        print(f"   Images detected: {result.images_detected}")
        print(f"   Image count: {result.image_count}")
        print(f"   Text length: {len(result.text):,} characters")
        print(f"   Confidence: {result.confidence}")
        
        # Step 2: Save full extracted text
        full_text_file = os.path.join(output_dir, f"{base_name}_FULL_TEXT_{timestamp}.txt")
        with open(full_text_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("FULL TEXT EXTRACTED BY DOCLING (INCLUDING OCR FROM IMAGES)\n")
            f.write("="*70 + "\n\n")
            f.write(result.text)
        print(f"\n✅ Saved full text ({len(result.text):,} chars): {os.path.basename(full_text_file)}")
        
        # Step 3: Extract image-by-image content
        print(f"\nStep 2: Extracting content from each image...")
        parts = result.text.split('<!-- image -->')
        marker_count = len(parts) - 1
        
        print(f"   Found {marker_count} image marker(s)")
        print(f"   Expected {result.image_count} images")
        coverage = (marker_count / result.image_count * 100) if result.image_count > 0 else 0
        print(f"   Coverage: {coverage:.1f}%")
        
        image_data = []
        for i, part in enumerate(parts[1:], 1):
            ocr_text = part.strip()
            
            # Save individual image content
            img_file = os.path.join(output_dir, f"{base_name}_IMAGE_{i:02d}_{timestamp}.txt")
            with open(img_file, 'w', encoding='utf-8') as f:
                f.write(f"IMAGE {i} - OCR CONTENT EXTRACTED BY DOCLING\n")
                f.write("="*70 + "\n\n")
                f.write(f"OCR Text Length: {len(ocr_text):,} characters\n\n")
                f.write("FULL OCR TEXT FROM IMAGE:\n")
                f.write("-"*70 + "\n")
                f.write(ocr_text)
                f.write("\n" + "-"*70 + "\n")
            
            # Analyze content
            import re
            img_info = {
                'image_number': i,
                'ocr_text_length': len(ocr_text),
                'has_part_numbers': bool(re.search(r'\b\d{5,}\b', ocr_text)),
                'has_drawer_refs': bool(re.search(r'DRAWER\s+\d+', ocr_text, re.IGNORECASE)),
                'has_tool_names': bool(re.search(r'\b(wrench|socket|ratchet|mallet|hammer|tool)\b', ocr_text, re.IGNORECASE)),
            }
            
            # Extract specific items
            tool_keywords = ['mallet', 'wrench', 'socket', 'ratchet', 'extension', 'allen', 'snips', 'cutter', 'hammer']
            img_info['tools_found'] = [tool for tool in tool_keywords if tool in ocr_text.lower()]
            img_info['part_numbers'] = list(set(re.findall(r'\b\d{5,}\b', ocr_text)))[:20]
            img_info['drawer_refs'] = list(set(re.findall(r'DRAWER\s+(\d+)', ocr_text, re.IGNORECASE)))
            
            image_data.append(img_info)
            
            if i <= 10:
                print(f"   Image {i}: {len(ocr_text):,} chars, Tools: {len(img_info['tools_found'])}, Parts: {len(img_info['part_numbers'])}")
        
        # Step 4: Create comprehensive report
        report_file = os.path.join(output_dir, f"{base_name}_OCR_REPORT_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("DOCLING OCR EXTRACTION TEST REPORT\n")
            f.write("="*70 + "\n\n")
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Document: {os.path.basename(file_path)}\n")
            f.write(f"Server: Production Server (High Processing Power)\n\n")
            
            f.write("DOCLING EXTRACTION RESULTS:\n")
            f.write("-"*70 + "\n")
            f.write(f"Pages: {result.pages}\n")
            f.write(f"Images Detected: {result.image_count}\n")
            f.write(f"Image Markers Inserted: {marker_count}\n")
            f.write(f"Marker Coverage: {coverage:.1f}%\n")
            f.write(f"Total Text Extracted: {len(result.text):,} characters\n")
            f.write(f"Words Extracted: {len(result.text.split()):,}\n")
            f.write(f"Confidence: {result.confidence:.1%}\n")
            f.write(f"Extraction Percentage: {result.extraction_percentage:.1%}\n\n")
            
            f.write("="*70 + "\n")
            f.write("IMAGE-BY-IMAGE BREAKDOWN\n")
            f.write("="*70 + "\n\n")
            
            for img in image_data:
                f.write(f"Image {img['image_number']}:\n")
                f.write(f"  OCR Text Length: {img['ocr_text_length']:,} characters\n")
                f.write(f"  Has Part Numbers: {img['has_part_numbers']}\n")
                f.write(f"  Has Drawer References: {img['has_drawer_refs']}\n")
                f.write(f"  Has Tool Names: {img['has_tool_names']}\n")
                if img['tools_found']:
                    f.write(f"  Tools Found: {', '.join(img['tools_found'])}\n")
                if img['part_numbers']:
                    f.write(f"  Part Numbers: {', '.join(img['part_numbers'][:10])}\n")
                if img['drawer_refs']:
                    f.write(f"  Drawer References: {', '.join(img['drawer_refs'])}\n")
                f.write("\n")
            
            f.write("="*70 + "\n")
            f.write("SEARCH FOR SPECIFIC ITEMS\n")
            f.write("="*70 + "\n\n")
            
            # Search for mallet and other tools
            search_terms = ['mallet', 'wrench', 'socket', 'ratchet', 'drawer', 'tool', 'part']
            for term in search_terms:
                count = result.text.lower().count(term)
                f.write(f"'{term}': {count} occurrence(s)\n")
                
                # Find which images contain it
                containing_images = [img['image_number'] for img in image_data 
                                   if term in parts[img['image_number']].lower()]
                if containing_images:
                    f.write(f"  Found in images: {containing_images}\n")
                f.write("\n")
            
            # Specific mallet search
            f.write("="*70 + "\n")
            f.write("DETAILED 'MALLET' SEARCH\n")
            f.write("="*70 + "\n\n")
            
            mallet_found = False
            mallet_locations = []
            
            # Check in marked images
            for img in image_data:
                img_text = parts[img['image_number']].lower()
                if 'mallet' in img_text:
                    mallet_found = True
                    idx = img_text.find('mallet')
                    context = parts[img['image_number']][max(0, idx-150):idx+250]
                    mallet_locations.append({
                        'image': img['image_number'],
                        'context': context
                    })
            
            if mallet_found:
                f.write(f"✅ 'mallet' FOUND in {len(mallet_locations)} marked image(s):\n\n")
                for loc in mallet_locations:
                    f.write(f"Image {loc['image']}:\n")
                    f.write(f"Context: ...{loc['context']}...\n\n")
            else:
                f.write(f"❌ 'mallet' NOT found in marked image sections\n\n")
                
                # Check full text
                if 'mallet' in result.text.lower():
                    f.write(f"⚠️  But 'mallet' IS in full extracted text!\n")
                    f.write(f"   This means it's likely in one of the {result.image_count - marker_count} images WITHOUT markers\n\n")
                    idx = result.text.lower().find('mallet')
                    context = result.text[max(0, idx-200):idx+300]
                    f.write(f"Context from full text:\n")
                    f.write(f"...{context}...\n")
                else:
                    f.write(f"❌ 'mallet' NOT found anywhere in extracted text\n\n")
                    f.write(f"Possible reasons:\n")
                    f.write(f"  1. OCR didn't recognize it (image quality issue)\n")
                    f.write(f"  2. It's spelled differently in the image\n")
                    f.write(f"  3. It's in an image that returned empty OCR result\n")
            
            f.write("\n" + "="*70 + "\n")
            f.write("HOW RAG SYSTEM PROCESSES THIS\n")
            f.write("="*70 + "\n\n")
            f.write("1. Docling extracts text and inserts <!-- image --> markers\n")
            f.write(f"   → {marker_count} markers inserted for {result.image_count} images ({coverage:.1f}% coverage)\n\n")
            f.write("2. RAG system finds chunks with <!-- image --> markers\n")
            f.write(f"   → Will find {marker_count} image sections\n\n")
            f.write("3. RAG extracts OCR text after each marker\n")
            f.write(f"   → Total OCR text available: {sum(img['ocr_text_length'] for img in image_data):,} characters\n\n")
            f.write("4. RAG creates image_content_map structure\n")
            f.write("   → Maps (source, image_num) to OCR content\n\n")
            f.write("5. RAG adds Image Content section to LLM context\n")
            f.write("   → LLM can search this section for tool/item names\n\n")
            f.write("6. When user asks 'Where can I find the Mallet?':\n")
            if mallet_found:
                f.write("   → ✅ Mallet IS in Image Content section\n")
                f.write("   → LLM should find it and provide answer\n")
            else:
                f.write("   → ❌ Mallet NOT in Image Content section (not in marked images)\n")
                f.write(f"   → Need to improve marker insertion or search all text\n")
        
        print(f"\n✅ Saved comprehensive report: {os.path.basename(report_file)}")
        
        # Step 5: Save JSON summary
        summary = {
            'document': os.path.basename(file_path),
            'timestamp': timestamp,
            'pages': result.pages,
            'images_detected': result.image_count,
            'markers_inserted': marker_count,
            'marker_coverage_pct': coverage,
            'total_text_chars': len(result.text),
            'images_with_content': len(image_data),
            'total_ocr_chars': sum(img['ocr_text_length'] for img in image_data),
            'mallet_found': mallet_found,
            'mallet_in_marked_images': len(mallet_locations) if mallet_found else 0,
            'images': image_data
        }
        
        json_file = os.path.join(output_dir, f"{base_name}_SUMMARY_{timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved JSON summary: {os.path.basename(json_file)}")
        
        # Final summary
        print(f"\n{'='*70}")
        print("TEST SUMMARY")
        print(f"{'='*70}")
        print(f"✅ Images detected: {result.image_count}")
        print(f"✅ Markers inserted: {marker_count} ({coverage:.1f}%)")
        print(f"✅ Images with content: {len(image_data)}")
        print(f"✅ Total OCR text: {sum(img['ocr_text_length'] for img in image_data):,} characters")
        print(f"\n🔍 'Mallet' Status:")
        if mallet_found:
            print(f"   ✅ Found in {len(mallet_locations)} marked image(s)")
        elif 'mallet' in result.text.lower():
            print(f"   ⚠️  Found in full text but NOT in marked sections")
            print(f"   → Likely in one of the {result.image_count - marker_count} images without markers")
        else:
            print(f"   ❌ Not found in extracted text")
        
        print(f"\n📁 All files saved to: {output_dir}/")
        print(f"   - Full text: {base_name}_FULL_TEXT_{timestamp}.txt")
        print(f"   - Report: {base_name}_OCR_REPORT_{timestamp}.txt")
        print(f"   - JSON summary: {base_name}_SUMMARY_{timestamp}.json")
        print(f"   - Individual images: {base_name}_IMAGE_XX_{timestamp}.txt")
        
        return True
        
    except Exception as e:
        import traceback
        print(f"\n❌ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_file = "FL10.11 SPECIFIC8 (1).pdf"
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    # Check if file exists in common locations
    if not os.path.exists(test_file):
        # Try in /app (Docker container)
        if os.path.exists(f"/app/{test_file}"):
            test_file = f"/app/{test_file}"
        elif os.path.exists(f"/opt/aris-rag/{test_file}"):
            test_file = f"/opt/aris-rag/{test_file}"
        else:
            print(f"❌ File not found: {test_file}")
            sys.exit(1)
    
    success = test_ocr_extraction(test_file)
    sys.exit(0 if success else 1)

