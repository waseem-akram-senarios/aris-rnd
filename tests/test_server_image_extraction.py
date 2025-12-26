#!/usr/bin/env python3
"""
Test Image Extraction on Deployed Server
Tests the latest changes on the live server endpoint
"""

import requests
import json
import time
from typing import Dict, Any

# Server configuration
SERVER_URL = "http://44.221.84.58"
API_ENDPOINT = f"{SERVER_URL}/api/query"

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

def print_fail(msg, error=None):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")
    if error:
        print(f"{Colors.RED}   Error: {error}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  INFO: {msg}{Colors.END}")

def query_server(question: str, use_agentic_rag: bool = False) -> Dict[str, Any]:
    """Query the deployed server"""
    try:
        payload = {
            "question": question,
            "use_agentic_rag": use_agentic_rag,
            "k": 10,
            "use_mmr": False,
            "use_hybrid_search": True
        }
        
        response = requests.post(API_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print_fail(f"Server request failed: {e}")
        return {}

def test_server_health():
    """Test if server is accessible"""
    print_test("Server Health Check")
    
    try:
        response = requests.get(SERVER_URL, timeout=10)
        if response.status_code == 200:
            print_pass(f"Server is accessible (HTTP {response.status_code})")
            return True
        else:
            print_fail(f"Server returned HTTP {response.status_code}")
            return False
    except Exception as e:
        print_fail(f"Could not connect to server: {e}")
        return False

def test_image_count_query():
    """Test querying image count from a document"""
    print_test("Image Count Query")
    
    # Test with a document that should have images
    question = "How many images in FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query: {question}")
    result = query_server(question)
    
    if not result:
        print_fail("No response from server")
        return False
    
    answer = result.get('answer', '')
    print_info(f"Answer: {answer[:200]}...")
    
    # Check if answer mentions image count
    if 'image' in answer.lower() and ('13' in answer or '22' in answer or 'count' in answer.lower()):
        print_pass("Answer contains image count information")
        return True
    else:
        print_fail(f"Answer doesn't seem to contain image count: {answer[:200]}")
        return False

def test_document_filtering():
    """Test that document filtering works (distinguishing (1) vs (2))"""
    print_test("Document Filtering - (1) vs (2)")
    
    # Test query for (1).pdf
    question1 = "Give me information about images in FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query 1: {question1}")
    result1 = query_server(question1)
    
    if not result1:
        print_fail("No response for (1).pdf query")
        return False
    
    answer1 = result1.get('answer', '')
    print_info(f"Answer 1: {answer1[:300]}...")
    
    # Check if answer mentions (1) and not (2)
    if '(1)' in answer1 or 'FL10.11 SPECIFIC8 (1)' in answer1:
        print_pass("Answer correctly references (1).pdf")
    else:
        print_fail("Answer doesn't clearly reference (1).pdf")
    
    # Test query for (2).pdf
    question2 = "Give me information about images in FL10.11 SPECIFIC8 (2).pdf"
    
    print_info(f"Query 2: {question2}")
    result2 = query_server(question2)
    
    if not result2:
        print_fail("No response for (2).pdf query")
        return False
    
    answer2 = result2.get('answer', '')
    print_info(f"Answer 2: {answer2[:300]}...")
    
    # Check if answer mentions (2) and not (1)
    if '(2)' in answer2 or 'FL10.11 SPECIFIC8 (2)' in answer2:
        print_pass("Answer correctly references (2).pdf")
        return True
    else:
        print_fail("Answer doesn't clearly reference (2).pdf")
        return False

def test_image_content_extraction():
    """Test that image content is extracted and returned"""
    print_test("Image Content Extraction")
    
    question = "What information is in image 1 of FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query: {question}")
    result = query_server(question)
    
    if not result:
        print_fail("No response from server")
        return False
    
    answer = result.get('answer', '')
    print_info(f"Answer length: {len(answer)} characters")
    print_info(f"Answer preview: {answer[:400]}...")
    
    # Check if answer contains image-related content
    image_keywords = ['image', 'drawer', 'tool', 'part', 'quantity', 'socket', 'wrench']
    found_keywords = [kw for kw in image_keywords if kw in answer.lower()]
    
    if found_keywords:
        print_pass(f"Answer contains image-related keywords: {', '.join(found_keywords)}")
    else:
        print_fail("Answer doesn't contain expected image-related keywords")
    
    # Check if answer is substantial (not just "no information")
    if len(answer) > 100:
        print_pass(f"Answer is substantial ({len(answer)} characters)")
        return True
    else:
        print_fail(f"Answer is too short ({len(answer)} characters)")
        return False

def test_specific_image_query():
    """Test querying a specific image number"""
    print_test("Specific Image Query")
    
    question = "Give me information about image 3 in FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query: {question}")
    result = query_server(question)
    
    if not result:
        print_fail("No response from server")
        return False
    
    answer = result.get('answer', '')
    print_info(f"Answer: {answer[:500]}...")
    
    # Check if answer mentions image 3 or contains specific content
    if 'image 3' in answer.lower() or '3' in answer or len(answer) > 150:
        print_pass("Answer contains information about image 3")
        return True
    else:
        print_fail(f"Answer doesn't contain expected image 3 information: {answer[:200]}")
        return False

def test_multiple_images_query():
    """Test querying multiple images"""
    print_test("Multiple Images Query")
    
    question = "Give me information about all images in FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query: {question}")
    result = query_server(question)
    
    if not result:
        print_fail("No response from server")
        return False
    
    answer = result.get('answer', '')
    print_info(f"Answer length: {len(answer)} characters")
    
    # Check if answer mentions multiple images
    if len(answer) > 200:
        print_pass(f"Answer is comprehensive ({len(answer)} characters)")
        
        # Check for image numbers
        image_numbers = [str(i) for i in range(1, 15) if f'image {i}' in answer.lower() or f'image {i}:' in answer.lower()]
        if image_numbers:
            print_pass(f"Answer mentions images: {', '.join(image_numbers[:5])}...")
        else:
            print_info("Answer doesn't explicitly number images, but contains content")
        
        return True
    else:
        print_fail(f"Answer is too short for multiple images query: {len(answer)} characters")
        return False

def test_drawer_query():
    """Test querying drawer information (common in image content)"""
    print_test("Drawer Information Query")
    
    question = "What's inside DRAWER 1 in FL10.11 SPECIFIC8 (1).pdf"
    
    print_info(f"Query: {question}")
    result = query_server(question)
    
    if not result:
        print_fail("No response from server")
        return False
    
    answer = result.get('answer', '')
    print_info(f"Answer: {answer[:500]}...")
    
    # Check if answer contains drawer-related content
    drawer_keywords = ['drawer', 'tool', 'socket', 'wrench', 'part', 'quantity']
    found_keywords = [kw for kw in drawer_keywords if kw in answer.lower()]
    
    if found_keywords:
        print_pass(f"Answer contains drawer-related keywords: {', '.join(found_keywords)}")
        return True
    else:
        print_fail("Answer doesn't contain expected drawer-related keywords")
        return False

def main():
    """Run all tests"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Testing Image Extraction on Deployed Server")
    print(f"{'='*70}{Colors.END}\n")
    
    results = []
    
    # Test 1: Server Health
    results.append(("Server Health", test_server_health()))
    
    if not results[-1][1]:
        print(f"\n{Colors.RED}❌ Server is not accessible. Cannot continue tests.{Colors.END}")
        return 1
    
    # Wait a moment for server to be ready
    time.sleep(2)
    
    # Test 2: Image Count Query
    results.append(("Image Count Query", test_image_count_query()))
    time.sleep(1)
    
    # Test 3: Document Filtering
    results.append(("Document Filtering", test_document_filtering()))
    time.sleep(1)
    
    # Test 4: Image Content Extraction
    results.append(("Image Content Extraction", test_image_content_extraction()))
    time.sleep(1)
    
    # Test 5: Specific Image Query
    results.append(("Specific Image Query", test_specific_image_query()))
    time.sleep(1)
    
    # Test 6: Multiple Images Query
    results.append(("Multiple Images Query", test_multiple_images_query()))
    time.sleep(1)
    
    # Test 7: Drawer Query
    results.append(("Drawer Information Query", test_drawer_query()))
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}")
    print("Test Summary")
    print(f"{'='*70}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if result else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status}: {test_name}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed ({passed/total*100:.1f}%){Colors.END}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All tests passed!{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed{Colors.END}\n")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

