#!/usr/bin/env python3
"""
Diagnose why Docling fails on a specific PDF.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"

print("=" * 70)
print("DOCLING ERROR DIAGNOSIS")
print("=" * 70)
print()

# Check PDF with PyMuPDF first
print("1. Checking PDF with PyMuPDF...")
try:
    import fitz
    doc = fitz.open(pdf_path)
    print(f"   ✅ PyMuPDF can open the PDF")
    print(f"   📄 Pages: {doc.page_count}")
    print(f"   📋 PDF Version: {doc.metadata.get('format', 'Unknown')}")
    print(f"   🔒 Encrypted: {doc.is_encrypted}")
    print(f"   📝 Creator: {doc.metadata.get('creator', 'Unknown')}")
    print(f"   🏭 Producer: {doc.metadata.get('producer', 'Unknown')}")
    
    # Check first page
    page = doc[0]
    text = page.get_text()
    print(f"   📝 First page text: {len(text)} characters")
    
    doc.close()
except Exception as e:
    print(f"   ❌ PyMuPDF error: {e}")
    sys.exit(1)

print()
print("2. Testing Docling conversion...")
print()

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PipelineOptions
    
    # Create converter with minimal options
    pipeline_options = PipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    pipeline_options.do_vision = False
    
    converter = DocumentConverter()
    
    print("   🔧 Converter created")
    print("   📖 Attempting conversion...")
    print()
    
    # Try conversion with detailed error capture
    try:
        result = converter.convert(pdf_path, max_num_pages=1, raises_on_error=True)
        print("   ✅ Conversion successful!")
        if hasattr(result, 'document'):
            doc = result.document
            if hasattr(doc, 'export_to_markdown'):
                text = doc.export_to_markdown()
                print(f"   📝 Extracted text: {len(text)} characters")
    except Exception as convert_error:
        print("   ❌ Conversion failed!")
        print()
        print("   Error details:")
        print(f"   Type: {type(convert_error).__name__}")
        print(f"   Message: {str(convert_error)}")
        print()
        print("   Full traceback:")
        traceback.print_exc()
        
        # Check if it's a validation error
        error_str = str(convert_error).lower()
        if "not valid" in error_str or "invalid" in error_str:
            print()
            print("   💡 This appears to be a PDF validation error.")
            print("   Possible causes:")
            print("   - PDF version too old (PDF 1.3)")
            print("   - PDF structure not fully compliant")
            print("   - Docling's internal validation is stricter than PyMuPDF")
            print()
            print("   Solution: Use PyMuPDF parser for this document.")
        
except ImportError as e:
    print(f"   ❌ Cannot import Docling: {e}")
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")
    traceback.print_exc()

print()
print("=" * 70)
print("3. Testing with different Docling options...")
print("=" * 70)
print()

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PipelineOptions
    
    # Try with different pipeline options
    print("   Trying with simple pipeline...")
    converter = DocumentConverter()
    
    # Try with just 1 page to see if it's a page-specific issue
    try:
        result = converter.convert(pdf_path, max_num_pages=1, raises_on_error=False)
        print("   ✅ Conversion with raises_on_error=False succeeded!")
        if result:
            print(f"   Result type: {type(result)}")
    except Exception as e:
        print(f"   ❌ Still failed: {e}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)



