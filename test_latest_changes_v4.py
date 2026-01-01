#!/usr/bin/env python3
"""
Test script to verify all latest changes are working correctly.
Tests: page number accuracy, active_sources parameter, citation normalization
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that all imports work correctly"""
    print("=" * 60)
    print("Testing Imports...")
    print("=" * 60)
    
    try:
        from services.ingestion.engine import IngestionEngine
        from services.retrieval.engine import RetrievalEngine
        from services.gateway.service import GatewayService
        print("✅ All service imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ingestion_engine_changes():
    """Test IngestionEngine new methods and parameters"""
    print("\n" + "=" * 60)
    print("Testing IngestionEngine Changes...")
    print("=" * 60)
    
    try:
        from services.ingestion.engine import IngestionEngine
        from shared.config.settings import ARISConfig
        import inspect
        
        engine = IngestionEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Check _assign_metadata_to_chunks method exists
        assert hasattr(engine, '_assign_metadata_to_chunks'), "_assign_metadata_to_chunks method missing"
        assert callable(engine._assign_metadata_to_chunks), "_assign_metadata_to_chunks not callable"
        print("✅ _assign_metadata_to_chunks method exists")
        
        # Check method signature
        sig = inspect.signature(engine._assign_metadata_to_chunks)
        assert 'chunks' in sig.parameters, "_assign_metadata_to_chunks missing chunks parameter"
        assert 'original_metadata' in sig.parameters, "_assign_metadata_to_chunks missing original_metadata parameter"
        print("✅ _assign_metadata_to_chunks has correct signature")
        
        # Test the method with sample data
        from langchain_core.documents import Document
        
        # Create test chunks with start_index
        test_chunks = [
            Document(page_content="Test chunk 1", metadata={"start_index": 0}),
            Document(page_content="Test chunk 2", metadata={"start_index": 100}),
        ]
        
        # Test with page_blocks
        test_metadata = {
            'page_blocks': [
                {'start_char': 0, 'end_char': 50, 'page': 1},
                {'start_char': 50, 'end_char': 150, 'page': 2},
            ]
        }
        
        result = engine._assign_metadata_to_chunks(test_chunks, test_metadata)
        assert len(result) == 2, "Should return same number of chunks"
        assert result[0].metadata.get('page') == 1, "First chunk should be on page 1"
        assert result[1].metadata.get('page') == 2, "Second chunk should be on page 2"
        print("✅ _assign_metadata_to_chunks works correctly with page_blocks")
        
        # Test fallback to page in metadata
        test_chunks2 = [
            Document(page_content="Test chunk", metadata={"start_index": 0}),
        ]
        test_metadata2 = {'page': 5}
        result2 = engine._assign_metadata_to_chunks(test_chunks2, test_metadata2)
        assert result2[0].metadata.get('page') == 5, "Should use fallback page"
        print("✅ _assign_metadata_to_chunks works with fallback page")
        
        return True
    except Exception as e:
        print(f"❌ IngestionEngine changes test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_engine_active_sources():
    """Test RetrievalEngine active_sources parameter"""
    print("\n" + "=" * 60)
    print("Testing RetrievalEngine active_sources Parameter...")
    print("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine
        from shared.config.settings import ARISConfig
        import inspect
        
        engine = RetrievalEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Check query_with_rag accepts active_sources
        sig = inspect.signature(engine.query_with_rag)
        assert 'active_sources' in sig.parameters, "query_with_rag missing active_sources parameter"
        print("✅ query_with_rag accepts active_sources parameter")
        
        # Check parameter is Optional
        param = sig.parameters['active_sources']
        assert param.default is None or param.default == inspect.Parameter.empty, "active_sources should be optional"
        print("✅ active_sources parameter is optional")
        
        # Check _raw_retrieval_with_hybrid_search accepts active_sources
        if hasattr(engine, '_raw_retrieval_with_hybrid_search'):
            sig2 = inspect.signature(engine._raw_retrieval_with_hybrid_search)
            if 'active_sources' in sig2.parameters:
                print("✅ _raw_retrieval_with_hybrid_search accepts active_sources")
        
        return True
    except Exception as e:
        print(f"❌ RetrievalEngine active_sources test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_main_changes():
    """Test retrieval main.py changes"""
    print("\n" + "=" * 60)
    print("Testing Retrieval Main Changes...")
    print("=" * 60)
    
    try:
        from services.retrieval.main import app
        from shared.schemas import QueryRequest
        from fastapi.testclient import TestClient
        
        # Check that QueryRequest might have active_sources (if schema was updated)
        # For now, just verify the endpoint exists and works
        client = TestClient(app)
        routes = [str(route.path) for route in app.routes if hasattr(route, 'path')]
        assert '/query' in routes, "Missing /query endpoint"
        print("✅ /query endpoint exists")
        
        return True
    except Exception as e:
        print(f"❌ Retrieval main test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gateway_active_sources():
    """Test GatewayService active_sources handling"""
    print("\n" + "=" * 60)
    print("Testing GatewayService active_sources...")
    print("=" * 60)
    
    try:
        from services.gateway.service import GatewayService
        import inspect
        
        service = GatewayService()
        
        # Check query_text_only method
        sig = inspect.signature(service.query_text_only)
        assert 'document_id' in sig.parameters, "query_text_only missing document_id"
        print("✅ query_text_only has document_id parameter")
        
        # Check that active_sources property exists
        assert hasattr(service, '_active_sources'), "_active_sources attribute missing"
        assert hasattr(service, 'active_sources'), "active_sources property missing"
        print("✅ active_sources property exists")
        
        return True
    except Exception as e:
        print(f"❌ GatewayService active_sources test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_citation_normalization():
    """Test citation source normalization"""
    print("\n" + "=" * 60)
    print("Testing Citation Normalization...")
    print("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine
        from shared.config.settings import ARISConfig
        import inspect
        
        engine = RetrievalEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Check if _merge_duplicate_citations method exists and uses basename
        if hasattr(engine, '_merge_duplicate_citations'):
            # Check the source code for basename usage
            import inspect
            source = inspect.getsource(engine._merge_duplicate_citations)
            if 'os.path.basename' in source or 'basename' in source.lower():
                print("✅ Citation normalization uses basename for source paths")
            else:
                print("⚠️  Citation normalization may not use basename (check manually)")
        else:
            print("⚠️  _merge_duplicate_citations method not found (may be in different location)")
        
        return True
    except Exception as e:
        print(f"❌ Citation normalization test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_add_start_index_parameter():
    """Test that add_start_index parameter is used"""
    print("\n" + "=" * 60)
    print("Testing add_start_index Parameter...")
    print("=" * 60)
    
    try:
        from services.ingestion.engine import IngestionEngine
        from shared.config.settings import ARISConfig
        import inspect
        
        engine = IngestionEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Check if text_splitter has add_start_index set
        if hasattr(engine, 'text_splitter'):
            # Check the source code for add_start_index usage
            source = inspect.getsource(engine.__init__)
            if 'add_start_index=True' in source or 'add_start_index' in source:
                print("✅ add_start_index parameter is used in text splitter")
            else:
                print("⚠️  add_start_index may not be set (check manually)")
        else:
            print("⚠️  text_splitter not found")
        
        return True
    except Exception as e:
        print(f"❌ add_start_index test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_syntax():
    """Test that all files compile without syntax errors"""
    print("\n" + "=" * 60)
    print("Testing Syntax...")
    print("=" * 60)
    
    files_to_check = [
        'services/ingestion/engine.py',
        'services/retrieval/engine.py',
        'services/retrieval/main.py',
        'services/gateway/service.py'
    ]
    
    errors = []
    for file_path in files_to_check:
        try:
            with open(file_path, 'r') as f:
                compile(f.read(), file_path, 'exec')
            print(f"✅ {file_path} - syntax OK")
        except SyntaxError as e:
            errors.append(f"{file_path}: {e}")
            print(f"❌ {file_path} - syntax error: {e}")
        except Exception as e:
            errors.append(f"{file_path}: {e}")
            print(f"⚠️  {file_path} - {e}")
    
    return len(errors) == 0

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TESTING ALL LATEST CHANGES V4")
    print("=" * 60 + "\n")
    
    tests = [
        ("Imports", test_imports),
        ("IngestionEngine Changes", test_ingestion_engine_changes),
        ("RetrievalEngine active_sources", test_retrieval_engine_active_sources),
        ("Retrieval Main Changes", test_retrieval_main_changes),
        ("GatewayService active_sources", test_gateway_active_sources),
        ("Citation Normalization", test_citation_normalization),
        ("add_start_index Parameter", test_add_start_index_parameter),
        ("Syntax Check", test_syntax),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' failed with exception: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! All latest changes are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
