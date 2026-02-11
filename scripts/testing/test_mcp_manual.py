#!/usr/bin/env python3
"""
Manual MCP Server Testing Script
Tests both the MCP engine and server endpoints
"""
import os
import sys
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

# MCP Server Configuration
MCP_SERVER_URL = "http://localhost:8503"
MCP_HEALTH_URL = f"{MCP_SERVER_URL}/health"
MCP_INFO_URL = f"{MCP_SERVER_URL}/info"

async def test_mcp_server_endpoints():
    """Test MCP server endpoints"""
    print("🌐 Testing MCP Server Endpoints...")
    print(f"   Target: {MCP_SERVER_URL}")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Test health endpoint
        try:
            response = await client.get(MCP_HEALTH_URL)
            if response.status_code == 200:
                health = response.json()
                print(f"✅ Health Check: {health.get('status', 'unknown')}")
                if 'services' in health:
                    print(f"   Services: {health['services']}")
            else:
                print(f"⚠️ Health Check: HTTP {response.status_code}")
        except httpx.ConnectError:
            print("❌ MCP Server not running")
            return False
        except Exception as e:
            print(f"❌ Health Check Error: {e}")
            return False
        
        # Test info endpoint
        try:
            response = await client.get(MCP_INFO_URL)
            if response.status_code == 200:
                info = response.json()
                print(f"✅ Server Info: {info.get('name', 'unknown')} v{info.get('version', 'unknown')}")
                if 'tools' in info:
                    tools = info['tools']
                    print(f"   Tools: {len(tools)} available")
                    for tool in tools:
                        print(f"     - {tool}")
            else:
                print(f"⚠️ Info Check: HTTP {response.status_code}")
        except Exception as e:
            print(f"❌ Info Check Error: {e}")
        
        return True

def test_mcp_engine():
    """Test MCP engine functionality"""
    print("\n🔧 Testing MCP Engine...")
    
    try:
        from services.mcp.engine import MCPEngine
        engine = MCPEngine()
        print("✅ MCP Engine initialized")
        
        # Test utility functions
        print("\n📋 Testing Utility Functions...")
        
        # S3 URI handling
        assert engine.is_s3_uri("s3://bucket/file.pdf") == True
        assert engine.is_s3_uri("plain text") == False
        print("✅ S3 URI detection works")
        
        bucket, key = engine.parse_s3_uri("s3://my-bucket/path/doc.pdf")
        assert bucket == "my-bucket"
        assert key == "path/doc.pdf"
        print("✅ S3 URI parsing works")
        
        # Document ID generation
        doc_id = engine.generate_document_id("test content", "test_source")
        assert doc_id.startswith("doc-")
        print(f"✅ Document ID generation: {doc_id}")
        
        # Language conversion
        assert engine.convert_language_code("en") == "eng"
        assert engine.convert_language_code("es") == "spa"
        print("✅ Language code conversion works")
        
        # Confidence scoring
        confidence = engine.calculate_confidence_score(0, 10, 0.95)
        assert 0 <= confidence <= 100
        print(f"✅ Confidence scoring: {confidence}")
        
        return True
        
    except ImportError as e:
        print(f"❌ MCP Engine import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ MCP Engine test failed: {e}")
        return False

def test_mcp_tools_mock():
    """Test MCP tools with mocked HTTP calls"""
    print("\n🛠️ Testing MCP Tools (Mocked)...")
    
    try:
        from services.mcp.engine import MCPEngine
        from unittest.mock import patch
        
        engine = MCPEngine()
        
        # Test ingestion with mock
        with patch.object(engine, '_call_ingestion_service') as mock_ingest:
            mock_ingest.return_value = {
                "document_id": "test-123",
                "chunks_created": 2,
                "tokens_extracted": 15,
                "message": "Success"
            }
            
            with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                mock_sync.return_value = True
                
                result = engine.ingest("Test content for ingestion")
                assert result["success"] == True
                assert result["document_id"] == "test-123"
                print("✅ Ingestion tool works (mocked)")
        
        # Test search with mock
        with patch.object(engine, '_call_retrieval_service') as mock_retrieval:
            mock_retrieval.return_value = {
                "answer": "Test answer",
                "citations": [{
                    "source": "test.pdf",
                    "page": 1,
                    "snippet": "Test snippet",
                    "full_text": "Full test content",
                    "similarity_score": 0.95
                }],
                "sources": ["test.pdf"]
            }
            
            result = engine.search("test query")
            assert result["success"] == True
            assert result["answer"] == "Test answer"
            assert len(result["results"]) == 1
            print("✅ Search tool works (mocked)")
        
        # Test document upload with mock
        with patch.object(engine, '_call_ingestion_service') as mock_ingest:
            mock_ingest.return_value = {
                "document_id": "upload-123",
                "chunks_created": 1,
                "tokens_extracted": 8,
                "message": "Upload success"
            }
            
            with patch.object(engine, '_broadcast_sync_after_ingestion') as mock_sync:
                mock_sync.return_value = True
                
                result = engine.upload_document("Test content", "test.txt")
                assert result["success"] == True
                assert result["filename"] == "test.txt"
                assert result["file_type"] == "txt"
                print("✅ Document upload tool works (mocked)")
        
        return True
        
    except Exception as e:
        print(f"❌ MCP Tools test failed: {e}")
        return False

def test_service_configuration():
    """Test service configuration"""
    print("\n⚙️ Testing Service Configuration...")
    
    try:
        from services.mcp.engine import INGESTION_SERVICE_URL, RETRIEVAL_SERVICE_URL, GATEWAY_URL
        
        print(f"   Ingestion Service: {INGESTION_SERVICE_URL}")
        print(f"   Retrieval Service: {RETRIEVAL_SERVICE_URL}")
        print(f"   Gateway Service: {GATEWAY_URL}")
        
        # Check environment variables
        required_vars = [
            'OPENAI_API_KEY',
            'AWS_OPENSEARCH_ACCESS_KEY_ID',
            'AWS_OPENSEARCH_SECRET_ACCESS_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if os.getenv(var):
                print(f"✅ {var}: {'*' * 8}{os.getenv(var)[-2:]}")
            else:
                print(f"⚠️ {var}: MISSING")
                missing_vars.append(var)
        
        if not missing_vars:
            print("✅ All required credentials available")
        else:
            print(f"⚠️ Missing: {missing_vars}")
        
        return len(missing_vars) == 0
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

async def main():
    """Run all MCP tests"""
    print("🚀 MCP SERVER COMPREHENSIVE TESTING")
    print("="*60)
    
    # Test 1: Engine
    engine_ok = test_mcp_engine()
    
    # Test 2: Tools (mocked)
    tools_ok = test_mcp_tools_mock()
    
    # Test 3: Configuration
    config_ok = test_service_configuration()
    
    # Test 4: Server endpoints
    server_ok = await test_mcp_server_endpoints()
    
    # Summary
    print("\n" + "="*60)
    print("📊 MCP TEST SUMMARY")
    print("="*60)
    print(f"Engine:        {'✅ OK' if engine_ok else '❌ FAIL'}")
    print(f"Tools:         {'✅ OK' if tools_ok else '❌ FAIL'}")
    print(f"Configuration: {'✅ OK' if config_ok else '❌ FAIL'}")
    print(f"Server:        {'✅ OK' if server_ok else '❌ NOT RUNNING'}")
    
    core_ok = engine_ok and tools_ok and config_ok
    
    print(f"\nCore MCP:     {'✅ WORKING' if core_ok else '❌ ISSUES'}")
    print(f"MCP Server:   {'✅ RUNNING' if server_ok else '❌ STOPPED'}")
    
    if core_ok:
        print("\n🎉 MCP Server core functionality is working perfectly!")
        
        if not server_ok:
            print("\n📝 To start the MCP server:")
            print("   python services/mcp/main.py")
            print("\n📝 Or with Docker:")
            print("   docker-compose up mcp")
    else:
        print("\n⚠️ Fix the core issues before starting the server")
    
    print(f"\n📊 Overall Status: {'✅ READY' if core_ok else '❌ NEEDS FIXES'}")

if __name__ == "__main__":
    asyncio.run(main())
