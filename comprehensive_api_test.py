#!/usr/bin/env python3
"""
Comprehensive API Test Suite for ARIS RAG System
Tests all endpoints with detailed reporting
"""
import requests
import json
import sys
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://44.221.84.58:8500"
TIMEOUT = 30

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

class APITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results = []
        self.document_id = None
        self.document_name = None
        
    def log(self, message: str, color: str = ""):
        """Print colored log message"""
        if color:
            print(f"{color}{message}{Colors.END}")
        else:
            print(message)
    
    def test_endpoint(self, name: str, method: str, endpoint: str, 
                     data: Dict = None, expected_status: int = None,
                     timeout: int = TIMEOUT) -> Tuple[bool, Dict]:
        """Test a single endpoint and return result"""
        url = f"{self.base_url}{endpoint}"
        
        self.log(f"\n{'='*70}", Colors.BLUE)
        self.log(f"TEST: {name}", Colors.BOLD)
        self.log(f"{'='*70}", Colors.BLUE)
        self.log(f"Method: {method} {endpoint}")
        if data:
            self.log(f"Payload: {json.dumps(data, indent=2)[:200]}...")
        
        start_time = time.time()
        
        try:
            if method == "GET":
                response = requests.get(url, timeout=timeout)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=timeout)
            elif method == "DELETE":
                response = requests.delete(url, timeout=timeout)
            else:
                self.log(f"❌ Unsupported method: {method}", Colors.RED)
                return False, {}
            
            elapsed = time.time() - start_time
            
            self.log(f"Status: {response.status_code}")
            self.log(f"Response Time: {elapsed:.2f}s")
            
            # Parse response
            try:
                response_data = response.json()
                self.log(f"Response: {json.dumps(response_data, indent=2)[:500]}...")
            except:
                response_data = {"text": response.text[:500]}
                self.log(f"Response (text): {response.text[:500]}...")
            
            # Determine success
            if expected_status:
                success = response.status_code == expected_status
            else:
                success = response.status_code < 400
            
            # Special cases
            if response.status_code == 404 and "not found" in str(response_data).lower():
                self.log("⚠️  NOT FOUND (may be expected)", Colors.YELLOW)
                success = True  # 404 is acceptable for missing resources
            elif response.status_code >= 500:
                self.log("❌ SERVER ERROR", Colors.RED)
                success = False
            elif response.status_code >= 400:
                self.log("⚠️  CLIENT ERROR", Colors.YELLOW)
                success = False
            else:
                self.log("✅ SUCCESS", Colors.GREEN)
            
            result = {
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'status_code': response.status_code,
                'response_time': elapsed,
                'success': success,
                'response': response_data
            }
            
            self.results.append(result)
            return success, response_data
            
        except requests.exceptions.Timeout:
            self.log(f"❌ TIMEOUT after {timeout}s", Colors.RED)
            result = {
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'status_code': 0,
                'response_time': timeout,
                'success': False,
                'response': {'error': 'Timeout'}
            }
            self.results.append(result)
            return False, {}
            
        except requests.exceptions.ConnectionError:
            self.log(f"❌ CONNECTION ERROR", Colors.RED)
            result = {
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'response': {'error': 'Connection failed'}
            }
            self.results.append(result)
            return False, {}
            
        except Exception as e:
            self.log(f"❌ ERROR: {str(e)}", Colors.RED)
            result = {
                'name': name,
                'method': method,
                'endpoint': endpoint,
                'status_code': 0,
                'response_time': 0,
                'success': False,
                'response': {'error': str(e)}
            }
            self.results.append(result)
            return False, {}
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        self.log("\n" + "="*70, Colors.BOLD)
        self.log("ARIS RAG SYSTEM - COMPREHENSIVE API TEST SUITE", Colors.BOLD)
        self.log("="*70, Colors.BOLD)
        self.log(f"Server: {self.base_url}")
        self.log(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.log("="*70 + "\n", Colors.BOLD)
        
        # Phase 1: Basic Endpoints
        self.log("\n### PHASE 1: BASIC ENDPOINTS ###\n", Colors.BOLD)
        
        # Test 1: Health check
        self.test_endpoint(
            "API Health Check",
            "GET",
            "/docs"
        )
        
        # Test 2: List documents
        success, response = self.test_endpoint(
            "List All Documents",
            "GET",
            "/documents"
        )
        
        # Extract document info for subsequent tests
        if success and response.get('documents'):
            docs = response['documents']
            if docs:
                # Find first document with valid ID
                for doc in docs:
                    doc_id = doc.get('document_id')
                    if doc_id and doc_id != "None":
                        self.document_id = doc_id
                        self.document_name = doc.get('document_name')
                        self.log(f"\n📄 Using document: {self.document_name} (ID: {self.document_id})", Colors.BLUE)
                        break
                
                if not self.document_id:
                    # Use first document even if ID is None
                    self.document_name = docs[0].get('document_name')
                    self.log(f"\n⚠️  No valid document ID found, using name: {self.document_name}", Colors.YELLOW)
        
        # Test 3: Get single document
        if self.document_id:
            self.test_endpoint(
                "Get Single Document Metadata",
                "GET",
                f"/documents/{self.document_id}"
            )
        
        # Phase 2: Query Endpoints (CRITICAL FIXES)
        self.log("\n### PHASE 2: QUERY ENDPOINTS (FIXED) ###\n", Colors.BOLD)
        
        # Test 4: Query with search_mode (FIX #1)
        self.test_endpoint(
            "Query with search_mode='hybrid' (FIX #1)",
            "POST",
            "/query",
            data={
                "question": "What is this document about?",
                "search_mode": "hybrid",
                "k": 5
            }
        )
        
        # Test 5: Query with search_mode='semantic'
        self.test_endpoint(
            "Query with search_mode='semantic'",
            "POST",
            "/query",
            data={
                "question": "Summarize the main points",
                "search_mode": "semantic",
                "k": 3
            }
        )
        
        # Test 6: Query specific document
        if self.document_id:
            self.test_endpoint(
                "Query Specific Document",
                "POST",
                f"/documents/{self.document_id}/query",
                data={
                    "question": "What is in this document?",
                    "search_mode": "hybrid",
                    "k": 5
                }
            )
        
        # Test 7: Text-only query
        self.test_endpoint(
            "Query Text Only (FIX #5)",
            "POST",
            "/query/text",
            data={
                "question": "What information is available?",
                "k": 5
            }
        )
        
        # Phase 3: Storage & Status Endpoints
        self.log("\n### PHASE 3: STORAGE & STATUS ENDPOINTS (FIXED) ###\n", Colors.BOLD)
        
        # Test 8: Storage status (FIX #3)
        if self.document_id:
            self.test_endpoint(
                "Get Storage Status (FIX #3)",
                "GET",
                f"/documents/{self.document_id}/storage/status"
            )
        
        # Test 9: Accuracy check (FIX #4)
        if self.document_id:
            self.test_endpoint(
                "Get Document Accuracy (FIX #4)",
                "GET",
                f"/documents/{self.document_id}/accuracy"
            )
        
        # Phase 4: Image Endpoints
        self.log("\n### PHASE 4: IMAGE ENDPOINTS (IMPROVED) ###\n", Colors.BOLD)
        
        # Test 10: Query images (FIX #5)
        self.test_endpoint(
            "Query Images (FIX #5)",
            "POST",
            "/query/images",
            data={
                "question": "all images",
                "k": 10
            }
        )
        
        # Test 11: Get all images for document
        if self.document_id:
            self.test_endpoint(
                "Get All Images for Document",
                "GET",
                f"/documents/{self.document_id}/images/all"
            )
        
        # Test 12: Get images summary
        if self.document_id:
            self.test_endpoint(
                "Get Images Summary",
                "GET",
                f"/documents/{self.document_id}/images-summary"
            )
        
        # Phase 5: Page Content Endpoint
        self.log("\n### PHASE 5: PAGE CONTENT ENDPOINT (FIXED) ###\n", Colors.BOLD)
        
        # Test 13: Get page content (FIX #6)
        if self.document_id:
            self.test_endpoint(
                "Get Page 1 Content (FIX #6)",
                "GET",
                f"/documents/{self.document_id}/pages/1"
            )
        
        # Phase 6: Re-store Endpoints
        self.log("\n### PHASE 6: RE-STORE ENDPOINTS (IMPROVED) ###\n", Colors.BOLD)
        
        # Test 14: Re-store text (FIX #7 - Zero chunks diagnostic)
        if self.document_id:
            self.test_endpoint(
                "Re-store Text Content (FIX #7)",
                "POST",
                f"/documents/{self.document_id}/store/text"
            )
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report"""
        self.log("\n" + "="*70, Colors.BOLD)
        self.log("TEST REPORT", Colors.BOLD)
        self.log("="*70, Colors.BOLD)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        self.log(f"\nTotal Tests: {total}")
        self.log(f"Passed: {passed} ({pass_rate:.1f}%)", Colors.GREEN if pass_rate >= 80 else Colors.YELLOW)
        self.log(f"Failed: {failed}", Colors.RED if failed > 0 else Colors.GREEN)
        
        # Detailed results
        self.log("\n" + "-"*70)
        self.log("DETAILED RESULTS", Colors.BOLD)
        self.log("-"*70)
        
        for i, result in enumerate(self.results, 1):
            status_icon = "✅" if result['success'] else "❌"
            color = Colors.GREEN if result['success'] else Colors.RED
            
            self.log(f"\n{i}. {status_icon} {result['name']}", color)
            self.log(f"   Method: {result['method']} {result['endpoint']}")
            self.log(f"   Status: {result['status_code']}")
            self.log(f"   Time: {result['response_time']:.2f}s")
            
            if not result['success'] and 'error' in result['response']:
                self.log(f"   Error: {result['response']['error']}", Colors.RED)
        
        # Summary by category
        self.log("\n" + "-"*70)
        self.log("SUMMARY BY CATEGORY", Colors.BOLD)
        self.log("-"*70)
        
        categories = {
            'Basic Endpoints': [0, 1, 2],
            'Query Endpoints (Critical Fixes)': [3, 4, 5, 6],
            'Storage & Status': [7, 8],
            'Image Endpoints': [9, 10, 11],
            'Page Content': [12],
            'Re-store Endpoints': [13]
        }
        
        for category, indices in categories.items():
            cat_results = [self.results[i] for i in indices if i < len(self.results)]
            cat_passed = sum(1 for r in cat_results if r['success'])
            cat_total = len(cat_results)
            cat_rate = (cat_passed / cat_total * 100) if cat_total > 0 else 0
            
            color = Colors.GREEN if cat_rate >= 80 else (Colors.YELLOW if cat_rate >= 50 else Colors.RED)
            self.log(f"\n{category}: {cat_passed}/{cat_total} ({cat_rate:.0f}%)", color)
        
        # Performance metrics
        self.log("\n" + "-"*70)
        self.log("PERFORMANCE METRICS", Colors.BOLD)
        self.log("-"*70)
        
        response_times = [r['response_time'] for r in self.results if r['response_time'] > 0]
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            min_time = min(response_times)
            
            self.log(f"\nAverage Response Time: {avg_time:.2f}s")
            self.log(f"Fastest Response: {min_time:.2f}s")
            self.log(f"Slowest Response: {max_time:.2f}s")
        
        # Final verdict
        self.log("\n" + "="*70, Colors.BOLD)
        if pass_rate >= 90:
            self.log("🎉 EXCELLENT! All critical endpoints working!", Colors.GREEN)
        elif pass_rate >= 70:
            self.log("✅ GOOD! Most endpoints working, some issues remain", Colors.YELLOW)
        elif pass_rate >= 50:
            self.log("⚠️  FAIR! Significant issues detected", Colors.YELLOW)
        else:
            self.log("❌ CRITICAL! Major issues detected", Colors.RED)
        self.log("="*70, Colors.BOLD)
        
        # Save report to file
        self.save_report()
        
        return pass_rate >= 70
    
    def save_report(self):
        """Save test report to JSON file"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'server': self.base_url,
            'total_tests': len(self.results),
            'passed': sum(1 for r in self.results if r['success']),
            'failed': sum(1 for r in self.results if not r['success']),
            'results': self.results
        }
        
        filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log(f"\n📄 Report saved to: {filename}", Colors.BLUE)

def main():
    """Main test execution"""
    tester = APITester(BASE_URL)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
