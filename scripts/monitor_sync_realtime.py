#!/usr/bin/env python3
"""
Real-time Synchronization Monitor for ARIS RAG Microservices
Continuously monitors synchronization status and detects issues
"""
import requests
import json
import time
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from shared.config.settings import ARISConfig

# Server configuration
BASE_URL = "http://44.221.84.58"
GATEWAY_URL = f"{BASE_URL}:8500"
INGESTION_URL = f"{BASE_URL}:8501"
RETRIEVAL_URL = f"{BASE_URL}:8502"

class SyncEvent:
    def __init__(self, timestamp: str, event_type: str, service: str, 
                 status: str, details: Dict = None):
        self.timestamp = timestamp
        self.event_type = event_type
        self.service = service
        self.status = status
        self.details = details or {}

class RealtimeSyncMonitor:
    def __init__(self, interval: int = 10, duration: int = 300):
        self.interval = interval  # Check interval in seconds
        self.duration = duration  # Total monitoring duration in seconds
        self.events: List[SyncEvent] = []
        self.baseline_state: Dict = {}
        self.alerts: List[Dict] = []
    
    def check_service_health(self, service_name: str, url: str) -> Dict:
        """Check health of a service"""
        try:
            start = time.time()
            response = requests.get(f"{url}/health", timeout=5)
            response_time = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy",
                    "response_time": response_time,
                    "data": data,
                    "accessible": True
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time": response_time,
                    "http_code": response.status_code,
                    "accessible": False
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "accessible": False
            }
    
    def check_sync_status(self) -> Dict:
        """Check synchronization status from Gateway"""
        try:
            response = requests.get(f"{GATEWAY_URL}/sync/status", timeout=10)
            if response.status_code == 200:
                return {
                    "status": "success",
                    "data": response.json()
                }
            else:
                return {
                    "status": "error",
                    "http_code": response.status_code
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def check_shared_resources(self) -> Dict:
        """Check shared resource accessibility"""
        resources = {}
        
        # Check registry file
        registry_path = ARISConfig.DOCUMENT_REGISTRY_PATH
        resources["registry"] = {
            "exists": os.path.exists(registry_path),
            "path": registry_path,
            "readable": os.access(registry_path, os.R_OK) if os.path.exists(registry_path) else False,
            "writable": os.access(registry_path, os.W_OK) if os.path.exists(registry_path) else False
        }
        
        # Check index map file
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        resources["index_map"] = {
            "exists": os.path.exists(index_map_path),
            "path": index_map_path,
            "readable": os.access(index_map_path, os.R_OK) if os.path.exists(index_map_path) else False,
            "writable": os.access(index_map_path, os.W_OK) if os.path.exists(index_map_path) else False
        }
        
        return resources
    
    def detect_anomalies(self, current_state: Dict, baseline: Dict) -> List[Dict]:
        """Detect anomalies compared to baseline"""
        anomalies = []
        
        # Check service health changes
        for service in ["Gateway", "Ingestion", "Retrieval"]:
            current_health = current_state.get("services", {}).get(service, {})
            baseline_health = baseline.get("services", {}).get(service, {})
            
            if baseline_health.get("status") == "healthy" and current_health.get("status") != "healthy":
                anomalies.append({
                    "type": "service_degradation",
                    "service": service,
                    "severity": "high",
                    "message": f"{service} service became unhealthy"
                })
        
        # Check document count changes (significant drops)
        current_docs = current_state.get("document_count", 0)
        baseline_docs = baseline.get("document_count", 0)
        
        if baseline_docs > 0 and current_docs < baseline_docs * 0.9:
            anomalies.append({
                "type": "data_loss",
                "severity": "critical",
                "message": f"Document count dropped from {baseline_docs} to {current_docs}"
            })
        
        # Check sync status changes
        current_sync = current_state.get("sync_status", {})
        baseline_sync = baseline.get("sync_status", {})
        
        if baseline_sync.get("registry", {}).get("accessible") and \
           not current_sync.get("registry", {}).get("accessible"):
            anomalies.append({
                "type": "sync_failure",
                "severity": "high",
                "message": "Registry became inaccessible"
            })
        
        return anomalies
    
    def record_event(self, event_type: str, service: str, status: str, details: Dict = None):
        """Record a synchronization event"""
        event = SyncEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            service=service,
            status=status,
            details=details or {}
        )
        self.events.append(event)
    
    def monitor_cycle(self) -> Dict:
        """Perform one monitoring cycle"""
        cycle_data = {
            "timestamp": datetime.now().isoformat(),
            "services": {},
            "sync_status": {},
            "shared_resources": {},
            "document_count": 0
        }
        
        # Check all services
        services = [
            ("Gateway", GATEWAY_URL),
            ("Ingestion", INGESTION_URL),
            ("Retrieval", RETRIEVAL_URL)
        ]
        
        for service_name, service_url in services:
            health = self.check_service_health(service_name, service_url)
            cycle_data["services"][service_name] = health
            
            if health.get("accessible"):
                self.record_event("health_check", service_name, "healthy", health)
            else:
                self.record_event("health_check", service_name, "unhealthy", health)
        
        # Check sync status
        sync_status = self.check_sync_status()
        if sync_status.get("status") == "success":
            sync_data = sync_status.get("data", {})
            cycle_data["sync_status"] = sync_data
            
            # Extract document count
            registry_info = sync_data.get("registry", {})
            cycle_data["document_count"] = registry_info.get("document_count", 0)
        
        # Check shared resources
        resources = self.check_shared_resources()
        cycle_data["shared_resources"] = resources
        
        return cycle_data
    
    def run_monitoring(self):
        """Run continuous monitoring"""
        print("\n" + "="*80)
        print("Real-time Synchronization Monitor")
        print("="*80)
        print(f"Monitoring interval: {self.interval}s")
        print(f"Duration: {self.duration}s ({self.duration/60:.1f} minutes)")
        print("Press Ctrl+C to stop early\n")
        
        start_time = time.time()
        cycle_count = 0
        
        # Establish baseline
        print("Establishing baseline state...")
        self.baseline_state = self.monitor_cycle()
        print("? Baseline established\n")
        
        try:
            while time.time() - start_time < self.duration:
                cycle_count += 1
                elapsed = time.time() - start_time
                
                print(f"[Cycle {cycle_count}] Elapsed: {elapsed:.0f}s")
                
                # Perform monitoring cycle
                current_state = self.monitor_cycle()
                
                # Detect anomalies
                if self.baseline_state:
                    anomalies = self.detect_anomalies(current_state, self.baseline_state)
                    if anomalies:
                        for anomaly in anomalies:
                            severity_icon = "??" if anomaly["severity"] == "critical" else "??"
                            print(f"  {severity_icon} ALERT: {anomaly['message']}")
                            self.alerts.append({
                                "timestamp": current_state["timestamp"],
                                **anomaly
                            })
                
                # Print status summary
                healthy_services = sum(
                    1 for s in current_state["services"].values() 
                    if s.get("status") == "healthy"
                )
                print(f"  Services healthy: {healthy_services}/3")
                print(f"  Documents: {current_state.get('document_count', 0)}")
                
                registry_accessible = current_state.get("sync_status", {}).get("registry", {}).get("accessible", False)
                index_map_accessible = current_state.get("sync_status", {}).get("index_map", {}).get("accessible", False)
                print(f"  Registry: {'?' if registry_accessible else '?'} | Index Map: {'?' if index_map_accessible else '?'}")
                print()
                
                # Wait for next cycle
                if time.time() - start_time < self.duration:
                    time.sleep(self.interval)
        
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")
        
        # Generate summary
        self.generate_summary(cycle_count)
    
    def generate_summary(self, cycle_count: int):
        """Generate monitoring summary"""
        print("\n" + "="*80)
        print("Monitoring Summary")
        print("="*80 + "\n")
        
        print(f"Total cycles: {cycle_count}")
        print(f"Total events: {len(self.events)}")
        print(f"Total alerts: {len(self.alerts)}\n")
        
        if self.alerts:
            print("Alerts:")
            for alert in self.alerts:
                severity_icon = "??" if alert["severity"] == "critical" else "??"
                print(f"  {severity_icon} [{alert['timestamp']}] {alert['message']}")
        else:
            print("? No alerts during monitoring period\n")
        
        # Event timeline
        if self.events:
            print("Event Timeline (last 10 events):")
            for event in self.events[-10:]:
                status_icon = "?" if event.status == "healthy" else "?"
                print(f"  {status_icon} [{event.timestamp}] {event.service}: {event.event_type}")
        
        # Save results
        output_file = "sync_monitor_results.json"
        with open(output_file, 'w') as f:
            json.dump({
                "cycles": cycle_count,
                "events": [
                    {
                        "timestamp": e.timestamp,
                        "event_type": e.event_type,
                        "service": e.service,
                        "status": e.status,
                        "details": e.details
                    }
                    for e in self.events
                ],
                "alerts": self.alerts,
                "baseline": self.baseline_state
            }, f, indent=2)
        
        print(f"\nResults saved to: {output_file}\n")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Real-time synchronization monitor")
    parser.add_argument("--interval", type=int, default=10, help="Check interval in seconds (default: 10)")
    parser.add_argument("--duration", type=int, default=300, help="Monitoring duration in seconds (default: 300)")
    
    args = parser.parse_args()
    
    monitor = RealtimeSyncMonitor(interval=args.interval, duration=args.duration)
    monitor.run_monitoring()

if __name__ == "__main__":
    main()
