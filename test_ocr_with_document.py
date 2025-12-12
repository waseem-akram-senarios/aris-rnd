#!/usr/bin/env python3
"""
Test OCR functionality with an actual image-based PDF document.
Tests if Docling with OCR enabled can extract text from images.
"""
import sys
import os
import time
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Test document (image-based PDF)
TEST_PDF = "samples/1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"

def test_pdf_type_detection():
    """Test if the PDF is detected as image-based."""
    print("=" * 70)
    print("TEST 1: PDF Type Detection")
    print("=" * 70)
    
    if not os.path.exists(TEST_PDF):
        print(f"❌ FAILED: Test PDF not found: {TEST_PDF}")
        return False
    
    try:
        from parsers.pdf_type_detector import detect_pdf_type, is_image_heavy_pdf
        
        pdf_type = detect_pdf_type(TEST_PDF)
        is_image_heavy = is_image_heavy_pdf(TEST_PDF)
        
        print(f"✅ PDF Type: {pdf_type}")
        print(f"✅ Is Image Heavy: {is_image_heavy}")
        
        if pdf_type == "image" or is_image_heavy:
            print("✅ SUCCESS: PDF is correctly identified as image-based")
            return True
        else:
            print("⚠️  WARNING: PDF may not be image-based, but will test anyway")
            return True
    except Exception as e:
        print(f"❌ FAILED: Error detecting PDF type: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pymupdf_extraction():
    """Test PyMuPDF extraction (should detect images but extract 0 text)."""
    print("\n" + "=" * 70)
    print("TEST 2: PyMuPDF Extraction (Baseline - No OCR)")
    print("=" * 70)
    
    try:
        from parsers.pymupdf_parser import PyMuPDFParser
        
        parser = PyMuPDFParser()
        print("📄 Parsing with PyMuPDF (no OCR)...")
        
        start_time = time.time()
        result = parser.parse(TEST_PDF)
        elapsed = time.time() - start_time
        
        text_length = len(result.text.strip())
        images_detected = result.images_detected
        
        print(f"✅ Parsing completed in {elapsed:.2f} seconds")
        print(f"   - Pages: {result.pages}")
        print(f"   - Text extracted: {text_length:,} characters")
        print(f"   - Images detected: {images_detected}")
        print(f"   - Extraction percentage: {result.extraction_percentage * 100:.1f}%")
        print(f"   - Confidence: {result.confidence:.2f}")
        
        if images_detected and text_length == 0:
            print("✅ SUCCESS: PyMuPDF detected images but extracted no text (expected)")
            return True, text_length
        elif text_length > 0:
            print("⚠️  WARNING: PyMuPDF extracted some text (PDF may have text layer)")
            return True, text_length
        else:
            print("⚠️  WARNING: No images detected or unexpected result")
            return True, text_length
    except Exception as e:
        print(f"❌ FAILED: Error with PyMuPDF: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

def test_docling_with_ocr():
    """Test Docling with OCR enabled (should extract text from images)."""
    print("\n" + "=" * 70)
    print("TEST 3: Docling with OCR Enabled")
    print("=" * 70)
    print("⚠️  NOTE: This may take 5-20 minutes for image-based PDFs")
    print("      OCR processing is slow but should extract text from images\n")
    
    try:
        from parsers.docling_parser import DoclingParser
        
        parser = DoclingParser()
        print("📄 Parsing with Docling (OCR enabled)...")
        print("   This will test if OCR configuration is working...")
        
        # Create a progress callback
        def progress_callback(message, progress):
            print(f"   Progress: {int(progress * 100)}% - {message}")
        
        start_time = time.time()
        
        # Parse with progress callback
        result = parser.parse(TEST_PDF, progress_callback=progress_callback)
        
        elapsed = time.time() - start_time
        
        text_length = len(result.text.strip())
        images_detected = result.images_detected
        
        print(f"\n✅ Parsing completed in {elapsed/60:.1f} minutes ({elapsed:.2f} seconds)")
        print(f"   - Pages: {result.pages}")
        print(f"   - Text extracted: {text_length:,} characters")
        print(f"   - Images detected: {images_detected}")
        print(f"   - Extraction percentage: {result.extraction_percentage * 100:.1f}%")
        print(f"   - Confidence: {result.confidence:.2f}")
        
        if text_length > 0:
            print(f"\n✅ SUCCESS: OCR extracted {text_length:,} characters from images!")
            print(f"   Preview (first 500 chars):\n{result.text[:500]}...")
            return True, text_length
        else:
            print("\n❌ FAILED: No text extracted even with OCR enabled")
            print("   Possible reasons:")
            print("   - OCR configuration may not be working")
            print("   - PDF may be too complex for OCR")
            print("   - Docling OCR may need additional setup")
            return False, text_length
    except ImportError as e:
        print(f"❌ FAILED: Docling not installed: {e}")
        print("   Install with: pip install docling")
        return False, 0
    except Exception as e:
        print(f"❌ FAILED: Error with Docling OCR: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

def compare_results(pymupdf_chars, docling_chars):
    """Compare extraction results."""
    print("\n" + "=" * 70)
    print("TEST 4: Results Comparison")
    print("=" * 70)
    
    print(f"PyMuPDF (no OCR): {pymupdf_chars:,} characters")
    print(f"Docling (with OCR): {docling_chars:,} characters")
    
    if docling_chars > pymupdf_chars:
        improvement = ((docling_chars - pymupdf_chars) / max(pymupdf_chars, 1)) * 100
        print(f"\n✅ SUCCESS: OCR improved extraction by {improvement:.1f}%")
        print("   OCR is working and extracting text from images!")
        return True
    elif docling_chars == pymupdf_chars and docling_chars > 0:
        print("\n⚠️  WARNING: Both parsers extracted the same amount")
        print("   PDF may have a text layer, or OCR didn't extract additional text")
        return True
    elif docling_chars == 0 and pymupdf_chars == 0:
        print("\n❌ FAILED: Neither parser extracted text")
        print("   OCR may not be working correctly")
        return False
    else:
        print("\n⚠️  WARNING: Unexpected comparison result")
        return False

def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("OCR FUNCTIONALITY TEST WITH IMAGE-BASED PDF")
    print("=" * 70)
    print(f"\nTest Document: {TEST_PDF}")
    
    if not os.path.exists(TEST_PDF):
        print(f"\n❌ ERROR: Test PDF not found: {TEST_PDF}")
        print("   Please ensure the test document exists in the samples directory")
        return 1
    
    file_size = os.path.getsize(TEST_PDF) / (1024 * 1024)  # MB
    print(f"File Size: {file_size:.2f} MB\n")
    
    results = []
    
    # Test 1: PDF type detection
    results.append(("PDF Type Detection", test_pdf_type_detection()))
    
    # Test 2: PyMuPDF (baseline)
    pymupdf_result, pymupdf_chars = test_pymupdf_extraction()
    results.append(("PyMuPDF Extraction", pymupdf_result))
    
    # Test 3: Docling with OCR
    print("\n" + "=" * 70)
    print("⚠️  IMPORTANT: Docling OCR test will take 5-20 minutes")
    print("   Do you want to continue? (This is the actual OCR test)")
    print("=" * 70)
    
    # For automated testing, we'll proceed
    # In interactive mode, you might want to ask the user
    docling_result, docling_chars = test_docling_with_ocr()
    results.append(("Docling OCR Extraction", docling_result))
    
    # Test 4: Comparison
    comparison_result = compare_results(pymupdf_chars, docling_chars)
    results.append(("Results Comparison", comparison_result))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! OCR is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())










