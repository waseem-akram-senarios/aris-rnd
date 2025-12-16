#!/usr/bin/env python3
"""
Extract and Save Image Information - Shows how Docling extracts and RAG processes it
This version saves information step-by-step so you can see the process
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, '.')

def extract_and_save_info(file_path: str):
    """Extract image info and save to files"""
    
    output_dir = "extracted_image_info"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    
    print(f"\n{'='*70}")
    print(f"Extracting Image Information from Docling")
    print(f"File: {os.path.basename(file_path)}")
    print(f"Output: {output_dir}/")
    print(f"{'='*70}\n")
    
    # Step 1: Parse with Docling
    print("Step 1: Parsing with Docling...")
    from parsers.docling_parser import DoclingParser
    parser = DoclingParser()
    result = parser.parse(file_path)
    
    print(f"✅ Parsed: {result.pages} pages, {result.image_count} images, {len(result.text):,} chars")
    
    # Step 2: Save full text
    full_text_file = os.path.join(output_dir, f"{base_name}_FULL_TEXT_{timestamp}.txt")
    with open(full_text_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("FULL EXTRACTED TEXT FROM DOCLING\n")
        f.write("="*70 + "\n\n")
        f.write(result.text)
    print(f"✅ Saved full text: {os.path.basename(full_text_file)}")
    
    # Step 3: Extract image-by-image content
    print(f"\nStep 2: Extracting image content...")
    parts = result.text.split('<!-- image -->')
    marker_count = len(parts) - 1
    
    image_contents = []
    for i, part in enumerate(parts[1:], 1):
        ocr_text = part.strip()
        
        # Save individual image
        img_file = os.path.join(output_dir, f"{base_name}_IMAGE_{i:02d}_{timestamp}.txt")
        with open(img_file, 'w', encoding='utf-8') as f:
            f.write(f"IMAGE {i} - OCR CONTENT EXTRACTED BY DOCLING\n")
            f.write("="*70 + "\n\n")
            f.write(f"Length: {len(ocr_text):,} characters\n\n")
            f.write("FULL OCR TEXT:\n")
            f.write("-"*70 + "\n")
            f.write(ocr_text)
            f.write("\n" + "-"*70 + "\n")
        
        image_contents.append({
            'image_num': i,
            'ocr_text': ocr_text,
            'length': len(ocr_text)
        })
        
        if i <= 5:
            print(f"   Image {i}: {len(ocr_text):,} chars")
    
    # Step 4: Show how RAG would process this
    print(f"\nStep 3: Simulating RAG processing...")
    
    # Simulate what RAG does
    rag_processing = {
        'document': os.path.basename(file_path),
        'images_detected': result.image_count,
        'markers_found': marker_count,
        'marker_coverage_pct': (marker_count / result.image_count * 100) if result.image_count > 0 else 0,
        'images_with_content': len(image_contents),
        'total_ocr_chars': sum(img['length'] for img in image_contents),
        'image_content_map': {}
    }
    
    # Simulate image_content_map structure (how RAG stores it)
    for img in image_contents:
        key = f"(source, {img['image_num']})"
        rag_processing['image_content_map'][key] = {
            'content': f"[IMAGE {img['image_num']} OCR CONTENT]\n{img['ocr_text'][:2000]}...",
            'ocr_text': img['ocr_text'],
            'ocr_text_length': img['length']
        }
    
    # Save RAG processing simulation
    rag_file = os.path.join(output_dir, f"{base_name}_RAG_PROCESSING_{timestamp}.json")
    with open(rag_file, 'w', encoding='utf-8') as f:
        json.dump(rag_processing, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved RAG processing info: {os.path.basename(rag_file)}")
    
    # Step 5: Create summary report
    report_file = os.path.join(output_dir, f"{base_name}_SUMMARY_{timestamp}.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write("DOCLING IMAGE EXTRACTION & RAG PROCESSING SUMMARY\n")
        f.write("="*70 + "\n\n")
        
        f.write("DOCLING EXTRACTION:\n")
        f.write("-"*70 + "\n")
        f.write(f"Document: {os.path.basename(file_path)}\n")
        f.write(f"Pages: {result.pages}\n")
        f.write(f"Images Detected: {result.image_count}\n")
        f.write(f"Image Markers Inserted: {marker_count}\n")
        f.write(f"Marker Coverage: {rag_processing['marker_coverage_pct']:.1f}%\n")
        f.write(f"Total Text Extracted: {len(result.text):,} characters\n")
        f.write(f"Images with OCR Content: {len(image_contents)}\n")
        f.write(f"Total OCR Characters: {rag_processing['total_ocr_chars']:,}\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("HOW RAG SYSTEM PROCESSES THIS:\n")
        f.write("-"*70 + "\n")
        f.write("1. Docling extracts text and inserts <!-- image --> markers\n")
        f.write("2. RAG system finds chunks with <!-- image --> markers\n")
        f.write("3. RAG extracts OCR text after each marker\n")
        f.write("4. RAG creates image_content_map: (source, image_num) -> content\n")
        f.write("5. RAG adds Image Content section to LLM context\n")
        f.write("6. LLM searches Image Content section for answers\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("IMAGE CONTENT MAP STRUCTURE (as RAG creates it):\n")
        f.write("-"*70 + "\n")
        for key, content_info in list(rag_processing['image_content_map'].items())[:5]:
            f.write(f"\n{key}:\n")
            f.write(f"  OCR Text Length: {content_info['ocr_text_length']:,} chars\n")
            f.write(f"  Preview: {content_info['ocr_text'][:150]}...\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("SEARCH FOR 'MALLET':\n")
        f.write("-"*70 + "\n")
        
        # Search for mallet
        mallet_found = False
        mallet_locations = []
        for img in image_contents:
            if 'mallet' in img['ocr_text'].lower():
                mallet_found = True
                mallet_locations.append({
                    'image': img['image_num'],
                    'position': img['ocr_text'].lower().find('mallet'),
                    'context': img['ocr_text'][max(0, img['ocr_text'].lower().find('mallet')-100):img['ocr_text'].lower().find('mallet')+200]
                })
        
        if mallet_found:
            f.write(f"✅ 'mallet' FOUND in {len(mallet_locations)} image(s):\n")
            for loc in mallet_locations:
                f.write(f"\n  Image {loc['image']}:\n")
                f.write(f"  Position: {loc['position']} characters from marker\n")
                f.write(f"  Context: ...{loc['context']}...\n")
        else:
            f.write(f"❌ 'mallet' NOT found in marked image sections\n")
            # Check full text
            if 'mallet' in result.text.lower():
                f.write(f"⚠️  But 'mallet' IS in full text (may be in unmarked section)\n")
                idx = result.text.lower().find('mallet')
                context = result.text[max(0, idx-200):idx+300]
                f.write(f"   Context from full text: ...{context}...\n")
            else:
                f.write(f"❌ 'mallet' NOT found anywhere in extracted text\n")
                f.write(f"   Possible reasons:\n")
                f.write(f"   - OCR didn't recognize it\n")
                f.write(f"   - It's in one of the {result.image_count - marker_count} images without markers\n")
                f.write(f"   - Image quality too low for OCR\n")
    
    print(f"✅ Saved summary report: {os.path.basename(report_file)}")
    
    # Show final summary
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"📁 Files saved to: {output_dir}/")
    print(f"   ✅ Full text: {os.path.basename(full_text_file)}")
    print(f"   ✅ Individual images: {base_name}_IMAGE_XX_{timestamp}.txt")
    print(f"   ✅ RAG processing: {os.path.basename(rag_file)}")
    print(f"   ✅ Summary report: {os.path.basename(report_file)}")
    print(f"\n📊 Statistics:")
    print(f"   Images detected: {result.image_count}")
    print(f"   Markers inserted: {marker_count} ({rag_processing['marker_coverage_pct']:.1f}%)")
    print(f"   Images with content: {len(image_contents)}")
    print(f"   Total OCR chars: {rag_processing['total_ocr_chars']:,}")
    
    # Check mallet
    mallet_in_marked = any('mallet' in img['ocr_text'].lower() for img in image_contents)
    mallet_in_full = 'mallet' in result.text.lower()
    
    print(f"\n🔍 'Mallet' Status:")
    if mallet_in_marked:
        print(f"   ✅ Found in marked image sections")
    elif mallet_in_full:
        print(f"   ⚠️  Found in full text but NOT in marked sections")
        print(f"   → May be in one of the {result.image_count - marker_count} images without markers")
    else:
        print(f"   ❌ Not found in extracted text")
    
    print(f"\n💡 To view the extracted information:")
    print(f"   cat {output_dir}/{os.path.basename(report_file)}")
    print(f"   cat {output_dir}/{os.path.basename(full_text_file)} | grep -i mallet")

if __name__ == "__main__":
    test_file = "FL10.11 SPECIFIC8 (1).pdf"
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        sys.exit(1)
    
    extract_and_save_info(test_file)

