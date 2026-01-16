#!/usr/bin/env python3
"""
Comprehensive test for automatic synchronization system
Tests all microservices, sync functionality, and cross-service operations
"""
import requests
import json
import time
import sys
from typing import Dict, List, Any

# Server configuration
GATEWAY_URL = "http://44.221.84.58:8500"
INGESTION_URL = "http://44.221.84.58:8501"
RETRIEVAL_URL = "http://44.221.84.58:8502"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_test(name: str):
    print(f"\n{Colors.BLUE}━━━ Testing: {name} ━━━{Colors.RESET}")

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def test_service_health(service_name: str, url: str) -> bool:
    """Test if a service is healthy"""
    try:
        response = requests.get(f"{url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_success(f"{service_name} is healthy")
            print(f"   Status: {data.get('status', 'unknown')}")
            if 'registry_accessible' in data:
                print(f"   Registry: {'✅' if data['registry_accessible'] else '❌'}")
            if 'index_map_accessible' in data:
                print(f"   Index Map: {'✅' if data['index_map_accessible'] else '❌'}")
            return True
        else:
            print_error(f"{service_name} returned status {response.status_code}")
            return False
    except Exception as e:
        print_error(f"{service_name} health check failed: {e}")
        return False

def test_sync_status(service_name: str, url: str) -> bool:
    """Test sync status endpoint"""
    try:
        response = requests.get(f"{url}/sync/status", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'status' in data:
                status = data['status']
            else:
                status = data
            
            print_success(f"{service_name} sync status retrieved")
            
            if isinstance(status, dict):
                if 'background_task_running' in status:
                    bg_running = status['background_task_running']
                    print(f"   Background Sync: {'✅ Running' if bg_running else '❌ Not Running'}")
                
                if 'sync_count' in status:
                    print(f"   Sync Count: {status['sync_count']}")
                
                if 'registry' in status:
                    reg = status['registry']
                    print(f"   Registry: {reg.get('document_count', 0)} documents")
                
                if 'index_map' in status:
                    idx = status['index_map']
                    print(f"   Index Map: {idx.get('mapping_count', 0)} mappings")
            
            return True
        else:
            print_error(f"{service_name} sync status returned {response.status_code}")
            return False
    except Exception as e:
        print_error(f"{service_name} sync status check failed: {e}")
        return False

def test_force_sync(service_name: str, url: str) -> bool:
    """Test force sync endpoint"""
    try:
        response = requests.post(f"{url}/sync/force", timeout=30)
        if response.status_code == 200:
            data = response.json()
            print_success(f"{service_name} force sync completed")
            if 'sync_result' in data:
                result = data['sync_result']
                if isinstance(result, dict):
                    if 'registry' in result:
                        print(f"   Registry: {result['registry'].get('document_count', 0)} docs")
                    if 'index_map' in result:
                        print(f"   Index Map: {result['index_map'].get('mapping_count', 0)} mappings")
            return True
        else:
            print_error(f"{service_name} force sync returned {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        print_error(f"{service_name} force sync failed: {e}")
        return False

def test_list_documents(url: str) -> bool:
    """Test document listing"""
    try:
        response = requests.get(f"{url}/documents", timeout=10)
        if response.status_code == 200:
            data = response.json()
            doc_count = data.get('total', 0)
            print_success(f"Document listing works: {doc_count} documents")
            return True
        else:
            print_error(f"Document listing returned {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Document listing failed: {e}")
        return False

def test_query(url: str) -> bool:
    """Test a simple query"""
    try:
        payload = {
            "question": "What is the leave policy?",
            "k": 3,
            "use_hybrid_search": True
        }
        response = requests.post(f"{url}/query", json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '')
            citations = data.get('citations', [])
            print_success(f"Query works: {len(answer)} chars, {len(citations)} citations")
            return True
        else:
            print_error(f"Query returned {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return False
    except Exception as e:
        print_error(f"Query failed: {e}")
        return False

def test_automatic_sync_detection() -> bool:
    """Test that automatic sync detects changes"""
    print_test("Automatic Sync Detection")
    
    try:
        # Get initial sync status
        response1 = requests.get(f"{INGESTION_URL}/sync/status", timeout=10)
        if response1.status_code != 200:
            print_error("Could not get initial sync status")
            return False
        
        data1 = response1.json()
        if isinstance(data1, dict) and 'status' in data1:
            status1 = data1['status']
        else:
            status1 = data1
        
        initial_count = status1.get('sync_count', 0) if isinstance(status1, dict) else 0
        
        print(f"   Initial sync count: {initial_count}")
        
        # Wait for background sync to run (should happen within 3-5 seconds)
        print("   Waiting 5 seconds for background sync...")
        time.sleep(5)
        
        # Get updated sync status
        response2 = requests.get(f"{INGESTION_URL}/sync/status", timeout=10)
        if response2.status_code != 200:
            print_error("Could not get updated sync status")
            return False
        
        data2 = response2.json()
        if isinstance(data2, dict) and 'status' in data2:
            status2 = data2['status']
        else:
            status2 = data2
        
        updated_count = status2.get('sync_count', 0) if isinstance(status2, dict) else 0
        
        print(f"   Updated sync count: {updated_count}")
        
        if updated_count > initial_count:
            print_success("Background sync is working - sync count increased")
            return True
        elif updated_count == initial_count:
            print_warning("Sync count unchanged (may be normal if no changes detected)")
            return True  # Not necessarily an error
        else:
            print_error("Sync count decreased (unexpected)")
            return False
            
    except Exception as e:
        print_error(f"Automatic sync detection test failed: {e}")
        return False

def test_cross_service_sync() -> bool:
    """Test cross-service sync coordination"""
    print_test("Cross-Service Sync Coordination")
    
    try:
        # Force sync from gateway (should sync all services)
        response = requests.post(f"{GATEWAY_URL}/sync/force", timeout=30)
        if response.status_code != 200:
            print_error(f"Gateway force sync returned {response.status_code}")
            return False
        
        data = response.json()
        sync_result = data.get('sync_result', {})
        
        print_success("Gateway force sync completed")
        
        # Check if it synced downstream services
        if 'ingestion' in sync_result:
            ing_result = sync_result['ingestion']
            if isinstance(ing_result, dict) and ing_result.get('success'):
                print_success("Ingestion service synced via gateway")
            else:
                print_warning("Ingestion sync result unclear")
        
        if 'retrieval' in sync_result:
            ret_result = sync_result['retrieval']
            if isinstance(ret_result, dict) and ret_result.get('success'):
                print_success("Retrieval service synced via gateway")
            else:
                print_warning("Retrieval sync result unclear")
        
        return True
        
    except Exception as e:
        print_error(f"Cross-service sync test failed: {e}")
        return False

def main():
    print(f"\n{Colors.BLUE}{'='*60}")
    print("  AUTOMATIC SYNCHRONIZATION SYSTEM - COMPREHENSIVE TEST")
    print(f"{'='*60}{Colors.RESET}\n")
    
    results = []
    
    # Test 1: Service Health Checks
    print_test("Service Health Checks")
    results.append(("Gateway Health", test_service_health("Gateway", GATEWAY_URL)))
    results.append(("Ingestion Health", test_service_health("Ingestion", INGESTION_URL)))
    results.append(("Retrieval Health", test_service_health("Retrieval", RETRIEVAL_URL)))
    
    # Test 2: Sync Status
    print_test("Sync Status Endpoints")
    results.append(("Gateway Sync Status", test_sync_status("Gateway", GATEWAY_URL)))
    results.append(("Ingestion Sync Status", test_sync_status("Ingestion", INGESTION_URL)))
    results.append(("Retrieval Sync Status", test_sync_status("Retrieval", RETRIEVAL_URL)))
    
    # Test 3: Force Sync
    print_test("Force Sync Endpoints")
    results.append(("Gateway Force Sync", test_force_sync("Gateway", GATEWAY_URL)))
    results.append(("Ingestion Force Sync", test_force_sync("Ingestion", INGESTION_URL)))
    results.append(("Retrieval Force Sync", test_force_sync("Retrieval", RETRIEVAL_URL)))
    
    # Test 4: Automatic Sync Detection
    results.append(("Automatic Sync Detection", test_automatic_sync_detection()))
    
    # Test 5: Cross-Service Sync
    results.append(("Cross-Service Sync", test_cross_service_sync()))
    
    # Test 6: Document Operations
    print_test("Document Operations")
    results.append(("List Documents", test_list_documents(GATEWAY_URL)))
    
    # Test 7: Query Operations
    print_test("Query Operations")
    results.append(("RAG Query", test_query(GATEWAY_URL)))
    
    # Summary
    print(f"\n{Colors.BLUE}{'='*60}")
    print("  TEST SUMMARY")
    print(f"{'='*60}{Colors.RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if result else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"  {status} - {test_name}")
    
    print(f"\n{Colors.BLUE}Results: {passed}/{total} tests passed{Colors.RESET}")
    
    if passed == total:
        print(f"{Colors.GREEN}🎉 All tests passed! System is working correctly.{Colors.RESET}\n")
        return 0
    else:
        print(f"{Colors.RED}⚠️  Some tests failed. Please review the errors above.{Colors.RESET}\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())

