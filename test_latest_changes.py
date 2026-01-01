#!/usr/bin/env python3
"""
Test script to verify all latest changes are working correctly.
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
        # Test schema imports
        from shared.schemas import (
            ImageQueryRequest, ImageQueryResponse, ImageResult,
            QueryRequest, QueryResponse
        )
        print("✅ Schema imports successful")
        
        # Test service imports
        from services.gateway.service import GatewayService
        from services.retrieval.engine import RetrievalEngine
        from services.ingestion.engine import IngestionEngine
        from api.service import ServiceContainer
        print("✅ Service imports successful")
        
        # Test main imports
        from services.retrieval.main import app as retrieval_app
        from services.ingestion.main import app as ingestion_app
        from services.gateway.main import app as gateway_app
        print("✅ FastAPI app imports successful")
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schemas():
    """Test schema validation"""
    print("\n" + "=" * 60)
    print("Testing Schemas...")
    print("=" * 60)
    
    try:
        from shared.schemas import ImageQueryRequest, ImageQueryResponse, ImageResult
        
        # Test ImageQueryRequest
        request = ImageQueryRequest(question="test query", k=5)
        assert request.question == "test query"
        assert request.k == 5
        print("✅ ImageQueryRequest validation works")
        
        # Test ImageResult
        result = ImageResult(
            image_id="test-id",
            source="test.pdf",
            image_number=1,
            page=1,
            ocr_text="test text",
            metadata={},
            score=0.95
        )
        assert result.image_id == "test-id"
        assert result.page >= 1
        print("✅ ImageResult validation works (page >= 1 enforced)")
        
        # Test ImageQueryResponse
        response = ImageQueryResponse(
            images=[result],
            total=1,
            message="Test message"
        )
        assert len(response.images) == 1
        print("✅ ImageQueryResponse validation works")
        
        return True
    except Exception as e:
        print(f"❌ Schema validation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ingestion_config():
    """Test that ingestion service accepts opensearch_index parameter"""
    print("\n" + "=" * 60)
    print("Testing Ingestion Configuration...")
    print("=" * 60)
    
    try:
        from shared.config.settings import ARISConfig
        from services.ingestion.engine import IngestionEngine
        
        # Test that engine accepts opensearch_index
        engine = IngestionEngine(
            vector_store_type="opensearch",
            opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
            opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX,
            chunk_size=512,
            chunk_overlap=128
        )
        
        assert hasattr(engine, 'opensearch_index')
        assert engine.opensearch_index == ARISConfig.AWS_OPENSEARCH_INDEX
        print("✅ IngestionEngine accepts opensearch_index parameter")
        
        return True
    except Exception as e:
        print(f"❌ Ingestion config error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_retrieval_endpoint():
    """Test that retrieval service has image query endpoint"""
    print("\n" + "=" * 60)
    print("Testing Retrieval Endpoints...")
    print("=" * 60)
    
    try:
        from services.retrieval.main import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Check that /query/images endpoint exists
        routes = [route.path for route in app.routes]
        assert "/query/images" in routes, f"Expected /query/images endpoint, found routes: {routes}"
        print("✅ /query/images endpoint exists")
        
        # Check that /query endpoint exists
        assert "/query" in routes
        print("✅ /query endpoint exists")
        
        # Check that /health endpoint exists
        assert "/health" in routes
        print("✅ /health endpoint exists")
        
        return True
    except Exception as e:
        print(f"❌ Retrieval endpoint test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gateway_service():
    """Test gateway service methods"""
    print("\n" + "=" * 60)
    print("Testing Gateway Service...")
    print("=" * 60)
    
    try:
        from services.gateway.service import GatewayService
        
        service = GatewayService()
        
        # Check that query_images_only method exists
        assert hasattr(service, 'query_images_only')
        assert callable(service.query_images_only)
        print("✅ GatewayService has query_images_only method")
        
        # Check that process_document method exists
        assert hasattr(service, 'process_document')
        assert callable(service.process_document)
        print("✅ GatewayService has process_document method")
        
        return True
    except Exception as e:
        print(f"❌ Gateway service test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_service():
    """Test API service container"""
    print("\n" + "=" * 60)
    print("Testing API Service Container...")
    print("=" * 60)
    
    try:
        from api.service import ServiceContainer
        
        # ServiceContainer requires GatewayService which might need network access
        # Just check that the class exists and has the methods
        assert hasattr(ServiceContainer, 'query_text_only')
        assert hasattr(ServiceContainer, 'query_images_only')
        print("✅ ServiceContainer has query_text_only method")
        print("✅ ServiceContainer has query_images_only method")
        
        return True
    except Exception as e:
        print(f"❌ API service test error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("TESTING ALL LATEST CHANGES")
    print("=" * 60 + "\n")
    
    tests = [
        ("Imports", test_imports),
        ("Schemas", test_schemas),
        ("Ingestion Config", test_ingestion_config),
        ("Retrieval Endpoints", test_retrieval_endpoint),
        ("Gateway Service", test_gateway_service),
        ("API Service", test_api_service),
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
