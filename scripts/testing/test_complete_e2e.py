#!/usr/bin/env python3
"""
Complete End-to-End Test for ARIS System
Tests all major components and integrations
"""
import os
import sys
import time
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print('='*60)

def print_test(name, status, details=""):
    """Print test result"""
    status_emoji = "✅" if status else "❌"
    print(f"{status_emoji} {name}")
    if details:
        print(f"   {details}")

def test_environment():
    """Test environment setup"""
    print_section("ENVIRONMENT SETUP")
    
    tests_passed = 0
    total_tests = 0
    
    # Test Python version
    total_tests += 1
    python_version = sys.version_info
    if python_version.major >= 3 and python_version.minor >= 8:
        print_test("Python Version", True, f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")
        tests_passed += 1
    else:
        print_test("Python Version", False, f"Python {python_version.major}.{python_version.minor} (need 3.8+)")
    
    # Test project structure
    total_tests += 1
    required_dirs = ["tests", "services", "api", "shared"]
    missing_dirs = []
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            missing_dirs.append(dir_name)
    
    if not missing_dirs:
        print_test("Project Structure", True, "All required directories present")
        tests_passed += 1
    else:
        print_test("Project Structure", False, f"Missing: {missing_dirs}")
    
    # Test environment variables
    total_tests += 1
    required_env_vars = ["OPENAI_API_KEY", "AWS_OPENSEARCH_ACCESS_KEY_ID", "AWS_OPENSEARCH_SECRET_ACCESS_KEY"]
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if not missing_vars:
        print_test("Environment Variables", True, "All required credentials available")
        tests_passed += 1
    else:
        print_test("Environment Variables", False, f"Missing: {missing_vars}")
    
    return tests_passed, total_tests

def test_dependencies():
    """Test Python dependencies"""
    print_section("DEPENDENCIES CHECK")
    
    tests_passed = 0
    total_tests = 0
    
    # Core dependencies
    dependencies = {
        "pytest": "Testing framework",
        "httpx": "HTTP client",
        "fastapi": "API framework", 
        "streamlit": "UI framework",
        "pandas": "Data processing",
        "plotly": "Visualization"
    }
    
    for dep, desc in dependencies.items():
        total_tests += 1
        try:
            __import__(dep)
            print_test(f"{dep} Import", True, desc)
            tests_passed += 1
        except ImportError:
            print_test(f"{dep} Import", False, f"{desc} - MISSING")
    
    return tests_passed, total_tests

def test_mcp_engine():
    """Test MCP Engine functionality"""
    print_section("MCP ENGINE TESTING")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        
        # Test engine initialization
        total_tests += 1
        print_test("MCP Engine Import", True, "Engine initialized successfully")
        tests_passed += 1
        
        # Test utility functions
        total_tests += 1
        if engine.is_s3_uri("s3://bucket/file.pdf") and not engine.is_s3_uri("plain text"):
            print_test("S3 URI Detection", True, "S3 URI parsing works")
            tests_passed += 1
        else:
            print_test("S3 URI Detection", False, "S3 URI parsing failed")
        
        # Test language conversion
        total_tests += 1
        if engine.convert_language_code("en") == "eng" and engine.convert_language_code("es") == "spa":
            print_test("Language Conversion", True, "Language code conversion works")
            tests_passed += 1
        else:
            print_test("Language Conversion", False, "Language code conversion failed")
        
        # Test document ID generation
        total_tests += 1
        doc_id = engine.generate_document_id("test content", "test_source")
        if doc_id.startswith("doc-") and len(doc_id) > 10:
            print_test("Document ID Generation", True, f"Generated: {doc_id}")
            tests_passed += 1
        else:
            print_test("Document ID Generation", False, "Invalid document ID format")
        
    except Exception as e:
        total_tests += 5
        print_test("MCP Engine Tests", False, f"Engine failed: {e}")
    
    return tests_passed, total_tests

def test_server_connectivity():
    """Test server connectivity"""
    print_section("SERVER CONNECTIVITY")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        import requests
        from requests_aws4auth import AWS4Auth
        
        # OpenSearch configuration
        server_domain = "search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com"
        base_url = f"https://{server_domain}"
        
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        if access_key and secret_key:
            # Test cluster health
            total_tests += 1
            try:
                awsauth = AWS4Auth(access_key, secret_key, region, 'es')
                response = requests.get(f"{base_url}/_cluster/health", auth=awsauth, timeout=10)
                
                if response.status_code == 200:
                    health = response.json()
                    status = health.get('status', 'unknown')
                    nodes = health.get('number_of_nodes', 0)
                    print_test("OpenSearch Health", True, f"Status: {status}, Nodes: {nodes}")
                    tests_passed += 1
                else:
                    print_test("OpenSearch Health", False, f"HTTP {response.status_code}")
            except Exception as e:
                print_test("OpenSearch Health", False, f"Connection failed: {e}")
            
            # Test indices
            total_tests += 1
            try:
                response = requests.get(f"{base_url}/_cat/indices?format=json", auth=awsauth, timeout=10)
                
                if response.status_code == 200:
                    indices = response.json()
                    aris_indices = [idx for idx in indices if 'aris-rag' in idx['index']]
                    print_test("OpenSearch Indices", True, f"Found {len(indices)} indices, {len(aris_indices)} ARIS indices")
                    tests_passed += 1
                else:
                    print_test("OpenSearch Indices", False, f"HTTP {response.status_code}")
            except Exception as e:
                print_test("OpenSearch Indices", False, f"Failed to list indices: {e}")
        else:
            total_tests += 2
            print_test("AWS Credentials", False, "Missing OpenSearch credentials")
        
    except ImportError as e:
        total_tests += 2
        print_test("Server Dependencies", False, f"Missing dependencies: {e}")
    
    return tests_passed, total_tests

def test_test_infrastructure():
    """Test testing infrastructure"""
    print_section("TEST INFRASTRUCTURE")
    
    tests_passed = 0
    total_tests = 0
    
    # Test pytest configuration
    total_tests += 1
    pytest_ini = Path("pytest.ini")
    if pytest_ini.exists():
        print_test("Pytest Configuration", True, "pytest.ini found")
        tests_passed += 1
    else:
        print_test("Pytest Configuration", False, "pytest.ini missing")
    
    # Test test files
    total_tests += 1
    test_files = list(Path("tests").glob("**/test_*.py"))
    if len(test_files) > 0:
        print_test("Test Files", True, f"Found {len(test_files)} test files")
        tests_passed += 1
    else:
        print_test("Test Files", False, "No test files found")
    
    # Test specific test categories
    categories = {
        "E2E Tests": "tests/e2e/",
        "MCP Tests": "tests/mcp/",
        "Unit Tests": "tests/unit/",
        "Integration Tests": "tests/integration/"
    }
    
    for category, path in categories.items():
        total_tests += 1
        if Path(path).exists():
            category_tests = list(Path(path).glob("**/test_*.py"))
            print_test(category, True, f"{len(category_tests)} test files")
            tests_passed += 1
        else:
            print_test(category, False, f"Directory {path} not found")
    
    return tests_passed, total_tests

def test_dashboard_setup():
    """Test test dashboard setup"""
    print_section("TEST DASHBOARD")
    
    tests_passed = 0
    total_tests = 0
    
    # Test dashboard directory
    total_tests += 1
    dashboard_dir = Path("test_dashboard")
    if dashboard_dir.exists():
        print_test("Dashboard Directory", True, "test_dashboard directory exists")
        tests_passed += 1
        
        # Test dashboard files
        dashboard_files = ["app.py", "requirements.txt", "run_dashboard.py"]
        for file_name in dashboard_files:
            total_tests += 1
            file_path = dashboard_dir / file_name
            if file_path.exists():
                print_test(f"Dashboard {file_name}", True, f"{file_name} found")
                tests_passed += 1
            else:
                print_test(f"Dashboard {file_name}", False, f"{file_name} missing")
    else:
        print_test("Dashboard Directory", False, "test_dashboard directory not found")
    
    return tests_passed, total_tests

def run_sample_tests():
    """Run sample tests to verify functionality"""
    print_section("SAMPLE TEST EXECUTION")
    
    tests_passed = 0
    total_tests = 0
    
    # Run a quick MCP test
    total_tests += 1
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/mcp/test_mcp_server.py::TestMCPTools::test_mcp_engine_import",
            "-v", "--tb=no"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print_test("MCP Engine Test", True, "MCP engine import test passed")
            tests_passed += 1
        else:
            print_test("MCP Engine Test", False, f"Test failed with return code {result.returncode}")
    except subprocess.TimeoutExpired:
        print_test("MCP Engine Test", False, "Test timed out")
    except Exception as e:
        print_test("MCP Engine Test", False, f"Test execution failed: {e}")
    
    # Run a quick server test
    total_tests += 1
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/e2e/test_server_sync.py::TestServerSanityChecks::test_credentials_available",
            "-v", "--tb=no"
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print_test("Server Sanity Test", True, "Server credentials test passed")
            tests_passed += 1
        else:
            print_test("Server Sanity Test", False, f"Test failed with return code {result.returncode}")
    except subprocess.TimeoutExpired:
        print_test("Server Sanity Test", False, "Test timed out")
    except Exception as e:
        print_test("Server Sanity Test", False, f"Test execution failed: {e}")
    
    return tests_passed, total_tests

async def main():
    """Run complete E2E test"""
    print("🚀 ARIS COMPLETE END-TO-END TEST")
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Run all test suites
    all_passed = 0
    all_total = 0
    
    # Environment tests
    passed, total = test_environment()
    all_passed += passed
    all_total += total
    
    # Dependency tests
    passed, total = test_dependencies()
    all_passed += passed
    all_total += total
    
    # MCP Engine tests
    passed, total = test_mcp_engine()
    all_passed += passed
    all_total += total
    
    # Server connectivity tests
    passed, total = test_server_connectivity()
    all_passed += passed
    all_total += total
    
    # Test infrastructure tests
    passed, total = test_test_infrastructure()
    all_passed += passed
    all_total += total
    
    # Dashboard setup tests
    passed, total = test_dashboard_setup()
    all_passed += passed
    all_total += total
    
    # Sample test execution
    passed, total = run_sample_tests()
    all_passed += passed
    all_total += total
    
    # Final summary
    print_section("FINAL RESULTS")
    
    success_rate = (all_passed / all_total * 100) if all_total > 0 else 0
    
    print(f"📊 Overall Results: {all_passed}/{all_total} tests passed ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("🎉 EXCELLENT: Your ARIS system is working perfectly!")
    elif success_rate >= 75:
        print("✅ GOOD: Your ARIS system is working well with minor issues")
    elif success_rate >= 50:
        print("⚠️ FAIR: Your ARIS system has some issues that need attention")
    else:
        print("❌ POOR: Your ARIS system has significant issues")
    
    print(f"\n🕐 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Recommendations
    print_section("RECOMMENDATIONS")
    
    if success_rate >= 90:
        print("🚀 Your system is ready for production!")
        print("📊 Start the test dashboard: python test_dashboard/run_dashboard.py")
        print("🧪 Run full test suite: pytest tests/ -v")
    else:
        print("🔧 Address the failed tests above")
        print("📋 Check missing dependencies")
        print("🌐 Verify server connectivity")
        print("⚙️ Review configuration files")
    
    return success_rate

if __name__ == "__main__":
    asyncio.run(main())
