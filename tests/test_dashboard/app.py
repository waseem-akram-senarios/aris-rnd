"""
ARIS Test Dashboard - Real-time Test Monitoring UI
Web-based dashboard to visualize test execution, results, and metrics
"""
import os
import sys
import json
import time
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from collections import defaultdict

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))


@dataclass
class TestResult:
    """Test result data structure"""
    name: str
    status: str  # PASSED, FAILED, SKIPPED, ERROR
    duration: float
    category: str
    marker: str
    error_message: str = ""
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass 
class TestSuite:
    """Test suite data structure"""
    name: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration: float
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


class TestRunner:
    """Test runner for executing tests and collecting results"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.results_cache = {}
        
    def run_pytest(self, test_path: str, markers: str = "") -> Dict[str, Any]:
        """Run pytest and return results"""
        try:
            # Build pytest command
            cmd = [
                sys.executable, "-m", "pytest", 
                test_path,
                "-v",
                "--tb=short",
                "--json-report",
                "--json-report-file=/tmp/pytest_report.json"
            ]
            
            if markers:
                cmd.extend(["-m", markers])
            
            # Run pytest
            start_time = time.time()
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            duration = time.time() - start_time
            
            # Parse JSON report if available
            test_results = []
            if os.path.exists("/tmp/pytest_report.json"):
                try:
                    with open("/tmp/pytest_report.json", "r") as f:
                        report = json.load(f)
                        
                    for test in report.get("tests", []):
                        test_results.append(TestResult(
                            name=test.get("nodeid", ""),
                            status=test.get("outcome", "UNKNOWN").upper(),
                            duration=test.get("duration", 0.0),
                            category=self._extract_category(test.get("nodeid", "")),
                            marker=self._extract_marker(test.get("nodeid", "")),
                            error_message=test.get("call", {}).get("longrepr", "")[:200]
                        ))
                except Exception as e:
                    print(f"Error parsing pytest report: {e}")
            
            # Create suite summary
            passed = len([t for t in test_results if t.status == "PASSED"])
            failed = len([t for t in test_results if t.status == "FAILED"])
            skipped = len([t for t in test_results if t.status == "SKIPPED"])
            errors = len([t for t in test_results if t.status == "ERROR"])
            
            suite = TestSuite(
                name=test_path,
                total_tests=len(test_results),
                passed=passed,
                failed=failed,
                skipped=skipped,
                errors=errors,
                duration=duration
            )
            
            return {
                "suite": asdict(suite),
                "tests": [asdict(t) for t in test_results],
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Test execution timed out"}
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_category(self, test_name: str) -> str:
        """Extract test category from test name"""
        if "e2e" in test_name.lower():
            return "E2E"
        elif "unit" in test_name.lower():
            return "Unit"
        elif "integration" in test_name.lower():
            return "Integration"
        elif "mcp" in test_name.lower():
            return "MCP"
        elif "server" in test_name.lower():
            return "Server"
        else:
            return "Other"
    
    def _extract_marker(self, test_name: str) -> str:
        """Extract test marker from test name"""
        markers = ["e2e", "unit", "integration", "mcp", "server", "performance", "sanity"]
        for marker in markers:
            if marker in test_name.lower():
                return marker
        return "general"


class TestDashboard:
    """Main dashboard application"""
    
    def __init__(self):
        self.runner = TestRunner()
        self.test_categories = {
            "E2E Tests": "tests/e2e/",
            "MCP Tests": "tests/mcp/",
            "Unit Tests": "tests/unit/",
            "Integration Tests": "tests/integration/",
            "All Tests": "tests/"
        }
        
    def run(self):
        """Run the Streamlit dashboard"""
        st.set_page_config(
            page_title="ARIS Test Dashboard",
            page_icon="🧪",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🧪 ARIS Test Dashboard")
        st.markdown("Real-time test monitoring and visualization for ARIS RAG System")
        
        # Sidebar
        self.render_sidebar()
        
        # Main content
        self.render_main_content()
    
    def render_sidebar(self):
        """Render sidebar controls"""
        st.sidebar.header("🎛️ Test Controls")
        
        # Test category selection
        selected_category = st.sidebar.selectbox(
            "Select Test Category",
            list(self.test_categories.keys()),
            index=0
        )
        
        # Test markers
        available_markers = ["", "e2e", "mcp", "server", "unit", "integration", "performance", "sanity"]
        selected_marker = st.sidebar.selectbox(
            "Test Marker (Optional)",
            available_markers,
            index=0
        )
        
        # Run tests button
        if st.sidebar.button("🚀 Run Tests", type="primary"):
            self.run_tests(selected_category, selected_marker)
        
        # Auto-refresh
        auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30s)", value=False)
        if auto_refresh:
            st.sidebar.write("Dashboard will refresh every 30 seconds")
        
        # Test configuration
        st.sidebar.header("⚙️ Configuration")
        timeout = st.sidebar.slider("Test Timeout (seconds)", 60, 600, 300)
        parallel = st.sidebar.checkbox("Run tests in parallel", value=False)
        
        return selected_category, selected_marker
    
    def render_main_content(self):
        """Render main dashboard content"""
        # Get session state
        if "test_results" not in st.session_state:
            st.session_state.test_results = {}
        
        # Display results if available
        if st.session_state.test_results:
            self.render_test_results(st.session_state.test_results)
        else:
            self.render_welcome_screen()
    
    def render_welcome_screen(self):
        """Render welcome screen when no results available"""
        st.markdown("## 🎯 Welcome to ARIS Test Dashboard")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📊 Test Categories", len(self.test_categories))
            st.info("Select a category from sidebar and click 'Run Tests'")
        
        with col2:
            st.metric("🧪 Available Tests", self.count_available_tests())
            st.info("Tests are organized by category and markers")
        
        with col3:
            st.metric("⚡ Last Run", "Never")
            st.info("Run tests to see performance metrics")
        
        # Test categories overview
        st.markdown("### 📋 Available Test Categories")
        
        for category, path in self.test_categories.items():
            with st.expander(f"📁 {category}"):
                st.code(f"Path: {path}")
                
                # Show some example tests
                try:
                    test_files = list(Path(path).glob("**/test_*.py"))[:5]
                    if test_files:
                        st.write("Example test files:")
                        for test_file in test_files:
                            st.write(f"  - {test_file.relative_to(Path.cwd())}")
                except Exception:
                    st.write("  (Unable to list test files)")
    
    def render_test_results(self, results: Dict[str, Any]):
        """Render test results dashboard"""
        if "error" in results:
            st.error(f"❌ Test execution failed: {results['error']}")
            return
        
        suite = results.get("suite", {})
        tests = results.get("tests", [])
        
        # Header metrics
        st.markdown("## 📊 Test Results Summary")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📈 Total Tests", suite.get("total_tests", 0))
        
        with col2:
            passed = suite.get("passed", 0)
            st.metric("✅ Passed", passed, delta=None)
        
        with col3:
            failed = suite.get("failed", 0)
            st.metric("❌ Failed", failed, delta=None)
        
        with col4:
            success_rate = suite.get("passed", 0) / max(suite.get("total_tests", 1), 1) * 100
            st.metric("📊 Success Rate", f"{success_rate:.1f}%")
        
        with col5:
            duration = suite.get("duration", 0)
            st.metric("⏱️ Duration", f"{duration:.2f}s")
        
        # Progress bar
        if suite.get("total_tests", 0) > 0:
            progress = suite.get("passed", 0) / suite.get("total_tests", 1)
            st.progress(progress, text=f"Test Progress: {progress*100:.1f}%")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            self.render_status_chart(suite)
        
        with col2:
            self.render_category_chart(tests)
        
        # Test details
        st.markdown("## 📋 Test Details")
        
        # Filter controls
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All", "PASSED", "FAILED", "SKIPPED", "ERROR"]
            )
        
        with col2:
            category_filter = st.selectbox(
                "Filter by Category",
                ["All"] + list(set(t.get("category", "Other") for t in tests))
            )
        
        with col3:
            sort_by = st.selectbox(
                "Sort by",
                ["Name", "Duration", "Status"]
            )
        
        # Filter and sort tests
        filtered_tests = self.filter_tests(tests, status_filter, category_filter)
        filtered_tests = self.sort_tests(filtered_tests, sort_by)
        
        # Display tests
        if filtered_tests:
            self.render_test_table(filtered_tests)
        else:
            st.info("No tests match the selected filters")
        
        # Error details
        failed_tests = [t for t in tests if t.get("status") in ["FAILED", "ERROR"]]
        if failed_tests:
            st.markdown("## ❌ Error Details")
            
            for test in failed_tests:
                with st.expander(f"❌ {test.get('name', 'Unknown')}"):
                    st.code(test.get("error_message", "No error message available"))
    
    def render_status_chart(self, suite: Dict[str, Any]):
        """Render test status pie chart"""
        labels = ["Passed", "Failed", "Skipped", "Errors"]
        values = [
            suite.get("passed", 0),
            suite.get("failed", 0), 
            suite.get("skipped", 0),
            suite.get("errors", 0)
        ]
        colors = ["#2E8B57", "#DC143C", "#FFD700", "#FF6347"]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.3,
            marker_colors=colors
        )])
        
        fig.update_layout(
            title="Test Status Distribution",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_category_chart(self, tests: List[Dict[str, Any]]):
        """Render test category bar chart"""
        categories = defaultdict(int)
        for test in tests:
            category = test.get("category", "Other")
            categories[category] += 1
        
        fig = go.Figure(data=[
            go.Bar(
                x=list(categories.keys()),
                y=list(categories.values()),
                marker_color="#1E90FF"
            )
        ])
        
        fig.update_layout(
            title="Tests by Category",
            xaxis_title="Category",
            yaxis_title="Number of Tests",
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_test_table(self, tests: List[Dict[str, Any]]):
        """Render test results table"""
        df = pd.DataFrame(tests)
        
        # Format the dataframe
        if not df.empty:
            df["duration"] = df["duration"].round(3)
            df["status"] = df["status"].apply(self.format_status)
            
            # Rename columns
            df = df.rename(columns={
                "name": "Test Name",
                "status": "Status",
                "duration": "Duration (s)",
                "category": "Category",
                "marker": "Marker"
            })
            
            # Display table
            st.dataframe(
                df[["Test Name", "Status", "Duration (s)", "Category", "Marker"]],
                use_container_width=True,
                hide_index=True
            )
    
    def format_status(self, status: str) -> str:
        """Format status with emoji"""
        status_map = {
            "PASSED": "✅ PASSED",
            "FAILED": "❌ FAILED", 
            "SKIPPED": "⏭️ SKIPPED",
            "ERROR": "🚨 ERROR"
        }
        return status_map.get(status, status)
    
    def filter_tests(self, tests: List[Dict[str, Any]], status_filter: str, category_filter: str) -> List[Dict[str, Any]]:
        """Filter tests by status and category"""
        filtered = tests.copy()
        
        if status_filter != "All":
            filtered = [t for t in filtered if t.get("status") == status_filter]
        
        if category_filter != "All":
            filtered = [t for t in filtered if t.get("category") == category_filter]
        
        return filtered
    
    def sort_tests(self, tests: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        """Sort tests by specified field"""
        reverse = sort_by == "Duration"  # Sort duration descending
        
        if sort_by == "Name":
            return sorted(tests, key=lambda x: x.get("name", ""), reverse=reverse)
        elif sort_by == "Duration":
            return sorted(tests, key=lambda x: x.get("duration", 0), reverse=reverse)
        elif sort_by == "Status":
            return sorted(tests, key=lambda x: x.get("status", ""), reverse=reverse)
        
        return tests
    
    def count_available_tests(self) -> int:
        """Count total available test files"""
        try:
            count = 0
            for path in self.test_categories.values():
                count += len(list(Path(path).glob("**/test_*.py")))
            return count
        except Exception:
            return 0
    
    def run_tests(self, category: str, marker: str):
        """Run tests and store results"""
        test_path = self.test_categories[category]
        
        with st.spinner(f"🚀 Running {category}..."):
            results = self.runner.run_pytest(test_path, marker)
            st.session_state.test_results = results
            
            if "error" not in results:
                suite = results.get("suite", {})
                st.success(f"✅ Tests completed! {suite.get('passed', 0)}/{suite.get('total_tests', 0)} passed")
            else:
                st.error("❌ Test execution failed")


def main():
    """Main entry point"""
    dashboard = TestDashboard()
    dashboard.run()


if __name__ == "__main__":
    main()
