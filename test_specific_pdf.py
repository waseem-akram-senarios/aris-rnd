#!/usr/bin/env python3
"""
Test a specific PDF file with Docling parser.
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_pdf_with_docling(pdf_path: str):
    """Test a specific PDF file with Docling."""
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print("=" * 70)
    print("DOCLING PDF TEST")
    print("=" * 70)
    print(f"📄 File: {os.path.basename(pdf_path)}")
    print(f"📊 Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
    print()
    
    try:
        from parsers.docling_parser import DoclingParser
        
        print("🔧 Initializing Docling parser...")
        parser = DoclingParser()
        print("✅ Parser initialized")
        print()
        
        print("📖 Parsing document with Docling...")
        print("   (This may take 20-60 seconds depending on document complexity)")
        print()
        
        start_time = time.time()
        result = parser.parse(pdf_path)
        elapsed = time.time() - start_time
        
        print("=" * 70)
        print("✅ DOCLING PARSING RESULTS")
        print("=" * 70)
        print(f"⏱️  Parsing Time: {elapsed:.2f} seconds")
        print(f"📄 Pages: {result.pages}")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📊 Extraction Percentage: {result.extraction_percentage*100:.1f}%")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        print(f"🔧 Parser Used: {result.parser_used}")
        print()
        
        if result.images_detected:
            print("🖼️  Images detected in document")
        else:
            print("🖼️  No images detected")
        print()
        
        # Show text sample
        if result.text and len(result.text.strip()) > 0:
            print("=" * 70)
            print("TEXT SAMPLE (first 1000 characters):")
            print("=" * 70)
            preview = result.text[:1000]
            print(preview)
            if len(result.text) > 1000:
                print(f"\n... ({len(result.text) - 1000:,} more characters)")
            print()
            
            # Show word count
            words = result.text.split()
            print(f"📊 Word Count: {len(words):,} words")
            print()
            
            print("=" * 70)
            print("✅ DOCLING SUCCESSFULLY PARSED THE DOCUMENT!")
            print("=" * 70)
            return True
        else:
            print("=" * 70)
            print("⚠️  WARNING: No text extracted from document")
            print("=" * 70)
            return False
            
    except ValueError as e:
        error_msg = str(e)
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        
        print("=" * 70)
        print("❌ DOCLING PARSING FAILED")
        print("=" * 70)
        print(f"⏱️  Time before failure: {elapsed:.2f} seconds")
        print(f"❌ Error: {error_msg}")
        print()
        
        if "timed out" in error_msg.lower():
            print("💡 This document may be too large or complex for Docling.")
            print("   Try using PyMuPDF or Textract parser instead.")
        elif "too large" in error_msg.lower():
            print("💡 This document exceeds Docling's size limit (3MB).")
            print("   Try using PyMuPDF or Textract parser instead.")
        elif "not valid" in error_msg.lower() or "cannot process" in error_msg.lower():
            print("💡 This PDF format is not compatible with Docling.")
            print("   The document may be corrupted, encrypted, or in an unsupported format.")
            print("   Try using PyMuPDF parser instead (it's more compatible).")
        else:
            print("💡 Try using a different parser (PyMuPDF or Textract).")
        
        print()
        return False
        
    except Exception as e:
        elapsed = time.time() - start_time if 'start_time' in locals() else 0
        print("=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"⏱️  Time before error: {elapsed:.2f} seconds")
        print(f"❌ Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False

def test_with_fallback(pdf_path: str):
    """Test PDF with automatic fallback mechanism."""
    print()
    print("=" * 70)
    print("TESTING WITH AUTOMATIC FALLBACK")
    print("=" * 70)
    print()
    
    try:
        from parsers.parser_factory import ParserFactory
        
        print("🔄 Testing with automatic parser selection (Auto mode)...")
        print("   This will try: PyMuPDF → Docling → Textract")
        print()
        
        start_time = time.time()
        result = ParserFactory.parse_with_fallback(pdf_path, preferred_parser="auto")
        elapsed = time.time() - start_time
        
        print("=" * 70)
        print("✅ PARSING RESULTS (with fallback)")
        print("=" * 70)
        print(f"⏱️  Parsing Time: {elapsed:.2f} seconds")
        print(f"🔧 Parser Used: {result.parser_used}")
        print(f"📄 Pages: {result.pages}")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📊 Extraction Percentage: {result.extraction_percentage*100:.1f}%")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        print()
        
        if result.text and len(result.text.strip()) > 0:
            words = result.text.split()
            print(f"📊 Word Count: {len(words):,} words")
            print()
            print("✅ Document successfully parsed!")
            return True
        else:
            print("⚠️  No text extracted")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    pdf_file = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"
    
    # Test with Docling directly
    docling_success = test_pdf_with_docling(pdf_file)
    
    # Test with automatic fallback
    fallback_success = test_with_fallback(pdf_file)
    
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Docling Direct: {'✅ Success' if docling_success else '❌ Failed'}")
    print(f"Auto Fallback:  {'✅ Success' if fallback_success else '❌ Failed'}")
    print("=" * 70)
    
    sys.exit(0 if (docling_success or fallback_success) else 1)



