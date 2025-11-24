#!/usr/bin/env python3
"""
Test script for Docling parser with sample documents.
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docling_parser(pdf_path):
    """Test Docling parser with a PDF file."""
    print("=" * 70)
    print("DOCLING PARSER TEST")
    print("=" * 70)
    print()
    
    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    print(f"📄 Testing with: {os.path.basename(pdf_path)}")
    print(f"   File size: {file_size / 1024:.2f} KB")
    print()
    
    try:
        from parsers.docling_parser import DoclingParser
        
        print("✅ Docling parser imported successfully")
        print()
        
        # Initialize parser
        print("🔧 Initializing Docling parser...")
        parser = DoclingParser()
        print("✅ Parser initialized")
        print()
        
        # Test parsing
        print("📖 Starting document parsing...")
        print("   (This may take a while for complex documents)")
        print()
        
        start_time = time.time()
        
        try:
            result = parser.parse(pdf_path)
            parsing_time = time.time() - start_time
            
            print("✅ Parsing completed successfully!")
            print()
            print("=" * 70)
            print("RESULTS")
            print("=" * 70)
            print()
            
            print(f"📊 Parser Used: {result.parser_used}")
            print(f"📄 Pages: {result.pages}")
            print(f"📝 Text Length: {len(result.text):,} characters")
            print(f"⏱️  Processing Time: {parsing_time:.2f} seconds")
            print(f"📈 Extraction Percentage: {result.extraction_percentage * 100:.1f}%")
            print(f"🎯 Confidence: {result.confidence:.2f}")
            print(f"🖼️  Images Detected: {'Yes' if result.images_detected else 'No'}")
            print()
            
            # Show text preview
            text_preview = result.text[:500] if len(result.text) > 500 else result.text
            print("=" * 70)
            print("TEXT PREVIEW (first 500 characters):")
            print("=" * 70)
            print(text_preview)
            if len(result.text) > 500:
                print("\n... (truncated)")
            print()
            
            # Show metadata
            print("=" * 70)
            print("METADATA:")
            print("=" * 70)
            for key, value in result.metadata.items():
                print(f"  {key}: {value}")
            print()
            
            # Calculate some statistics
            words = len(result.text.split())
            lines = len(result.text.split('\n'))
            print("=" * 70)
            print("STATISTICS:")
            print("=" * 70)
            print(f"  Total Characters: {len(result.text):,}")
            print(f"  Total Words: {words:,}")
            print(f"  Total Lines: {lines:,}")
            if result.pages > 0:
                print(f"  Avg Chars/Page: {len(result.text) / result.pages:,.0f}")
                print(f"  Avg Words/Page: {words / result.pages:,.0f}")
            print()
            
            print("=" * 70)
            print("✅ TEST PASSED - Docling parser is working correctly!")
            print("=" * 70)
            
            return True
            
        except ValueError as e:
            parsing_time = time.time() - start_time
            print(f"❌ Parsing failed after {parsing_time:.2f} seconds")
            print(f"   Error: {str(e)}")
            print()
            print("💡 Suggestions:")
            if "timed out" in str(e):
                print("   - The document may be too large or complex")
                print("   - Try increasing DOCLING_TIMEOUT environment variable")
                print("   - Or use PyMuPDF parser for faster processing")
            else:
                print("   - Check if the PDF is corrupted")
                print("   - Try with a different document")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure Docling is installed: pip install docling")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    # Find PDF files in current directory
    pdf_files = [
        "FL10.11 SPECIFIC8 (1).pdf",
        "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf",
        "1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"
    ]
    
    # Try to find an existing PDF
    test_file = None
    for pdf in pdf_files:
        if os.path.exists(pdf):
            test_file = pdf
            break
    
    if not test_file:
        print("❌ No PDF files found in current directory")
        print("   Available PDFs should be:")
        for pdf in pdf_files:
            print(f"     - {pdf}")
        return
    
    # Run test
    success = test_docling_parser(test_file)
    
    if success:
        print("\n🎉 Docling parser test completed successfully!")
    else:
        print("\n⚠️  Docling parser test encountered issues")
        sys.exit(1)


if __name__ == "__main__":
    main()


