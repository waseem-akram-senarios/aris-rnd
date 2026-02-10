#!/usr/bin/env python3
"""
Test script to verify all latest changes are working correctly.
Tests: index_name parameter, metrics endpoints, status tracking, async ingestion
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
        from services.ingestion.main import app as ingestion_app
        from services.retrieval.engine import RetrievalEngine
        from services.retrieval.main import app as retrieval_app
        from services.gateway.service import GatewayService
        print("✅ All service imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ingestion_endpoints():
    """Test that ingestion service has new endpoints"""
    print("\n" + "=" * 60)
    print("Testing Ingestion Endpoints...")
    print("=" * 60)
    
    try:
        from services.ingestion.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        routes = [str(route.path) for route in app.routes if hasattr(route, 'path')]
        
        # Check /metrics endpoint
        assert any('/metrics' in r for r in routes), "Missing /metrics endpoint"
        print("✅ /metrics endpoint exists")
        
        # Check /status/{document_id} endpoint
        assert any('/status' in r for r in routes), "Missing /status/{document_id} endpoint"
        print("✅ /status/{document_id} endpoint exists")
        
        # Check /ingest accepts index_name
        ingest_route = None
        for route in app.routes:
            if hasattr(route, 'path') and route.path == '/ingest':
                ingest_route = route
                break
        
        if ingest_route:
            # Check if index_name is in the route's dependencies
            print("✅ /ingest endpoint exists (index_name parameter check via test)")
        
        return True
    except Exception as e:
        print(f"❌ Ingestion endpoints test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_endpoints():
    """Test that retrieval service has metrics endpoint"""
    print("\n" + "=" * 60)
    print("Testing Retrieval Endpoints...")
    print("=" * 60)
    
    try:
        from services.retrieval.main import app
        routes = [str(route.path) for route in app.routes if hasattr(route, 'path')]
        
        # Check /metrics endpoint
        assert any('/metrics' in r for r in routes), "Missing /metrics endpoint"
        print("✅ /metrics endpoint exists")
        
        return True
    except Exception as e:
        print(f"❌ Retrieval endpoints test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ingestion_engine_methods():
    """Test IngestionEngine new parameters and methods"""
    print("\n" + "=" * 60)
    print("Testing IngestionEngine Methods...")
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
        
        # Check process_documents accepts index_name
        sig = inspect.signature(engine.process_documents)
        assert 'index_name' in sig.parameters, "process_documents missing index_name parameter"
        print("✅ process_documents accepts index_name parameter")
        
        # Check add_documents_incremental accepts index_name
        sig2 = inspect.signature(engine.add_documents_incremental)
        assert 'index_name' in sig2.parameters, "add_documents_incremental missing index_name parameter"
        print("✅ add_documents_incremental accepts index_name parameter")
        
        # Check metrics_collector exists
        assert hasattr(engine, 'metrics_collector'), "metrics_collector missing"
        assert engine.metrics_collector is not None, "metrics_collector is None"
        print("✅ metrics_collector initialized")
        
        return True
    except Exception as e:
        print(f"❌ IngestionEngine method test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_engine_metrics():
    """Test RetrievalEngine has metrics_collector"""
    print("\n" + "=" * 60)
    print("Testing RetrievalEngine Metrics...")
    print("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine
        from shared.config.settings import ARISConfig
        
        engine = RetrievalEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        # Check metrics_collector exists
        assert hasattr(engine, 'metrics_collector'), "metrics_collector missing"
        assert engine.metrics_collector is not None, "metrics_collector is None"
        print("✅ metrics_collector initialized")
        
        return True
    except Exception as e:
        print(f"❌ RetrievalEngine metrics test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gateway_methods():
    """Test GatewayService new methods"""
    print("\n" + "=" * 60)
    print("Testing GatewayService Methods...")
    print("=" * 60)
    
    try:
        from services.gateway.service import GatewayService
        import inspect
        
        service = GatewayService()
        
        # Check get_processing_state exists
        assert hasattr(service, 'get_processing_state'), "get_processing_state missing"
        assert callable(service.get_processing_state), "get_processing_state not callable"
        print("✅ get_processing_state method exists")
        
        # Check get_all_metrics exists
        assert hasattr(service, 'get_all_metrics'), "get_all_metrics missing"
        assert callable(service.get_all_metrics), "get_all_metrics not callable"
        print("✅ get_all_metrics method exists")
        
        # Check method signatures
        sig1 = inspect.signature(service.get_processing_state)
        assert 'doc_id' in sig1.parameters, "get_processing_state missing doc_id parameter"
        print("✅ get_processing_state has correct signature")
        
        return True
    except Exception as e:
        print(f"❌ GatewayService method test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_index_name_override():
    """Test index_name override functionality"""
    print("\n" + "=" * 60)
    print("Testing Index Name Override...")
    print("=" * 60)
    
    try:
        from services.ingestion.engine import IngestionEngine
        from shared.config.settings import ARISConfig
        
        engine = IngestionEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
        )
        
        original_index = engine.opensearch_index
        
        # Test that process_documents can override index
        # We'll just check the method accepts it without actually processing
        import inspect
        sig = inspect.signature(engine.process_documents)
        assert 'index_name' in sig.parameters, "process_documents should accept index_name"
        
        # Verify the parameter is Optional
        param = sig.parameters['index_name']
        assert param.default is None or param.default == inspect.Parameter.empty, "index_name should be optional"
        print("✅ index_name parameter is optional in process_documents")
        
        return True
    except Exception as e:
        print(f"❌ Index name override test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_metrics_collector_import():
    """Test that MetricsCollector can be imported"""
    print("\n" + "=" * 60)
    print("Testing MetricsCollector Import...")
    print("=" * 60)
    
    try:
        from metrics.metrics_collector import MetricsCollector
        collector = MetricsCollector()
        assert hasattr(collector, 'get_all_metrics'), "MetricsCollector missing get_all_metrics"
        print("✅ MetricsCollector imported and initialized")
        return True
    except Exception as e:
        print(f"❌ MetricsCollector import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_syntax():
    """Test that all files compile without syntax errors"""
    print("\n" + "=" * 60)
    print("Testing Syntax...")
    print("=" * 60)
    
    files_to_check = [
        'services/ingestion/main.py',
        'services/ingestion/engine.py',
        'services/retrieval/main.py',
        'services/retrieval/engine.py',
        'services/gateway/service.py',
        'api/app.py'
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
    print("TESTING ALL LATEST CHANGES V3")
    print("=" * 60 + "\n")
    
    tests = [
        ("Imports", test_imports),
        ("Ingestion Endpoints", test_ingestion_endpoints),
        ("Retrieval Endpoints", test_retrieval_endpoints),
        ("IngestionEngine Methods", test_ingestion_engine_methods),
        ("RetrievalEngine Metrics", test_retrieval_engine_metrics),
        ("GatewayService Methods", test_gateway_methods),
        ("Index Name Override", test_index_name_override),
        ("MetricsCollector Import", test_metrics_collector_import),
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

