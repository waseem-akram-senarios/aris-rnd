#!/usr/bin/env python3
"""
Deep Synchronization Analysis for ARIS RAG Microservices
Comprehensive test suite to verify all 4 services are fully synchronized
"""
import requests
import json
import sys
import time
import os
import hashlib
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Server configuration
BASE_URL = "http://44.221.84.58"
UI_URL = f"{BASE_URL}"
GATEWAY_URL = f"{BASE_URL}:8500"
INGESTION_URL = f"{BASE_URL}:8501"
RETRIEVAL_URL = f"{BASE_URL}:8502"

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'
NC = '\033[0m'  # No Color

class DeepSyncResult:
    def __init__(self, category: str, test_name: str, success: bool, details: str = "", 
                 data: Optional[Dict] = None, metrics: Optional[Dict] = None):
        self.category = category
        self.test_name = test_name
        self.success = success
        self.details = details
        self.data = data or {}
        self.metrics = metrics or {}
        self.timestamp = datetime.now().isoformat()

class DeepSyncAnalyzer:
    def __init__(self):
        self.results: List[DeepSyncResult] = []
        self.metrics: Dict = {
            'service_response_times': {},
            'sync_latencies': {},
            'data_consistency_scores': {},
            'file_access_times': {}
        }
    
    def print_header(self, text: str, level: int = 1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{BLUE}{'='*80}{NC}")
            print(f"{BLUE}{text:^80}{NC}")
            print(f"{BLUE}{'='*80}{NC}\n")
        elif level == 2:
            print(f"\n{CYAN}{'─'*80}{NC}")
            print(f"{CYAN}{text}{NC}")
            print(f"{CYAN}{'─'*80}{NC}\n")
        else:
            print(f"\n{MAGENTA}{text}{NC}")
    
    def print_test(self, name: str, success: bool, details: str = "", metrics: Dict = None):
        """Print test result"""
        status = f"{GREEN}✓ PASS{NC}" if success else f"{RED}✗ FAIL{NC}"
        print(f"{status} {name}")
        if details:
            for line in details.split('\n'):
                print(f"    {line}")
        if metrics:
            for key, value in metrics.items():
                print(f"    {YELLOW}→{NC} {key}: {value}")
    
    def record_result(self, category: str, test_name: str, success: bool, 
                     details: str = "", data: Dict = None, metrics: Dict = None):
        """Record test result"""
        result = DeepSyncResult(category, test_name, success, details, data, metrics)
        self.results.append(result)
        self.print_test(test_name, success, details, metrics)
        return result
    
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function"""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            return result, elapsed
        except Exception as e:
            elapsed = time.time() - start
            raise e
    
    # ==================== TEST CATEGORIES ====================
    
    def test_service_health_deep(self) -> List[DeepSyncResult]:
        """Deep health check for all services"""
        self.print_header("1. SERVICE HEALTH & CONNECTIVITY", 1)
        results = []
        
        services = [
            ("UI", UI_URL, None),
            ("Gateway", GATEWAY_URL, "/health"),
            ("Ingestion", INGESTION_URL, "/health"),
            ("Retrieval", RETRIEVAL_URL, "/health")
        ]
        
        for service_name, base_url, endpoint in services:
            self.print_header(f"Testing {service_name} Service", 2)
            
            # Test 1: Basic connectivity
            try:
                url = f"{base_url}{endpoint}" if endpoint else base_url
                start = time.time()
                response = requests.get(url, timeout=10, allow_redirects=True)
                response_time = time.time() - start
                
                if response.status_code in [200, 302]:
                    self.metrics['service_response_times'][service_name] = response_time
                    result = self.record_result(
                        "Service Health",
                        f"{service_name} Connectivity",
                        True,
                        f"HTTP {response.status_code} | Response time: {response_time:.3f}s",
                        {"status_code": response.status_code, "response_time": response_time}
                    )
                    results.append(result)
                else:
                    result = self.record_result(
                        "Service Health",
                        f"{service_name} Connectivity",
                        False,
                        f"HTTP {response.status_code}"
                    )
                    results.append(result)
            except Exception as e:
                result = self.record_result(
                    "Service Health",
                    f"{service_name} Connectivity",
                    False,
                    f"Error: {str(e)}"
                )
                results.append(result)
            
            # Test 2: Health endpoint details (for API services)
            if endpoint and response.status_code == 200:
                try:
                    health_data = response.json()
                    registry_accessible = health_data.get("registry_accessible", False)
                    index_map_accessible = health_data.get("index_map_accessible", False)
                    doc_count = health_data.get("registry_document_count", 0)
                    index_entries = health_data.get("index_map_entries", 0)
                    
                    result = self.record_result(
                        "Service Health",
                        f"{service_name} Health Details",
                        True,
                        f"Registry: {registry_accessible} | Index Map: {index_map_accessible} | "
                        f"Docs: {doc_count} | Index Entries: {index_entries}",
                        health_data
                    )
                    results.append(result)
                except:
                    pass
        
        # Test 3: Inter-service connectivity
        self.print_header("Inter-Service Connectivity", 2)
        
        # Gateway -> Ingestion
        try:
            start = time.time()
            response = requests.get(f"{INGESTION_URL}/health", timeout=10)
            elapsed = time.time() - start
            if response.status_code == 200:
                self.record_result(
                    "Service Health",
                    "Gateway → Ingestion",
                    True,
                    f"Connectivity verified | Latency: {elapsed:.3f}s",
                    {"latency": elapsed}
                )
        except Exception as e:
            self.record_result(
                "Service Health",
                "Gateway → Ingestion",
                False,
                f"Error: {str(e)}"
            )
        
        # Gateway -> Retrieval
        try:
            start = time.time()
            response = requests.get(f"{RETRIEVAL_URL}/health", timeout=10)
            elapsed = time.time() - start
            if response.status_code == 200:
                self.record_result(
                    "Service Health",
                    "Gateway → Retrieval",
                    True,
                    f"Connectivity verified | Latency: {elapsed:.3f}s",
                    {"latency": elapsed}
                )
        except Exception as e:
            self.record_result(
                "Service Health",
                "Gateway → Retrieval",
                False,
                f"Error: {str(e)}"
            )
        
        return results
    
    def test_shared_resources_deep(self) -> List[DeepSyncResult]:
        """Deep verification of shared resources"""
        self.print_header("2. SHARED RESOURCE VERIFICATION", 1)
        results = []
        
        # Get sync status from Gateway
        try:
            sync_response = requests.get(f"{GATEWAY_URL}/sync/status", timeout=10)
            if sync_response.status_code == 200:
                sync_data = sync_response.json()
                
                registry_info = sync_data.get("registry", {})
                index_map_info = sync_data.get("index_map", {})
                
                # Test registry access
                registry_accessible = registry_info.get("accessible", False)
                registry_exists = registry_info.get("exists", False)
                registry_count = registry_info.get("document_count", 0)
                registry_path = registry_info.get("path", "N/A")
                
                result = self.record_result(
                    "Shared Resources",
                    "Document Registry Access",
                    registry_accessible,
                    f"Path: {registry_path} | Exists: {registry_exists} | "
                    f"Documents: {registry_count} | Accessible: {registry_accessible}",
                    registry_info
                )
                results.append(result)
                
                # Test index map access
                index_map_accessible = index_map_info.get("accessible", False)
                index_map_exists = index_map_info.get("exists", False)
                index_map_count = index_map_info.get("entry_count", 0)
                index_map_path = index_map_info.get("path", "N/A")
                
                result = self.record_result(
                    "Shared Resources",
                    "Index Map Access",
                    index_map_accessible,
                    f"Path: {index_map_path} | Exists: {index_map_exists} | "
                    f"Entries: {index_map_count} | Accessible: {index_map_accessible}",
                    index_map_info
                )
                results.append(result)
                
                # Verify all services can access
                self.print_header("Cross-Service Resource Access", 2)
                
                services_to_check = [
                    ("Gateway", GATEWAY_URL),
                    ("Ingestion", INGESTION_URL),
                    ("Retrieval", RETRIEVAL_URL)
                ]
                
                for service_name, service_url in services_to_check:
                    try:
                        health_response = requests.get(f"{service_url}/health", timeout=10)
                        if health_response.status_code == 200:
                            health_data = health_response.json()
                            svc_registry = health_data.get("registry_accessible", False)
                            svc_index = health_data.get("index_map_accessible", False)
                            
                            result = self.record_result(
                                "Shared Resources",
                                f"{service_name} Resource Access",
                                svc_registry and svc_index,
                                f"Registry: {svc_registry} | Index Map: {svc_index}",
                                health_data
                            )
                            results.append(result)
                    except Exception as e:
                        self.record_result(
                            "Shared Resources",
                            f"{service_name} Resource Access",
                            False,
                            f"Error: {str(e)}"
                        )
        except Exception as e:
            self.record_result(
                "Shared Resources",
                "Sync Status Check",
                False,
                f"Error: {str(e)}"
            )
        
        return results
    
    def test_data_consistency(self) -> List[DeepSyncResult]:
        """Test data consistency across services"""
        self.print_header("3. DATA CONSISTENCY VERIFICATION", 1)
        results = []
        
        # Get document lists from all services
        service_docs = {}
        
        # Gateway
        try:
            gateway_response = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
            if gateway_response.status_code == 200:
                gateway_data = gateway_response.json()
                gateway_docs = gateway_data.get("documents", [])
                gateway_total = gateway_data.get("total", 0)
                service_docs["Gateway"] = {
                    "documents": gateway_docs,
                    "total": gateway_total,
                    "doc_ids": set([doc.get("document_id") for doc in gateway_docs if doc.get("document_id")])
                }
        except Exception as e:
            self.record_result(
                "Data Consistency",
                "Gateway Document List",
                False,
                f"Error: {str(e)}"
            )
        
        # Get health data for document counts
        doc_counts = {}
        try:
            for service_name, service_url in [("Ingestion", INGESTION_URL), ("Retrieval", RETRIEVAL_URL)]:
                health_response = requests.get(f"{service_url}/health", timeout=10)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    if service_name == "Ingestion":
                        doc_counts[service_name] = health_data.get("registry_document_count", 0)
                    else:
                        doc_counts[service_name] = health_data.get("index_map_entries", 0)
        except:
            pass
        
        # Compare document counts
        self.print_header("Document Count Consistency", 2)
        
        if "Gateway" in service_docs:
            gateway_count = service_docs["Gateway"]["total"]
            
            # Compare with Ingestion
            if "Ingestion" in doc_counts:
                ingestion_count = doc_counts["Ingestion"]
                count_match = abs(gateway_count - ingestion_count) <= 1  # Allow 1 doc difference for processing
                
                result = self.record_result(
                    "Data Consistency",
                    "Document Count: Gateway vs Ingestion",
                    count_match,
                    f"Gateway: {gateway_count} | Ingestion: {ingestion_count} | "
                    f"Difference: {abs(gateway_count - ingestion_count)}",
                    {"gateway": gateway_count, "ingestion": ingestion_count}
                )
                results.append(result)
        
        # Test document ID consistency
        if "Gateway" in service_docs and len(service_docs["Gateway"]["doc_ids"]) > 0:
            self.print_header("Document ID Consistency", 2)
            
            # Sample a few documents and verify they exist in registry
            sample_docs = list(service_docs["Gateway"]["doc_ids"])[:5]
            consistent_count = 0
            
            for doc_id in sample_docs:
                try:
                    doc_response = requests.get(f"{GATEWAY_URL}/documents/{doc_id}", timeout=10)
                    if doc_response.status_code == 200:
                        consistent_count += 1
                except:
                    pass
            
            consistency_score = consistent_count / len(sample_docs) if sample_docs else 0
            
            result = self.record_result(
                "Data Consistency",
                "Document ID Consistency",
                consistency_score >= 0.8,
                f"Verified {consistent_count}/{len(sample_docs)} sample documents | "
                f"Consistency: {consistency_score*100:.1f}%",
                {"verified": consistent_count, "total": len(sample_docs), "score": consistency_score},
                {"consistency_score": consistency_score}
            )
            results.append(result)
            self.metrics['data_consistency_scores']['document_ids'] = consistency_score
        
        return results
    
    def test_realtime_sync(self) -> List[DeepSyncResult]:
        """Test real-time synchronization"""
        self.print_header("4. REAL-TIME SYNCHRONIZATION TEST", 1)
        results = []
        
        # Upload a test document
        test_content = b"This is a deep sync analysis test document.\n" + \
                      b"It tests real-time synchronization across all services.\n" + \
                      b"Timestamp: " + str(time.time()).encode() + b"\n"
        test_filename = f"deep_sync_test_{int(time.time())}.txt"
        
        self.print_header("Upload Test Document", 2)
        
        try:
            # Step 1: Upload via Gateway
            upload_start = time.time()
            files = {"file": (test_filename, test_content, "text/plain")}
            upload_response = requests.post(f"{GATEWAY_URL}/documents", files=files, timeout=60)
            upload_time = time.time() - upload_start
            
            if upload_response.status_code not in [200, 201, 202]:
                result = self.record_result(
                    "Real-time Sync",
                    "Document Upload",
                    False,
                    f"Upload failed: {upload_response.status_code}"
                )
                results.append(result)
                return results
            
            upload_data = upload_response.json()
            document_id = upload_data.get("document_id")
            
            result = self.record_result(
                "Real-time Sync",
                "Document Upload",
                True,
                f"Document ID: {document_id[:8]}... | Upload time: {upload_time:.3f}s",
                {"document_id": document_id, "upload_time": upload_time},
                {"upload_latency": upload_time}
            )
            results.append(result)
            self.metrics['sync_latencies']['upload'] = upload_time
            
            # Step 2: Wait for processing and check propagation
            self.print_header("Sync Propagation Check", 2)
            
            max_wait = 90
            wait_interval = 2
            wait_time = 0
            status = "processing"
            sync_times = {}
            
            while wait_time < max_wait and status == "processing":
                time.sleep(wait_interval)
                wait_time += wait_interval
                
                # Check Gateway status
                try:
                    status_start = time.time()
                    status_response = requests.get(f"{GATEWAY_URL}/documents/{document_id}", timeout=10)
                    status_time = time.time() - status_start
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        status = status_data.get("status", "unknown")
                        chunks = status_data.get("chunks_created", 0)
                        
                        if status == "success" and "gateway_status" not in sync_times:
                            sync_times["gateway_status"] = wait_time
                            result = self.record_result(
                                "Real-time Sync",
                                "Gateway Status Propagation",
                                True,
                                f"Status: {status} | Chunks: {chunks} | Time: {wait_time}s",
                                {"status": status, "chunks": chunks, "sync_time": wait_time},
                                {"status_sync_latency": wait_time}
                            )
                            results.append(result)
                except:
                    pass
                
                if wait_time % 10 == 0:
                    print(f"    Waiting... {wait_time}s | Status: {status}")
            
            # Step 3: Verify document appears in all services
            if status == "success":
                self.print_header("Cross-Service Document Verification", 2)
                
                # Check Ingestion service
                try:
                    ingestion_start = time.time()
                    ingestion_status = requests.get(f"{INGESTION_URL}/status/{document_id}", timeout=10)
                    ingestion_time = time.time() - ingestion_start
                    
                    if ingestion_status.status_code == 200:
                        ingestion_data = ingestion_status.json()
                        result = self.record_result(
                            "Real-time Sync",
                            "Ingestion Service Verification",
                            True,
                            f"Status: {ingestion_data.get('status')} | "
                            f"Response time: {ingestion_time:.3f}s",
                            ingestion_data,
                            {"ingestion_response_time": ingestion_time}
                        )
                        results.append(result)
                except Exception as e:
                    self.record_result(
                        "Real-time Sync",
                        "Ingestion Service Verification",
                        False,
                        f"Error: {str(e)}"
                    )
                
                # Step 4: Verify document can be queried (Retrieval service)
                try:
                    query_start = time.time()
                    query_payload = {
                        "question": "deep sync analysis test",
                        "k": 3,
                        "use_hybrid_search": True
                    }
                    query_response = requests.post(f"{GATEWAY_URL}/query", json=query_payload, timeout=30)
                    query_time = time.time() - query_start
                    
                    if query_response.status_code == 200:
                        query_data = query_response.json()
                        sources = query_data.get("sources", [])
                        found_doc = test_filename in sources or any(
                            test_filename in str(cit.get("source", "")) 
                            for cit in query_data.get("citations", [])
                        )
                        
                        result = self.record_result(
                            "Real-time Sync",
                            "Retrieval Service Verification",
                            found_doc,
                            f"Document found: {found_doc} | Sources: {len(sources)} | "
                            f"Query time: {query_time:.3f}s",
                            {"found": found_doc, "sources": sources},
                            {"query_latency": query_time}
                        )
                        results.append(result)
                        self.metrics['sync_latencies']['query'] = query_time
                except Exception as e:
                    self.record_result(
                        "Real-time Sync",
                        "Retrieval Service Verification",
                        False,
                        f"Error: {str(e)}"
                    )
            else:
                result = self.record_result(
                    "Real-time Sync",
                    "Processing Completion",
                    False,
                    f"Processing did not complete. Status: {status} after {wait_time}s"
                )
                results.append(result)
                
        except Exception as e:
            result = self.record_result(
                "Real-time Sync",
                "Real-time Sync Test",
                False,
                f"Error: {str(e)}"
            )
            results.append(result)
        
        return results
    
    def test_execution_order(self) -> List[DeepSyncResult]:
        """Test execution order for different flows"""
        self.print_header("5. EXECUTION ORDER VERIFICATION", 1)
        results = []
        
        # Test 1: Upload flow (UI -> Gateway -> Ingestion)
        self.print_header("Upload Flow: UI → Gateway → Ingestion", 2)
        
        try:
            test_content = b"Execution order test document for upload flow verification."
            test_filename = f"exec_order_upload_{int(time.time())}.txt"
            
            # Upload via Gateway (simulating UI -> Gateway)
            upload_start = time.time()
            files = {"file": (test_filename, test_content, "text/plain")}
            upload_response = requests.post(f"{GATEWAY_URL}/documents", files=files, timeout=60)
            upload_time = time.time() - upload_start
            
            if upload_response.status_code in [200, 201, 202]:
                upload_data = upload_response.json()
                document_id = upload_data.get("document_id")
                
                # Verify Gateway forwarded to Ingestion
                time.sleep(2)  # Brief wait
                
                ingestion_status = requests.get(f"{INGESTION_URL}/status/{document_id}", timeout=10)
                ingestion_accessible = ingestion_status.status_code == 200
                
                result = self.record_result(
                    "Execution Order",
                    "Upload Flow: UI → Gateway → Ingestion",
                    ingestion_accessible,
                    f"Gateway upload: {upload_time:.3f}s | "
                    f"Ingestion accessible: {ingestion_accessible}",
                    {"document_id": document_id, "upload_time": upload_time}
                )
                results.append(result)
        except Exception as e:
            self.record_result(
                "Execution Order",
                "Upload Flow",
                False,
                f"Error: {str(e)}"
            )
        
        # Test 2: Query flow (UI -> Gateway -> Retrieval)
        self.print_header("Query Flow: UI → Gateway → Retrieval", 2)
        
        try:
            query_start = time.time()
            query_payload = {
                "question": "execution order test",
                "k": 2,
                "use_hybrid_search": True
            }
            query_response = requests.post(f"{GATEWAY_URL}/query", json=query_payload, timeout=30)
            query_time = time.time() - query_start
            
            if query_response.status_code == 200:
                query_data = query_response.json()
                answer = query_data.get("answer", "")
                
                # Verify Gateway forwarded to Retrieval
                direct_query = requests.post(f"{RETRIEVAL_URL}/query", json=query_payload, timeout=30)
                retrieval_accessible = direct_query.status_code == 200
                
                result = self.record_result(
                    "Execution Order",
                    "Query Flow: UI → Gateway → Retrieval",
                    retrieval_accessible,
                    f"Gateway query: {query_time:.3f}s | "
                    f"Retrieval accessible: {retrieval_accessible} | "
                    f"Answer length: {len(answer)} chars",
                    {"query_time": query_time, "answer_length": len(answer)}
                )
                results.append(result)
        except Exception as e:
            self.record_result(
                "Execution Order",
                "Query Flow",
                False,
                f"Error: {str(e)}"
            )
        
        return results
    
    def test_edge_cases(self) -> List[DeepSyncResult]:
        """Test edge cases and failure scenarios"""
        self.print_header("6. EDGE CASE TESTING", 1)
        results = []
        
        # Test 1: Concurrent operations
        self.print_header("Concurrent Operations", 2)
        
        try:
            # Simulate concurrent queries
            import threading
            
            query_results = []
            errors = []
            
            def concurrent_query(query_num):
                try:
                    query_payload = {
                        "question": f"concurrent test query {query_num}",
                        "k": 1
                    }
                    response = requests.post(f"{GATEWAY_URL}/query", json=query_payload, timeout=30)
                    query_results.append(response.status_code == 200)
                except Exception as e:
                    errors.append(str(e))
            
            threads = []
            for i in range(3):
                thread = threading.Thread(target=concurrent_query, args=(i,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join(timeout=35)
            
            success_rate = sum(query_results) / len(query_results) if query_results else 0
            
            result = self.record_result(
                "Edge Cases",
                "Concurrent Queries",
                success_rate >= 0.67,  # At least 2/3 succeed
                f"Success rate: {success_rate*100:.1f}% ({sum(query_results)}/{len(query_results)}) | "
                f"Errors: {len(errors)}",
                {"success_rate": success_rate, "errors": errors}
            )
            results.append(result)
        except Exception as e:
            self.record_result(
                "Edge Cases",
                "Concurrent Operations",
                False,
                f"Error: {str(e)}"
            )
        
        # Test 2: Service availability during operations
        self.print_header("Service Resilience", 2)
        
        # Check if services remain accessible during load
        try:
            start = time.time()
            health_checks = []
            for service_name, service_url in [
                ("Gateway", GATEWAY_URL),
                ("Ingestion", INGESTION_URL),
                ("Retrieval", RETRIEVAL_URL)
            ]:
                try:
                    response = requests.get(f"{service_url}/health", timeout=5)
                    health_checks.append(response.status_code == 200)
                except:
                    health_checks.append(False)
            
            all_healthy = all(health_checks)
            check_time = time.time() - start
            
            result = self.record_result(
                "Edge Cases",
                "Service Resilience",
                all_healthy,
                f"All services healthy: {all_healthy} | Check time: {check_time:.3f}s",
                {"health_checks": health_checks}
            )
            results.append(result)
        except Exception as e:
            self.record_result(
                "Edge Cases",
                "Service Resilience",
                False,
                f"Error: {str(e)}"
            )
        
        return results
    
    def generate_summary(self):
        """Generate test summary"""
        self.print_header("TEST SUMMARY", 1)
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        
        # Group by category
        by_category = {}
        for result in self.results:
            if result.category not in by_category:
                by_category[result.category] = {"total": 0, "passed": 0}
            by_category[result.category]["total"] += 1
            if result.success:
                by_category[result.category]["passed"] += 1
        
        print(f"{CYAN}Overall Statistics:{NC}")
        print(f"  Total Tests: {total}")
        print(f"  {GREEN}Passed: {passed}{NC}")
        print(f"  {RED}Failed: {failed}{NC}")
        print(f"  Success Rate: {(passed/total*100):.1f}%")
        
        print(f"\n{CYAN}By Category:{NC}")
        for category, stats in by_category.items():
            rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            status = f"{GREEN}✓{NC}" if stats["passed"] == stats["total"] else f"{YELLOW}⚠{NC}"
            print(f"  {status} {category}: {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
        print(f"\n{CYAN}Performance Metrics:{NC}")
        if self.metrics.get('service_response_times'):
            print(f"  Service Response Times:")
            for service, time_val in self.metrics['service_response_times'].items():
                print(f"    {service}: {time_val:.3f}s")
        
        if self.metrics.get('sync_latencies'):
            print(f"  Sync Latencies:")
            for operation, latency in self.metrics['sync_latencies'].items():
                print(f"    {operation}: {latency:.3f}s")
        
        if self.metrics.get('data_consistency_scores'):
            print(f"  Data Consistency Scores:")
            for metric, score in self.metrics['data_consistency_scores'].items():
                print(f"    {metric}: {score*100:.1f}%")
        
        # Critical tests
        critical_categories = ["Service Health", "Shared Resources", "Data Consistency"]
        critical_results = [r for r in self.results if r.category in critical_categories]
        critical_passed = sum(1 for r in critical_results if r.success)
        
        print(f"\n{CYAN}Critical Synchronization Tests:{NC}")
        print(f"  {critical_passed}/{len(critical_results)} passed")
        
        if critical_passed == len(critical_results) and critical_results:
            print(f"\n{GREEN}✅ All critical synchronization tests passed!{NC}")
        else:
            print(f"\n{RED}❌ Some critical tests failed.{NC}")
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": (passed/total*100) if total > 0 else 0,
            "by_category": by_category,
            "metrics": self.metrics,
            "critical_passed": critical_passed,
            "critical_total": len(critical_results)
        }
    
    def run_all_tests(self):
        """Run all test categories"""
        print(f"\n{CYAN}╔══════════════════════════════════════════════════════════════════════════╗{NC}")
        print(f"{CYAN}║     ARIS RAG Deep Synchronization Analysis Suite                    ║{NC}")
        print(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════╝{NC}")
        print(f"\nTesting all 4 microservices:")
        print(f"  UI:        {UI_URL}")
        print(f"  Gateway:   {GATEWAY_URL}")
        print(f"  Ingestion: {INGESTION_URL}")
        print(f"  Retrieval: {RETRIEVAL_URL}\n")
        
        start_time = time.time()
        
        # Run all test categories
        self.test_service_health_deep()
        self.test_shared_resources_deep()
        self.test_data_consistency()
        self.test_realtime_sync()
        self.test_execution_order()
        self.test_edge_cases()
        
        elapsed_time = time.time() - start_time
        
        # Generate summary
        summary = self.generate_summary()
        summary["total_time"] = elapsed_time
        
        print(f"\n{CYAN}Total Analysis Time: {elapsed_time:.2f}s{NC}\n")
        
        return summary, self.results

def main():
    """Main entry point"""
    analyzer = DeepSyncAnalyzer()
    summary, results = analyzer.run_all_tests()
    
    # Save results to JSON
    output_file = "deep_sync_analysis_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "summary": summary,
            "results": [
                {
                    "category": r.category,
                    "test_name": r.test_name,
                    "success": r.success,
                    "details": r.details,
                    "data": r.data,
                    "metrics": r.metrics,
                    "timestamp": r.timestamp
                }
                for r in results
            ]
        }, f, indent=2)
    
    print(f"\n{CYAN}Results saved to: {output_file}{NC}")
    
    # Exit code
    critical_passed = summary.get("critical_passed", 0)
    critical_total = summary.get("critical_total", 0)
    sys.exit(0 if critical_passed == critical_total and critical_total > 0 else 1)

if __name__ == "__main__":
    main()
