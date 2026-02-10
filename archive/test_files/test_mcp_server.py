#!/usr/bin/env python3
"""
MCP Server Test Script
Tests the ARIS RAG MCP Server tools: rag_ingest and rag_search
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_local_import():
    """Test 1: Verify MCP server can be imported locally"""
    print("=" * 60)
    print("TEST 1: Local Import Test")
    print("=" * 60)
    
    try:
        from mcp_server import mcp, rag_ingest, rag_search
        print("✅ MCP Server imported successfully")
        print(f"   Server Name: {mcp.name}")
        
        # Check registered tools
        tools = list(mcp._tool_manager._tools.keys())
        print(f"   Registered Tools: {tools}")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_rag_ingest_text():
    """Test 2: Test rag_ingest with plain text"""
    print("\n" + "=" * 60)
    print("TEST 2: rag_ingest with Plain Text")
    print("=" * 60)
    
    try:
        # Import the actual function (not the wrapped tool)
        from mcp_server import mcp
        
        # Get the underlying function
        tool = mcp._tool_manager._tools.get('rag_ingest')
        if not tool:
            print("❌ rag_ingest tool not found")
            return False
        
        # Test with sample text
        test_content = """
        This is a test document for the MCP server verification.
        It contains information about testing procedures and validation.
        The MCP server should be able to ingest this content and make it searchable.
        """
        
        test_metadata = {
            "domain": "test",
            "language": "en",
            "source": "mcp_test_document"
        }
        
        print(f"   Content length: {len(test_content)} chars")
        print(f"   Metadata: {test_metadata}")
        
        # Call the function
        result = tool.fn(content=test_content, metadata=test_metadata)
        
        print(f"✅ Ingestion successful!")
        print(f"   Document ID: {result.get('document_id', 'N/A')}")
        print(f"   Chunks created: {result.get('chunks_created', 0)}")
        print(f"   Message: {result.get('message', 'N/A')}")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_search():
    """Test 3: Test rag_search"""
    print("\n" + "=" * 60)
    print("TEST 3: rag_search Query")
    print("=" * 60)
    
    try:
        from mcp_server import mcp
        
        # Get the underlying function
        tool = mcp._tool_manager._tools.get('rag_search')
        if not tool:
            print("❌ rag_search tool not found")
            return False
        
        # Test search
        test_query = "testing procedures and validation"
        test_filters = {"domain": "test"}
        
        print(f"   Query: {test_query}")
        print(f"   Filters: {test_filters}")
        
        # Call the function
        result = tool.fn(query=test_query, filters=test_filters, k=5)
        
        print(f"✅ Search successful!")
        print(f"   Total results: {result.get('total_results', 0)}")
        print(f"   Search mode: {result.get('search_mode', 'N/A')}")
        
        # Show first result snippet if available
        results = result.get('results', [])
        if results:
            first = results[0]
            snippet = first.get('snippet', first.get('content', ''))[:100]
            print(f"   First result: {snippet}...")
        
        return result.get('success', False)
        
    except Exception as e:
        print(f"❌ Search failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_remote_sse_endpoint():
    """Test 4: Test remote SSE endpoint"""
    print("\n" + "=" * 60)
    print("TEST 4: Remote SSE Endpoint Test")
    print("=" * 60)
    
    import urllib.request
    import urllib.error
    
    url = "http://44.221.84.58:8503/sse"
    
    try:
        req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = response.read(200).decode('utf-8')
            
            if 'session_id' in data:
                print(f"✅ SSE endpoint is responding!")
                print(f"   Response: {data[:100]}...")
                return True
            else:
                print(f"⚠️ Unexpected response: {data[:100]}")
                return False
                
    except urllib.error.URLError as e:
        print(f"❌ Connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🔍 " + "=" * 56 + " 🔍")
    print("       ARIS RAG MCP Server - Verification Tests")
    print("🔍 " + "=" * 56 + " 🔍\n")
    
    results = {}
    
    # Test 1: Import
    results['import'] = test_local_import()
    
    # Test 2: Remote SSE
    results['sse_endpoint'] = test_remote_sse_endpoint()
    
    # Test 3: Ingest (optional - requires OpenSearch connection)
    print("\n" + "-" * 60)
    print("The following tests require OpenSearch connection:")
    print("-" * 60)
    
    run_integration = input("\nRun integration tests (ingest/search)? [y/N]: ").strip().lower()
    
    if run_integration == 'y':
        results['ingest'] = test_rag_ingest_text()
        results['search'] = test_rag_search()
    else:
        print("⏭️  Skipping integration tests")
        results['ingest'] = None
        results['search'] = None
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results.items():
        if passed is None:
            status = "⏭️  SKIPPED"
        elif passed:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"   {test_name}: {status}")
    
    # Overall result
    failed = [k for k, v in results.items() if v is False]
    if failed:
        print(f"\n❌ {len(failed)} test(s) failed: {failed}")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

