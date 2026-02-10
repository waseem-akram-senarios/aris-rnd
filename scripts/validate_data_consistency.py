#!/usr/bin/env python3
"""
Data Consistency Validator for ARIS RAG Microservices
Validates data consistency across all services
"""
import requests
import json
import sys
import os
from typing import Dict, List, Optional, Set, Tuple
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

class ConsistencyIssue:
    def __init__(self, severity: str, category: str, description: str, details: Dict = None):
        self.severity = severity  # "error", "warning", "info"
        self.category = category
        self.description = description
        self.details = details or {}

class DataConsistencyValidator:
    def __init__(self):
        self.issues: List[ConsistencyIssue] = []
        self.metrics: Dict = {}
    
    def add_issue(self, severity: str, category: str, description: str, details: Dict = None):
        """Add a consistency issue"""
        issue = ConsistencyIssue(severity, category, description, details)
        self.issues.append(issue)
    
    def validate_document_counts(self) -> Dict:
        """Validate document counts across services"""
        print("\n" + "="*80)
        print("Document Count Consistency Validation")
        print("="*80 + "\n")
        
        counts = {}
        
        # Get from Gateway
        try:
            response = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
            if response.status_code == 200:
                data = response.json()
                counts["Gateway"] = data.get("total", 0)
                counts["Gateway_documents"] = data.get("documents", [])
        except Exception as e:
            self.add_issue("error", "Document Count", f"Failed to get Gateway count: {str(e)}")
        
        # Get from Ingestion health
        try:
            response = requests.get(f"{INGESTION_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                counts["Ingestion"] = data.get("registry_document_count", 0)
        except Exception as e:
            self.add_issue("error", "Document Count", f"Failed to get Ingestion count: {str(e)}")
        
        # Get from Retrieval health
        try:
            response = requests.get(f"{RETRIEVAL_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                counts["Retrieval"] = data.get("index_map_entries", 0)
        except Exception as e:
            self.add_issue("error", "Document Count", f"Failed to get Retrieval count: {str(e)}")
        
        # Compare counts
        if "Gateway" in counts and "Ingestion" in counts:
            gateway_count = counts["Gateway"]
            ingestion_count = counts["Ingestion"]
            difference = abs(gateway_count - ingestion_count)
            
            print(f"Gateway document count: {gateway_count}")
            print(f"Ingestion registry count: {ingestion_count}")
            print(f"Difference: {difference}")
            
            if difference > 1:
                self.add_issue(
                    "warning" if difference <= 5 else "error",
                    "Document Count",
                    f"Document count mismatch: Gateway={gateway_count}, Ingestion={ingestion_count}",
                    {"gateway": gateway_count, "ingestion": ingestion_count, "difference": difference}
                )
            else:
                print("✓ Document counts are consistent\n")
        
        self.metrics["document_counts"] = counts
        return counts
    
    def validate_document_metadata(self) -> Dict:
        """Validate document metadata consistency"""
        print("\n" + "="*80)
        print("Document Metadata Consistency Validation")
        print("="*80 + "\n")
        
        # Get documents from Gateway
        try:
            response = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
            if response.status_code != 200:
                self.add_issue("error", "Metadata", "Failed to get documents from Gateway")
                return {}
            
            data = response.json()
            documents = data.get("documents", [])
            
            if not documents:
                print("No documents found to validate\n")
                return {}
            
            # Sample documents for validation
            sample_size = min(10, len(documents))
            sample_docs = documents[:sample_size]
            
            print(f"Validating {sample_size} sample documents...\n")
            
            validated = 0
            inconsistencies = []
            
            for doc in sample_docs:
                doc_id = doc.get("document_id")
                if not doc_id:
                    continue
                
                # Get document details from Gateway
                try:
                    doc_response = requests.get(f"{GATEWAY_URL}/documents/{doc_id}", timeout=10)
                    if doc_response.status_code == 200:
                        doc_data = doc_response.json()
                        
                        # Check required fields
                        required_fields = ["document_id", "document_name", "status"]
                        missing_fields = [f for f in required_fields if f not in doc_data]
                        
                        if missing_fields:
                            inconsistencies.append({
                                "document_id": doc_id,
                                "issue": f"Missing fields: {missing_fields}"
                            })
                        else:
                            validated += 1
                except Exception as e:
                    inconsistencies.append({
                        "document_id": doc_id,
                        "issue": f"Error retrieving: {str(e)}"
                    })
            
            consistency_score = validated / sample_size if sample_size > 0 else 0
            
            print(f"Validated: {validated}/{sample_size} ({consistency_score*100:.1f}%)")
            
            if inconsistencies:
                print(f"\n⚠️  Found {len(inconsistencies)} inconsistencies:")
                for inc in inconsistencies[:5]:  # Show first 5
                    print(f"  - {inc['document_id'][:8]}...: {inc['issue']}")
            
            if consistency_score < 0.9:
                self.add_issue(
                    "warning" if consistency_score >= 0.7 else "error",
                    "Metadata",
                    f"Metadata consistency below threshold: {consistency_score*100:.1f}%",
                    {"score": consistency_score, "validated": validated, "total": sample_size}
                )
            else:
                print("✓ Metadata consistency is good\n")
            
            self.metrics["metadata_consistency"] = {
                "score": consistency_score,
                "validated": validated,
                "total": sample_size,
                "inconsistencies": len(inconsistencies)
            }
            
            return {
                "consistency_score": consistency_score,
                "validated": validated,
                "total": sample_size,
                "inconsistencies": inconsistencies
            }
            
        except Exception as e:
            self.add_issue("error", "Metadata", f"Metadata validation failed: {str(e)}")
            return {}
    
    def validate_index_map_consistency(self) -> Dict:
        """Validate index map consistency"""
        print("\n" + "="*80)
        print("Index Map Consistency Validation")
        print("="*80 + "\n")
        
        # Check if index map file exists locally
        index_map_path = os.path.join(ARISConfig.VECTORSTORE_PATH, "document_index_map.json")
        
        local_index_map = {}
        if os.path.exists(index_map_path):
            try:
                with open(index_map_path, 'r') as f:
                    local_index_map = json.load(f)
                print(f"✓ Local index map found: {len(local_index_map)} entries")
            except Exception as e:
                self.add_issue("error", "Index Map", f"Failed to read local index map: {str(e)}")
        else:
            self.add_issue("warning", "Index Map", "Local index map file not found")
        
        # Get index map info from services
        service_index_info = {}
        
        # From Retrieval health
        try:
            response = requests.get(f"{RETRIEVAL_URL}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                service_index_info["Retrieval"] = data.get("index_map_entries", 0)
                print(f"Retrieval service index entries: {service_index_info['Retrieval']}")
        except Exception as e:
            self.add_issue("error", "Index Map", f"Failed to get Retrieval index info: {str(e)}")
        
        # From Gateway sync status
        try:
            response = requests.get(f"{GATEWAY_URL}/sync/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                index_info = data.get("index_map", {})
                service_index_info["Gateway"] = index_info.get("entry_count", 0)
                print(f"Gateway sync status index entries: {service_index_info['Gateway']}")
        except Exception as e:
            self.add_issue("error", "Index Map", f"Failed to get Gateway sync status: {str(e)}")
        
        # Compare
        if len(service_index_info) >= 2:
            values = list(service_index_info.values())
            if len(set(values)) > 1:
                self.add_issue(
                    "warning",
                    "Index Map",
                    f"Index map entry counts differ: {service_index_info}",
                    service_index_info
                )
            else:
                print("✓ Index map entry counts are consistent\n")
        
        self.metrics["index_map"] = {
            "local_entries": len(local_index_map),
            "service_entries": service_index_info
        }
        
        return {
            "local_entries": len(local_index_map),
            "service_entries": service_index_info
        }
    
    def validate_document_id_uniqueness(self) -> Dict:
        """Validate document IDs are unique"""
        print("\n" + "="*80)
        print("Document ID Uniqueness Validation")
        print("="*80 + "\n")
        
        try:
            response = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
            if response.status_code != 200:
                self.add_issue("error", "ID Uniqueness", "Failed to get documents")
                return {}
            
            data = response.json()
            documents = data.get("documents", [])
            
            doc_ids = [doc.get("document_id") for doc in documents if doc.get("document_id")]
            unique_ids = set(doc_ids)
            
            duplicates = len(doc_ids) - len(unique_ids)
            
            print(f"Total documents: {len(doc_ids)}")
            print(f"Unique IDs: {len(unique_ids)}")
            print(f"Duplicates: {duplicates}")
            
            if duplicates > 0:
                self.add_issue(
                    "error",
                    "ID Uniqueness",
                    f"Found {duplicates} duplicate document IDs",
                    {"total": len(doc_ids), "unique": len(unique_ids), "duplicates": duplicates}
                )
            else:
                print("✓ All document IDs are unique\n")
            
            self.metrics["id_uniqueness"] = {
                "total": len(doc_ids),
                "unique": len(unique_ids),
                "duplicates": duplicates
            }
            
            return {
                "total": len(doc_ids),
                "unique": len(unique_ids),
                "duplicates": duplicates
            }
            
        except Exception as e:
            self.add_issue("error", "ID Uniqueness", f"Validation failed: {str(e)}")
            return {}
    
    def validate_timestamp_consistency(self) -> Dict:
        """Validate timestamp consistency"""
        print("\n" + "="*80)
        print("Timestamp Consistency Validation")
        print("="*80 + "\n")
        
        try:
            response = requests.get(f"{GATEWAY_URL}/documents", timeout=10)
            if response.status_code != 200:
                return {}
            
            data = response.json()
            documents = data.get("documents", [])
            
            if not documents:
                print("No documents to validate\n")
                return {}
            
            timestamps = []
            for doc in documents[:20]:  # Sample 20 documents
                created_at = doc.get("created_at")
                if created_at:
                    timestamps.append(created_at)
            
            if not timestamps:
                print("No timestamps found in documents\n")
                return {}
            
            # Check if timestamps are in valid ISO format
            valid_timestamps = 0
            for ts in timestamps:
                try:
                    from datetime import datetime
                    datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    valid_timestamps += 1
                except:
                    pass
            
            validity_score = valid_timestamps / len(timestamps) if timestamps else 0
            
            print(f"Valid timestamps: {valid_timestamps}/{len(timestamps)} ({validity_score*100:.1f}%)")
            
            if validity_score < 1.0:
                self.add_issue(
                    "warning",
                    "Timestamps",
                    f"Some timestamps are invalid: {validity_score*100:.1f}% valid",
                    {"valid": valid_timestamps, "total": len(timestamps)}
                )
            else:
                print("✓ All timestamps are valid\n")
            
            self.metrics["timestamp_consistency"] = {
                "valid": valid_timestamps,
                "total": len(timestamps),
                "score": validity_score
            }
            
            return {
                "valid": valid_timestamps,
                "total": len(timestamps),
                "score": validity_score
            }
            
        except Exception as e:
            self.add_issue("error", "Timestamps", f"Validation failed: {str(e)}")
            return {}
    
    def generate_report(self) -> Dict:
        """Generate validation report"""
        print("\n" + "="*80)
        print("Data Consistency Validation Summary")
        print("="*80 + "\n")
        
        error_count = sum(1 for i in self.issues if i.severity == "error")
        warning_count = sum(1 for i in self.issues if i.severity == "warning")
        info_count = sum(1 for i in self.issues if i.severity == "info")
        
        print(f"Total Issues: {len(self.issues)}")
        print(f"  Errors: {error_count}")
        print(f"  Warnings: {warning_count}")
        print(f"  Info: {info_count}\n")
        
        if error_count > 0:
            print("Errors:")
            for issue in self.issues:
                if issue.severity == "error":
                    print(f"  ✗ [{issue.category}] {issue.description}")
        
        if warning_count > 0:
            print("\nWarnings:")
            for issue in self.issues:
                if issue.severity == "warning":
                    print(f"  ⚠ [{issue.category}] {issue.description}")
        
        overall_status = "PASS" if error_count == 0 else "FAIL"
        print(f"\nOverall Status: {overall_status}\n")
        
        return {
            "status": overall_status,
            "errors": error_count,
            "warnings": warning_count,
            "info": info_count,
            "issues": [
                {
                    "severity": i.severity,
                    "category": i.category,
                    "description": i.description,
                    "details": i.details
                }
                for i in self.issues
            ],
            "metrics": self.metrics
        }
    
    def run_all_validations(self):
        """Run all validation checks"""
        print("\n" + "="*80)
        print("ARIS RAG Data Consistency Validator")
        print("="*80)
        
        self.validate_document_counts()
        self.validate_document_metadata()
        self.validate_index_map_consistency()
        self.validate_document_id_uniqueness()
        self.validate_timestamp_consistency()
        
        return self.generate_report()

def main():
    """Main entry point"""
    validator = DataConsistencyValidator()
    report = validator.run_all_validations()
    
    # Save report
    output_file = "data_consistency_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {output_file}\n")
    
    # Exit code
    sys.exit(0 if report["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
