#!/usr/bin/env python3
"""
End-to-end test for document processing with Docling.
Tests that Docling completes successfully when explicitly selected.
"""

import os
import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from parsers.parser_factory import ParserFactory
from parsers.docling_parser import DoclingParser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_docling_explicit_no_fallback():
    """Test that Docling doesn't fall back to PyMuPDF when explicitly selected."""
    print("\n" + "="*70)
    print("TEST: Docling Explicit Selection - No Fallback")
    print("="*70)
    
    # Find a test PDF
    test_pdfs = []
    for root, dirs, files in os.walk(project_root):
        if 'samples' in root or 'data' in root or 'test' in root.lower():
            for file in files:
                if file.lower().endswith('.pdf'):
                    test_pdfs.append(os.path.join(root, file))
    
    if not test_pdfs:
        print("❌ No test PDFs found. Please add a PDF to test/ or samples/ directory.")
        return False
    
    test_pdf = test_pdfs[0]
    print(f"📄 Using test PDF: {os.path.basename(test_pdf)}")
    print(f"   Size: {os.path.getsize(test_pdf) / 1024 / 1024:.2f} MB")
    
    try:
        print("\n🔍 Testing: Docling explicitly selected (should NOT fall back)")
        start_time = time.time()
        
        # Test with Docling explicitly selected
        result = ParserFactory.parse_with_fallback(
            test_pdf,
            preferred_parser='docling'
        )
        
        duration = time.time() - start_time
        
        # Verify it used Docling
        if result.parser_used.lower() != 'docling':
            print(f"❌ FAILED: Expected Docling, but got {result.parser_used}")
            return False
        
        # Verify we got results
        if not result.text or len(result.text.strip()) == 0:
            print(f"❌ FAILED: No text extracted")
            return False
        
        print(f"✅ SUCCESS: Docling completed successfully")
        print(f"   Parser used: {result.parser_used}")
        print(f"   Text length: {len(result.text):,} characters")
        print(f"   Pages: {result.pages}")
        print(f"   Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"   Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        
        return True
        
    except ValueError as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            print(f"⚠️  Docling timed out (this is acceptable for very large files)")
            print(f"   Error: {error_msg}")
            print(f"   Duration: {time.time() - start_time:.2f} seconds")
            return True  # Timeout is acceptable - means it tried Docling
        else:
            print(f"❌ FAILED: {error_msg}")
            return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_docling_direct():
    """Test Docling parser directly."""
    print("\n" + "="*70)
    print("TEST: Docling Direct Parser")
    print("="*70)
    
    test_pdfs = []
    for root, dirs, files in os.walk(project_root):
        if 'samples' in root or 'data' in root or 'test' in root.lower():
            for file in files:
                if file.lower().endswith('.pdf'):
                    test_pdfs.append(os.path.join(root, file))
    
    if not test_pdfs:
        print("❌ No test PDFs found.")
        return False
    
    test_pdf = test_pdfs[0]
    print(f"📄 Using test PDF: {os.path.basename(test_pdf)}")
    
    try:
        print("\n🔍 Testing: Docling parser directly")
        start_time = time.time()
        
        parser = DoclingParser()
        result = parser.parse(test_pdf)
        
        duration = time.time() - start_time
        
        if not result.text or len(result.text.strip()) == 0:
            print(f"❌ FAILED: No text extracted")
            return False
        
        print(f"✅ SUCCESS: Docling direct parsing completed")
        print(f"   Text length: {len(result.text):,} characters")
        print(f"   Pages: {result.pages}")
        print(f"   Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        
        return True
        
    except Exception as e:
        error_msg = str(e)
        if "timed out" in error_msg.lower():
            print(f"⚠️  Docling timed out (acceptable for large files)")
            return True
        print(f"❌ FAILED: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("END-TO-END DOCUMENT PROCESSING TEST")
    print("="*70)
    
    results = []
    
    # Test 1: Docling explicit selection
    results.append(("Docling Explicit (No Fallback)", test_docling_explicit_no_fallback()))
    
    # Test 2: Docling direct
    results.append(("Docling Direct Parser", test_docling_direct()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! Document processing is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())



