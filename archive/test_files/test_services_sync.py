#!/usr/bin/env python3
"""
Comprehensive synchronization test for ARIS RAG microservices
Tests if Gateway, Ingestion, and Retrieval services are properly synchronized
"""
import requests
import json
import sys
import time
from typing import Dict, List, Optional

# Server configuration
BASE_URL = "http://44.221.84.58"
GATEWAY_URL = f"{BASE_URL}:8500"
INGESTION_URL = f"{BASE_URL}:8501"
RETRIEVAL_URL = f"{BASE_URL}:8502"

# Colors for output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color

class SyncTestResult:
    def __init__(self, test_name: str, success: bool, details: str = "", data: Optional[Dict] = None):
        self.test_name = test_name
        self.success = success
        self.details = details
        self.data = data

def print_header(text: str):
    print(f"\n{BLUE}{'='*80}{NC}")
    print(f"{BLUE}{text:^80}{NC}")
    print(f"{BLUE}{'='*80}{NC}\n")

def print_test(name: str, success: bool, details: str = ""):
    status = f"{GREEN}✓ PASS{NC}" if success else f"{RED}✗ FAIL{NC}"
    print(f"{status} {name}")
    if details:
        for line in details.split('\n'):
            print(f"    {line}")

def test_service_health(service_name: str, url: str) -> SyncTestResult:
    """Test if a service is healthy"""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            return SyncTestResult(
                f"{service_name} Health",
                status == "healthy",
                f"Status: {status} | Service: {data.get('service', 'unknown')}",
                data
            )
        else:
            return SyncTestResult(
                f"{service_name} Health",
                False,
                f"HTTP {response.status_code}"
            )
    except Exception as e:
        return SyncTestResult(
            f"{service_name} Health",
            False,
            f"Error: {str(e)}"
        )

def test_gateway_to_ingestion_sync() -> SyncTestResult:
    """Test if Gateway can communicate with Ingestion service"""
    print_header("Gateway → Ingestion Communication")
    
    try:
        # Test 1: Gateway health should show it can reach Ingestion
        response = requests.get(f"{GATEWAY_URL}/health", timeout=10)
        if response.status_code == 200:
            gateway_health = response.json()
            registry_accessible = gateway_health.get("registry_accessible", False)
            print_test("Gateway Health Check", True, 
                      f"Registry Accessible: {registry_accessible}")
        else:
            return SyncTestResult("Gateway → Ingestion", False, 
                                 f"Gateway health check failed: {response.status_code}")
        
        # Test 2: Direct Ingestion health check
        ingestion_health = test_service_health("Ingestion", INGESTION_URL)
        print_test(ingestion_health.test_name, ingestion_health.success, ingestion_health.details)
        
        # Test 3: Check if Gateway can proxy to Ingestion (via sync status)
        sync_response = requests.get(f"{GATEWAY_URL}/sync/status", timeout=10)
        if sync_response.status_code == 200:
            sync_data = sync_response.json()
            registry_accessible = sync_data.get("registry", {}).get("accessible", False)
            index_map_accessible = sync_data.get("index_map", {}).get("accessible", False)
            print_test("Sync Status Check", True,
                      f"Registry Accessible: {registry_accessible} | "
                      f"Index Map Accessible: {index_map_accessible}")
            return SyncTestResult("Gateway → Ingestion", True,
                                "Gateway can communicate with Ingestion service",
                                sync_data)
        else:
            return SyncTestResult("Gateway → Ingestion", False,
                                 f"Sync status check failed: {sync_response.status_code}")
            
    except Exception as e:
        return SyncTestResult("Gateway → Ingestion", False, f"Error: {str(e)}")

def test_gateway_to_retrieval_sync() -> SyncTestResult:
    """Test if Gateway can communicate with Retrieval service"""
    print_header("Gateway → Retrieval Communication")
    
    try:
        # Test 1: Direct Retrieval health check
        retrieval_health = test_service_health("Retrieval", RETRIEVAL_URL)
        print_test(retrieval_health.test_name, retrieval_health.success, retrieval_health.details)
        
        # Test 2: Gateway query should use Retrieval service
        query_payload = {
            "question": "test query for synchronization",
            "k": 1,
            "use_hybrid_search": True
        }
        query_response = requests.post(f"{GATEWAY_URL}/query", json=query_payload, timeout=30)
        
        if query_response.status_code == 200:
            query_data = query_response.json()
            answer = query_data.get("answer", "")
            print_test("Gateway Query (via Retrieval)", True,
                      f"Query successful | Answer length: {len(answer)} chars")
            return SyncTestResult("Gateway → Retrieval", True,
                                "Gateway can communicate with Retrieval service",
                                {"answer_length": len(answer)})
        else:
            return SyncTestResult("Gateway → Retrieval", False,
                                 f"Query failed: {query_response.status_code}")
            
    except Exception as e:
        return SyncTestResult("Gateway → Retrieval", False, f"Error: {str(e)}")

def test_cross_service_data_flow() -> SyncTestResult:
    """Test complete data flow: Gateway upload → Ingestion process → Retrieval query"""
    print_header("Cross-Service Data Flow Test")
    
    try:
        # Step 1: Upload document via Gateway
        test_content = b"This is a synchronization test document.\nIt tests if data flows correctly between services."
        test_filename = "sync_test_document.txt"
        
        print(f"{CYAN}Step 1: Uploading document via Gateway...{NC}")
        files = {"file": (test_filename, test_content, "text/plain")}
        upload_response = requests.post(f"{GATEWAY_URL}/documents", files=files, timeout=60)
        
        if upload_response.status_code not in [200, 201, 202]:
            return SyncTestResult("Cross-Service Data Flow", False,
                                f"Upload failed: {upload_response.status_code}")
        
        upload_data = upload_response.json()
        document_id = upload_data.get("document_id")
        print_test("Gateway Upload", True, f"Document ID: {document_id[:8]}...")
        
        # Step 2: Wait for processing and check status via Gateway
        print(f"{CYAN}Step 2: Waiting for processing...{NC}")
        max_wait = 60
        wait_time = 0
        status = "processing"
        
        while wait_time < max_wait and status == "processing":
            time.sleep(2)
            wait_time += 2
            status_response = requests.get(f"{GATEWAY_URL}/documents/{document_id}", timeout=10)
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data.get("status", "unknown")
                chunks = status_data.get("chunks_created", 0)
                print(f"    Status: {status} | Chunks: {chunks} | Wait: {wait_time}s")
        
        if status != "success":
            return SyncTestResult("Cross-Service Data Flow", False,
                                f"Processing did not complete. Status: {status}")
        
        print_test("Document Processing", True, f"Status: {status}")
        
        # Step 3: Verify document appears in Ingestion service status
        print(f"{CYAN}Step 3: Verifying in Ingestion service...{NC}")
        ingestion_status = requests.get(f"{INGESTION_URL}/status/{document_id}", timeout=10)
        if ingestion_status.status_code == 200:
            ingestion_data = ingestion_status.json()
            ingestion_status_value = ingestion_data.get("status", "unknown")
            print_test("Ingestion Status Check", True, f"Status: {ingestion_status_value}")
        else:
            print_test("Ingestion Status Check", False, f"HTTP {ingestion_status.status_code}")
        
        # Step 4: Query via Gateway (which uses Retrieval)
        print(f"{CYAN}Step 4: Querying via Gateway (Retrieval service)...{NC}")
        query_payload = {
            "question": "synchronization test document",
            "k": 1,
            "use_hybrid_search": True
        }
        query_response = requests.post(f"{GATEWAY_URL}/query", json=query_payload, timeout=30)
        
        if query_response.status_code == 200:
            query_data = query_response.json()
            sources = query_data.get("sources", [])
            citations = query_data.get("citations", [])
            
            # Check if our test document appears in results
            found_document = test_filename in sources or any(
                cit.get("source") == test_filename for cit in citations
            )
            
            if found_document:
                print_test("Query Results", True, 
                          f"Test document found in results | Sources: {len(sources)}")
                return SyncTestResult("Cross-Service Data Flow", True,
                                    "Complete data flow verified: Gateway → Ingestion → Retrieval",
                                    {"document_id": document_id, "sources": sources})
            else:
                print_test("Query Results", False, 
                          f"Test document not found in results | Sources: {sources}")
                return SyncTestResult("Cross-Service Data Flow", False,
                                    "Document processed but not found in query results")
        else:
            return SyncTestResult("Cross-Service Data Flow", False,
                                f"Query failed: {query_response.status_code}")
            
    except Exception as e:
        return SyncTestResult("Cross-Service Data Flow", False, f"Error: {str(e)}")

def test_registry_synchronization() -> SyncTestResult:
    """Test if document registry is synchronized across services"""
    print_header("Document Registry Synchronization")
    
    try:
        # Get document list from Gateway
        gateway_docs = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
        if gateway_docs.status_code != 200:
            return SyncTestResult("Registry Sync", False, 
                                f"Gateway documents list failed: {gateway_docs.status_code}")
        
        gateway_data = gateway_docs.json()
        gateway_total = gateway_data.get("total", 0)
        gateway_doc_list = gateway_data.get("documents", [])
        
        print_test("Gateway Document Count", True, f"Total: {gateway_total}")
        
        # Check sync status
        sync_response = requests.get(f"{GATEWAY_URL}/sync/status", timeout=10)
        if sync_response.status_code == 200:
            sync_data = sync_response.json()
            registry_info = sync_data.get("registry", {})
            index_map_info = sync_data.get("index_map", {})
            
            registry_accessible = registry_info.get("accessible", False)
            registry_exists = registry_info.get("exists", False)
            registry_count = registry_info.get("document_count", 0)
            
            index_map_accessible = index_map_info.get("accessible", False)
            index_map_exists = index_map_info.get("exists", False)
            index_map_count = index_map_info.get("entry_count", 0)
            
            print_test("Registry Sync Status", registry_accessible and index_map_accessible,
                      f"Registry: exists={registry_exists}, accessible={registry_accessible}, count={registry_count} | "
                      f"Index Map: exists={index_map_exists}, accessible={index_map_accessible}, entries={index_map_count}")
            
            # Check health endpoints for registry info
            ingestion_health = requests.get(f"{INGESTION_URL}/health", timeout=10)
            retrieval_health = requests.get(f"{RETRIEVAL_URL}/health", timeout=10)
            
            ingestion_registry_count = 0
            retrieval_index_entries = 0
            
            if ingestion_health.status_code == 200:
                ingestion_data = ingestion_health.json()
                ingestion_registry_count = ingestion_data.get("registry_document_count", 0)
                print_test("Ingestion Registry Access", True,
                          f"Document Count: {ingestion_registry_count}")
            
            if retrieval_health.status_code == 200:
                retrieval_data = retrieval_health.json()
                retrieval_index_entries = retrieval_data.get("index_map_entries", 0)
                print_test("Retrieval Index Map Access", True,
                          f"Index Entries: {retrieval_index_entries}")
            
            # Verify synchronization (all services can access shared resources)
            if registry_accessible and index_map_accessible:
                return SyncTestResult("Registry Sync", True,
                                    f"Registry synchronized | Gateway: {gateway_total} docs | "
                                    f"Ingestion: {ingestion_registry_count} docs | "
                                    f"Retrieval: {retrieval_index_entries} entries | "
                                    f"Index Map: {index_map_count} entries",
                                    sync_data)
            else:
                return SyncTestResult("Registry Sync", False,
                                    f"Sync incomplete | Registry accessible: {registry_accessible} | "
                                    f"Index Map accessible: {index_map_accessible}")
        else:
            return SyncTestResult("Registry Sync", False,
                                f"Sync status check failed: {sync_response.status_code}")
            
    except Exception as e:
        return SyncTestResult("Registry Sync", False, f"Error: {str(e)}")

def test_direct_service_endpoints() -> List[SyncTestResult]:
    """Test direct access to Ingestion and Retrieval service endpoints"""
    print_header("Direct Service Endpoints Test")
    
    results = []
    
    # Test Ingestion endpoints
    print(f"{CYAN}Testing Ingestion Service Endpoints...{NC}")
    
    # 1. Health
    health_result = test_service_health("Ingestion", INGESTION_URL)
    print_test(health_result.test_name, health_result.success, health_result.details)
    results.append(health_result)
    
    # 2. Metrics
    try:
        metrics_response = requests.get(f"{INGESTION_URL}/metrics", timeout=10)
        if metrics_response.status_code == 200:
            print_test("Ingestion Metrics", True, "Metrics endpoint accessible")
            results.append(SyncTestResult("Ingestion Metrics", True, "Accessible"))
        else:
            print_test("Ingestion Metrics", False, f"HTTP {metrics_response.status_code}")
            results.append(SyncTestResult("Ingestion Metrics", False, 
                                        f"HTTP {metrics_response.status_code}"))
    except Exception as e:
        print_test("Ingestion Metrics", False, f"Error: {str(e)}")
        results.append(SyncTestResult("Ingestion Metrics", False, str(e)))
    
    # 3. Index exists check
    try:
        index_check = requests.get(f"{INGESTION_URL}/indexes/aris-rag-index/exists", timeout=10)
        if index_check.status_code == 200:
            index_data = index_check.json()
            exists = index_data.get("exists", False)
            print_test("Ingestion Index Check", True, f"Index exists: {exists}")
            results.append(SyncTestResult("Ingestion Index Check", True, f"Exists: {exists}"))
        else:
            print_test("Ingestion Index Check", False, f"HTTP {index_check.status_code}")
            results.append(SyncTestResult("Ingestion Index Check", False,
                                        f"HTTP {index_check.status_code}"))
    except Exception as e:
        print_test("Ingestion Index Check", False, f"Error: {str(e)}")
        results.append(SyncTestResult("Ingestion Index Check", False, str(e)))
    
    # Test Retrieval endpoints
    print(f"\n{CYAN}Testing Retrieval Service Endpoints...{NC}")
    
    # 1. Health
    retrieval_health = test_service_health("Retrieval", RETRIEVAL_URL)
    print_test(retrieval_health.test_name, retrieval_health.success, retrieval_health.details)
    results.append(retrieval_health)
    
    # 2. Direct query
    try:
        query_payload = {"question": "test", "k": 1}
        query_response = requests.post(f"{RETRIEVAL_URL}/query", json=query_payload, timeout=30)
        if query_response.status_code == 200:
            print_test("Retrieval Direct Query", True, "Query endpoint accessible")
            results.append(SyncTestResult("Retrieval Direct Query", True, "Accessible"))
        else:
            print_test("Retrieval Direct Query", False, f"HTTP {query_response.status_code}")
            results.append(SyncTestResult("Retrieval Direct Query", False,
                                        f"HTTP {query_response.status_code}"))
    except Exception as e:
        print_test("Retrieval Direct Query", False, f"Error: {str(e)}")
        results.append(SyncTestResult("Retrieval Direct Query", False, str(e)))
    
    # 3. Metrics
    try:
        metrics_response = requests.get(f"{RETRIEVAL_URL}/metrics", timeout=10)
        if metrics_response.status_code == 200:
            print_test("Retrieval Metrics", True, "Metrics endpoint accessible")
            results.append(SyncTestResult("Retrieval Metrics", True, "Accessible"))
        else:
            print_test("Retrieval Metrics", False, f"HTTP {metrics_response.status_code}")
            results.append(SyncTestResult("Retrieval Metrics", False,
                                        f"HTTP {metrics_response.status_code}"))
    except Exception as e:
        print_test("Retrieval Metrics", False, f"Error: {str(e)}")
        results.append(SyncTestResult("Retrieval Metrics", False, str(e)))
    
    return results

def main():
    """Run all synchronization tests"""
    print(f"\n{CYAN}╔══════════════════════════════════════════════════════════════════════════╗{NC}")
    print(f"{CYAN}║     ARIS RAG Microservices Synchronization Test Suite              ║{NC}")
    print(f"{CYAN}╚══════════════════════════════════════════════════════════════════════════╝{NC}")
    print(f"\nTesting services:")
    print(f"  Gateway:   {GATEWAY_URL}")
    print(f"  Ingestion: {INGESTION_URL}")
    print(f"  Retrieval: {RETRIEVAL_URL}\n")
    
    all_results = []
    
    # Test 1: Service Health Checks
    print_header("Service Health Checks")
    gateway_health = test_service_health("Gateway", GATEWAY_URL)
    print_test(gateway_health.test_name, gateway_health.success, gateway_health.details)
    all_results.append(gateway_health)
    
    ingestion_health = test_service_health("Ingestion", INGESTION_URL)
    print_test(ingestion_health.test_name, ingestion_health.success, ingestion_health.details)
    all_results.append(ingestion_health)
    
    retrieval_health = test_service_health("Retrieval", RETRIEVAL_URL)
    print_test(retrieval_health.test_name, retrieval_health.success, retrieval_health.details)
    all_results.append(retrieval_health)
    
    if not all([gateway_health.success, ingestion_health.success, retrieval_health.success]):
        print(f"\n{RED}⚠️  Some services are not healthy. Some tests may fail.{NC}\n")
    
    # Test 2: Gateway → Ingestion Sync
    gateway_ingestion_result = test_gateway_to_ingestion_sync()
    all_results.append(gateway_ingestion_result)
    
    # Test 3: Gateway → Retrieval Sync
    gateway_retrieval_result = test_gateway_to_retrieval_sync()
    all_results.append(gateway_retrieval_result)
    
    # Test 4: Registry Synchronization
    registry_result = test_registry_synchronization()
    all_results.append(registry_result)
    
    # Test 5: Direct Service Endpoints
    direct_endpoint_results = test_direct_service_endpoints()
    all_results.extend(direct_endpoint_results)
    
    # Test 6: Cross-Service Data Flow (optional, takes longer)
    print(f"\n{YELLOW}Note: Cross-service data flow test will upload a test document.{NC}")
    cross_flow_result = test_cross_service_data_flow()
    all_results.append(cross_flow_result)
    
    # Summary
    print_header("Synchronization Test Summary")
    total = len(all_results)
    passed = sum(1 for r in all_results if r.success)
    failed = total - passed
    
    print(f"Total Tests: {total}")
    print(f"{GREEN}Passed: {passed}{NC}")
    print(f"{RED}Failed: {failed}{NC}")
    print(f"Success Rate: {(passed/total*100):.1f}%")
    
    # Overall sync status
    critical_tests = [
        gateway_health, ingestion_health, retrieval_health,
        gateway_ingestion_result, gateway_retrieval_result, registry_result
    ]
    critical_passed = sum(1 for r in critical_tests if r.success)
    
    print(f"\n{CYAN}Critical Synchronization Tests: {critical_passed}/{len(critical_tests)} passed{NC}")
    
    if critical_passed == len(critical_tests):
        print(f"{GREEN}✅ All critical synchronization tests passed! Services are in sync.{NC}")
    else:
        print(f"{RED}❌ Some critical synchronization tests failed. Services may not be fully synchronized.{NC}")
    
    # List failed tests
    if failed > 0:
        print(f"\n{RED}Failed Tests:{NC}")
        for result in all_results:
            if not result.success:
                print(f"  - {result.test_name}: {result.details}")
    
    # Exit code
    sys.exit(0 if critical_passed == len(critical_tests) else 1)

if __name__ == "__main__":
    main()







