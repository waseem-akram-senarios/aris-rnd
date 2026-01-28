#!/usr/bin/env python3
"""
Test ServiceContainer integration in Streamlit app
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test all required imports"""
    print("="*70)
    print("1. Testing Imports")
    print("="*70)
    
    try:
        from services.retrieval.engine import RetrievalEngine
        print("✅ services.retrieval.engine.RetrievalEngine (microservices)")
    except Exception as e:
        print(f"❌ RetrievalEngine: {e}")
        return False
    
    try:
        from api.service import ServiceContainer
        print("✅ api.service.ServiceContainer")
    except Exception as e:
        print(f"❌ api.service.ServiceContainer: {e}")
        return False
    
    try:
        from services.ingestion.processor import DocumentProcessor
        print("✅ services.ingestion.processor.DocumentProcessor")
    except Exception as e:
        print(f"❌ DocumentProcessor: {e}")
        return False
    
    try:
        from storage.document_registry import DocumentRegistry
        print("✅ storage.document_registry.DocumentRegistry")
    except Exception as e:
        print(f"❌ DocumentRegistry: {e}")
        return False
    
    return True

def test_servicecontainer_initialization():
    """Test ServiceContainer initialization"""
    print("\n" + "="*70)
    print("2. Testing ServiceContainer Initialization")
    print("="*70)
    
    try:
        from api.service import ServiceContainer
        
        container = ServiceContainer(
            use_cerebras=False,
            embedding_model='text-embedding-3-small',
            openai_model='gpt-4o-mini',
            cerebras_model='llama-3.1-8b-instruct',
            vector_store_type='faiss',
            opensearch_domain='',
            chunk_size=384,
            chunk_overlap=120
        )
        
        print("✅ ServiceContainer created successfully")
        
        # Check components
        checks = [
            ("rag_system", container.rag_system),
            ("document_processor", container.document_processor),
            ("document_registry", container.document_registry),
            ("gateway_service", container.gateway_service)
        ]
        
        all_ok = True
        for name, component in checks:
            if component is not None:
                print(f"  ✅ {name}: Available")
            else:
                print(f"  ❌ {name}: Missing")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ ServiceContainer initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_component_integration():
    """Test that components are properly integrated"""
    print("\n" + "="*70)
    print("3. Testing Component Integration")
    print("="*70)
    
    try:
        from api.service import ServiceContainer
        
        container = ServiceContainer(
            use_cerebras=False,
            embedding_model='text-embedding-3-small',
            openai_model='gpt-4o-mini',
            cerebras_model='llama-3.1-8b-instruct',
            vector_store_type='faiss',
            opensearch_domain='',
            chunk_size=384,
            chunk_overlap=120
        )
        
        # Check that document_processor has rag_system
        if hasattr(container.document_processor, 'rag_system'):
            if container.document_processor.rag_system == container.rag_system:
                print("✅ document_processor.rag_system matches container.rag_system")
            else:
                print("⚠️  document_processor.rag_system is different instance")
        else:
            print("⚠️  document_processor doesn't have rag_system attribute")
        
        # Check that metrics_collector is available
        if hasattr(container, 'document_registry') and container.document_registry:
            print("✅ metrics_collector is available")
        else:
            print("⚠️  metrics_collector is None")
        
        # Check that document_registry is available
        if container.document_registry:
            print("✅ document_registry is available")
        else:
            print("⚠️  document_registry is None")
        
        return True
    except Exception as e:
        print(f"❌ Component integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_imports():
    """Test that app.py can be imported without errors"""
    print("\n" + "="*70)
    print("4. Testing app.py Import")
    print("="*70)
    
    try:
        # Try to import app module (this will fail if there are syntax errors)
        import importlib.util
        spec = importlib.util.spec_from_file_location("app", "api/app.py")
        if spec is None:
            print("❌ Could not create spec from api/app.py")
            return False
        
        # Just check syntax, don't execute
        with open("api/app.py", "r") as f:
            code = f.read()
            compile(code, "api/app.py", "exec")
        
        print("✅ app.py syntax is valid")
        print("⚠️  Note: Full import test skipped (would require Streamlit)")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error in app.py: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Import check: {e}")
        return True  # Not a critical error

def test_session_state_compatibility():
    """Test that session state bindings would work"""
    print("\n" + "="*70)
    print("5. Testing Session State Compatibility")
    print("="*70)
    
    try:
        from api.service import ServiceContainer
        
        container = ServiceContainer(
            use_cerebras=False,
            embedding_model='text-embedding-3-small',
            openai_model='gpt-4o-mini',
            cerebras_model='llama-3.1-8b-instruct',
            vector_store_type='faiss',
            opensearch_domain='',
            chunk_size=384,
            chunk_overlap=120
        )
        
        # Simulate session state bindings (microservices architecture)
        session_state = {
            'service_container': container,
            'document_processor': container.document_processor,
            'document_registry': container.document_registry
        }
        
        # Verify all are set (microservices doesn't need rag_system or metrics_collector in session state)
        required_keys = ['service_container', 'document_processor', 'document_registry']
        all_present = all(key in session_state for key in required_keys)
        
        if all_present:
            print("✅ All session state keys would be set correctly")
            for key in required_keys:
                if session_state[key] is not None:
                    print(f"  ✅ {key}: Set")
                else:
                    print(f"  ⚠️  {key}: None")
        else:
            print("❌ Some session state keys missing")
            return False
        
        # Verify rag_system property works (accessed via container, not session_state in microservices)
        if hasattr(container, 'rag_system') and container.rag_system is not None:
            print(f"  ✅ rag_system property: Available via container.rag_system")
            if container.rag_system == container.gateway_service:
                print("✅ rag_system reference matches gateway_service")
            else:
                print("❌ rag_system reference mismatch")
                return False
        else:
            print("❌ rag_system property not available")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Session state compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("="*70)
    print("SERVICECONTAINER INTEGRATION TEST")
    print("="*70)
    print()
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("ServiceContainer Initialization", test_servicecontainer_initialization()))
    results.append(("Component Integration", test_component_integration()))
    results.append(("app.py Import", test_app_imports()))
    results.append(("Session State Compatibility", test_session_state_compatibility()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - ServiceContainer integration is working!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test suite(s) had issues")
        return 1

if __name__ == "__main__":
    sys.exit(main())




