#!/usr/bin/env python3
"""
MCP Server UI Test Dashboard
Web-based dashboard to visually test MCP server functionality
"""
import os
import sys
import asyncio
import httpx
import json
import time
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# MCP Server Configuration
MCP_SERVER_URL = "http://localhost:8503"
MCP_HEALTH_URL = f"{MCP_SERVER_URL}/health"
MCP_INFO_URL = f"{MCP_SERVER_URL}/info"
MCP_SSE_URL = f"{MCP_SERVER_URL}/sse"


@dataclass
class UITestResult:
    """UI Test result data structure"""
    test_name: str
    status: str
    response_time: float
    details: str
    timestamp: str
    error_message: str = ""


class MCPUITestDashboard:
    """MCP Server UI Test Dashboard"""
    
    def __init__(self):
        self.base_url = MCP_SERVER_URL
        self.test_history: List[UITestResult] = []
    
    async def run_health_test(self) -> UITestResult:
        """Run health endpoint test"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(MCP_HEALTH_URL)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    health_data = response.json()
                    status = health_data.get("status", "unknown")
                    tools = health_data.get("tools", [])
                    
                    return UITestResult(
                        test_name="Health Check",
                        status="PASSED" if status == "healthy" else "FAILED",
                        response_time=response_time,
                        details=f"Status: {status}, Tools: {len(tools)}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    return UITestResult(
                        test_name="Health Check",
                        status="FAILED",
                        response_time=response_time,
                        details=f"HTTP {response.status_code}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
        except Exception as e:
            return UITestResult(
                test_name="Health Check",
                status="FAILED",
                response_time=time.time() - start_time,
                details="Connection failed",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message=str(e)
            )
    
    async def run_info_test(self) -> UITestResult:
        """Run info endpoint test"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(MCP_INFO_URL)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    info_data = response.json()
                    service = info_data.get("service", "unknown")
                    version = info_data.get("version", "unknown")
                    tools = info_data.get("tools", {})
                    
                    return UITestResult(
                        test_name="Service Info",
                        status="PASSED",
                        response_time=response_time,
                        details=f"{service} v{version}, Tools: {len(tools)}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    return UITestResult(
                        test_name="Service Info",
                        status="FAILED",
                        response_time=response_time,
                        details=f"HTTP {response.status_code}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
        except Exception as e:
            return UITestResult(
                test_name="Service Info",
                status="FAILED",
                response_time=time.time() - start_time,
                details="Connection failed",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message=str(e)
            )
    
    async def run_sse_test(self) -> UITestResult:
        """Run SSE endpoint test"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(MCP_SSE_URL)
                response_time = time.time() - start_time
                
                if response.status_code in [200, 307]:
                    return UITestResult(
                        test_name="SSE Endpoint",
                        status="PASSED",
                        response_time=response_time,
                        details=f"SSE accessible (HTTP {response.status_code})",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    return UITestResult(
                        test_name="SSE Endpoint",
                        status="FAILED",
                        response_time=response_time,
                        details=f"HTTP {response.status_code}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
        except Exception as e:
            return UITestResult(
                test_name="SSE Endpoint",
                status="FAILED",
                response_time=time.time() - start_time,
                details="Connection failed",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message=str(e)
            )
    
    async def run_tools_test(self) -> UITestResult:
        """Run MCP tools verification test"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(MCP_HEALTH_URL)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    health_data = response.json()
                    tools = health_data.get("tools", [])
                    
                    expected_tools = ["rag_ingest", "rag_upload_document", "rag_search"]
                    missing_tools = [tool for tool in expected_tools if tool not in tools]
                    
                    if not missing_tools:
                        return UITestResult(
                            test_name="MCP Tools",
                            status="PASSED",
                            response_time=response_time,
                            details=f"All tools available: {', '.join(tools)}",
                            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                    else:
                        return UITestResult(
                            test_name="MCP Tools",
                            status="FAILED",
                            response_time=response_time,
                            details=f"Missing tools: {missing_tools}",
                            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        )
                else:
                    return UITestResult(
                        test_name="MCP Tools",
                        status="FAILED",
                        response_time=response_time,
                        details=f"Health check failed: HTTP {response.status_code}",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
        except Exception as e:
            return UITestResult(
                test_name="MCP Tools",
                status="FAILED",
                response_time=time.time() - start_time,
                details="Connection failed",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message=str(e)
            )
    
    async def run_performance_test(self) -> UITestResult:
        """Run performance test"""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test multiple endpoints
                endpoints = [MCP_HEALTH_URL, MCP_INFO_URL]
                response_times = []
                
                for endpoint in endpoints:
                    endpoint_start = time.time()
                    response = await client.get(endpoint)
                    endpoint_time = time.time() - endpoint_start
                    response_times.append(endpoint_time)
                
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
                
                if avg_response_time < 1.0 and max_response_time < 2.0:
                    return UITestResult(
                        test_name="Performance",
                        status="PASSED",
                        response_time=avg_response_time,
                        details=f"Avg: {avg_response_time:.3f}s, Max: {max_response_time:.3f}s",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
                else:
                    return UITestResult(
                        test_name="Performance",
                        status="FAILED",
                        response_time=avg_response_time,
                        details=f"Too slow - Avg: {avg_response_time:.3f}s, Max: {max_response_time:.3f}s",
                        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    )
        except Exception as e:
            return UITestResult(
                test_name="Performance",
                status="FAILED",
                response_time=time.time() - start_time,
                details="Performance test failed",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                error_message=str(e)
            )
    
    async def run_all_tests(self) -> List[UITestResult]:
        """Run all UI tests"""
        tests = [
            self.run_health_test,
            self.run_info_test,
            self.run_sse_test,
            self.run_tools_test,
            self.run_performance_test
        ]
        
        results = []
        for test_func in tests:
            result = await test_func()
            results.append(result)
            self.test_history.append(result)
        
        return results
    
    def render_dashboard(self):
        """Render the Streamlit dashboard"""
        st.set_page_config(
            page_title="MCP Server UI Test Dashboard",
            page_icon="🧪",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🧪 MCP Server UI Test Dashboard")
        st.markdown("Visual testing dashboard for MCP Server functionality")
        
        # Sidebar
        st.sidebar.header("🎛️ Test Controls")
        
        # Server URL configuration
        server_url = st.sidebar.text_input(
            "MCP Server URL",
            value=MCP_SERVER_URL,
            help="URL of the MCP server to test"
        )
        
        # Auto-refresh
        auto_refresh = st.sidebar.checkbox("🔄 Auto-refresh (30s)", value=False)
        
        # Run tests button
        if st.sidebar.button("🚀 Run All Tests", type="primary"):
            with st.spinner("Running UI tests..."):
                results = asyncio.run(self.run_all_tests())
                st.session_state.last_test_results = results
                st.session_state.last_test_time = datetime.now()
        
        # Individual test buttons
        st.sidebar.subheader("Individual Tests")
        
        if st.sidebar.button("🏥 Health Check"):
            with st.spinner("Testing health endpoint..."):
                result = asyncio.run(self.run_health_test())
                st.session_state.health_result = result
        
        if st.sidebar.button("📋 Service Info"):
            with st.spinner("Testing service info..."):
                result = asyncio.run(self.run_info_test())
                st.session_state.info_result = result
        
        if st.sidebar.button("🔌 SSE Endpoint"):
            with st.spinner("Testing SSE endpoint..."):
                result = asyncio.run(self.run_sse_test())
                st.session_state.sse_result = result
        
        if st.sidebar.button("🛠️ MCP Tools"):
            with st.spinner("Testing MCP tools..."):
                result = asyncio.run(self.run_tools_test())
                st.session_state.tools_result = result
        
        if st.sidebar.button("⚡ Performance"):
            with st.spinner("Testing performance..."):
                result = asyncio.run(self.run_performance_test())
                st.session_state.performance_result = result
        
        # Main content
        if "last_test_results" in st.session_state:
            self.render_test_results(st.session_state.last_test_results)
        else:
            self.render_welcome_screen()
        
        # Auto-refresh
        if auto_refresh:
            time.sleep(30)
            st.rerun()
    
    def render_test_results(self, results: List[UITestResult]):
        """Render test results"""
        st.header("📊 Test Results")
        
        # Summary metrics
        passed = len([r for r in results if r.status == "PASSED"])
        failed = len([r for r in results if r.status == "FAILED"])
        total = len(results)
        success_rate = (passed / total * 100) if total > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📈 Total Tests", total)
        
        with col2:
            st.metric("✅ Passed", passed)
        
        with col3:
            st.metric("❌ Failed", failed)
        
        with col4:
            st.metric("📊 Success Rate", f"{success_rate:.1f}%")
        
        # Progress bar
        if total > 0:
            st.progress(passed / total, text=f"Test Progress: {passed}/{total}")
        
        # Test details
        st.subheader("📋 Test Details")
        
        for result in results:
            status_emoji = "✅" if result.status == "PASSED" else "❌"
            
            with st.expander(f"{status_emoji} {result.test_name}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Status:** {result.status}")
                    st.write(f"**Response Time:** {result.response_time:.3f}s")
                    st.write(f"**Timestamp:** {result.timestamp}")
                
                with col2:
                    st.write(f"**Details:** {result.details}")
                    if result.error_message:
                        st.error(f"**Error:** {result.error_message}")
        
        # Performance chart
        self.render_performance_chart(results)
        
        # Test history
        if len(self.test_history) > 0:
            self.render_test_history()
    
    def render_performance_chart(self, results: List[UITestResult]):
        """Render performance chart"""
        st.subheader("⚡ Performance Metrics")
        
        test_names = [r.test_name for r in results]
        response_times = [r.response_time for r in results]
        statuses = [r.status for r in results]
        
        colors = ['green' if status == 'PASSED' else 'red' for status in statuses]
        
        fig = go.Figure(data=[
            go.Bar(
                x=test_names,
                y=response_times,
                marker_color=colors,
                text=[f"{rt:.3f}s" for rt in response_times],
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            title="Response Times by Test",
            xaxis_title="Test",
            yaxis_title="Response Time (seconds)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def render_test_history(self):
        """Render test history"""
        st.subheader("📈 Test History")
        
        if len(self.test_history) > 0:
            # Group by test name
            test_groups = {}
            for result in self.test_history:
                if result.test_name not in test_groups:
                    test_groups[result.test_name] = []
                test_groups[result.test_name].append(result)
            
            # Create timeline chart
            fig = go.Figure()
            
            for test_name, test_results in test_groups.items():
                timestamps = [r.timestamp for r in test_results]
                response_times = [r.response_time for r in test_results]
                statuses = [1 if r.status == 'PASSED' else 0 for r in test_results]
                
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=response_times,
                    mode='lines+markers',
                    name=test_name,
                    line=dict(width=2),
                    marker=dict(size=8)
                ))
            
            fig.update_layout(
                title="Response Time History",
                xaxis_title="Time",
                yaxis_title="Response Time (seconds)",
                height=400,
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def render_welcome_screen(self):
        """Render welcome screen"""
        st.header("🎯 Welcome to MCP Server UI Test Dashboard")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🧪 Test Categories", 5)
            st.info("Health, Info, SSE, Tools, Performance")
        
        with col2:
            st.metric("🌐 Server Status", "Unknown")
            st.info("Run tests to check server status")
        
        with col3:
            st.metric("⚡ Last Run", "Never")
            st.info("Click 'Run All Tests' to start")
        
        st.markdown("### 🚀 Getting Started")
        st.markdown("""
        1. **Configure Server URL** - Use the sidebar to set your MCP server URL
        2. **Run Tests** - Click 'Run All Tests' or individual test buttons
        3. **View Results** - Check detailed results and performance metrics
        4. **Monitor History** - Track performance over time
        """)
        
        st.markdown("### 📋 Available Tests")
        
        tests_info = {
            "Health Check": "Tests the /health endpoint for server status",
            "Service Info": "Tests the /info endpoint for service details",
            "SSE Endpoint": "Tests the /sse endpoint for Server-Sent Events",
            "MCP Tools": "Verifies all MCP tools are available",
            "Performance": "Tests response times and performance metrics"
        }
        
        for test_name, description in tests_info.items():
            with st.expander(f"🔧 {test_name}"):
                st.write(description)


def main():
    """Main function to run the dashboard"""
    dashboard = MCPUITestDashboard()
    dashboard.render_dashboard()


if __name__ == "__main__":
    main()
