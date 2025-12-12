#!/usr/bin/env python3
"""
Complete OCR + RAG System Test
Tests OCR functionality with the RAG system end-to-end.
"""
import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test document
TEST_PDF = "samples/1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

def test_baseline_pymupdf():
    """Test 1: Baseline with PyMuPDF (no OCR)."""
    print_header("TEST 1: BASELINE - PyMuPDF (No OCR)")
    
    if not os.path.exists(TEST_PDF):
        print(f"❌ Test document not found: {TEST_PDF}")
        return None
    
    try:
        from parsers.pymupdf_parser import PyMuPDFParser
        
        parser = PyMuPDFParser()
        print("✓ PyMuPDFParser instantiated")
        
        print("Processing document (this should be fast)...")
        start = time.time()
        result = parser.parse(TEST_PDF)
        elapsed = time.time() - start
        
        text_length = len(result.text.strip())
        
        print(f"\n✓ Processing completed in {elapsed:.2f} seconds")
        print(f"\nResults:")
        print(f"  • Pages: {result.pages}")
        print(f"  • Text extracted: {text_length:,} characters")
        print(f"  • Images detected: {result.images_detected}")
        print(f"  • Extraction: {result.extraction_percentage * 100:.1f}%")
        print(f"  • Confidence: {result.confidence:.2f}")
        
        baseline = {
            'parser': 'pymupdf',
            'pages': result.pages,
            'text_length': text_length,
            'images_detected': result.images_detected,
            'extraction_percentage': result.extraction_percentage,
            'confidence': result.confidence,
            'processing_time': elapsed,
            'timestamp': datetime.now().isoformat()
        }
        
        if result.images_detected and text_length == 0:
            print("\n✅ EXPECTED: Images detected but no text extracted")
            print("   → Confirms PDF is image-based and needs OCR")
        
        return baseline
        
    except ImportError:
        print("❌ PyMuPDF not installed")
        print("   Install with: pip install pymupdf")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_ocr_docling():
    """Test 2: OCR with Docling."""
    print_header("TEST 2: OCR - Docling (With OCR)")
    
    if not os.path.exists(TEST_PDF):
        print(f"❌ Test document not found: {TEST_PDF}")
        return None
    
    try:
        from parsers.docling_parser import DoclingParser
        
        parser = DoclingParser()
        print("✓ DoclingParser instantiated")
        
        # Check OCR models
        models_available = parser._verify_ocr_models()
        if models_available:
            print("✓ OCR models available")
        else:
            print("⚠️  OCR models not found - OCR may not work")
            print("   Install with: docling download-models")
        
        # Test OCR configuration
        ocr_config = parser.test_ocr_configuration()
        print(f"\nOCR Configuration:")
        print(f"  • OCR Available: {ocr_config.get('ocr_available', False)}")
        print(f"  • Models Available: {ocr_config.get('models_available', False)}")
        print(f"  • Config Success: {ocr_config.get('config_success', False)}")
        
        if ocr_config.get('errors'):
            print(f"  • Errors: {ocr_config['errors']}")
        
        print("\n⚠️  Processing with OCR (this will take 5-20 minutes)...")
        print("   Starting OCR processing...")
        
        start = time.time()
        
        # Progress callback
        def progress_callback(status, progress, **kwargs):
            elapsed = time.time() - start
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            print(f"   [{minutes}m {seconds}s] {status}: {progress*100:.1f}%")
        
        result = parser.parse(TEST_PDF, progress_callback=progress_callback)
        
        elapsed = time.time() - start
        text_length = len(result.text.strip())
        
        print(f"\n✓ OCR processing completed in {elapsed/60:.1f} minutes")
        print(f"\nResults:")
        print(f"  • Pages: {result.pages}")
        print(f"  • Text extracted: {text_length:,} characters")
        print(f"  • Images detected: {result.images_detected}")
        print(f"  • Extraction: {result.extraction_percentage * 100:.1f}%")
        print(f"  • Confidence: {result.confidence:.2f}")
        print(f"  • Parser used: {result.parser_used}")
        
        ocr_result = {
            'parser': 'docling',
            'pages': result.pages,
            'text_length': text_length,
            'images_detected': result.images_detected,
            'extraction_percentage': result.extraction_percentage,
            'confidence': result.confidence,
            'processing_time': elapsed,
            'timestamp': datetime.now().isoformat()
        }
        
        if text_length > 0:
            print("\n✅ SUCCESS: OCR extracted text from images!")
            print(f"   → Extracted {text_length:,} characters from image-based PDF")
        else:
            print("\n⚠️  WARNING: No text extracted")
            print("   → OCR may have failed or document has no readable text")
        
        return ocr_result
        
    except ImportError:
        print("❌ Docling not installed")
        print("   Install with: pip install docling")
        print("   Then run: docling download-models")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_rag_integration(ocr_result):
    """Test 3: RAG System Integration."""
    print_header("TEST 3: RAG SYSTEM INTEGRATION")
    
    if not ocr_result or ocr_result['text_length'] == 0:
        print("⚠️  Skipping RAG test - no OCR text extracted")
        return None
    
    try:
        from rag_system import RAGSystem
        from ingestion.document_processor import DocumentProcessor
        from metrics.metrics_collector import MetricsCollector
        from config.settings import ARISConfig
        
        print("Initializing RAG system...")
        metrics = MetricsCollector()
        rag = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics,
            embedding_model=ARISConfig.EMBEDDING_MODEL,
            openai_model=ARISConfig.OPENAI_MODEL,
            vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
            chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
            chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
        )
        print("✓ RAG system initialized")
        
        processor = DocumentProcessor(rag)
        print("✓ Document processor initialized")
        
        # Read file
        with open(TEST_PDF, 'rb') as f:
            file_content = f.read()
        
        print("\nProcessing document through RAG pipeline...")
        print("  (Chunking, embedding, storing in vectorstore)")
        
        start = time.time()
        result = processor.process_document(
            file_path=TEST_PDF,
            file_content=file_content,
            file_name=os.path.basename(TEST_PDF),
            parser_preference='docling'
        )
        elapsed = time.time() - start
        
        if result.status == 'success':
            print(f"\n✓ RAG processing completed in {elapsed:.2f} seconds")
            print(f"\nResults:")
            print(f"  • Chunks created: {result.chunks_created}")
            print(f"  • Tokens extracted: {result.tokens_extracted:,}")
            print(f"  • Parser used: {result.parser_used}")
            print(f"  • Extraction: {result.extraction_percentage * 100:.1f}%")
            
            rag_result = {
                'status': 'success',
                'chunks_created': result.chunks_created,
                'tokens_extracted': result.tokens_extracted,
                'parser_used': result.parser_used,
                'processing_time': elapsed,
                'timestamp': datetime.now().isoformat()
            }
            
            return rag_result
        else:
            print(f"\n❌ RAG processing failed: {result.error}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_query_functionality(rag_system):
    """Test 4: Query Functionality."""
    print_header("TEST 4: QUERY FUNCTIONALITY")
    
    if not rag_system or rag_system.vectorstore is None:
        print("⚠️  Skipping query test - no vectorstore available")
        return None
    
    try:
        print("Testing queries with OCR-extracted content...")
        
        test_queries = [
            "What is this document about?",
            "What are the main specifications?",
            "What is the model number?",
        ]
        
        results = []
        for query in test_queries:
            print(f"\nQuery: {query}")
            try:
                result = rag_system.query_with_rag(
                    question=query,
                    k=3
                )
                
                if result and 'answer' in result:
                    answer = result['answer']
                    sources = result.get('sources', [])
                    citations = result.get('citations', [])
                    
                    print(f"  ✓ Answer length: {len(answer)} characters")
                    print(f"  ✓ Sources: {len(sources)}")
                    print(f"  ✓ Citations: {len(citations)}")
                    print(f"  Answer preview: {answer[:150]}...")
                    
                    results.append({
                        'query': query,
                        'answer_length': len(answer),
                        'sources': len(sources),
                        'citations': len(citations),
                        'success': True
                    })
                else:
                    print("  ⚠️  No answer returned")
                    results.append({
                        'query': query,
                        'success': False
                    })
            except Exception as e:
                print(f"  ❌ Query error: {e}")
                results.append({
                    'query': query,
                    'success': False,
                    'error': str(e)
                })
        
        return results
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def compare_results(baseline, ocr_result):
    """Compare baseline vs OCR results."""
    print_header("COMPARISON: PyMuPDF vs Docling OCR")
    
    if not baseline or not ocr_result:
        print("⚠️  Cannot compare - missing results")
        return
    
    print("\nText Extraction Comparison:")
    print(f"  PyMuPDF:  {baseline['text_length']:,} characters")
    print(f"  Docling:  {ocr_result['text_length']:,} characters")
    
    improvement = ocr_result['text_length'] - baseline['text_length']
    if baseline['text_length'] > 0:
        improvement_pct = (improvement / baseline['text_length']) * 100
    else:
        improvement_pct = float('inf') if improvement > 0 else 0
    
    print(f"  Improvement: {improvement:,} characters ({improvement_pct:.1f}%)")
    
    print("\nProcessing Time Comparison:")
    print(f"  PyMuPDF:  {baseline['processing_time']:.2f} seconds")
    print(f"  Docling:  {ocr_result['processing_time']/60:.1f} minutes")
    
    print("\nExtraction Percentage:")
    print(f"  PyMuPDF:  {baseline['extraction_percentage']*100:.1f}%")
    print(f"  Docling:  {ocr_result['extraction_percentage']*100:.1f}%")
    
    if ocr_result['text_length'] > baseline['text_length']:
        print("\n✅ OCR SUCCESS: Docling extracted significantly more text!")
        print("   → OCR is working correctly")
    elif ocr_result['text_length'] == baseline['text_length']:
        print("\n⚠️  WARNING: OCR extracted same amount as baseline")
        print("   → OCR may not be working or document has text layer")
    else:
        print("\n⚠️  WARNING: OCR extracted less than baseline")
        print("   → This is unexpected, check OCR configuration")

def main():
    """Run all tests."""
    print("=" * 70)
    print("COMPLETE OCR + RAG SYSTEM TEST")
    print("=" * 70)
    print(f"\nTest document: {TEST_PDF}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    all_results = {}
    
    # Test 1: Baseline
    baseline = test_baseline_pymupdf()
    all_results['baseline'] = baseline
    
    # Test 2: OCR
    ocr_result = test_ocr_docling()
    all_results['ocr'] = ocr_result
    
    # Comparison
    if baseline and ocr_result:
        compare_results(baseline, ocr_result)
    
    # Test 3: RAG Integration
    if ocr_result and ocr_result['text_length'] > 0:
        rag_result = test_rag_integration(ocr_result)
        all_results['rag'] = rag_result
        
        # Test 4: Queries (if RAG worked)
        if rag_result and rag_result['status'] == 'success':
            from rag_system import RAGSystem
            from metrics.metrics_collector import MetricsCollector
            from config.settings import ARISConfig
            
            metrics = MetricsCollector()
            rag = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model=ARISConfig.EMBEDDING_MODEL,
                openai_model=ARISConfig.OPENAI_MODEL,
                vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
                chunk_size=ARISConfig.DEFAULT_CHUNK_SIZE,
                chunk_overlap=ARISConfig.DEFAULT_CHUNK_OVERLAP
            )
            # Load vectorstore if it exists
            vectorstore_path = ARISConfig.get_vectorstore_path()
            if os.path.exists(vectorstore_path):
                rag.load_vectorstore(vectorstore_path)
            
            query_results = test_query_functionality(rag)
            all_results['queries'] = query_results
    
    # Save all results
    results_file = 'ocr_rag_test_results.json'
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n✓ All results saved to {results_file}")
    
    # Final summary
    print_header("TEST SUMMARY")
    
    if baseline:
        print("✓ Baseline test completed")
    else:
        print("✗ Baseline test failed (PyMuPDF not installed)")
    
    if ocr_result:
        if ocr_result['text_length'] > 0:
            print("✓ OCR test completed - text extracted from images")
        else:
            print("⚠️  OCR test completed but no text extracted")
    else:
        print("✗ OCR test failed (Docling not installed)")
    
    if all_results.get('rag'):
        print("✓ RAG integration test completed")
    else:
        print("⚠️  RAG integration test skipped or failed")
    
    if all_results.get('queries'):
        successful_queries = sum(1 for q in all_results['queries'] if q.get('success'))
        print(f"✓ Query test completed ({successful_queries}/{len(all_results['queries'])} successful)")
    else:
        print("⚠️  Query test skipped or failed")
    
    print("\n" + "=" * 70)
    
    return 0 if (baseline and ocr_result) else 1

if __name__ == "__main__":
    sys.exit(main())

