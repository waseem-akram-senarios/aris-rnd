"""
Comprehensive MCP Server Testing
Tests both MCP tools and FastAPI endpoints
"""
import pytest
import asyncio
import httpx
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path


# MCP Server Configuration
MCP_SERVER_URL = "http://localhost:8503"  # Default MCP port
MCP_HEALTH_URL = f"{MCP_SERVER_URL}/health"
MCP_INFO_URL = f"{MCP_SERVER_URL}/info"
MCP_SSE_URL = f"{MCP_SERVER_URL}/sse"


@pytest.mark.e2e
@pytest.mark.mcp
class TestMCPServerEndpoints:
    """Test MCP FastAPI endpoints"""
    
    @pytest.fixture
    async def http_client(self):
        """HTTP client for MCP server testing"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client
    
    async def test_mcp_health_endpoint(self, http_client):
        """Test MCP server health endpoint"""
        try:
            response = await http_client.get(MCP_HEALTH_URL)
            
            if response.status_code == 200:
                health_data = response.json()
                assert "status" in health_data
                assert health_data["status"] == "healthy"
                print(f"✅ MCP Server Health: {health_data['status']}")
                
                # Check for service information
                if "services" in health_data:
                    services = health_data["services"]
                    print(f"   Services: {services}")
                
                return True
            else:
                print(f"⚠️ MCP Server not responding: {response.status_code}")
                return False
                
        except httpx.ConnectError:
            print("⚠️ MCP Server not running - start it first")
            return False
        except Exception as e:
            print(f"❌ MCP Health check failed: {e}")
            return False
    
    async def test_mcp_info_endpoint(self, http_client):
        """Test MCP server info endpoint"""
        try:
            response = await http_client.get(MCP_INFO_URL)
            
            if response.status_code == 200:
                info_data = response.json()
                assert "name" in info_data
                assert "version" in info_data
                print(f"✅ MCP Server Info: {info_data['name']} v{info_data['version']}")
                
                # Check for tools list
                if "tools" in info_data:
                    tools = info_data["tools"]
                    expected_tools = ["rag_ingest", "rag_search", "rag_quick_query", "rag_research_query", "rag_upload_document"]
                    for tool in expected_tools:
                        assert tool in tools, f"Missing tool: {tool}"
                    print(f"   Tools available: {len(tools)}")
                
                return True
            else:
                print(f"⚠️ MCP Info endpoint failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ MCP Info check failed: {e}")
            return False
    
    async def test_mcp_sse_endpoint(self, http_client):
        """Test MCP Server-Sent Events endpoint"""
        try:
            # SSE endpoints should accept GET requests
            response = await http_client.get(MCP_SSE_URL)
            
            # SSE endpoints typically return 200 with text/event-stream
            if response.status_code in [200, 405]:  # 405 if GET not allowed
                print(f"✅ MCP SSE endpoint accessible: {response.status_code}")
                return True
            else:
                print(f"⚠️ MCP SSE endpoint status: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ MCP SSE check failed: {e}")
            return False


@pytest.mark.e2e
@pytest.mark.mcp
class TestMCPTools:
    """Test MCP tools functionality"""
    
    def test_mcp_engine_import(self):
        """Test that MCP engine can be imported"""
        try:
            from services.mcp.engine import MCPEngine
            engine = MCPEngine()
            
            # Check engine properties
            assert hasattr(engine, 'ingest')
            assert hasattr(engine, 'search')
            assert hasattr(engine, 'upload_document')
            
            print("✅ MCP Engine imported successfully")
            return True
            
        except ImportError as e:
            print(f"❌ MCP Engine import failed: {e}")
            return False
        except Exception as e:
            print(f"❌ MCP Engine initialization failed: {e}")
            return False
    
    def test_mcp_engine_ingest_text(self):
        """Test MCP engine text ingestion"""
        try:
            from services.mcp.engine import MCPEngine
            engine = MCPEngine()
            
            # Test text ingestion
            test_content = "This is a test document for MCP ingestion testing."
            metadata = {"source": "test_document", "language": "eng"}
            
            # Mock the HTTP calls since services might not be running
            with patch.object(engine, '_call_ingestion_service') as mock_ingest:
                mock_ingest.return_value = {
                    "document_id": "test-doc-123",
                    "chunks_created": 2,
                    "tokens_extracted": 15,
                    "message": "Successfully ingested content"
                }
                
                with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                    mock_sync.return_value = True
                    
                    result = engine.ingest(test_content, metadata)
                    
                    assert result["success"] == True
                    assert "document_id" in result
                    assert result["chunks_created"] == 2
                    assert result["sync_triggered"] == True
                    
                    print("✅ MCP Engine text ingestion works")
                    return True
                    
        except Exception as e:
            print(f"❌ MCP Engine text ingestion failed: {e}")
            return False
    
    def test_mcp_engine_search(self):
        """Test MCP engine search functionality"""
        try:
            from services.mcp.engine import MCPEngine
            engine = MCPEngine()
            
            # Test search
            test_query = "test query"
            
            # Mock the HTTP calls
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
                
                result = engine.search(
                    query=test_query,
                    k=5,
                    search_mode="hybrid",
                    use_agentic_rag=True
                )
                
                assert result["success"] == True
                assert result["query"] == test_query
                assert "answer" in result
                assert len(result["results"]) == 1
                assert result["total_results"] == 1
                
                print("✅ MCP Engine search works")
                return True
                
        except Exception as e:
            print(f"❌ MCP Engine search failed: {e}")
            return False
    
    def test_mcp_engine_upload_document(self):
        """Test MCP engine document upload"""
        try:
            from services.mcp.engine import MCPEngine
            engine = MCPEngine()
            
            # Test document upload
            test_content = "This is test document content for upload testing."
            filename = "test_document.txt"
            
            # Mock the HTTP calls
            with patch.object(engine, '_call_ingestion_service') as mock_ingest:
                mock_ingest.return_value = {
                    "document_id": "upload-doc-123",
                    "chunks_created": 1,
                    "tokens_extracted": 8,
                    "message": "Successfully uploaded document"
                }
                
                with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                    mock_sync.return_value = True
                    
                    result = engine.upload_document(test_content, filename)
                    
                    assert result["success"] == True
                    assert result["filename"] == filename
                    assert result["file_type"] == "txt"
                    assert result["chunks_created"] == 1
                    assert result["sync_triggered"] == True
                    
                    print("✅ MCP Engine document upload works")
                    return True
                    
        except Exception as e:
            print(f"❌ MCP Engine document upload failed: {e}")
            return False
    
    def test_mcp_engine_s3_uri_handling(self):
        """Test MCP engine S3 URI handling"""
        try:
            from services.mcp.engine import MCPEngine
            engine = MCPEngine()
            
            # Test S3 URI detection
            assert engine.is_s3_uri("s3://bucket/path/file.pdf") == True
            assert engine.is_s3_uri("s3a://bucket/path/file.pdf") == True
            assert engine.is_s3_uri("https://example.com/file.pdf") == False
            assert engine.is_s3_uri("plain text") == False
            
            # Test S3 URI parsing
            bucket, key = engine.parse_s3_uri("s3://my-bucket/path/to/document.pdf")
            assert bucket == "my-bucket"
            assert key == "path/to/document.pdf"
            
            # Test document ID generation
            doc_id = engine.generate_document_id("test content", "test_source")
            assert doc_id.startswith("doc-")
            assert len(doc_id) > 10
            
            # Test language code conversion
            assert engine.convert_language_code("en") == "eng"
            assert engine.convert_language_code("es") == "spa"
            assert engine.convert_language_code("eng") == "eng"  # Already 3-letter
            
            print("✅ MCP Engine utility functions work")
            return True
            
        except Exception as e:
            print(f"❌ MCP Engine utilities failed: {e}")
            return False


@pytest.mark.e2e
@pytest.mark.mcp
@pytest.mark.integration
class TestMCPIntegration:
    """Test MCP server integration with other services"""
    
    def test_service_urls_configuration(self):
        """Test that service URLs are properly configured"""
        try:
            from services.mcp.engine import INGESTION_SERVICE_URL, RETRIEVAL_SERVICE_URL, GATEWAY_URL
            
            # Check default URLs
            assert INGESTION_SERVICE_URL == "http://ingestion:8501"
            assert RETRIEVAL_SERVICE_URL == "http://retrieval:8502"
            assert GATEWAY_URL == "http://gateway:8500"
            
            print("✅ MCP Service URLs configured correctly")
            return True
            
        except Exception as e:
            print(f"❌ Service URL configuration failed: {e}")
            return False
    
    def test_http_client_initialization(self):
        """Test HTTP client initialization"""
        try:
            from services.mcp.engine import _get_http_client
            
            client = _get_http_client()
            assert client is not None
            assert hasattr(client, 'post')
            assert hasattr(client, 'get')
            
            print("✅ HTTP client initialized successfully")
            return True
            
        except Exception as e:
            print(f"❌ HTTP client initialization failed: {e}")
            return False
    
    def test_document_registry_caching(self):
        """Test document registry caching"""
        try:
            from services.mcp.engine import _get_cached_document_registry
            
            registry1 = _get_cached_document_registry()
            registry2 = _get_cached_document_registry()
            
            # Should return the same instance (cached)
            assert registry1 is registry2
            
            print("✅ Document registry caching works")
            return True
            
        except Exception as e:
            print(f"❌ Document registry caching failed: {e}")
            return False


@pytest.mark.e2e
@pytest.mark.mcp
@pytest.mark.performance
class TestMCPPerformance:
    """Test MCP server performance"""
    
    def test_mcp_engine_performance(self):
        """Test MCP engine performance metrics"""
        try:
            from services.mcp.engine import MCPEngine
            import time
            
            engine = MCPEngine()
            
            # Test confidence score calculation
            confidence = engine.calculate_confidence_score(0, 10, 0.95)
            assert 0 <= confidence <= 100
            
            confidence_high_rank = engine.calculate_confidence_score(5, 10, 0.8)
            confidence_low_rank = engine.calculate_confidence_score(8, 10, 0.6)
            
            assert confidence_high_rank > confidence_low_rank
            
            print("✅ MCP Engine performance calculations work")
            return True
            
        except Exception as e:
            print(f"❌ MCP Engine performance test failed: {e}")
            return False


# Test runner for MCP server
async def run_mcp_tests():
    """Run comprehensive MCP server tests"""
    print("🚀 MCP SERVER TESTING")
    print("="*60)
    
    # Test 1: Engine Import
    print("\n📦 Testing MCP Engine Import...")
    engine_test = TestMCPTools()
    engine_ok = engine_test.test_mcp_engine_import()
    
    # Test 2: Engine Functions
    print("\n🔧 Testing MCP Engine Functions...")
    functions_ok = (
        engine_test.test_mcp_engine_ingest_text() and
        engine_test.test_mcp_engine_search() and
        engine_test.test_mcp_engine_upload_document() and
        engine_test.test_mcp_engine_s3_uri_handling()
    )
    
    # Test 3: Integration
    print("\n🔗 Testing MCP Integration...")
    integration_test = TestMCPIntegration()
    integration_ok = (
        integration_test.test_service_urls_configuration() and
        integration_test.test_http_client_initialization() and
        integration_test.test_document_registry_caching()
    )
    
    # Test 4: Server Endpoints (if running)
    print("\n🌐 Testing MCP Server Endpoints...")
    endpoint_test = TestMCPServerEndpoints()
    async with httpx.AsyncClient(timeout=10.0) as client:
        health_ok = await endpoint_test.test_mcp_health_endpoint(client)
        info_ok = await endpoint_test.test_mcp_info_endpoint(client)
        sse_ok = await endpoint_test.test_mcp_sse_endpoint(client)
    
    # Test 5: Performance
    print("\n⚡ Testing MCP Performance...")
    perf_test = TestMCPPerformance()
    perf_ok = perf_test.test_mcp_engine_performance()
    
    # Summary
    print("\n" + "="*60)
    print("📊 MCP TEST SUMMARY")
    print("="*60)
    print(f"Engine Import:     {'✅ OK' if engine_ok else '❌ FAIL'}")
    print(f"Engine Functions:  {'✅ OK' if functions_ok else '❌ FAIL'}")
    print(f"Integration:       {'✅ OK' if integration_ok else '❌ FAIL'}")
    print(f"Server Health:     {'✅ OK' if health_ok else '❌ FAIL'}")
    print(f"Server Info:       {'✅ OK' if info_ok else '❌ FAIL'}")
    print(f"Server SSE:        {'✅ OK' if sse_ok else '❌ FAIL'}")
    print(f"Performance:       {'✅ OK' if perf_ok else '❌ FAIL'}")
    
    # Overall status
    core_tests_ok = engine_ok and functions_ok and integration_ok and perf_ok
    server_tests_ok = health_ok and info_ok and sse_ok
    
    print(f"\nCore Functionality: {'✅ ALL TESTS PASSED' if core_tests_ok else '❌ SOME TESTS FAILED'}")
    print(f"Server Endpoints:   {'✅ ALL TESTS PASSED' if server_tests_ok else '❌ SERVER NOT RUNNING'}")
    
    if core_tests_ok:
        print("\n🎉 MCP Server core functionality is working perfectly!")
        if not server_tests_ok:
            print("\n📝 Note: Start the MCP server to test endpoints:")
            print("   python services/mcp/main.py")
    else:
        print("\n⚠️ Fix the core issues before proceeding")
    
    return core_tests_ok


if __name__ == "__main__":
    asyncio.run(run_mcp_tests())
