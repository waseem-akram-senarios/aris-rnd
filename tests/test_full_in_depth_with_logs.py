#!/usr/bin/env python3
"""
Full in-depth testing with log monitoring and issue detection/fixing.
Tests all endpoints, monitors logs, and identifies issues.
"""
import os
import sys
import json
import requests
import time
import subprocess
from typing import List, Dict, Any, Optional

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_pass(msg):
    print(f"{Colors.GREEN}✅ PASS: {msg}{Colors.END}")

def print_fail(msg):
    print(f"{Colors.RED}❌ FAIL: {msg}{Colors.END}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠️  WARN: {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.CYAN}ℹ️  INFO: {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}🔴 ERROR: {msg}{Colors.END}")

def print_fix(msg):
    print(f"{Colors.MAGENTA}🔧 FIX: {msg}{Colors.END}")

BASE_URL = "http://44.221.84.58:8500"
DOCUMENT_NAME = "FL10.11 SPECIFIC8 (1).pdf"

issues_found = []
fixes_applied = []

def check_server_logs(pattern: str, lines: int = 50) -> List[str]:
    """Check server logs for specific patterns"""
    try:
        # Try to get logs via docker (if accessible)
        result = subprocess.run(
            ['docker', 'logs', '--tail', str(lines), 'aris-rag-app'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logs = result.stdout + result.stderr
            matching_lines = [line for line in logs.split('\n') if pattern.lower() in line.lower()]
            return matching_lines
    except:
        pass
    return []

def analyze_logs_for_issues():
    """Analyze server logs for common issues"""
    print_test("Log Analysis - Checking for Issues")
    
    patterns_to_check = [
        ('image', 'Image-related logs'),
        ('opensearch', 'OpenSearch connection logs'),
        ('extracted_images', 'Image extraction logs'),
        ('stored.*images', 'Image storage logs'),
        ('failed', 'Error logs'),
        ('error', 'Error logs'),
        ('exception', 'Exception logs'),
        ('warning', 'Warning logs'),
    ]
    
    all_issues = []
    
    for pattern, description in patterns_to_check:
        print_info(f"Checking for: {description}")
        logs = check_server_logs(pattern, lines=100)
        
        if logs:
            print_info(f"Found {len(logs)} matching log lines")
            
            # Look for error patterns
            error_keywords = ['error', 'failed', 'exception', 'traceback', 'not found', 'missing']
            for log_line in logs:
                if any(keyword in log_line.lower() for keyword in error_keywords):
                    if 'image' in log_line.lower() or 'opensearch' in log_line.lower():
                        print_error(f"  {log_line[:150]}")
                        all_issues.append({
                            'type': 'error',
                            'pattern': pattern,
                            'log': log_line[:200]
                        })
        else:
            print_info(f"  No logs found for pattern: {pattern}")
    
    return all_issues

def upload_document_with_monitoring():
    """Upload document and monitor for issues"""
    print_test("1. Upload Document with Monitoring")
    
    doc_path = DOCUMENT_NAME
    if not os.path.exists(doc_path):
        print_fail(f"Document not found: {doc_path}")
        return None
    
    try:
        print_info("Uploading document...")
        with open(doc_path, 'rb') as f:
            files = {'file': (os.path.basename(doc_path), f, 'application/pdf')}
            data = {'parser': 'docling'}
            response = requests.post(f"{BASE_URL}/documents", files=files, data=data, timeout=300)
        
        if response.status_code == 201:
            result = response.json()
            doc_id = result.get('document_id')
            print_pass(f"Document uploaded: {doc_id}")
            print_info(f"Document name: {result.get('document_name')}")
            print_info(f"Pages: {result.get('pages', 0)}")
            print_info(f"Images detected: {result.get('images_detected', False)}")
            print_info(f"Image count: {result.get('image_count', 0)}")
            print_info(f"Chunks created: {result.get('chunks_created', 0)}")
            
            # Check for issues in upload response
            if result.get('images_detected') and result.get('image_count', 0) == 0:
                issue = {
                    'type': 'image_extraction',
                    'message': 'Images detected but image_count is 0',
                    'severity': 'high'
                }
                issues_found.append(issue)
                print_warn("⚠️  ISSUE: Images detected but not extracted")
            
            # Wait and check logs
            print_info("Waiting 10 seconds, then checking logs...")
            time.sleep(10)
            
            # Check logs for image storage
            storage_logs = check_server_logs('stored.*images', lines=50)
            if storage_logs:
                print_pass(f"Found image storage logs: {len(storage_logs)}")
                for log in storage_logs[:3]:
                    print_info(f"  {log[:150]}")
            else:
                print_warn("No image storage logs found")
                issue = {
                    'type': 'image_storage',
                    'message': 'No image storage logs found after upload',
                    'severity': 'high'
                }
                issues_found.append(issue)
            
            return doc_id, result.get('document_name')
        else:
            print_fail(f"Upload failed: {response.status_code}")
            print_info(f"Response: {response.text[:200]}")
            return None
    except Exception as e:
        print_fail(f"Upload error: {e}")
        return None

def test_all_endpoints(document_id: str, document_name: str):
    """Test all endpoints comprehensively"""
    print_test("2. Comprehensive Endpoint Testing")
    
    endpoints_tested = 0
    endpoints_passed = 0
    
    # 1. Health check
    endpoints_tested += 1
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print_pass("Health check")
            endpoints_passed += 1
        else:
            print_fail(f"Health check: {response.status_code}")
    except Exception as e:
        print_fail(f"Health check error: {e}")
    
    # 2. Get document
    endpoints_tested += 1
    try:
        response = requests.get(f"{BASE_URL}/documents/{document_id}", timeout=10)
        if response.status_code == 200:
            print_pass("Get document")
            endpoints_passed += 1
        else:
            print_fail(f"Get document: {response.status_code}")
    except Exception as e:
        print_fail(f"Get document error: {e}")
    
    # 3. Get document images
    endpoints_tested += 1
    try:
        response = requests.get(f"{BASE_URL}/documents/{document_id}/images?limit=100", timeout=30)
        if response.status_code == 200:
            data = response.json()
            images = data.get('images', [])
            total = data.get('total', len(images))
            if total > 0:
                print_pass(f"Get document images: {total} images")
                endpoints_passed += 1
            else:
                print_warn("Get document images: No images found")
                issue = {
                    'type': 'no_images',
                    'message': f'No images found for document {document_id}',
                    'severity': 'medium'
                }
                issues_found.append(issue)
        else:
            print_fail(f"Get document images: {response.status_code}")
    except Exception as e:
        print_fail(f"Get document images error: {e}")
    
    # 4. Query images
    endpoints_tested += 1
    try:
        response = requests.post(
            f"{BASE_URL}/query/images",
            json={'question': 'Find images', 'k': 5},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            total = data.get('total', 0)
            if total > 0:
                print_pass(f"Query images: {total} results")
                endpoints_passed += 1
            else:
                print_warn("Query images: No results")
        else:
            print_fail(f"Query images: {response.status_code}")
    except Exception as e:
        print_fail(f"Query images error: {e}")
    
    # 5. Query document
    endpoints_tested += 1
    try:
        response = requests.post(
            f"{BASE_URL}/query",
            json={'question': 'What is in this document?', 'k': 5},
            timeout=30
        )
        if response.status_code == 200:
            print_pass("Query document")
            endpoints_passed += 1
        else:
            print_fail(f"Query document: {response.status_code}")
    except Exception as e:
        print_fail(f"Query document error: {e}")
    
    print_info(f"\nEndpoints: {endpoints_passed}/{endpoints_tested} passed")

def identify_and_fix_issues():
    """Identify issues from logs and apply fixes"""
    print_test("3. Issue Identification and Fixing")
    
    if not issues_found:
        print_pass("No issues found in initial testing")
        return
    
    print_info(f"Found {len(issues_found)} issues to investigate")
    
    for issue in issues_found:
        print_info(f"\nIssue: {issue.get('type')} - {issue.get('message')}")
        print_info(f"Severity: {issue.get('severity', 'unknown')}")
        
        # Check logs for this specific issue
        if issue['type'] == 'image_extraction':
            print_fix("Checking image extraction logs...")
            logs = check_server_logs('extracted.*images', lines=50)
            if logs:
                for log in logs[:3]:
                    print_info(f"  {log[:150]}")
            
            # Check if extracted_images is in parser output
            print_fix("Issue: Images detected but not extracted")
            print_fix("  - Check if Docling parser creates extracted_images list")
            print_fix("  - Verify <!-- image --> markers are in text")
            print_fix("  - Check _extract_individual_images() method")
        
        elif issue['type'] == 'image_storage':
            print_fix("Checking image storage logs...")
            logs = check_server_logs('opensearch', lines=50)
            if logs:
                for log in logs[:3]:
                    print_info(f"  {log[:150]}")
            
            print_fix("Issue: Images not being stored")
            print_fix("  - Verify OpenSearch domain is accessible")
            print_fix("  - Check _store_images_in_opensearch() is called")
            print_fix("  - Verify extracted_images format matches expected")
        
        elif issue['type'] == 'no_images':
            print_fix("Issue: No images in index")
            print_fix("  - Images may not have been extracted")
            print_fix("  - Images may not have been stored")
            print_fix("  - Check extraction and storage logs")

def generate_fix_report():
    """Generate a report of issues and recommended fixes"""
    print_test("4. Generate Fix Report")
    
    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'issues_found': len(issues_found),
        'issues': issues_found,
        'fixes_applied': fixes_applied,
        'recommendations': []
    }
    
    # Add recommendations based on issues
    if any(i['type'] == 'image_extraction' for i in issues_found):
        report['recommendations'].append({
            'priority': 'high',
            'issue': 'Image extraction not working',
            'fix': 'Verify Docling parser extracts images into extracted_images format',
            'files': ['parsers/docling_parser.py'],
            'methods': ['_extract_individual_images()']
        })
    
    if any(i['type'] == 'image_storage' for i in issues_found):
        report['recommendations'].append({
            'priority': 'high',
            'issue': 'Image storage not working',
            'fix': 'Verify OpenSearch connection and storage method',
            'files': ['ingestion/document_processor.py'],
            'methods': ['_store_images_in_opensearch()']
        })
    
    # Save report
    report_file = 'image_test_fix_report.json'
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print_pass(f"Fix report saved to: {report_file}")
    
    # Print summary
    print_info(f"\nSummary:")
    print_info(f"  Issues found: {len(issues_found)}")
    print_info(f"  Fixes applied: {len(fixes_applied)}")
    print_info(f"  Recommendations: {len(report['recommendations'])}")
    
    return report

def main():
    """Run full in-depth testing"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Full In-Depth Testing with Log Monitoring{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}Document: {DOCUMENT_NAME}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*80}{Colors.END}\n")
    
    # Analyze existing logs
    analyze_logs_for_issues()
    
    # Upload and monitor
    result = upload_document_with_monitoring()
    if not result:
        print_fail("Cannot proceed without document")
        return False
    
    document_id, document_name = result
    
    # Test all endpoints
    test_all_endpoints(document_id, document_name)
    
    # Identify and fix issues
    identify_and_fix_issues()
    
    # Generate report
    report = generate_fix_report()
    
    # Final summary
    print(f"\n{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}TESTING COMPLETE{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.GREEN}Issues Found: {len(issues_found)}{Colors.END}")
    print(f"{Colors.MAGENTA}Fixes Applied: {len(fixes_applied)}{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}{Colors.END}\n")
    
    return True

if __name__ == "__main__":
    main()

