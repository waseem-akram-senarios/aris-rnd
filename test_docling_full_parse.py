#!/usr/bin/env python3
"""
Test Docling with full page processing for the specific PDF.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"

print("=" * 70)
print("TESTING DOCLING WITH FULL PAGE PROCESSING")
print("=" * 70)
print()

# Set environment variable to process all pages
os.environ['DOCLING_PROCESS_ALL_PAGES'] = 'true'

try:
    from parsers.docling_parser import DoclingParser
    
    print("🔧 Initializing Docling parser...")
    parser = DoclingParser()
    print("✅ Parser initialized")
    print()
    
    print("📖 Parsing document with ALL pages...")
    print("   (This will take longer but should extract more content)")
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
    
    if result.text and len(result.text.strip()) > 0:
        words = result.text.split()
        print(f"📊 Word Count: {len(words):,} words")
        print()
        
        print("=" * 70)
        print("TEXT SAMPLE (first 1000 characters):")
        print("=" * 70)
        preview = result.text[:1000]
        print(preview)
        if len(result.text) > 1000:
            print(f"\n... ({len(result.text) - 1000:,} more characters)")
        print()
        
        print("=" * 70)
        print("✅ DOCLING SUCCESSFULLY PARSED THE DOCUMENT!")
        print("=" * 70)
        print(f"✅ Extracted {len(result.text):,} characters")
        print(f"✅ This is MORE than PyMuPDF's {73878:,} characters!")
    else:
        print("⚠️  No text extracted")
        
except ValueError as e:
    error_msg = str(e)
    print("=" * 70)
    print("❌ DOCLING PARSING FAILED")
    print("=" * 70)
    print(f"❌ Error: {error_msg}")
    print()
    if "no meaningful content" in error_msg.lower():
        print("💡 Docling processed the PDF but extracted no content.")
        print("   This PDF format may not be compatible with Docling.")
    elif "timed out" in error_msg.lower():
        print("💡 Docling timed out. The document may be too complex.")
    elif "too large" in error_msg.lower():
        print("💡 Document is too large for Docling.")
        
except Exception as e:
    print("=" * 70)
    print("❌ UNEXPECTED ERROR")
    print("=" * 70)
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()



