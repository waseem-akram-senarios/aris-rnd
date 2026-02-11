#!/usr/bin/env python3
"""
Complete MCP Server End-to-End Test
Tests MCP server functionality from engine to endpoints
"""
import os
import sys
import asyncio
import httpx
import json
import time
import tempfile
import base64
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(str(Path(__file__).parent))

def print_section(title):
    """Print section header"""
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print('='*60)

def print_test(name, status, details=""):
    """Print test result"""
    status_emoji = "✅" if status else "❌"
    print(f"{status_emoji} {name}")
    if details:
        print(f"   {details}")

def test_mcp_dependencies():
    """Test MCP server dependencies"""
    print_section("MCP DEPENDENCIES CHECK")
    
    tests_passed = 0
    total_tests = 0
    
    # Core MCP dependencies
    dependencies = {
        "fastmcp": "MCP Framework",
        "fastapi": "API Framework",
        "httpx": "HTTP Client",
        "dotenv": "Environment Management"
    }
    
    for dep, desc in dependencies.items():
        total_tests += 1
        try:
            if dep == "dotenv":
                import dotenv
            else:
                __import__(dep)
            print_test(f"{dep} Import", True, desc)
            tests_passed += 1
        except ImportError:
            print_test(f"{dep} Import", False, f"{desc} - MISSING")
    
    return tests_passed, total_tests

def test_mcp_engine_core():
    """Test MCP engine core functionality"""
    print_section("MCP ENGINE CORE TESTING")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        
        # Test engine initialization
        total_tests += 1
        print_test("Engine Initialization", True, "MCPEngine created successfully")
        tests_passed += 1
        
        # Test HTTP client
        total_tests += 1
        client = engine.http_client
        if client and hasattr(client, 'post'):
            print_test("HTTP Client", True, "HTTP client initialized")
            tests_passed += 1
        else:
            print_test("HTTP Client", False, "HTTP client not properly initialized")
        
        # Test document registry
        total_tests += 1
        registry = engine.document_registry
        if registry:
            print_test("Document Registry", True, "Registry initialized (cached)")
            tests_passed += 1
        else:
            print_test("Document Registry", False, "Registry initialization failed")
        
        # Test sync manager
        total_tests += 1
        sync_manager = engine.sync_manager
        if sync_manager:
            print_test("Sync Manager", True, "Sync manager available")
            tests_passed += 1
        else:
            print_test("Sync Manager", False, "Sync manager not available")
        
    except Exception as e:
        total_tests += 4
        print_test("Engine Core Tests", False, f"Engine failed: {e}")
    
    return tests_passed, total_tests

def test_mcp_utilities():
    """Test MCP utility functions"""
    print_section("MCP UTILITY FUNCTIONS")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        
        # Test S3 URI detection
        total_tests += 1
        s3_tests = [
            ("s3://bucket/file.pdf", True),
            ("s3a://bucket/file.pdf", True), 
            ("https://example.com/file.pdf", False),
            ("plain text", False),
            ("", False)
        ]
        
        all_s3_passed = True
        for uri, expected in s3_tests:
            result = engine.is_s3_uri(uri)
            if result != expected:
                all_s3_passed = False
                break
        
        if all_s3_passed:
            print_test("S3 URI Detection", True, "All S3 URI tests passed")
            tests_passed += 1
        else:
            print_test("S3 URI Detection", False, "S3 URI detection failed")
        
        # Test S3 URI parsing
        total_tests += 1
        try:
            bucket, key = engine.parse_s3_uri("s3://my-bucket/path/to/document.pdf")
            if bucket == "my-bucket" and key == "path/to/document.pdf":
                print_test("S3 URI Parsing", True, "S3 URI parsing works correctly")
                tests_passed += 1
            else:
                print_test("S3 URI Parsing", False, f"Expected bucket='my-bucket', got='{bucket}'")
        except Exception as e:
            print_test("S3 URI Parsing", False, f"Parse error: {e}")
        
        # Test language code conversion
        total_tests += 1
        lang_tests = [
            ("en", "eng"),
            ("es", "spa"),
            ("de", "deu"),
            ("eng", "eng"),  # Already 3-letter
            ("spa", "spa")   # Already 3-letter
        ]
        
        all_lang_passed = True
        for input_lang, expected in lang_tests:
            result = engine.convert_language_code(input_lang)
            if result != expected:
                all_lang_passed = False
                break
        
        if all_lang_passed:
            print_test("Language Conversion", True, "All language code tests passed")
            tests_passed += 1
        else:
            print_test("Language Conversion", False, "Language code conversion failed")
        
        # Test document ID generation
        total_tests += 1
        doc_id1 = engine.generate_document_id("test content", "test_source")
        doc_id2 = engine.generate_document_id("test content", "test_source")
        
        if doc_id1.startswith("doc-") and len(doc_id1) > 10 and doc_id1 != doc_id2:
            print_test("Document ID Generation", True, f"Generated unique IDs: {doc_id1[:20]}...")
            tests_passed += 1
        else:
            print_test("Document ID Generation", False, "Document ID generation failed")
        
        # Test confidence scoring
        total_tests += 1
        confidence1 = engine.calculate_confidence_score(0, 10, 0.95)
        confidence2 = engine.calculate_confidence_score(5, 10, 0.80)
        
        if 0 <= confidence1 <= 100 and 0 <= confidence2 <= 100 and confidence1 > confidence2:
            print_test("Confidence Scoring", True, f"High rank: {confidence1}, Low rank: {confidence2}")
            tests_passed += 1
        else:
            print_test("Confidence Scoring", False, "Confidence scoring logic failed")
        
        # Test base64 detection
        total_tests += 1
        base64_content = base64.b64encode(b"test content").decode()
        plain_content = "This is plain text content"
        
        if engine.is_base64(base64_content) and not engine.is_base64(plain_content):
            print_test("Base64 Detection", True, "Base64 and plain text correctly identified")
            tests_passed += 1
        else:
            print_test("Base64 Detection", False, "Base64 detection failed")
        
    except Exception as e:
        total_tests += 6
        print_test("Utility Functions", False, f"Utility tests failed: {e}")
    
    return tests_passed, total_tests

def test_mcp_tools_mocked():
    """Test MCP tools with mocked HTTP calls"""
    print_section("MCP TOOLS (MOCKED HTTP)")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        
        # Test ingestion tool
        total_tests += 1
        with patch.object(engine, '_call_ingestion_service') as mock_ingest:
            mock_ingest.return_value = {
                "document_id": "test-doc-123",
                "chunks_created": 2,
                "tokens_extracted": 15,
                "message": "Successfully ingested content"
            }
            
            with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                mock_sync.return_value = True
                
                result = engine.ingest("This is test content for ingestion", {"source": "test"})
                
                if (result["success"] == True and 
                    result["document_id"] == "test-doc-123" and
                    result["chunks_created"] == 2 and
                    result["sync_triggered"] == True):
                    print_test("Ingestion Tool", True, "Document ingestion works (mocked)")
                    tests_passed += 1
                else:
                    print_test("Ingestion Tool", False, "Ingestion tool returned unexpected results")
        
        # Test search tool
        total_tests += 1
        with patch.object(engine, '_call_retrieval_service') as mock_retrieval:
            mock_retrieval.return_value = {
                "answer": "This is a test answer",
                "citations": [
                    {
                        "source": "test_document.pdf",
                        "page": 1,
                        "snippet": "This is a relevant snippet",
                        "full_text": "This is the full text content",
                        "similarity_score": 0.95
                    }
                ],
                "sources": ["test_document.pdf"]
            }
            
            result = engine.search("test query", k=5, search_mode="hybrid")
            
            if (result["success"] == True and
                result["query"] == "test query" and
                result["answer"] == "This is a test answer" and
                len(result["results"]) == 1):
                print_test("Search Tool", True, "Document search works (mocked)")
                tests_passed += 1
            else:
                print_test("Search Tool", False, "Search tool returned unexpected results")
        
        # Test document upload tool
        total_tests += 1
        with patch.object(engine, '_call_ingestion_service') as mock_ingest:
            mock_ingest.return_value = {
                "document_id": "upload-doc-123",
                "chunks_created": 1,
                "tokens_extracted": 8,
                "message": "Successfully uploaded document"
            }
            
            with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                mock_sync.return_value = True
                
                result = engine.upload_document("This is test document content", "test.txt")
                
                if (result["success"] == True and
                    result["filename"] == "test.txt" and
                    result["file_type"] == "txt" and
                    result["chunks_created"] == 1):
                    print_test("Document Upload Tool", True, "Document upload works (mocked)")
                    tests_passed += 1
                else:
                    print_test("Document Upload Tool", False, "Upload tool returned unexpected results")
        
    except Exception as e:
        total_tests += 3
        print_test("MCP Tools (Mocked)", False, f"Tool tests failed: {e}")
    
    return tests_passed, total_tests

def test_mcp_service_integration():
    """Test MCP service integration"""
    print_section("MCP SERVICE INTEGRATION")
    
    tests_passed = 0
    total_tests = 0
    
    try:
        from services.mcp.engine import INGESTION_SERVICE_URL, RETRIEVAL_SERVICE_URL, GATEWAY_URL
        
        # Test service URLs
        total_tests += 1
        expected_urls = {
            "INGESTION_SERVICE_URL": ("http://ingestion:8501", INGESTION_SERVICE_URL),
            "RETRIEVAL_SERVICE_URL": ("http://retrieval:8502", RETRIEVAL_SERVICE_URL),
            "GATEWAY_URL": ("http://gateway:8500", GATEWAY_URL)
        }
        
        all_urls_correct = True
        for name, (expected, actual) in expected_urls.items():
            if actual != expected:
                all_urls_correct = False
                break
        
        if all_urls_correct:
            print_test("Service URLs", True, "All service URLs configured correctly")
            tests_passed += 1
        else:
            print_test("Service URLs", False, "Service URLs not configured correctly")
        
        # Test HTTP client initialization
        total_tests += 1
        from services.mcp.engine import _get_http_client
        client = _get_http_client()
        
        if client and hasattr(client, 'post') and hasattr(client, 'get'):
            print_test("HTTP Client Pool", True, "HTTP client with connection pooling initialized")
            tests_passed += 1
        else:
            print_test("HTTP Client Pool", False, "HTTP client initialization failed")
        
        # Test document registry caching
        total_tests += 1
        from services.mcp.engine import _get_cached_document_registry
        
        registry1 = _get_cached_document_registry()
        registry2 = _get_cached_document_registry()
        
        if registry1 is registry2:
            print_test("Document Registry Cache", True, "Singleton caching working")
            tests_passed += 1
        else:
            print_test("Document Registry Cache", False, "Caching not working properly")
        
    except Exception as e:
        total_tests += 3
        print_test("Service Integration", False, f"Integration tests failed: {e}")
    
    return tests_passed, total_tests

async def test_mcp_server_endpoints():
    """Test MCP server endpoints (if running)"""
    print_section("MCP SERVER ENDPOINTS")
    
    tests_passed = 0
    total_tests = 0
    
    MCP_SERVER_URL = "http://localhost:8503"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test health endpoint
        total_tests += 1
        try:
            response = await client.get(f"{MCP_SERVER_URL}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                if "status" in health_data:
                    print_test("Health Endpoint", True, f"Status: {health_data['status']}")
                    tests_passed += 1
                else:
                    print_test("Health Endpoint", False, "Health endpoint missing status field")
            else:
                print_test("Health Endpoint", False, f"HTTP {response.status_code}")
        except httpx.ConnectError:
            print_test("Health Endpoint", False, "Server not running on port 8503")
        except Exception as e:
            print_test("Health Endpoint", False, f"Error: {e}")
        
        # Test info endpoint
        total_tests += 1
        try:
            response = await client.get(f"{MCP_SERVER_URL}/info")
            
            if response.status_code == 200:
                info_data = response.json()
                if "name" in info_data and "tools" in info_data:
                    print_test("Info Endpoint", True, f"Server: {info_data['name']}, Tools: {len(info_data['tools'])}")
                    tests_passed += 1
                else:
                    print_test("Info Endpoint", False, "Info endpoint missing required fields")
            else:
                print_test("Info Endpoint", False, f"HTTP {response.status_code}")
        except httpx.ConnectError:
            print_test("Info Endpoint", False, "Server not running on port 8503")
        except Exception as e:
            print_test("Info Endpoint", False, f"Error: {e}")
        
        # Test SSE endpoint
        total_tests += 1
        try:
            response = await client.get(f"{MCP_SERVER_URL}/sse")
            
            if response.status_code in [200, 405]:  # 405 if GET not allowed for SSE
                print_test("SSE Endpoint", True, f"Accessible (HTTP {response.status_code})")
                tests_passed += 1
            else:
                print_test("SSE Endpoint", False, f"HTTP {response.status_code}")
        except httpx.ConnectError:
            print_test("SSE Endpoint", False, "Server not running on port 8503")
        except Exception as e:
            print_test("SSE Endpoint", False, f"Error: {e}")
    
    return tests_passed, total_tests

def test_mcp_server_import():
    """Test MCP server import and basic setup"""
    print_section("MCP SERVER IMPORT")
    
    tests_passed = 0
    total_tests = 0
    
    # Test FastMCP import
    total_tests += 1
    try:
        from fastmcp import FastMCP
        print_test("FastMCP Import", True, "FastMCP library available")
        tests_passed += 1
    except ImportError:
        print_test("FastMCP Import", False, "FastMCP not installed")
    
    # Test MCP main import
    total_tests += 1
    try:
        # Try to import the main module
        sys.path.append(str(Path(__file__).parent / "services" / "mcp"))
        
        # Check if main.py exists and is readable
        main_file = Path("services/mcp/main.py")
        if main_file.exists() and main_file.is_file():
            with open(main_file, 'r') as f:
                content = f.read()
                if "FastMCP" in content and "MCPEngine" in content:
                    print_test("MCP Main Module", True, "main.py contains FastMCP and MCPEngine")
                    tests_passed += 1
                else:
                    print_test("MCP Main Module", False, "main.py missing required components")
        else:
            print_test("MCP Main Module", False, "main.py not found")
    except Exception as e:
        print_test("MCP Main Module", False, f"Import error: {e}")
    
    return tests_passed, total_tests

def test_mcp_configuration():
    """Test MCP configuration"""
    print_section("MCP CONFIGURATION")
    
    tests_passed = 0
    total_tests = 0
    
    # Test environment variables
    total_tests += 1
    required_vars = [
        'OPENAI_API_KEY',
        'AWS_OPENSEARCH_ACCESS_KEY_ID',
        'AWS_OPENSEARCH_SECRET_ACCESS_KEY',
        'AWS_OPENSEARCH_REGION'
    ]
    
    missing_vars = []
    available_vars = []
    
    for var in required_vars:
        if os.getenv(var):
            available_vars.append(var)
        else:
            missing_vars.append(var)
    
    if len(available_vars) >= 2:  # At least OpenAI and one AWS key
        print_test("Environment Variables", True, f"Available: {len(available_vars)}/{len(required_vars)}")
        tests_passed += 1
    else:
        print_test("Environment Variables", False, f"Missing critical variables: {missing_vars}")
    
    # Test service configuration
    total_tests += 1
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        
        # Check if engine has required properties
        required_props = ['http_client', 'document_registry', 'sync_manager']
        missing_props = []
        
        for prop in required_props:
            if not hasattr(engine, prop):
                missing_props.append(prop)
        
        if not missing_props:
            print_test("Engine Configuration", True, "All required properties available")
            tests_passed += 1
        else:
            print_test("Engine Configuration", False, f"Missing properties: {missing_props}")
    except Exception as e:
        print_test("Engine Configuration", False, f"Configuration check failed: {e}")
    
    return tests_passed, total_tests

async def main():
    """Run complete MCP E2E test"""
    print("🚀 MCP SERVER COMPLETE END-TO-END TEST")
    print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Run all test suites
    all_passed = 0
    all_total = 0
    
    # Dependencies test
    passed, total = test_mcp_dependencies()
    all_passed += passed
    all_total += total
    
    # Engine core test
    passed, total = test_mcp_engine_core()
    all_passed += passed
    all_total += total
    
    # Utilities test
    passed, total = test_mcp_utilities()
    all_passed += passed
    all_total += total
    
    # Tools test (mocked)
    passed, total = test_mcp_tools_mocked()
    all_passed += passed
    all_total += total
    
    # Service integration test
    passed, total = test_mcp_service_integration()
    all_passed += passed
    all_total += total
    
    # Server import test
    passed, total = test_mcp_server_import()
    all_passed += passed
    all_total += total
    
    # Configuration test
    passed, total = test_mcp_configuration()
    all_passed += passed
    all_total += total
    
    # Server endpoints test (async)
    passed, total = await test_mcp_server_endpoints()
    all_passed += passed
    all_total += total
    
    # Final summary
    print_section("FINAL MCP RESULTS")
    
    success_rate = (all_passed / all_total * 100) if all_total > 0 else 0
    
    print(f"📊 MCP Results: {all_passed}/{all_total} tests passed ({success_rate:.1f}%)")
    
    if success_rate >= 90:
        print("🎉 EXCELLENT: MCP server is working perfectly!")
    elif success_rate >= 75:
        print("✅ GOOD: MCP server is working well with minor issues")
    elif success_rate >= 50:
        print("⚠️ FAIR: MCP server has some issues that need attention")
    else:
        print("❌ POOR: MCP server has significant issues")
    
    print(f"\n🕐 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Recommendations
    print_section("MCP RECOMMENDATIONS")
    
    if success_rate >= 90:
        print("🚀 Your MCP server is ready for production!")
        print("📝 Start the MCP server: python services/mcp/main.py")
        print("🧪 Run MCP tests: pytest tests/mcp/ -v -m mcp")
        print("📊 Monitor with dashboard: python test_dashboard/run_dashboard.py")
    else:
        print("🔧 Address the failed tests above")
        print("📋 Check missing dependencies")
        print("⚙️ Review configuration files")
        print("🌐 Verify service connectivity")
    
    return success_rate

if __name__ == "__main__":
    asyncio.run(main())
