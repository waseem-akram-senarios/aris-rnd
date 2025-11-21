#!/usr/bin/env python3
"""
Simple test to verify Docling can extract text from a sample document.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docling_simple():
    """Simple test with a small document."""
    test_file = "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf"
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        return False
    
    file_size = os.path.getsize(test_file)
    print(f"📄 Testing: {os.path.basename(test_file)} ({file_size/1024:.1f} KB)")
    print()
    
    try:
        from parsers.docling_parser import DoclingParser
        
        print("🔧 Initializing parser...")
        parser = DoclingParser()
        print("✅ Parser initialized")
        print()
        
        print("📖 Parsing document (this may take 30-60 seconds)...")
        print("   Docling uses layout models which are slow on CPU")
        print()
        
        start = time.time()
        result = parser.parse(test_file)
        elapsed = time.time() - start
        
        print("=" * 70)
        print("✅ DOCLING TEST RESULTS")
        print("=" * 70)
        print(f"⏱️  Time: {elapsed:.2f} seconds")
        print(f"📄 Pages: {result.pages}")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📊 Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        print()
        
        # Show text sample
        if result.text:
            preview = result.text[:500].replace('\n', ' ')
            print("=" * 70)
            print("TEXT SAMPLE (first 500 chars):")
            print("=" * 70)
            print(preview)
            print()
            print("=" * 70)
            print("✅ DOCLING IS WORKING! Text extracted successfully.")
            print("=" * 70)
            return True
        else:
            print("❌ No text extracted")
            return False
            
    except ValueError as e:
        error_msg = str(e)
        if "too large" in error_msg:
            print(f"⚠️  {error_msg}")
            print("   This is expected - Docling is optimized for smaller files")
            print("   Use PyMuPDF for large documents")
        elif "timed out" in error_msg:
            print(f"⚠️  {error_msg}")
            print("   Docling timed out - document may be too complex")
            print("   This is normal for large/complex PDFs")
        else:
            print(f"❌ Error: {error_msg}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_docling_simple()
    sys.exit(0 if success else 1)






