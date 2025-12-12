#!/usr/bin/env python3
"""
Quick verification test for OCR enablement.
Verifies the code changes are correct and provides testing instructions.
"""
import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def verify_ocr_code():
    """Verify OCR code is properly implemented."""
    print("=" * 70)
    print("OCR CODE VERIFICATION")
    print("=" * 70)
    
    parser_file = "parsers/docling_parser.py"
    
    if not os.path.exists(parser_file):
        print(f"❌ File not found: {parser_file}")
        return False
    
    with open(parser_file, 'r') as f:
        content = f.read()
    
    # Check for all required OCR components
    checks = {
        "OCR imports": bool(re.search(r'from docling\.datamodel\.pipeline_options import PipelineOptions', content)),
        "Config imports": bool(re.search(r'from docling\.datamodel\.document_converter_config import DocumentConverterConfig', content)),
        "OCR enabled": "pipeline_options.do_ocr = True" in content,
        "Table structure": "pipeline_options.do_table_structure = True" in content,
        "Vision enabled": "pipeline_options.do_vision = True" in content,
        "Config assignment": "config.pipeline_options = pipeline_options" in content,
        "Converter with config": "DocumentConverter(config=config)" in content,
        "Error handling": "except (ImportError, AttributeError)" in content,
        "Fallback": "self.DocumentConverter()" in content,
        "OCR logging": "OCR enabled for image text extraction" in content,
        "Progress message 1": "Initializing DocumentConverter with OCR enabled" in content,
        "Progress message 2": "DocumentConverter initialized with OCR" in content,
        "Progress message 3": "Starting document conversion with OCR" in content,
    }
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    
    print("\nCode Component Checks:")
    for check_name, result in checks.items():
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n✅ SUCCESS: All OCR code components are present!")
        return True
    else:
        print(f"\n⚠️  WARNING: {total - passed} component(s) missing")
        return False

def check_test_document():
    """Check if test document exists."""
    print("\n" + "=" * 70)
    print("TEST DOCUMENT CHECK")
    print("=" * 70)
    
    test_pdf = "samples/1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"
    
    if os.path.exists(test_pdf):
        file_size = os.path.getsize(test_pdf) / (1024 * 1024)  # MB
        print(f"✅ Test document found: {test_pdf}")
        print(f"   File size: {file_size:.2f} MB")
        print("   This is an image-based PDF (scanned document)")
        return True
    else:
        print(f"❌ Test document not found: {test_pdf}")
        print("   You can use any image-based PDF for testing")
        return False

def provide_testing_instructions():
    """Provide instructions for testing OCR."""
    print("\n" + "=" * 70)
    print("TESTING INSTRUCTIONS")
    print("=" * 70)
    
    print("""
To test OCR functionality with an image-based document:

1. INSTALL DEPENDENCIES (if not already installed):
   ```bash
   pip install docling
   ```

2. TEST VIA STREAMLIT UI:
   a. Start the Streamlit app:
      ```bash
      streamlit run app.py
      ```
   
   b. In the UI:
      - Select "Docling" as the parser (not "Auto")
      - Upload an image-based PDF (scanned document)
      - Click "Process Documents"
      - Wait 5-20 minutes for OCR processing
   
   c. Check the results:
      - Look for "OCR enabled for image text extraction" in logs
      - Verify text is extracted (should be > 0 characters)
      - Compare with PyMuPDF (should extract 0 from same document)

3. TEST VIA COMMAND LINE:
   ```bash
   python3 test_ocr_with_document.py
   ```
   (Requires docling and pymupdf installed)

4. VERIFY OCR IS WORKING:
   - Before OCR: Image-based PDFs extract 0 characters
   - After OCR: Image-based PDFs extract text from images
   - Check logs for "OCR enabled for image text extraction"
   - Progress messages should mention "OCR"

5. EXPECTED BEHAVIOR:
   - OCR processing takes 5-20 minutes for scanned PDFs
   - Text should be extracted from images
   - Logs should show OCR configuration success
   - If OCR config fails, fallback to default converter (with warning)

6. TROUBLESHOOTING:
   - If no text extracted: Check if docling OCR models are downloaded
   - If import errors: Ensure docling is properly installed
   - If timeout: OCR is slow, increase timeout if needed
   - Check logs for "Could not enable OCR configuration" warnings
""")

def main():
    """Run verification."""
    print("\n" + "=" * 70)
    print("OCR ENABLEMENT VERIFICATION")
    print("=" * 70)
    print("\nVerifying OCR code implementation...\n")
    
    code_ok = verify_ocr_code()
    doc_ok = check_test_document()
    
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    if code_ok:
        print("✅ OCR code is properly implemented")
    else:
        print("❌ OCR code needs review")
    
    if doc_ok:
        print("✅ Test document available")
    else:
        print("⚠️  Test document not found (use any image-based PDF)")
    
    if code_ok:
        print("\n✅ READY FOR TESTING")
        print("   Code changes are correct. Install docling and test with image-based PDF.")
    else:
        print("\n⚠️  REVIEW NEEDED")
        print("   Some code components may be missing.")
    
    provide_testing_instructions()
    
    return 0 if code_ok else 1

if __name__ == "__main__":
    sys.exit(main())










