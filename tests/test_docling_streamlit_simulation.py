#!/usr/bin/env python3
"""
Test Docling parser exactly as it's called from Streamlit app.
This simulates the file_content (bytes) flow.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docling_streamlit_simulation():
    """Test Docling exactly as Streamlit calls it."""
    pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"
    
    print("=" * 70)
    print("DOCLING STREAMLIT SIMULATION TEST")
    print("=" * 70)
    print()
    print("Simulating exactly how Streamlit calls Docling:")
    print("  1. Read file as bytes (file_content)")
    print("  2. Pass to parser.parse(file_path, file_content=bytes)")
    print("  3. Parser creates temp file from bytes")
    print("  4. Docling processes temp file")
    print()
    
    # Step 1: Read file as bytes (like Streamlit does)
    print("📖 Step 1: Reading file as bytes (simulating Streamlit upload)...")
    with open(pdf_path, 'rb') as f:
        file_content = f.read()
    print(f"✅ Read {len(file_content):,} bytes")
    print()
    
    # Step 2: Call parser exactly as Streamlit does
    print("🔧 Step 2: Calling DoclingParser.parse() with file_content...")
    print("   This is how Streamlit calls it:")
    print("   parser.parse(file_path=uploaded_file.name, file_content=uploaded_file.read())")
    print()
    
    try:
        from parsers.docling_parser import DoclingParser
        
        parser = DoclingParser()
        print("✅ Parser initialized")
        print()
        
        print("📖 Step 3: Parsing with file_content (this takes 5-10 minutes)...")
        print("   Docling will create a temp file from the bytes")
        print()
        
        start_time = time.time()
        result = parser.parse(file_path=pdf_path, file_content=file_content)
        elapsed = time.time() - start_time
        
        print(f"✅ Parsing completed in {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        print()
        
        print("=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"📄 Parser Used: {result.parser_used}")
        print(f"📄 Pages: {result.pages}")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📊 Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        print()
        
        # Check if text is empty
        text_stripped = result.text.strip() if result.text else ""
        if not text_stripped:
            print("=" * 70)
            print("❌ PROBLEM DETECTED: Text is empty!")
            print("=" * 70)
            print(f"   Raw text length: {len(result.text) if result.text else 0}")
            print(f"   Stripped text length: {len(text_stripped)}")
            print()
            print("🔍 Debugging info:")
            print(f"   - result.text is None: {result.text is None}")
            print(f"   - result.text type: {type(result.text)}")
            if result.text:
                print(f"   - First 100 chars: {repr(result.text[:100])}")
            print()
            print("💡 This is why Streamlit shows 'empty'!")
            return False
        else:
            print("=" * 70)
            print("TEXT SAMPLE (first 500 characters):")
            print("=" * 70)
            preview = result.text[:500]
            print(preview)
            print()
            print("=" * 70)
            print("✅ SUCCESS! Docling extracted text via Streamlit flow!")
            print("=" * 70)
            print(f"✅ Extracted {len(result.text):,} characters")
            return True
            
    except ValueError as e:
        error_msg = str(e)
        print("=" * 70)
        print("❌ PARSING FAILED")
        print("=" * 70)
        print(f"❌ Error: {error_msg}")
        print()
        if "empty" in error_msg.lower() or "no content" in error_msg.lower():
            print("💡 Docling processed the PDF but extracted no content.")
            print("   This might be a temp file issue or Docling configuration issue.")
        import traceback
        traceback.print_exc()
        return False
        
    except Exception as e:
        print("=" * 70)
        print("❌ UNEXPECTED ERROR")
        print("=" * 70)
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_docling_streamlit_simulation()
    sys.exit(0 if success else 1)
