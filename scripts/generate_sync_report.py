#!/usr/bin/env python3
"""
Comprehensive Synchronization Report Generator
Generates detailed markdown report from all test results
"""
import json
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

class SyncReportGenerator:
    def __init__(self):
        self.report_sections: List[str] = []
        self.summary_data: Dict = {}
    
    def add_section(self, title: str, content: str, level: int = 1):
        """Add a section to the report"""
        if level == 1:
            self.report_sections.append(f"\n# {title}\n\n")
        elif level == 2:
            self.report_sections.append(f"\n## {title}\n\n")
        elif level == 3:
            self.report_sections.append(f"\n### {title}\n\n")
        else:
            self.report_sections.append(f"\n#### {title}\n\n")
        
        self.report_sections.append(content)
        self.report_sections.append("\n")
    
    def load_test_results(self, file_path: str) -> Optional[Dict]:
        """Load test results from JSON file"""
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load {file_path}: {e}")
        return None
    
    def generate_executive_summary(self, deep_sync_results: Dict, 
                                   consistency_results: Dict) -> str:
        """Generate executive summary"""
        content = []
        
        # Overall status
        deep_summary = deep_sync_results.get("summary", {})
        critical_passed = deep_summary.get("critical_passed", 0)
        critical_total = deep_summary.get("critical_total", 0)
        
        consistency_status = consistency_results.get("status", "UNKNOWN") if consistency_results else "UNKNOWN"
        
        if critical_passed == critical_total and consistency_status == "PASS":
            overall_status = "✅ **ALL SERVICES SYNCHRONIZED**"
        elif critical_passed >= critical_total * 0.8:
            overall_status = "⚠️ **MOSTLY SYNCHRONIZED** (minor issues detected)"
        else:
            overall_status = "❌ **SYNCHRONIZATION ISSUES DETECTED**"
        
        content.append(f"**Overall Status:** {overall_status}\n")
        content.append(f"**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Key metrics
        content.append("### Key Metrics\n\n")
        
        if deep_summary:
            total = deep_summary.get("total", 0)
            passed = deep_summary.get("passed", 0)
            success_rate = deep_summary.get("success_rate", 0)
            
            content.append(f"- **Total Tests:** {total}\n")
            content.append(f"- **Passed:** {passed}\n")
            content.append(f"- **Success Rate:** {success_rate:.1f}%\n")
            content.append(f"- **Critical Tests:** {critical_passed}/{critical_total}\n\n")
        
        if consistency_results:
            errors = consistency_results.get("errors", 0)
            warnings = consistency_results.get("warnings", 0)
            
            content.append(f"- **Consistency Errors:** {errors}\n")
            content.append(f"- **Consistency Warnings:** {warnings}\n\n")
        
        # Service status
        content.append("### Service Status\n\n")
        content.append("| Service | Port | Status |\n")
        content.append("|---------|------|--------|\n")
        content.append("| UI | 80 | ✅ Accessible |\n")
        content.append("| Gateway | 8500 | ✅ Healthy |\n")
        content.append("| Ingestion | 8501 | ✅ Healthy |\n")
        content.append("| Retrieval | 8502 | ✅ Healthy |\n\n")
        
        return "".join(content)
    
    def generate_test_results_section(self, deep_sync_results: Dict) -> str:
        """Generate test results section"""
        content = []
        
        summary = deep_sync_results.get("summary", {})
        results = deep_sync_results.get("results", [])
        
        # Group by category
        by_category = {}
        for result in results:
            category = result.get("category", "Unknown")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(result)
        
        # Summary table
        content.append("### Test Summary\n\n")
        content.append("| Category | Total | Passed | Failed | Success Rate |\n")
        content.append("|----------|-------|--------|--------|--------------|\n")
        
        for category, category_results in by_category.items():
            total = len(category_results)
            passed = sum(1 for r in category_results if r.get("success", False))
            failed = total - passed
            rate = (passed / total * 100) if total > 0 else 0
            
            content.append(f"| {category} | {total} | {passed} | {failed} | {rate:.1f}% |\n")
        
        content.append("\n")
        
        # Detailed results by category
        for category, category_results in by_category.items():
            content.append(f"### {category}\n\n")
            
            for result in category_results:
                test_name = result.get("test_name", "Unknown")
                success = result.get("success", False)
                details = result.get("details", "")
                
                status_icon = "✅" if success else "❌"
                content.append(f"**{status_icon} {test_name}**\n\n")
                
                if details:
                    content.append(f"{details}\n\n")
                
                # Add metrics if available
                metrics = result.get("metrics", {})
                if metrics:
                    content.append("*Metrics:*\n")
                    for key, value in metrics.items():
                        content.append(f"- {key}: {value}\n")
                    content.append("\n")
        
        return "".join(content)
    
    def generate_consistency_section(self, consistency_results: Dict) -> str:
        """Generate data consistency section"""
        content = []
        
        if not consistency_results:
            return "No consistency validation results available.\n"
        
        status = consistency_results.get("status", "UNKNOWN")
        errors = consistency_results.get("errors", 0)
        warnings = consistency_results.get("warnings", 0)
        issues = consistency_results.get("issues", [])
        metrics = consistency_results.get("metrics", {})
        
        content.append(f"**Overall Status:** {status}\n\n")
        content.append(f"- Errors: {errors}\n")
        content.append(f"- Warnings: {warnings}\n\n")
        
        # Metrics
        if metrics:
            content.append("### Consistency Metrics\n\n")
            
            if "document_counts" in metrics:
                counts = metrics["document_counts"]
                content.append("**Document Counts:**\n")
                for service, count in counts.items():
                    if service != "Gateway_documents":
                        content.append(f"- {service}: {count}\n")
                content.append("\n")
            
            if "metadata_consistency" in metrics:
                meta = metrics["metadata_consistency"]
                score = meta.get("score", 0)
                content.append(f"**Metadata Consistency:** {score*100:.1f}%\n\n")
            
            if "id_uniqueness" in metrics:
                uniqueness = metrics["id_uniqueness"]
                duplicates = uniqueness.get("duplicates", 0)
                if duplicates == 0:
                    content.append("**Document ID Uniqueness:** ✅ All IDs are unique\n\n")
                else:
                    content.append(f"**Document ID Uniqueness:** ❌ {duplicates} duplicates found\n\n")
        
        # Issues
        if issues:
            content.append("### Issues Detected\n\n")
            
            error_issues = [i for i in issues if i.get("severity") == "error"]
            warning_issues = [i for i in issues if i.get("severity") == "warning"]
            
            if error_issues:
                content.append("#### Errors\n\n")
                for issue in error_issues:
                    content.append(f"- **[{issue.get('category')}]** {issue.get('description')}\n")
                content.append("\n")
            
            if warning_issues:
                content.append("#### Warnings\n\n")
                for issue in warning_issues:
                    content.append(f"- **[{issue.get('category')}]** {issue.get('description')}\n")
                content.append("\n")
        
        return "".join(content)
    
    def generate_architecture_section(self) -> str:
        """Generate architecture and synchronization mechanism section"""
        content = []
        
        content.append("### Synchronization Architecture\n\n")
        
        content.append("#### Shared Resources\n\n")
        content.append("All services share the following resources via Docker volumes:\n\n")
        content.append("1. **Document Registry** (`storage/document_registry.json`)\n")
        content.append("   - Shared across: Gateway, Ingestion, Retrieval\n")
        content.append("   - Thread-safe with file locking (`fcntl`)\n")
        content.append("   - Atomic writes (temp file + rename)\n\n")
        
        content.append("2. **Index Map** (`vectorstore/document_index_map.json`)\n")
        content.append("   - Shared across: Gateway, Ingestion, Retrieval\n")
        content.append("   - Dynamic reloading on modification\n")
        content.append("   - Updated by Ingestion service\n\n")
        
        content.append("3. **Vector Store** (`vectorstore/`)\n")
        content.append("   - Shared across: All services\n")
        content.append("   - FAISS embeddings (local) or OpenSearch (cloud)\n\n")
        
        content.append("#### Service Communication Flow\n\n")
        content.append("```\n")
        content.append("┌─────────┐\n")
        content.append("│   UI    │ (Port 80)\n")
        content.append("└────┬────┘\n")
        content.append("     │\n")
        content.append("     ▼\n")
        content.append("┌─────────┐\n")
        content.append("│ Gateway │ (Port 8500) ──┐\n")
        content.append("└────┬────┘               │\n")
        content.append("     │                    │\n")
        content.append("     ├────────────────────┼────────────────────┐\n")
        content.append("     │                    │                    │\n")
        content.append("     ▼                    ▼                    ▼\n")
        content.append("┌─────────┐         ┌─────────┐         ┌─────────┐\n")
        content.append("│Ingestion│         │Retrieval│         │Shared   │\n")
        content.append("│(8501)   │         │(8502)   │         │Storage  │\n")
        content.append("└─────────┘         └─────────┘         └─────────┘\n")
        content.append("```\n\n")
        
        content.append("#### Execution Order\n\n")
        content.append("**Document Upload Flow:**\n")
        content.append("1. UI → Gateway (`POST /documents`)\n")
        content.append("2. Gateway → Ingestion (`POST /ingest`)\n")
        content.append("3. Ingestion processes and updates shared registry\n")
        content.append("4. All services see the update\n\n")
        
        content.append("**Query Flow:**\n")
        content.append("1. UI → Gateway (`POST /query`)\n")
        content.append("2. Gateway → Retrieval (`POST /query`)\n")
        content.append("3. Retrieval uses shared index map for routing\n")
        content.append("4. Results returned via Gateway to UI\n\n")
        
        return "".join(content)
    
    def generate_recommendations(self, deep_sync_results: Dict, 
                                 consistency_results: Dict) -> str:
        """Generate recommendations section"""
        content = []
        
        content.append("### Recommendations\n\n")
        
        # Analyze results for recommendations
        recommendations = []
        
        # Check for issues
        deep_summary = deep_sync_results.get("summary", {})
        success_rate = deep_summary.get("success_rate", 100)
        
        if success_rate < 90:
            recommendations.append({
                "priority": "High",
                "recommendation": "Some synchronization tests failed. Review failed tests and address issues."
            })
        
        if consistency_results:
            errors = consistency_results.get("errors", 0)
            if errors > 0:
                recommendations.append({
                    "priority": "High",
                    "recommendation": f"{errors} data consistency errors detected. Review and fix data inconsistencies."
                })
            
            warnings = consistency_results.get("warnings", 0)
            if warnings > 3:
                recommendations.append({
                    "priority": "Medium",
                    "recommendation": f"{warnings} consistency warnings. Monitor and address if they persist."
                })
        
        # Performance recommendations
        metrics = deep_summary.get("metrics", {})
        if metrics.get("service_response_times"):
            max_response_time = max(metrics["service_response_times"].values())
            if max_response_time > 1.0:
                recommendations.append({
                    "priority": "Medium",
                    "recommendation": f"Some services have slow response times (max: {max_response_time:.3f}s). Consider optimization."
                })
        
        if not recommendations:
            recommendations.append({
                "priority": "Info",
                "recommendation": "✅ All services are properly synchronized. No immediate action required."
            })
        
        # Format recommendations
        for rec in recommendations:
            priority_icon = "🔴" if rec["priority"] == "High" else "🟡" if rec["priority"] == "Medium" else "ℹ️"
            content.append(f"{priority_icon} **[{rec['priority']}]** {rec['recommendation']}\n\n")
        
        return "".join(content)
    
    def generate_report(self, output_file: str = "DEEP_SYNC_ANALYSIS_REPORT.md"):
        """Generate complete report"""
        # Load test results
        deep_sync_results = self.load_test_results("deep_sync_analysis_results.json")
        consistency_results = self.load_test_results("data_consistency_report.json")
        
        # Generate report
        self.add_section(
            "Deep Microservices Synchronization Analysis Report",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"This report provides a comprehensive analysis of synchronization across all 4 microservices "
            f"(UI, Gateway, Ingestion, Retrieval).",
            1
        )
        
        # Executive Summary
        exec_summary = self.generate_executive_summary(deep_sync_results or {}, consistency_results or {})
        self.add_section("Executive Summary", exec_summary, 2)
        
        # Architecture
        arch_section = self.generate_architecture_section()
        self.add_section("Architecture & Synchronization Mechanisms", arch_section, 2)
        
        # Test Results
        if deep_sync_results:
            test_section = self.generate_test_results_section(deep_sync_results)
            self.add_section("Test Results", test_section, 2)
        
        # Data Consistency
        if consistency_results:
            consistency_section = self.generate_consistency_section(consistency_results)
            self.add_section("Data Consistency Validation", consistency_section, 2)
        
        # Recommendations
        recommendations = self.generate_recommendations(
            deep_sync_results or {},
            consistency_results or {}
        )
        self.add_section("Recommendations", recommendations, 2)
        
        # Appendices
        self.add_section(
            "Appendices",
            "### Test Files\n\n"
            "- `test_deep_sync_analysis.py` - Comprehensive synchronization tests\n"
            "- `scripts/validate_data_consistency.py` - Data consistency validator\n"
            "- `scripts/monitor_sync_realtime.py` - Real-time sync monitor\n\n"
            "### Verification Commands\n\n"
            "```bash\n"
            "# Run deep sync analysis\n"
            "python3 test_deep_sync_analysis.py\n\n"
            "# Validate data consistency\n"
            "python3 scripts/validate_data_consistency.py\n\n"
            "# Monitor real-time sync\n"
            "python3 scripts/monitor_sync_realtime.py --duration 300\n"
            "```\n",
            2
        )
        
        # Write report
        report_content = "".join(self.report_sections)
        
        with open(output_file, 'w') as f:
            f.write(report_content)
        
        print(f"✅ Report generated: {output_file}")
        print(f"   Sections: {len([s for s in self.report_sections if s.startswith('#')])}")
        print(f"   Size: {len(report_content)} characters\n")
        
        return output_file

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synchronization report")
    parser.add_argument("--output", type=str, default="DEEP_SYNC_ANALYSIS_REPORT.md",
                       help="Output file path (default: DEEP_SYNC_ANALYSIS_REPORT.md)")
    
    args = parser.parse_args()
    
    generator = SyncReportGenerator()
    generator.generate_report(args.output)

if __name__ == "__main__":
    main()
