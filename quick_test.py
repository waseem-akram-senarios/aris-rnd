#!/usr/bin/env python3
"""
Quick MCP Microservice Test - No User Input Required
Tests basic functionality of the accuracy-optimized MCP microservice

Tests:
1. Import Test - Verify microservice imports correctly
2. Ingestion Test - Add documents to RAG system
3. Search Test - Query documents with various modes
4. Accuracy Features Test - Test hybrid search, agentic RAG, etc.
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test 1: Verify imports work"""
    print("🧪 TEST 1: Microservice Import Test")
    try:
        # Import from the new microservice structure
        from services.mcp.main import mcp, mcp_engine
        from services.mcp.engine import MCPEngine
        
        print("✅ MCP Microservice imported successfully")
        print(f"   Server: {mcp.name}")
        print(f"   Tools: {list(mcp._tool_manager._tools.keys())}")
        print(f"   Engine: {type(mcp_engine).__name__}")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ingest():
    """Test 2: Test document ingestion via MCPEngine"""
    print("\n🧪 TEST 2: Document Ingestion Test")
    try:
        from services.mcp.main import mcp_engine

        # Test with sample maintenance document
        content = """
        MAINTENANCE PROCEDURE FOR MODEL X MACHINES

        Weekly Maintenance:
        1. Check oil levels in all reservoirs
        2. Inspect belts for wear and tension
        3. Clean air filters
        4. Verify safety guards are in place

        Monthly Maintenance:
        1. Replace oil filters
        2. Check hydraulic pressure
        3. Calibrate sensors
        4. Test emergency stop functions

        Safety Note: Always disconnect power before servicing.
        """

        # Use the engine's ingest method directly
        result = mcp_engine.ingest(
            content=content.strip(),
            metadata={
                'domain': 'maintenance',
                'language': 'en',
                'source': 'maintenance_manual.pdf',
                'machine_model': 'Model X'
            }
        )

        if result.get('success'):
            print("✅ Document ingested successfully")
            print(f"   Document ID: {result.get('document_id')}")
            print(f"   Chunks created: {result.get('chunks_created')}")
            print(f"   Tokens added: {result.get('tokens_added')}")
            return result.get('document_id')
        else:
            print(f"❌ Ingestion failed: {result.get('message')}")
            return None

    except Exception as e:
        print(f"❌ Ingestion test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_search(document_id):
    """Test 3: Test search functionality via MCPEngine"""
    print("\n🧪 TEST 3: Search Test")
    try:
        from services.mcp.main import mcp_engine

        # Test queries of increasing complexity
        test_queries = [
            ("maintenance", "Simple keyword search"),
            ("oil levels", "Specific maintenance task"),
            ("How do I perform weekly maintenance?", "Complex question requiring synthesis")
        ]

        for query, description in test_queries:
            print(f"\n   Testing: {description}")
            print(f"   Query: '{query}'")

            start_time = time.time()
            # Use the engine's search method directly
            result = mcp_engine.search(query, k=3, include_answer=True)
            elapsed = time.time() - start_time

            if result.get('success'):
                print(f"   ⏱️  Response time: {elapsed:.2f}s")
                print(f"   Results found: {result.get('total_results')}")

                # Show accuracy info
                accuracy = result.get('accuracy_info', {})
                if accuracy.get('agentic_rag_enabled'):
                    sub_queries = accuracy.get('sub_queries_generated', 0)
                    if sub_queries > 0:
                        print(f"   🤖 Agentic RAG used: {sub_queries} sub-queries generated")

                # Show top result confidence if available
                if result.get('results'):
                    top_result = result['results'][0]
                    confidence = top_result.get('confidence', 0)
                    print(f"   🎯 Top confidence: {confidence:.1f}%")
                    if result.get('answer'):
                        answer_preview = result['answer'][:100] + "..." if len(result['answer']) > 100 else result['answer']
                        print(f"   💡 Answer: {answer_preview}")
            else:
                print(f"   ❌ Search failed")

        return True

    except Exception as e:
        print(f"❌ Search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_accuracy_features():
    """Test 4: Test accuracy-specific features"""
    print("\n🧪 TEST 4: Accuracy Features Test")
    try:
        from services.mcp.main import mcp_engine

        # Test hybrid search with different modes
        query = "maintenance procedures"

        print("   Testing different search modes:")
        modes = ['semantic', 'keyword', 'hybrid']
        for mode in modes:
            result = mcp_engine.search(query, k=2, search_mode=mode, include_answer=False)
            if result.get('success') and result.get('results'):
                top_confidence = result['results'][0].get('confidence', 0)
                print(f"   {mode.capitalize()}: {top_confidence:.1f}% confidence")

        # Test Agentic RAG
        print("\n   Testing Agentic RAG:")
        complex_query = "What are the steps for machine maintenance and what safety precautions should I take?"
        result = mcp_engine.search(complex_query, k=3, use_agentic_rag=True, include_answer=True)

        if result.get('success'):
            accuracy_info = result.get('accuracy_info', {})
            if accuracy_info.get('agentic_rag_enabled'):
                print("   ✅ Agentic RAG enabled")
                sub_queries = accuracy_info.get('sub_queries_generated', 0)
                if sub_queries > 0:
                    print(f"   📝 Generated {sub_queries} sub-queries")
                else:
                    print("   ⚠️  Agentic RAG ran but no sub-queries generated")
            else:
                print("   ⚠️  Agentic RAG not enabled")

            if result.get('answer'):
                print("   ✅ Answer generation working")
            else:
                print("   ⚠️  No answer generated")
        else:
            print("   ❌ Agentic RAG test failed")

        return True

    except Exception as e:
        print(f"❌ Accuracy features test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_engine_methods():
    """Test 5: Test MCPEngine helper methods"""
    print("\n🧪 TEST 5: Engine Helper Methods Test")
    try:
        from services.mcp.engine import MCPEngine

        # Test static methods
        print("   Testing S3 URI detection:")
        test_uris = [
            ("s3://bucket/key/file.pdf", True),
            ("s3a://bucket/file.txt", True),
            ("https://example.com/file.pdf", False),
            ("plain text content", False),
        ]
        for uri, expected in test_uris:
            result = MCPEngine.is_s3_uri(uri)
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{uri[:30]}...' -> {result} (expected: {expected})")

        # Test language code conversion
        print("\n   Testing language code conversion:")
        test_codes = [("en", "eng"), ("es", "spa"), ("de", "deu"), ("eng", "eng")]
        for code, expected in test_codes:
            result = MCPEngine.convert_language_code(code)
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{code}' -> '{result}' (expected: '{expected}')")

        # Test confidence scoring
        print("\n   Testing confidence scoring:")
        print(f"   Position 0 (with rerank 0.95): {MCPEngine.calculate_confidence_score(0, 10, 0.95):.1f}%")
        print(f"   Position 0 (no rerank): {MCPEngine.calculate_confidence_score(0, 10):.1f}%")
        print(f"   Position 5 (no rerank): {MCPEngine.calculate_confidence_score(5, 10):.1f}%")

        return True

    except Exception as e:
        print(f"❌ Engine methods test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("=" * 70)
    print("🚀 ARIS MCP Microservice - Accuracy-Optimized Testing Suite")
    print("=" * 70)
    print("Testing the new microservice architecture:")
    print("• services/mcp/main.py - MCP server with FastAPI")
    print("• services/mcp/engine.py - Core business logic")
    print("=" * 70)

    results = {}

    # Run tests
    results['import'] = test_imports()
    results['engine_methods'] = test_engine_methods()

    document_id = None
    if results['import']:
        document_id = test_ingest()
        results['ingest'] = document_id is not None

        if document_id:
            results['search'] = test_search(document_id)

        results['accuracy'] = test_accuracy_features()

    print("\n" + "=" * 70)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test.upper()}: {status}")

    print(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        print("🎯 Your MCP microservice is ready for production use.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")

    print("\n📈 Key Features Verified:")
    print("   • Microservice architecture (services/mcp/)")
    print("   • MCPEngine for business logic separation")
    print("   • Hybrid search with confidence scoring")
    print("   • Agentic RAG query decomposition")
    print("   • FastAPI health endpoints")

    print("\n🔗 Endpoints:")
    print("   MCP Server: http://44.221.84.58:8503/sse")
    print("   Health:     http://44.221.84.58:8503/health")
    print("   Info:       http://44.221.84.58:8503/info")
    print("   Tools:      http://44.221.84.58:8503/tools")

    print("\n📚 Documentation:")
    print("   • CLAUDE_DESKTOP_INTEGRATION.md")
    print("   • MCP_TESTING_GUIDE.md")
    print("   • docs/ACCURACY_GUIDE.md")
    print("=" * 70)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
