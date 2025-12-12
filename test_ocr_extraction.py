#!/usr/bin/env python3
"""
OCR Extraction Test Script
Run this on a server with more RAM and processing power.

This script will:
1. Test OCR configuration
2. Extract text using Docling OCR
3. Compare OCR results with non-OCR extraction
4. Generate a detailed report
"""

import sys
import os
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def test_ocr_extraction(pdf_path: str, output_dir: str = "ocr_test_results"):
    """
    Test OCR extraction on a PDF document.
    
    Args:
        pdf_path: Path to PDF file
        output_dir: Directory to save results
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_dir, f"ocr_test_report_{timestamp}.txt")
    
    # Redirect output to both console and file
    class TeeOutput:
        def __init__(self, *files):
            self.files = files
        
        def write(self, obj):
            for f in self.files:
                f.write(obj)
                f.flush()
        
        def flush(self):
            for f in self.files:
                f.flush()
    
    report_f = open(report_file, 'w', encoding='utf-8')
    original_stdout = sys.stdout
    sys.stdout = TeeOutput(original_stdout, report_f)
    
    try:
        print_section("OCR EXTRACTION TEST - Server Run")
        print(f"\n📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📄 Document: {os.path.basename(pdf_path)}")
        print(f"💾 Output Directory: {output_dir}")
        
        if not os.path.exists(pdf_path):
            print(f"\n❌ ERROR: Document not found: {pdf_path}")
            return
        
        # Document info
        file_size = os.path.getsize(pdf_path)
        print(f"\n📊 DOCUMENT INFORMATION:")
        print(f"  • File: {os.path.basename(pdf_path)}")
        print(f"  • Size: {file_size / 1024 / 1024:.2f} MB ({file_size:,} bytes)")
        print(f"  • Path: {pdf_path}")
        
        # Test 1: Non-OCR extraction (baseline)
        print_section("TEST 1: Non-OCR Extraction (Baseline)")
        
        non_ocr_text = None
        non_ocr_length = 0
        
        try:
            from parsers.pymupdf_parser import PyMuPDFParser
            
            print("\n🔹 Using PyMuPDF Parser (no OCR)...")
            start = time.time()
            parser = PyMuPDFParser()
            result = parser.parse(pdf_path)
            elapsed = time.time() - start
            
            non_ocr_text = result.text.strip()
            non_ocr_length = len(non_ocr_text)
            
            print(f"  ✅ Completed in {elapsed:.2f} seconds")
            print(f"  • Pages: {result.pages}")
            print(f"  • Text extracted: {non_ocr_length:,} characters")
            print(f"  • Images detected: {result.images_detected}")
            
            # Save baseline
            baseline_file = os.path.join(output_dir, f"baseline_pymupdf_{timestamp}.txt")
            with open(baseline_file, 'w', encoding='utf-8') as f:
                f.write(non_ocr_text)
            print(f"  💾 Saved to: {baseline_file}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: OCR Configuration Check
        print_section("TEST 2: OCR Configuration Check")
        
        try:
            from parsers.docling_parser import DoclingParser
            
            parser = DoclingParser()
            print("\n🔹 Checking OCR configuration...")
            
            ocr_test = parser.test_ocr_configuration()
            
            print(f"\n  OCR Status:")
            print(f"    • OCR Available: {ocr_test['ocr_available']}")
            print(f"    • Models Available: {ocr_test['models_available']}")
            print(f"    • Config Success: {ocr_test['config_success']}")
            
            if ocr_test['warnings']:
                print(f"\n  ⚠️  Warnings:")
                for warning in ocr_test['warnings']:
                    print(f"    • {warning}")
            
            if ocr_test['errors']:
                print(f"\n  ❌ Errors:")
                for error in ocr_test['errors']:
                    print(f"    • {error}")
            
        except Exception as e:
            print(f"  ❌ Error checking OCR config: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: OCR Extraction
        print_section("TEST 3: OCR Extraction (Docling)")
        
        ocr_text = None
        ocr_length = 0
        
        try:
            from parsers.docling_parser import DoclingParser
            
            parser = DoclingParser()
            
            # Progress callback
            last_progress_time = time.time()
            def progress_callback(status, progress, **kwargs):
                nonlocal last_progress_time
                current_time = time.time()
                elapsed = current_time - start
                
                # Print progress every 30 seconds
                if current_time - last_progress_time >= 30:
                    print(f"  [{progress*100:.0f}%] {status} | Elapsed: {elapsed/60:.1f}m")
                    last_progress_time = current_time
            
            print("\n🔹 Starting OCR extraction with Docling...")
            print("  ⚠️  This may take 10-20 minutes depending on document size and server power...")
            print("  📊 Progress updates every 30 seconds...\n")
            
            start = time.time()
            result = parser.parse(pdf_path, progress_callback=progress_callback)
            elapsed = time.time() - start
            
            ocr_text = result.text.strip()
            ocr_length = len(ocr_text)
            
            print(f"\n  ✅ OCR processing completed in {elapsed/60:.1f} minutes ({elapsed:.1f} seconds)")
            print(f"  • Pages: {result.pages}")
            print(f"  • Text extracted: {ocr_length:,} characters")
            print(f"  • Images detected: {result.images_detected}")
            print(f"  • Parser used: {result.parser_used}")
            print(f"  • Confidence: {result.confidence:.2%}")
            print(f"  • Extraction percentage: {result.extraction_percentage:.2%}")
            
            # Save OCR result
            ocr_file = os.path.join(output_dir, f"ocr_docling_{timestamp}.txt")
            with open(ocr_file, 'w', encoding='utf-8') as f:
                f.write(ocr_text)
            print(f"  💾 Saved to: {ocr_file}")
            
        except Exception as e:
            print(f"  ❌ Error during OCR extraction: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Comparison and Analysis
        print_section("TEST 4: Comparison and Analysis")
        
        if non_ocr_text and ocr_text:
            print("\n📊 EXTRACTION COMPARISON:")
            print(f"  • Non-OCR (PyMuPDF): {non_ocr_length:,} characters")
            print(f"  • OCR (Docling): {ocr_length:,} characters")
            
            diff = ocr_length - non_ocr_length
            diff_percent = (diff / non_ocr_length * 100) if non_ocr_length > 0 else 0
            
            print(f"  • Difference: {diff:+,} characters ({diff_percent:+.1f}%)")
            
            if diff > 1000:
                print(f"\n  ✅ OCR extracted SIGNIFICANTLY MORE text!")
                print(f"     → OCR found {diff:,} additional characters")
                print(f"     → This suggests OCR successfully extracted text from images")
            elif diff > 0:
                print(f"\n  ✅ OCR extracted MORE text")
                print(f"     → OCR found {diff:,} additional characters")
            elif abs(diff) < 100:
                print(f"\n  ℹ️  OCR and non-OCR extracted similar amounts")
                print(f"     → Document is likely text-based (not image-based)")
                print(f"     → OCR may not be necessary for this document")
            else:
                print(f"\n  ⚠️  OCR extracted LESS text")
                print(f"     → This is unusual - OCR should extract same or more")
                print(f"     → Possible reasons:")
                print(f"       - OCR processing errors")
                print(f"       - Different text extraction methods")
            
            # Find unique text in OCR
            print("\n🔍 ANALYZING OCR-SPECIFIC CONTENT:")
            
            # Simple word-based comparison
            non_ocr_words = set(non_ocr_text.lower().split())
            ocr_words = set(ocr_text.lower().split())
            
            unique_ocr_words = ocr_words - non_ocr_words
            unique_non_ocr_words = non_ocr_words - ocr_words
            
            print(f"  • Unique words in OCR: {len(unique_ocr_words)}")
            print(f"  • Unique words in non-OCR: {len(unique_non_ocr_words)}")
            
            if unique_ocr_words:
                print(f"\n  📝 Sample unique OCR words (first 20):")
                sample_words = list(unique_ocr_words)[:20]
                print(f"     {', '.join(sample_words)}")
            
            # Save comparison
            comparison_file = os.path.join(output_dir, f"comparison_{timestamp}.txt")
            with open(comparison_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("OCR EXTRACTION COMPARISON REPORT\n")
                f.write("=" * 70 + "\n\n")
                f.write(f"Document: {os.path.basename(pdf_path)}\n")
                f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"Non-OCR (PyMuPDF): {non_ocr_length:,} characters\n")
                f.write(f"OCR (Docling): {ocr_length:,} characters\n")
                f.write(f"Difference: {diff:+,} characters ({diff_percent:+.1f}%)\n\n")
                f.write("=" * 70 + "\n")
                f.write("UNIQUE WORDS IN OCR (not in non-OCR):\n")
                f.write("=" * 70 + "\n")
                for word in sorted(unique_ocr_words):
                    f.write(f"{word}\n")
            
            print(f"  💾 Comparison saved to: {comparison_file}")
        
        # Test 5: Text Preview
        print_section("TEST 5: OCR Extracted Text Preview")
        
        if ocr_text:
            print("\n📝 OCR EXTRACTED TEXT PREVIEW:")
            print("-" * 70)
            
            # Show first 2000 characters
            preview = ocr_text[:2000] if ocr_length > 2000 else ocr_text
            print(preview)
            
            if ocr_length > 2000:
                print(f"\n... (showing first 2000 of {ocr_length:,} characters)")
            
            print("-" * 70)
            
            # Statistics
            words = ocr_text.split()
            lines = ocr_text.split('\n')
            print(f"\n📊 OCR TEXT STATISTICS:")
            print(f"  • Total characters: {ocr_length:,}")
            print(f"  • Total words: ~{len(words):,}")
            print(f"  • Total lines: {len(lines):,}")
            if lines:
                print(f"  • Average words per line: {len(words)/len(lines):.1f}")
        
        # Summary
        print_section("TEST SUMMARY")
        
        print("\n✅ TESTS COMPLETED:")
        print(f"  ✓ Baseline extraction (PyMuPDF)")
        print(f"  ✓ OCR configuration check")
        print(f"  ✓ OCR extraction (Docling)")
        print(f"  ✓ Comparison and analysis")
        print(f"  ✓ Text preview")
        
        print(f"\n💾 FILES SAVED TO: {output_dir}/")
        print(f"  • Baseline: baseline_pymupdf_{timestamp}.txt")
        print(f"  • OCR result: ocr_docling_{timestamp}.txt")
        print(f"  • Comparison: comparison_{timestamp}.txt")
        print(f"  • Full report: ocr_test_report_{timestamp}.txt")
        
        print("\n" + "=" * 70)
        print("OCR TEST COMPLETE!")
        print("=" * 70)
        
    finally:
        sys.stdout = original_stdout
        report_f.close()
        print(f"\n📄 Full report saved to: {report_file}")

if __name__ == "__main__":
    # Default test document
    test_pdf = "samples/FL10.11 SPECIFIC8 (1).pdf"
    
    # Allow command line argument for different PDF
    if len(sys.argv) > 1:
        test_pdf = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(test_pdf):
        print(f"❌ ERROR: Document not found: {test_pdf}")
        print(f"\nUsage: python3 test_ocr_extraction.py [path_to_pdf]")
        sys.exit(1)
    
    # Run test
    test_ocr_extraction(test_pdf)

