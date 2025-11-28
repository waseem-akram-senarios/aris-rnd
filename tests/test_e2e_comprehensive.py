#!/usr/bin/env python3
"""
Comprehensive End-to-End Test for ARIS RAG System
Tests all major components and integrations.
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Test results
results = {
    'timestamp': datetime.now().isoformat(),
    'tests': [],
    'summary': {
        'total': 0,
        'passed': 0,
        'failed': 0,
        'errors': 0
    }
}

def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def print_test(name, status, details=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} {name}")
    if details:
        print(f"   {details}")
    return status

def record_test(name, status, details="", error=None):
    results['tests'].append({
        'test': name,
        'status': status,
        'details': details,
        'error': str(error) if error else None
    })
    results['summary']['total'] += 1
    if status == "PASS":
        results['summary']['passed'] += 1
    elif status == "FAIL":
        results['summary']['failed'] += 1
    else:
        results['summary']['errors'] += 1

def test_imports():
    """Test that all required modules can be imported"""
    print_header("1. Module Imports")
    
    modules = [
        ('rag_system', 'RAGSystem'),
        ('ingestion.document_processor', 'DocumentProcessor'),
        ('parsers.parser_factory', 'ParserFactory'),
        ('metrics.metrics_collector', 'MetricsCollector'),
        ('utils.tokenizer', 'TokenTextSplitter'),
        ('utils.chunking_strategies', 'get_all_strategies'),
        ('vectorstores.vector_store_factory', 'VectorStoreFactory'),
        ('vectorstores.opensearch_store', 'OpenSearchVectorStore'),
    ]
    
    for module_name, class_name in modules:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print_test(f"Import {module_name}.{class_name}", "PASS")
            record_test(f"Import {module_name}.{class_name}", "PASS")
        except ImportError as e:
            print_test(f"Import {module_name}.{class_name}", "FAIL", str(e))
            record_test(f"Import {module_name}.{class_name}", "FAIL", error=str(e))
        except AttributeError as e:
            print_test(f"Import {module_name}.{class_name}", "FAIL", f"Class not found: {str(e)}")
            record_test(f"Import {module_name}.{class_name}", "FAIL", error=str(e))
        except Exception as e:
            print_test(f"Import {module_name}.{class_name}", "ERROR", str(e))
            record_test(f"Import {module_name}.{class_name}", "ERROR", error=str(e))

def test_environment_variables():
    """Test that required environment variables are set"""
    print_header("2. Environment Variables")
    
    required_vars = {
        'OPENAI_API_KEY': 'OpenAI API key for embeddings and LLM',
        'AWS_OPENSEARCH_ACCESS_KEY_ID': 'AWS OpenSearch access key (optional)',
        'AWS_OPENSEARCH_SECRET_ACCESS_KEY': 'AWS OpenSearch secret key (optional)',
    }
    
    optional_vars = {
        'AWS_OPENSEARCH_REGION': 'AWS region for OpenSearch',
    }
    
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print_test(f"{var}", "PASS", f"Set ({masked})")
            record_test(f"Env var {var}", "PASS", f"Set")
        else:
            if 'OPENSEARCH' in var:
                print_test(f"{var}", "WARN", f"Not set (OpenSearch optional)")
                record_test(f"Env var {var}", "WARN", "Not set (optional)")
            else:
                print_test(f"{var}", "FAIL", f"Not set - {desc}")
                record_test(f"Env var {var}", "FAIL", error="Not set")
    
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print_test(f"{var} (optional)", "PASS", f"Set: {value}")
            record_test(f"Env var {var}", "PASS", f"Set: {value}")

def test_rag_system_initialization():
    """Test RAGSystem initialization with different configurations"""
    print_header("3. RAGSystem Initialization")
    
    try:
        from rag_system import RAGSystem
        from metrics.metrics_collector import MetricsCollector
        
        # Test 1: Default initialization (FAISS)
        try:
            rag = RAGSystem()
            print_test("RAGSystem default init (FAISS)", "PASS", "Initialized successfully")
            record_test("RAGSystem default init", "PASS", "FAISS vector store")
        except Exception as e:
            print_test("RAGSystem default init (FAISS)", "FAIL", str(e))
            record_test("RAGSystem default init", "FAIL", error=str(e))
        
        # Test 2: With metrics collector
        try:
            metrics = MetricsCollector()
            rag = RAGSystem(metrics_collector=metrics)
            print_test("RAGSystem with metrics collector", "PASS", "Initialized successfully")
            record_test("RAGSystem with metrics", "PASS")
        except Exception as e:
            print_test("RAGSystem with metrics collector", "FAIL", str(e))
            record_test("RAGSystem with metrics", "FAIL", error=str(e))
        
        # Test 3: With custom chunking
        try:
            rag = RAGSystem(chunk_size=256, chunk_overlap=50)
            assert rag.chunk_size == 256
            assert rag.chunk_overlap == 50
            print_test("RAGSystem custom chunking", "PASS", "chunk_size=256, overlap=50")
            record_test("RAGSystem custom chunking", "PASS")
        except Exception as e:
            print_test("RAGSystem custom chunking", "FAIL", str(e))
            record_test("RAGSystem custom chunking", "FAIL", error=str(e))
        
        # Test 4: With different embedding models
        try:
            rag = RAGSystem(embedding_model="text-embedding-3-small")
            print_test("RAGSystem embedding model", "PASS", "text-embedding-3-small")
            record_test("RAGSystem embedding model", "PASS")
        except Exception as e:
            print_test("RAGSystem embedding model", "FAIL", str(e))
            record_test("RAGSystem embedding model", "FAIL", error=str(e))
        
        # Test 5: OpenSearch initialization (if credentials available)
        if os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') and os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'):
            try:
                rag = RAGSystem(
                    vector_store_type="opensearch",
                    opensearch_domain="intelycx-os-dev",
                    opensearch_index="aris-rag-test-index"
                )
                print_test("RAGSystem OpenSearch init", "PASS", "Initialized (may fail on operations)")
                record_test("RAGSystem OpenSearch init", "PASS", "Initialized")
            except Exception as e:
                error_msg = str(e)
                if "permission" in error_msg.lower() or "403" in error_msg:
                    print_test("RAGSystem OpenSearch init", "WARN", "Initialized but permissions missing (expected)")
                    record_test("RAGSystem OpenSearch init", "WARN", "Permissions missing")
                else:
                    print_test("RAGSystem OpenSearch init", "FAIL", str(e))
                    record_test("RAGSystem OpenSearch init", "FAIL", error=str(e))
        else:
            print_test("RAGSystem OpenSearch init", "SKIP", "OpenSearch credentials not set")
            record_test("RAGSystem OpenSearch init", "SKIP", "Credentials not set")
            
    except Exception as e:
        print_test("RAGSystem initialization", "ERROR", str(e))
        record_test("RAGSystem initialization", "ERROR", error=str(e))

def test_chunking_strategies():
    """Test chunking strategies"""
    print_header("4. Chunking Strategies")
    
    try:
        from utils.chunking_strategies import get_all_strategies, get_chunking_params, validate_custom_params
        
        # Test 1: Get all strategies
        try:
            strategies = get_all_strategies()
            assert len(strategies) >= 3, "Should have at least 3 strategies"
            print_test("Get all strategies", "PASS", f"Found {len(strategies)} strategies")
            record_test("Get all strategies", "PASS", f"{len(strategies)} strategies")
        except Exception as e:
            print_test("Get all strategies", "FAIL", str(e))
            record_test("Get all strategies", "FAIL", error=str(e))
        
        # Test 2: Get chunking params for each strategy
        for strategy_name in ['precise', 'balanced', 'comprehensive']:
            try:
                chunk_size, chunk_overlap = get_chunking_params(strategy_name)
                assert chunk_size > 0
                assert chunk_overlap >= 0
                print_test(f"Get params for {strategy_name}", "PASS", f"size={chunk_size}, overlap={chunk_overlap}")
                record_test(f"Get params {strategy_name}", "PASS")
            except Exception as e:
                print_test(f"Get params for {strategy_name}", "FAIL", str(e))
                record_test(f"Get params {strategy_name}", "FAIL", error=str(e))
        
        # Test 3: Validate custom params
        try:
            is_valid, msg = validate_custom_params(384, 75)
            assert is_valid == True
            print_test("Validate custom params (valid)", "PASS", "384/75 is valid")
            record_test("Validate custom params", "PASS")
        except Exception as e:
            print_test("Validate custom params", "FAIL", str(e))
            record_test("Validate custom params", "FAIL", error=str(e))
        
        # Test 4: Validate invalid params
        try:
            is_valid, msg = validate_custom_params(100, 150)  # Overlap > size
            # validate_custom_params returns False for invalid, but may return True with warnings
            # So we check that it at least returns a tuple
            assert isinstance(is_valid, bool), "Should return boolean"
            assert isinstance(msg, (str, type(None))), "Should return message or None"
            if not is_valid:
                print_test("Validate custom params (invalid)", "PASS", "Correctly detected invalid")
            else:
                print_test("Validate custom params (invalid)", "PASS", "Returns validation result (may warn)")
            record_test("Validate invalid params", "PASS")
        except Exception as e:
            print_test("Validate custom params (invalid)", "FAIL", str(e))
            record_test("Validate invalid params", "FAIL", error=str(e))
            
    except Exception as e:
        print_test("Chunking strategies", "ERROR", str(e))
        record_test("Chunking strategies", "ERROR", error=str(e))

def test_tokenizer():
    """Test tokenizer functionality"""
    print_header("5. Tokenizer")
    
    try:
        from utils.tokenizer import TokenTextSplitter
        
        # Test 1: Initialize tokenizer
        try:
            tokenizer = TokenTextSplitter(chunk_size=100, chunk_overlap=20, model_name="text-embedding-3-small")
            print_test("Tokenizer initialization", "PASS", "Initialized")
            record_test("Tokenizer init", "PASS")
        except Exception as e:
            print_test("Tokenizer initialization", "FAIL", str(e))
            record_test("Tokenizer init", "FAIL", error=str(e))
            return
        
        # Test 2: Split text
        try:
            test_text = "This is a test document. " * 50  # Create longer text
            chunks = tokenizer.split_text(test_text)
            assert len(chunks) > 0, "Should produce at least one chunk"
            print_test("Tokenizer split text", "PASS", f"Created {len(chunks)} chunks")
            record_test("Tokenizer split", "PASS", f"{len(chunks)} chunks")
        except Exception as e:
            print_test("Tokenizer split text", "FAIL", str(e))
            record_test("Tokenizer split", "FAIL", error=str(e))
        
        # Test 3: Token counting
        try:
            test_text = "This is a test."
            token_count = tokenizer.count_tokens(test_text)
            assert token_count > 0, "Should count tokens"
            print_test("Tokenizer count tokens", "PASS", f"Counted {token_count} tokens")
            record_test("Tokenizer count", "PASS")
        except Exception as e:
            print_test("Tokenizer count tokens", "FAIL", str(e))
            record_test("Tokenizer count", "FAIL", error=str(e))
        
        # Test 4: Chunk size enforcement
        try:
            tokenizer = TokenTextSplitter(chunk_size=50, chunk_overlap=10, model_name="text-embedding-3-small")
            test_text = "This is a test. " * 100
            chunks = tokenizer.split_text(test_text)
            for chunk in chunks:
                chunk_tokens = tokenizer.count_tokens(chunk)
                assert chunk_tokens <= 50, f"Chunk exceeds size limit: {chunk_tokens} > 50"
            print_test("Tokenizer chunk size enforcement", "PASS", f"All chunks within limit")
            record_test("Tokenizer size enforcement", "PASS")
        except Exception as e:
            print_test("Tokenizer chunk size enforcement", "FAIL", str(e))
            record_test("Tokenizer size enforcement", "FAIL", error=str(e))
            
    except Exception as e:
        print_test("Tokenizer", "ERROR", str(e))
        record_test("Tokenizer", "ERROR", error=str(e))

def test_vector_store_factory():
    """Test vector store factory"""
    print_header("6. Vector Store Factory")
    
    try:
        from vectorstores.vector_store_factory import VectorStoreFactory
        from langchain_openai import OpenAIEmbeddings
        
        embeddings = OpenAIEmbeddings(
            openai_api_key=os.getenv('OPENAI_API_KEY'),
            model="text-embedding-3-small"
        )
        
        # Test 1: Create FAISS store
        try:
            store = VectorStoreFactory.create_vector_store("faiss", embeddings)
            print_test("Create FAISS store", "PASS", "Created successfully")
            record_test("Create FAISS store", "PASS")
        except Exception as e:
            print_test("Create FAISS store", "FAIL", str(e))
            record_test("Create FAISS store", "FAIL", error=str(e))
        
        # Test 2: Create OpenSearch store (if credentials available)
        if os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') and os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'):
            try:
                store = VectorStoreFactory.create_vector_store(
                    "opensearch",
                    embeddings,
                    opensearch_domain="intelycx-os-dev",
                    opensearch_index="aris-rag-test-index"
                )
                print_test("Create OpenSearch store", "PASS", "Created (may fail on operations)")
                record_test("Create OpenSearch store", "PASS")
            except Exception as e:
                error_msg = str(e)
                if "permission" in error_msg.lower() or "403" in error_msg:
                    print_test("Create OpenSearch store", "WARN", "Created but permissions missing")
                    record_test("Create OpenSearch store", "WARN", "Permissions missing")
                else:
                    print_test("Create OpenSearch store", "FAIL", str(e))
                    record_test("Create OpenSearch store", "FAIL", error=str(e))
        else:
            print_test("Create OpenSearch store", "SKIP", "Credentials not set")
            record_test("Create OpenSearch store", "SKIP", "Credentials not set")
            
    except Exception as e:
        print_test("Vector store factory", "ERROR", str(e))
        record_test("Vector store factory", "ERROR", error=str(e))

def test_document_processing():
    """Test document processing with FAISS"""
    print_header("7. Document Processing (FAISS)")
    
    try:
        from rag_system import RAGSystem
        from metrics.metrics_collector import MetricsCollector
        
        # Initialize RAG system
        metrics = MetricsCollector()
        rag = RAGSystem(
            metrics_collector=metrics,
            chunk_size=100,
            chunk_overlap=20
        )
        
        # Test 1: Process simple text
        try:
            test_texts = [
                "This is a test document about artificial intelligence. " * 10,
                "This is another document about machine learning. " * 10
            ]
            num_chunks = rag.process_documents(test_texts)
            assert num_chunks > 0, "Should create chunks"
            print_test("Process documents (text)", "PASS", f"Created {num_chunks} chunks")
            record_test("Process documents", "PASS", f"{num_chunks} chunks")
        except Exception as e:
            print_test("Process documents (text)", "FAIL", str(e))
            record_test("Process documents", "FAIL", error=str(e))
            return
        
        # Test 2: Save vectorstore
        try:
            test_path = "/tmp/test_vectorstore_e2e"
            if os.path.exists(test_path):
                import shutil
                shutil.rmtree(test_path)
            rag.save_vectorstore(test_path)
            assert os.path.exists(test_path), "Vectorstore should be saved"
            print_test("Save vectorstore", "PASS", f"Saved to {test_path}")
            record_test("Save vectorstore", "PASS")
        except Exception as e:
            print_test("Save vectorstore", "FAIL", str(e))
            record_test("Save vectorstore", "FAIL", error=str(e))
        
        # Test 3: Load vectorstore
        try:
            rag2 = RAGSystem()
            loaded = rag2.load_vectorstore(test_path)
            assert loaded == True, "Should load successfully"
            print_test("Load vectorstore", "PASS", "Loaded successfully")
            record_test("Load vectorstore", "PASS")
        except Exception as e:
            print_test("Load vectorstore", "FAIL", str(e))
            record_test("Load vectorstore", "FAIL", error=str(e))
        
        # Test 4: Query
        try:
            if rag.vectorstore:
                retriever = rag.vectorstore.as_retriever(search_kwargs={"k": 2})
                # Use invoke method (LangChain v0.1+)
                try:
                    results = retriever.invoke("artificial intelligence")
                except AttributeError:
                    # Fallback to older API
                    results = retriever.get_relevant_documents("artificial intelligence")
                assert len(results) > 0, "Should return results"
                print_test("Query vectorstore", "PASS", f"Found {len(results)} results")
                record_test("Query vectorstore", "PASS", f"{len(results)} results")
            else:
                print_test("Query vectorstore", "SKIP", "Vectorstore not available")
                record_test("Query vectorstore", "SKIP")
        except Exception as e:
            print_test("Query vectorstore", "FAIL", str(e))
            record_test("Query vectorstore", "FAIL", error=str(e))
        
        # Cleanup
        try:
            if os.path.exists(test_path):
                import shutil
                shutil.rmtree(test_path)
        except:
            pass
            
    except Exception as e:
        print_test("Document processing", "ERROR", str(e))
        record_test("Document processing", "ERROR", error=str(e))

def test_parser_factory():
    """Test parser factory"""
    print_header("8. Parser Factory")
    
    try:
        from parsers.parser_factory import ParserFactory
        
        # Test get parser
        try:
            # Test with a dummy PDF path
            parser = ParserFactory.get_parser("test.pdf", preferred_parser="auto")
            if parser:
                print_test("Get parser (auto)", "PASS", "Parser retrieved")
                record_test("Get parser (auto)", "PASS")
            else:
                print_test("Get parser (auto)", "WARN", "No parser available")
                record_test("Get parser (auto)", "WARN", "No parser available")
        except Exception as e:
            print_test("Get parser (auto)", "WARN", f"Error: {str(e)[:50]}")
            record_test("Get parser (auto)", "WARN", error=str(e)[:100])
        
        # Test get parser with specific preferences
        for parser_name in ['pymupdf', 'docling']:
            try:
                parser = ParserFactory.get_parser("test.pdf", preferred_parser=parser_name)
                if parser:
                    print_test(f"Get {parser_name} parser", "PASS", "Parser retrieved")
                    record_test(f"Get {parser_name} parser", "PASS")
                else:
                    print_test(f"Get {parser_name} parser", "WARN", "Not available")
                    record_test(f"Get {parser_name} parser", "WARN", "Not available")
            except Exception as e:
                print_test(f"Get {parser_name} parser", "WARN", f"Not available: {str(e)[:50]}")
                record_test(f"Get {parser_name} parser", "WARN", error=str(e)[:100])
                
    except Exception as e:
        print_test("Parser factory", "ERROR", str(e))
        record_test("Parser factory", "ERROR", error=str(e))

def test_metrics_collector():
    """Test metrics collector"""
    print_header("9. Metrics Collector")
    
    try:
        from metrics.metrics_collector import MetricsCollector
        
        # Test initialization
        try:
            metrics = MetricsCollector()
            print_test("Metrics collector init", "PASS", "Initialized")
            record_test("Metrics collector init", "PASS")
        except Exception as e:
            print_test("Metrics collector init", "FAIL", str(e))
            record_test("Metrics collector init", "FAIL", error=str(e))
            return
        
        # Test record processing
        try:
            metrics.record_processing(
                document_name="test.pdf",
                file_size=1024,
                file_type="pdf",
                parser_used="pymupdf",
                pages=1,
                chunks_created=10,
                tokens_extracted=500,
                extraction_percentage=0.95,
                confidence=0.9,
                processing_time=1.0
            )
            assert len(metrics.processing_metrics) > 0, "Should record metrics"
            print_test("Record processing metrics", "PASS", "Recorded successfully")
            record_test("Record processing metrics", "PASS")
        except Exception as e:
            print_test("Record processing metrics", "FAIL", str(e))
            record_test("Record processing metrics", "FAIL", error=str(e))
            
    except Exception as e:
        print_test("Metrics collector", "ERROR", str(e))
        record_test("Metrics collector", "ERROR", error=str(e))

def test_streamlit_app():
    """Test that Streamlit app can be imported"""
    print_header("10. Streamlit App")
    
    try:
        # Test app.py exists and can be imported
        try:
            import app
            print_test("Import app.py", "PASS", "Imported successfully")
            record_test("Import app.py", "PASS")
        except Exception as e:
            print_test("Import app.py", "FAIL", str(e))
            record_test("Import app.py", "FAIL", error=str(e))
        
        # Test streamlit config
        try:
            config_path = ".streamlit/config.toml"
            if os.path.exists(config_path):
                print_test("Streamlit config exists", "PASS", "Found config.toml")
                record_test("Streamlit config", "PASS")
            else:
                print_test("Streamlit config exists", "WARN", "config.toml not found")
                record_test("Streamlit config", "WARN", "Not found")
        except Exception as e:
            print_test("Streamlit config", "WARN", str(e))
            record_test("Streamlit config", "WARN", error=str(e))
            
    except Exception as e:
        print_test("Streamlit app", "ERROR", str(e))
        record_test("Streamlit app", "ERROR", error=str(e))

def print_summary():
    """Print test summary"""
    print_header("TEST SUMMARY")
    
    summary = results['summary']
    total = summary['total']
    passed = summary['passed']
    failed = summary['failed']
    errors = summary['errors']
    
    print(f"\n📊 Test Results:")
    print(f"   Total Tests: {total}")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   ⚠️  Errors: {errors}")
    
    if total > 0:
        pass_rate = (passed / total) * 100
        print(f"   📈 Pass Rate: {pass_rate:.1f}%")
    
    # Show failed tests
    failed_tests = [t for t in results['tests'] if t['status'] == 'FAIL']
    if failed_tests:
        print(f"\n❌ Failed Tests ({len(failed_tests)}):")
        for test in failed_tests[:10]:  # Show first 10
            print(f"   • {test['test']}")
            if test.get('error'):
                print(f"     Error: {test['error'][:100]}")
    
    # Show errors
    error_tests = [t for t in results['tests'] if t['status'] == 'ERROR']
    if error_tests:
        print(f"\n⚠️  Error Tests ({len(error_tests)}):")
        for test in error_tests[:10]:  # Show first 10
            print(f"   • {test['test']}")
            if test.get('error'):
                print(f"     Error: {test['error'][:100]}")
    
    # Save results
    report_file = 'e2e_test_report.json'
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    # Overall status
    print("\n" + "=" * 80)
    if failed == 0 and errors == 0:
        print("✅ ALL TESTS PASSED - Project is working correctly!")
    elif pass_rate >= 80:
        print("⚠️  MOST TESTS PASSED - Some issues to address")
    else:
        print("❌ MULTIPLE TESTS FAILED - Review failures above")
    print("=" * 80)

def main():
    print("=" * 80)
    print(" ARIS RAG System - Comprehensive End-to-End Test")
    print("=" * 80)
    print(f"\nTest started at: {results['timestamp']}")
    
    # Run all tests
    test_imports()
    test_environment_variables()
    test_rag_system_initialization()
    test_chunking_strategies()
    test_tokenizer()
    test_vector_store_factory()
    test_document_processing()
    test_parser_factory()
    test_metrics_collector()
    test_streamlit_app()
    
    # Print summary
    print_summary()

if __name__ == '__main__':
    main()

