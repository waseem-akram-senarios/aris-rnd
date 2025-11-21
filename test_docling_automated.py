#!/usr/bin/env python3
"""
Automated test to compare Docling parsing:
1. Direct file path (like simple test)
2. With file_content bytes (like Streamlit)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_direct_path():
    """Test with direct file path (like simple test)."""
    print("=" * 70)
    print("TEST 1: Direct File Path (Simple Test Method)")
    print("=" * 70)
    pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"
    
    try:
        from parsers.docling_parser import DoclingParser
        parser = DoclingParser()
        
        start = time.time()
        result = parser.parse(file_path=pdf_path, file_content=None)
        elapsed = time.time() - start
        
        print(f"⏱️  Time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📄 Pages: {result.pages}")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        
        if result.text and len(result.text.strip()) > 100:
            print("✅ SUCCESS: Text extracted")
            return True, len(result.text)
        else:
            print("❌ FAILED: No text extracted")
            return False, 0
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, 0

def test_with_file_content():
    """Test with file_content bytes (like Streamlit)."""
    print("\n" + "=" * 70)
    print("TEST 2: With file_content Bytes (Streamlit Method)")
    print("=" * 70)
    pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"
    
    # Read as bytes (like Streamlit does)
    with open(pdf_path, 'rb') as f:
        file_content = f.read()
    print(f"📦 Read {len(file_content):,} bytes")
    
    try:
        from parsers.docling_parser import DoclingParser
        parser = DoclingParser()
        
        start = time.time()
        result = parser.parse(file_path=pdf_path, file_content=file_content)
        elapsed = time.time() - start
        
        print(f"⏱️  Time: {elapsed:.2f} seconds ({elapsed/60:.1f} minutes)")
        print(f"📝 Text Length: {len(result.text):,} characters")
        print(f"📄 Pages: {result.pages}")
        print(f"🎯 Confidence: {result.confidence:.2f}")
        
        if result.text and len(result.text.strip()) > 100:
            print("✅ SUCCESS: Text extracted")
            return True, len(result.text)
        else:
            print("❌ FAILED: No text extracted")
            print(f"   Raw text: {len(result.text) if result.text else 0} chars")
            print(f"   Stripped: {len(result.text.strip()) if result.text else 0} chars")
            return False, 0
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, 0

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DOCLING AUTOMATED COMPARISON TEST")
    print("=" * 70)
    print("\nComparing two methods to find the difference:")
    print("  1. Direct file path (works in simple test)")
    print("  2. file_content bytes (fails in Streamlit)")
    print()
    
    # Test 1: Direct path
    success1, length1 = test_direct_path()
    
    # Test 2: With file_content
    success2, length2 = test_with_file_content()
    
    # Compare results
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)
    print(f"Direct Path:     {'✅' if success1 else '❌'} {length1:,} chars")
    print(f"With file_content: {'✅' if success2 else '❌'} {length2:,} chars")
    print()
    
    if success1 and success2:
        diff = abs(length1 - length2)
        if diff < 100:
            print("✅ Both methods work! Difference is minimal.")
        else:
            print(f"⚠️  Both work but different lengths (diff: {diff:,} chars)")
    elif success1 and not success2:
        print("❌ PROBLEM FOUND: Direct path works, but file_content fails!")
        print("   This is the Streamlit issue - temp file handling problem.")
    elif not success1 and success2:
        print("⚠️  Unexpected: file_content works but direct path doesn't")
    else:
        print("❌ Both methods failed - Docling may not work for this PDF")
    
    sys.exit(0 if (success1 and success2) else 1)


