from docling.document_converter import DocumentConverter
import os
import sys

def debug_docling_pages(pdf_path):
    print(f"\nDebugging: {pdf_path}")
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    doc = result.document
    
    print(f"Document Pages Type: {type(doc.pages)}")
    if isinstance(doc.pages, dict):
        keys = sorted(doc.pages.keys())
        print(f"Page Keys: {keys}")
    elif isinstance(doc.pages, list):
        print(f"Page Count (list): {len(doc.pages)}")
        
    # Check first page content and properties
    first_key = sorted(doc.pages.keys())[0] if isinstance(doc.pages, dict) else 0
    first_page = doc.pages[first_key]
    print(f"First Page Logical Index: {first_key}")
    print(f"First Page Object Dir: {dir(first_page)[:20]}")
    
    # Try to find physical page number property
    if hasattr(first_page, 'page_no'):
        print(f"First Page page_no: {first_page.page_no}")
    if hasattr(first_page, 'physical_page_number'):
        print(f"First Page physical_page_number: {first_page.physical_page_number}")
        
    # Check all pages mapping
    print("\nPage Mapping (Logical Index -> Physical Property):")
    for k in sorted(doc.pages.keys())[:5]:
        p = doc.pages[k]
        pno = getattr(p, 'page_no', 'N/A')
        print(f"  Logical {k} -> Physical {pno}")


if __name__ == "__main__":
    path = "docs/testing/clientSpanishDocs/EM11, top seal.pdf"
    if os.path.exists(path):
        debug_docling_pages(path)
    else:
        print(f"File not found: {path}")

