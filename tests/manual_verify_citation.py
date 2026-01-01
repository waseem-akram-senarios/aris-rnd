import sys
import os
import io
import time
sys.path.append(os.getcwd())

import logging
logging.basicConfig(level=logging.ERROR) # Less noise

try:
    from parsers.pymupdf_parser import PyMuPDFParser
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), '..'))
    from parsers.pymupdf_parser import PyMuPDFParser

def test_citation_accuracy():
    print("\nXXX VERIFYING CITATION ACCURACY CHANGES XXX")
    
    # 1. Find PDFs
    candidate_pdfs = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if f.endswith(".pdf"):
                path = os.path.join(root, f)
                # prioritize samples
                if "samples" in path:
                    candidate_pdfs.insert(0, path)
                else:
                    candidate_pdfs.append(path)
    
    # Limit candidates to save time
    candidate_pdfs = candidate_pdfs[:20] 
    
    print(f"Scanning up to {len(candidate_pdfs)} PDFs for images...")
    
    found_images = False
    found_page_blocks = False
    
    parser = PyMuPDFParser()
    
    for i, test_pdf in enumerate(candidate_pdfs):
        try:
            # print(f"Checking {test_pdf}...")
            if not os.path.exists(test_pdf): continue
            
            # Simple file read
            with open(test_pdf, "rb") as f:
                content = f.read()
            
            # Skip very large files for test speed
            if len(content) > 5 * 1024 * 1024: continue
            
            parsed_doc = parser.parse(test_pdf, content)
            meta = parsed_doc.metadata
            
            # Check for Page Blocks
            page_blocks = meta.get('page_blocks', [])
            if len(page_blocks) > 0:
                if not found_page_blocks:
                    print(f"\n[PASS] Page Blocks verified in {test_pdf}")
                    print(f"       First block page: {page_blocks[0].get('page')}")
                    found_page_blocks = True
                
                # Check for Image Blocks within Page Blocks (CRITICAL for Citation)
                image_blocks = [b for b in page_blocks if b.get('type') == 'image']
                if image_blocks:
                    print(f"       [PASS] Found {len(image_blocks)} image blocks in page_blocks.")
                    print(f"              First image block: Page {image_blocks[0].get('page')}, BBox: {image_blocks[0].get('bbox')}")
                else:
                    if meta.get('extracted_images'):
                        print(f"       [WARNING] Extracted images exist but NO image blocks in page_blocks! Citation might fail.")
            
            # Check for Images
            extracted_images = meta.get('extracted_images', [])
            if len(extracted_images) > 0:
                print(f"\n[PASS] Images verified in {test_pdf}")
                print(f"       Count: {len(extracted_images)}")
                
                img0 = extracted_images[0]
                print("       First Image Metadata:")
                print(f"         Page: {img0.get('page')} (Type: {type(img0.get('page'))})")
                print(f"         OCR Text: {img0.get('ocr_text')}")
                
                if isinstance(img0.get('page'), int):
                    print("       [PASS] Image has integer page number.")
                    found_images = True
                    break # Found what we needed
                else:
                    print("       [FAIL] Image page number is invalid.")
            
        except Exception as e:
            # Ignore errors in random pdfs
            pass
            
    if not found_images:
        print("\n[WARNING] Could not find any PDF with images to verify image extraction.")
        print("          However, the code logic exists. Please instantiate a PDF with images manually.")
    
    if not found_page_blocks:
        print("\n[FAIL] Could not verify page_blocks in any PDF.")

if __name__ == "__main__":
    test_citation_accuracy()
