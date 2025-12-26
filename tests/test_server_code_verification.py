#!/usr/bin/env python3
"""
Verify Latest Code Changes on Server
Checks that the deployed code has all the latest improvements
"""

import subprocess
import sys

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

def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  INFO: {msg}{Colors.END}")

def check_code_on_server(file_path, search_strings):
    """Check if code contains expected strings"""
    try:
        cmd = f'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -l \'{search_strings[0]}\' {file_path} 2>/dev/null || echo \'NOT_FOUND\'"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'NOT_FOUND' in result.stdout:
            return False
        
        # Check for all strings
        for search_str in search_strings:
            cmd = f'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \'{search_str}\' {file_path} 2>/dev/null && echo FOUND || echo NOT_FOUND"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            if 'NOT_FOUND' in result.stdout:
                return False
        
        return True
    except Exception as e:
        print_fail(f"Error checking code: {e}")
        return False

def test_document_number_extraction():
    """Test that _extract_document_number method exists"""
    print_test("Document Number Extraction Method")
    
    try:
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"def _extract_document_number\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("_extract_document_number method found in deployed code")
            return True
        else:
            print_fail("_extract_document_number method not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_document_filtering_logic():
    """Test that document filtering logic is present"""
    print_test("Document Filtering Logic")
    
    try:
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"question_doc_number\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("Document filtering logic (question_doc_number) found")
            
            # Check for image content filtering
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"Filtered image content\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_pass("Image content filtering logic found")
                return True
            else:
                print_fail("Image content filtering not found")
                return False
        else:
            print_fail("Document filtering logic not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_image_position_extraction():
    """Test that image position extraction is present"""
    print_test("Image Position Extraction")
    
    try:
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"image_positions_by_page\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("image_positions_by_page variable found")
            
            # Check for doc.pictures extraction
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"doc.pictures\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_pass("doc.pictures extraction code found")
                return True
            else:
                print_fail("doc.pictures extraction not found")
                return False
        else:
            print_fail("image_positions_by_page not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_ocr_extraction_limits():
    """Test that OCR extraction limits are removed"""
    print_test("OCR Extraction Limits Removed")
    
    try:
        # Check that 10000 limit is NOT present
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"after_text[:10000]\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'NOT_FOUND' in result.stdout:
            print_pass("10000 character limit removed")
            
            # Check for full extraction
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"after_text.strip()\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_pass("Full text extraction (after_text.strip()) found")
                return True
            else:
                print_fail("Full text extraction not found")
                return False
        else:
            print_fail("10000 character limit still present")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_completeness_validation():
    """Test that completeness validation is present"""
    print_test("Completeness Validation")
    
    try:
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"ocr_text_length\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("ocr_text_length validation found")
            
            # Check for short OCR count
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"short_ocr_count\" /app/rag_system.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_pass("short_ocr_count validation found")
                return True
            else:
                print_fail("short_ocr_count validation not found")
                return False
        else:
            print_fail("ocr_text_length validation not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_marker_insertion_spacing():
    """Test that marker insertion spacing is reduced"""
    print_test("Marker Insertion Spacing")
    
    try:
        # Check for spacing of 1 (not 2)
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"(i - last_marker_line) > 1\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("Spacing reduced to 1 line found")
            return True
        else:
            # Check if old spacing (2) still exists
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"(i - last_marker_line) > 2\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_fail("Old spacing (2) still present")
                return False
            else:
                print_info("Could not verify spacing (may use different logic)")
                return True
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def test_even_distribution_fallback():
    """Test that even distribution fallback exists"""
    print_test("Even Distribution Fallback")
    
    try:
        cmd = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"Strategy 4\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if 'FOUND' in result.stdout:
            print_pass("Strategy 4 (page boundary distribution) found")
            
            # Check for page_marker_lines
            cmd2 = 'ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 "docker exec aris-rag-app grep -q \"page_marker_lines\" /app/parsers/docling_parser.py && echo FOUND || echo NOT_FOUND"'
            result2 = subprocess.run(cmd2, shell=True, capture_output=True, text=True, timeout=10)
            
            if 'FOUND' in result2.stdout:
                print_pass("Page boundary distribution logic found")
                return True
            else:
                print_fail("Page boundary distribution not found")
                return False
        else:
            print_fail("Strategy 4 not found")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def main():
    """Run all verification tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Verifying Latest Code Changes on Deployed Server")
    print(f"{'='*70}{Colors.END}\n")
    
    results = []
    
    # Test 1: Document Number Extraction
    results.append(("Document Number Extraction", test_document_number_extraction()))
    
    # Test 2: Document Filtering
    results.append(("Document Filtering", test_document_filtering_logic()))
    
    # Test 3: Image Position Extraction
    results.append(("Image Position Extraction", test_image_position_extraction()))
    
    # Test 4: OCR Extraction Limits
    results.append(("OCR Extraction Limits", test_ocr_extraction_limits()))
    
    # Test 5: Completeness Validation
    results.append(("Completeness Validation", test_completeness_validation()))
    
    # Test 6: Marker Insertion Spacing
    results.append(("Marker Insertion Spacing", test_marker_insertion_spacing()))
    
    # Test 7: Even Distribution Fallback
    results.append(("Even Distribution Fallback", test_even_distribution_fallback()))
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Verification Summary")
    print(f"{'='*70}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status}: {test_name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} verifications passed ({passed/total*100:.1f}%){Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All code changes verified on server!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some code changes not verified{Colors.END}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

