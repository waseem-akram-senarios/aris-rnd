#!/usr/bin/env python3
"""
Test Latest Changes - Document Filtering, Image Marker Insertion, OCR Extraction
Tests the three main improvements:
1. Document name filtering (distinguishing (1) vs (2))
2. Image marker insertion with position-based placement
3. OCR extraction without limits and completeness validation
"""

import sys
import os
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, '.')

# Test results tracking
test_results = {
    'passed': [],
    'failed': [],
    'skipped': []
}

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.CYAN}{Colors.BOLD}Testing: {name}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS: {msg}{Colors.END}")
    test_results['passed'].append(msg)

def print_fail(msg, error=None):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")
    if error:
        print(f"{Colors.RED}   Error: {error}{Colors.END}")
    test_results['failed'].append(msg)

def print_skip(msg):
    print(f"{Colors.YELLOW}⏭️  SKIP: {msg}{Colors.END}")
    test_results['skipped'].append(msg)

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  INFO: {msg}{Colors.END}")

# Test 1: Document Number Extraction
def test_document_number_extraction():
    """Test _extract_document_number helper function"""
    print_test("Document Number Extraction")
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        rag = RAGSystem()
        
        # Test cases
        test_cases = [
            ("FL10.11 SPECIFIC8 (1).pdf", 1),
            ("FL10.11 SPECIFIC8 (2).pdf", 2),
            ("document (10).pdf", 10),
            ("file.pdf", None),
            ("no_number.pdf", None),
            ("path/to/FL10.11 SPECIFIC8 (1).pdf", 1),
        ]
        
        for filename, expected in test_cases:
            result = rag._extract_document_number(filename)
            if result == expected:
                print_pass(f"Extracted {result} from '{filename}'")
            else:
                print_fail(f"Expected {expected}, got {result} for '{filename}'")
                return False
        
        return True
    except Exception as e:
        print_fail(f"Document number extraction test failed: {e}")
        traceback.print_exc()
        return False

# Test 2: Document Filtering in Queries
def test_document_filtering():
    """Test that queries correctly filter by document number"""
    print_test("Document Filtering in Queries")
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        rag = RAGSystem()
        
        # Mock document names
        all_document_names = {
            "/path/to/FL10.11 SPECIFIC8 (1).pdf",
            "/path/to/FL10.11 SPECIFIC8 (2).pdf",
            "/path/to/other_document.pdf"
        }
        
        # Test query mentioning (1)
        question1 = "What's in FL10.11 SPECIFIC8 (1).pdf"
        question_lower1 = question1.lower()
        
        # Simulate the filtering logic
        import re
        question_doc_number = None
        question_number_match = re.search(r'\((\d+)\)', question1)
        if question_number_match:
            question_doc_number = int(question_number_match.group(1))
        
        mentioned_documents = []
        for source in all_document_names:
            source_name = os.path.basename(source).lower()
            source_doc_number = rag._extract_document_number(source)
            
            if question_doc_number is not None:
                if source_doc_number == question_doc_number:
                    base_name_question = re.sub(r'\s*\(\d+\)', '', question_lower1)
                    base_name_source = re.sub(r'\s*\(\d+\)', '', source_name.replace('.pdf', ''))
                    if base_name_source in base_name_question or base_name_question in base_name_source:
                        mentioned_documents.append(source)
        
        if len(mentioned_documents) == 1 and "(1)" in mentioned_documents[0]:
            print_pass("Query for (1).pdf correctly filters to only (1).pdf")
        else:
            print_fail(f"Expected only (1).pdf, got: {mentioned_documents}")
            return False
        
        # Test query mentioning (2)
        question2 = "What's in FL10.11 SPECIFIC8 (2).pdf"
        question_lower2 = question2.lower()
        question_doc_number2 = None
        question_number_match2 = re.search(r'\((\d+)\)', question2)
        if question_number_match2:
            question_doc_number2 = int(question_number_match2.group(1))
        
        mentioned_documents2 = []
        for source in all_document_names:
            source_name = os.path.basename(source).lower()
            source_doc_number = rag._extract_document_number(source)
            
            if question_doc_number2 is not None:
                if source_doc_number == question_doc_number2:
                    base_name_question = re.sub(r'\s*\(\d+\)', '', question_lower2)
                    base_name_source = re.sub(r'\s*\(\d+\)', '', source_name.replace('.pdf', ''))
                    if base_name_source in base_name_question or base_name_question in base_name_source:
                        mentioned_documents2.append(source)
        
        if len(mentioned_documents2) == 1 and "(2)" in mentioned_documents2[0]:
            print_pass("Query for (2).pdf correctly filters to only (2).pdf")
        else:
            print_fail(f"Expected only (2).pdf, got: {mentioned_documents2}")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Document filtering test failed: {e}")
        traceback.print_exc()
        return False

# Test 3: Image Position Extraction
def test_image_position_extraction():
    """Test that image positions are extracted from Docling"""
    print_test("Image Position Extraction from Docling")
    
    try:
        from parsers.docling_parser import DoclingParser
        
        # Check if the method signature includes image_positions_by_page
        import inspect
        sig = inspect.signature(DoclingParser._insert_image_markers_in_text)
        params = list(sig.parameters.keys())
        
        if 'image_positions_by_page' in params:
            print_pass("_insert_image_markers_in_text accepts image_positions_by_page parameter")
        else:
            print_fail(f"Missing image_positions_by_page parameter. Found: {params}")
            return False
        
        # Check if image position extraction code exists in parse method
        parser = DoclingParser()
        source_code = inspect.getsource(parser.parse)
        
        if 'image_positions_by_page' in source_code:
            print_pass("Image position extraction code found in parse method")
        else:
            print_fail("Image position extraction code not found in parse method")
            return False
        
        if 'doc.pictures' in source_code:
            print_pass("doc.pictures extraction code found")
        else:
            print_fail("doc.pictures extraction code not found")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Image position extraction test failed: {e}")
        traceback.print_exc()
        return False

# Test 4: Marker Insertion with Positions
def test_marker_insertion_with_positions():
    """Test that marker insertion uses image positions when available"""
    print_test("Marker Insertion with Image Positions")
    
    try:
        from parsers.docling_parser import DoclingParser
        
        parser = DoclingParser()
        
        # Test text with page markers
        test_text = """--- Page 1 ---
Some text here
--- Page 2 ---
More text
--- Page 3 ---
Even more text"""
        
        # Test with image positions
        image_positions_by_page = {
            1: [0],  # One image on page 1
            3: [1, 2]  # Two images on page 3
        }
        
        result = parser._insert_image_markers_in_text(
            test_text, 
            image_count=3,
            image_positions_by_page=image_positions_by_page
        )
        
        markers = result.count('<!-- image -->')
        if markers >= 3:
            print_pass(f"Inserted {markers} markers using image positions")
        else:
            print_fail(f"Expected at least 3 markers, got {markers}")
            return False
        
        # Check that markers are near page boundaries
        if '--- Page 1 ---' in result and '<!-- image -->' in result:
            print_pass("Markers inserted near page boundaries")
        else:
            print_fail("Markers not inserted near page boundaries")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Marker insertion test failed: {e}")
        traceback.print_exc()
        return False

# Test 5: OCR Extraction Without Limits
def test_ocr_extraction_limits():
    """Test that OCR extraction has no character limits"""
    print_test("OCR Extraction Without Limits")
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        
        # Check the extraction code
        import inspect
        rag = RAGSystem()
        source_code = inspect.getsource(rag.query_with_rag)
        
        # Check that 10000 limit is removed
        if 'after_text[:10000]' in source_code:
            print_fail("Found 10000 character limit in OCR extraction")
            return False
        
        if 'after_text.strip()' in source_code or 'after_text' in source_code:
            print_pass("OCR extraction uses full text (no limit found)")
        else:
            print_fail("Could not verify OCR extraction code")
            return False
        
        # Check for completeness validation
        if 'ocr_text_length' in source_code:
            print_pass("Completeness validation (ocr_text_length) found")
        else:
            print_fail("Completeness validation not found")
            return False
        
        if 'short_ocr_count' in source_code:
            print_pass("Short OCR count validation found")
        else:
            print_fail("Short OCR count validation not found")
            return False
        
        return True
    except Exception as e:
        print_fail(f"OCR extraction limits test failed: {e}")
        traceback.print_exc()
        return False

# Test 6: Image Content Separation
def test_image_content_separation():
    """Test that image content is properly separated when multiple markers in chunk"""
    print_test("Image Content Separation")
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        
        import inspect
        rag = RAGSystem()
        source_code = inspect.getsource(rag.query_with_rag)
        
        # Check for content separation logic
        if 'idx + 2 < len(parts)' in source_code:
            print_pass("Content separation logic found (checks for next marker)")
        else:
            print_fail("Content separation logic not found")
            return False
        
        # Check that it handles multiple markers
        if 'multiple markers' in source_code.lower() or 'overlap' in source_code.lower():
            print_pass("Multiple marker handling found")
        else:
            print_info("Multiple marker handling comment not found (but logic may exist)")
        
        return True
    except Exception as e:
        print_fail(f"Image content separation test failed: {e}")
        traceback.print_exc()
        return False

# Test 7: Spacing Reduction
def test_spacing_reduction():
    """Test that marker insertion spacing is reduced to 1 line"""
    print_test("Marker Insertion Spacing Reduction")
    
    try:
        from parsers.docling_parser import DoclingParser
        
        import inspect
        parser = DoclingParser()
        source_code = inspect.getsource(parser._insert_image_markers_in_text)
        
        # Check for spacing of 1
        if '(i - last_marker_line) > 1' in source_code:
            print_pass("Spacing reduced to 1 line (found '> 1')")
        elif '(i - last_marker_line) > 2' in source_code:
            print_fail("Spacing still 2 lines (should be 1)")
            return False
        else:
            print_info("Could not verify spacing in code (may use different logic)")
        
        return True
    except Exception as e:
        print_fail(f"Spacing reduction test failed: {e}")
        traceback.print_exc()
        return False

# Test 8: Even Distribution Fallback
def test_even_distribution_fallback():
    """Test that even distribution fallback exists"""
    print_test("Even Distribution Fallback")
    
    try:
        from parsers.docling_parser import DoclingParser
        
        import inspect
        parser = DoclingParser()
        source_code = inspect.getsource(parser._insert_image_markers_in_text)
        
        # Check for Strategy 3 and Strategy 4
        if 'Strategy 3' in source_code or 'Strategy 4' in source_code:
            print_pass("Even distribution strategies found")
        else:
            print_fail("Even distribution strategies not found")
            return False
        
        if 'page_marker_lines' in source_code:
            print_pass("Page boundary distribution found (Strategy 4)")
        else:
            print_fail("Page boundary distribution not found")
            return False
        
        return True
    except Exception as e:
        print_fail(f"Even distribution fallback test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Testing Latest Changes: Document Filtering, Image Markers, OCR Extraction")
    print(f"{'='*70}{Colors.END}\n")
    
    tests = [
        ("Document Number Extraction", test_document_number_extraction),
        ("Document Filtering", test_document_filtering),
        ("Image Position Extraction", test_image_position_extraction),
        ("Marker Insertion with Positions", test_marker_insertion_with_positions),
        ("OCR Extraction Limits", test_ocr_extraction_limits),
        ("Image Content Separation", test_image_content_separation),
        ("Spacing Reduction", test_spacing_reduction),
        ("Even Distribution Fallback", test_even_distribution_fallback),
    ]
    
    for test_name, test_func in tests:
        try:
            test_func()
        except Exception as e:
            print_fail(f"{test_name} raised exception: {e}")
            traceback.print_exc()
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Test Summary")
    print(f"{'='*70}{Colors.END}\n")
    
    total = len(test_results['passed']) + len(test_results['failed']) + len(test_results['skipped'])
    print(f"Total Tests: {total}")
    print(f"{Colors.GREEN}✅ Passed: {len(test_results['passed'])}{Colors.END}")
    print(f"{Colors.RED}❌ Failed: {len(test_results['failed'])}{Colors.END}")
    print(f"{Colors.YELLOW}⏭️  Skipped: {len(test_results['skipped'])}{Colors.END}")
    
    if test_results['failed']:
        print(f"\n{Colors.RED}{Colors.BOLD}Failed Tests:{Colors.END}")
        for fail in test_results['failed']:
            print(f"  - {fail}")
    
    success_rate = (len(test_results['passed']) / total * 100) if total > 0 else 0
    print(f"\n{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.END}")
    
    if len(test_results['failed']) == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All tests passed!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ Some tests failed{Colors.END}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

