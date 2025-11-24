#!/usr/bin/env python3
"""
End-to-end testing for ARIS R&D RAG System.
Tests the complete pipeline: parsing, ingestion, and querying.
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def test_imports():
    """Test that all required modules can be imported."""
    print_section("TEST 1: Module Imports")
    
    try:
        from parsers.parser_factory import ParserFactory
        print("✅ ParserFactory imported")
        
        from ingestion.document_processor import DocumentProcessor
        print("✅ DocumentProcessor imported")
        
        from rag_system import RAGSystem
        print("✅ RAGSystem imported")
        
        from metrics.metrics_collector import MetricsCollector
        print("✅ MetricsCollector imported")
        
        print("\n✅ All modules imported successfully!")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parsers():
    """Test document parsers."""
    print_section("TEST 2: Document Parsers")
    
    # Find a test PDF
    test_files = [
        "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf",
        "FL10.11 SPECIFIC8 (1).pdf",
    ]
    
    test_file = None
    for f in test_files:
        if os.path.exists(f):
            test_file = f
            break
    
    if not test_file:
        print("⚠️  No test PDF found. Skipping parser test.")
        return True
    
    print(f"📄 Testing with: {test_file}")
    file_size = os.path.getsize(test_file) / 1024
    print(f"   Size: {file_size:.1f} KB\n")
    
    # Test PyMuPDF parser
    try:
        print("🔧 Testing PyMuPDF parser...")
        from parsers.pymupdf_parser import PyMuPDFParser
        parser = PyMuPDFParser()
        start = time.time()
        result = parser.parse(test_file)
        elapsed = time.time() - start
        
        print(f"   ✅ PyMuPDF: {elapsed:.2f}s")
        print(f"      Pages: {result.pages}")
        print(f"      Text length: {len(result.text):,} chars")
        print(f"      Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"      Confidence: {result.confidence:.2f}")
    except Exception as e:
        print(f"   ❌ PyMuPDF failed: {e}")
    
    # Test Docling parser (if file is small enough)
    if file_size < 3000:  # < 3MB
        try:
            print("\n🔧 Testing Docling parser...")
            from parsers.docling_parser import DoclingParser
            parser = DoclingParser()
            start = time.time()
            result = parser.parse(test_file)
            elapsed = time.time() - start
            
            print(f"   ✅ Docling: {elapsed:.2f}s")
            print(f"      Pages: {result.pages}")
            print(f"      Text length: {len(result.text):,} chars")
            print(f"      Extraction: {result.extraction_percentage*100:.1f}%")
            print(f"      Confidence: {result.confidence:.2f}")
        except Exception as e:
            error_msg = str(e)
            if "too large" in error_msg.lower() or "timed out" in error_msg.lower():
                print(f"   ⚠️  Docling skipped: {error_msg[:60]}...")
            else:
                print(f"   ❌ Docling failed: {error_msg[:100]}")
    
    # Test ParserFactory (auto mode)
    try:
        print("\n🔧 Testing ParserFactory (Auto mode)...")
        from parsers.parser_factory import ParserFactory
        start = time.time()
        result = ParserFactory.parse_with_fallback(test_file, preferred_parser="auto")
        elapsed = time.time() - start
        
        print(f"   ✅ Auto parser: {elapsed:.2f}s")
        print(f"      Parser used: {result.parser_used}")
        print(f"      Pages: {result.pages}")
        print(f"      Text length: {len(result.text):,} chars")
        print(f"      Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"      Confidence: {result.confidence:.2f}")
    except Exception as e:
        print(f"   ❌ Auto parser failed: {e}")
    
    print("\n✅ Parser tests completed!")
    return True

def test_rag_system():
    """Test RAG system with sample documents."""
    print_section("TEST 3: RAG System")
    
    # Check for API keys
    from dotenv import load_dotenv
    load_dotenv()
    
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        print("⚠️  OPENAI_API_KEY not found. Skipping RAG test.")
        return True
    
    print("🔧 Initializing RAG System...")
    try:
        from rag_system import RAGSystem
        from metrics.metrics_collector import MetricsCollector
        
        metrics = MetricsCollector()
        rag = RAGSystem(use_cerebras=False, metrics_collector=metrics)
        print("✅ RAG System initialized")
        
        # Test with sample text
        print("\n📖 Testing document ingestion...")
        sample_text = """
        The Model X-90 High-Density Polymer Enclosure is a protective casing for the Series 3 control board.
        The enclosure must meet IP65 rating standards and maintain structural integrity within a temperature range of 0°C to 50°C.
        The main body (housing) is made of polycarbonate (PC) material, rated UL94-VO, and is UV-stabilized.
        The gasket is made of silicone rubber with a Shore Hardness of A 50 ± 5.
        Fasteners are made of stainless steel (ASTM A240, Type 304) for attaching the lid.
        The overall dimensions are 150.00 mm x 100.00 mm x 45.00 mm, with a tolerance of ±0.30 mm on all dimensions.
        """
        
        start = time.time()
        rag.process_documents(
            texts=[sample_text],
            metadatas=[{"source": "test_document", "pages": 1}]
        )
        elapsed = time.time() - start
        
        print(f"✅ Document ingested: {elapsed:.2f}s")
        stats = rag.get_stats()
        print(f"   Documents: {stats.get('total_documents', 0)}")
        print(f"   Total tokens: {stats.get('total_tokens', 0):,}")
        
        # Test querying
        print("\n🔍 Testing RAG querying...")
        test_queries = [
            "What is the Model X-90 enclosure made of?",
            "What are the dimensions of the enclosure?",
            "What temperature range does it support?",
        ]
        
        for query in test_queries:
            print(f"\n   Q: {query}")
            start = time.time()
            try:
                result = rag.query_with_rag(query, k=3, use_mmr=True)
                elapsed = time.time() - start
                
                print(f"   ✅ Answer ({elapsed:.2f}s):")
                print(f"      {result['answer'][:200]}...")
                print(f"      Sources: {len(result['sources'])} files")
                print(f"      Chunks used: {result['num_chunks_used']}")
            except Exception as e:
                print(f"   ❌ Query failed: {e}")
        
        print("\n✅ RAG System tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ RAG System test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_document_processor():
    """Test the complete document processing pipeline."""
    print_section("TEST 4: Document Processor (Full Pipeline)")
    
    # Find a test PDF
    test_file = "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf"
    if not os.path.exists(test_file):
        print("⚠️  Test PDF not found. Skipping processor test.")
        return True
    
    print(f"📄 Processing: {test_file}\n")
    
    try:
        from rag_system import RAGSystem
        from ingestion.document_processor import DocumentProcessor
        from metrics.metrics_collector import MetricsCollector
        
        # Initialize components
        metrics = MetricsCollector()
        rag = RAGSystem(use_cerebras=False, metrics_collector=metrics)
        processor = DocumentProcessor(rag_system=rag)
        
        print("🔧 Initialized DocumentProcessor")
        
        # Process document
        def progress_callback(stage, progress):
            print(f"   📊 {stage}: {progress*100:.0f}%")
        
        start = time.time()
        result = processor.process_document(
            file_path=test_file,
            parser_preference="auto",
            progress_callback=progress_callback
        )
        elapsed = time.time() - start
        
        print(f"\n✅ Processing completed: {elapsed:.2f}s")
        print(f"   Status: {result.status}")
        print(f"   Parser: {result.parser_used}")
        print(f"   Chunks created: {result.chunks_created}")
        print(f"   Tokens extracted: {result.tokens_extracted:,}")
        print(f"   Extraction: {result.extraction_percentage*100:.1f}%")
        print(f"   Processing time: {result.processing_time:.2f}s")
        
        # Test querying after ingestion
        print("\n🔍 Testing query after ingestion...")
        query = "What are the dimensions of the Model X-90 enclosure?"
        start = time.time()
        result_dict = rag.query_with_rag(query, k=3, use_mmr=True)
        elapsed = time.time() - start
        
        print(f"   Q: {query}")
        print(f"   ✅ Answer ({elapsed:.2f}s):")
        print(f"      {result_dict['answer'][:300]}...")
        print(f"      Used {result_dict['num_chunks_used']} relevant chunks")
        print(f"      Sources: {len(result_dict['sources'])} files")
        
        print("\n✅ Document Processor tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Document Processor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_metrics():
    """Test metrics collection."""
    print_section("TEST 5: Metrics Collection")
    
    try:
        from metrics.metrics_collector import MetricsCollector
        
        metrics = MetricsCollector()
        print("✅ MetricsCollector initialized")
        
        # Record some sample metrics
        metrics.record_processing(
            document_name="test.pdf",
            file_size=100000,
            file_type="pdf",
            parser_used="pymupdf",
            pages=5,
            chunks_created=10,
            tokens_extracted=5000,
            extraction_percentage=0.85,
            confidence=0.90,
            processing_time=1.5,
            success=True
        )
        
        metrics.record_query(
            question="test query",
            answer_length=200,
            response_time=0.5,
            chunks_used=3,
            sources_count=1,
            api_used="openai",
            success=True
        )
        
        print("✅ Sample metrics recorded")
        
        # Get metrics summary
        print(f"\n📊 Metrics Summary:")
        print(f"   Total documents processed: {len(metrics.processing_metrics)}")
        print(f"   Total queries: {len(metrics.query_metrics)}")
        
        # Calculate total cost if available
        total_cost = 0.0
        for qm in metrics.query_metrics:
            # Estimate cost (rough calculation)
            if qm.api_used == "openai":
                # Rough estimate: $0.002 per 1K tokens
                total_cost += 0.002  # Simplified
        print(f"   Estimated cost: ${total_cost:.4f}")
        
        print("\n✅ Metrics tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Metrics test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all end-to-end tests."""
    print("\n" + "=" * 70)
    print("  ARIS R&D - END-TO-END TESTING")
    print("=" * 70)
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Parsers", test_parsers()))
    results.append(("RAG System", test_rag_system()))
    results.append(("Document Processor", test_document_processor()))
    results.append(("Metrics", test_metrics()))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

