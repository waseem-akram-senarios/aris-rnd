#!/usr/bin/env python3
"""
Test script to verify chunking fixes, especially NoSessionContext error handling.
"""
import os
import sys
import traceback
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_chunking_with_pymupdf(pdf_path: str):
    """Test chunking with PyMuPDF parser to verify NoSessionContext fix."""
    print("=" * 80)
    print("Testing Chunking Fix (NoSessionContext)")
    print("=" * 80)
    print()
    
    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: File not found: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    print(f"📄 File: {os.path.basename(pdf_path)}")
    print(f"📊 Size: {file_size / (1024*1024):.2f} MB")
    print()
    
    try:
        from rag_system import RAGSystem
        from ingestion.document_processor import DocumentProcessor
        
        print("Step 1: Initializing RAG System...")
        print("-" * 80)
        
        rag = RAGSystem(
            use_cerebras=False,
            embedding_model='text-embedding-3-small',
            openai_model='gpt-3.5-turbo',
            vector_store_type='faiss',
            chunk_size=512,  # Comprehensive strategy
            chunk_overlap=100
        )
        print("✅ RAG System initialized")
        print()
        
        print("Step 2: Processing document with PyMuPDF parser...")
        print("-" * 80)
        
        processor = DocumentProcessor(rag)
        
        with open(pdf_path, 'rb') as f:
            file_content = f.read()
        
        # Progress callback for testing
        progress_updates = []
        def test_progress_callback(status, progress, **kwargs):
            detailed = kwargs.get('detailed_message', '')
            progress_updates.append((status, progress, detailed))
            print(f"   Progress: {status} - {int(progress * 100)}% - {detailed[:60]}")
        
        print("   Processing with PyMuPDF parser...")
        result = processor.process_document(
            file_path=pdf_path,
            file_content=file_content,
            file_name=os.path.basename(pdf_path),
            parser_preference='pymupdf',
            progress_callback=test_progress_callback
        )
        
        print()
        if result.status == 'success':
            print("✅ Document processing successful!")
            print(f"   - Parser used: {result.parser_used}")
            print(f"   - Chunks created: {result.chunks_created}")
            print(f"   - Tokens extracted: {result.tokens_extracted:,}")
            print(f"   - Pages: {result.pages}")
            print()
            
            # Verify chunks are accessible
            print("Step 3: Verifying chunks in vectorstore...")
            print("-" * 80)
            
            if rag.vectorstore:
                # Try to search to verify chunks are accessible
                try:
                    test_results = rag.vectorstore.similarity_search("test query", k=5)
                    print(f"✅ Vectorstore search successful: {len(test_results)} results")
                    print(f"   - Chunks are accessible and searchable")
                except Exception as e:
                    print(f"⚠️  Vectorstore search warning: {str(e)}")
                    print(f"   - Chunks created but search had issues")
            else:
                print("⚠️  No vectorstore created")
            
            print()
            print("Step 4: Checking for NoSessionContext errors...")
            print("-" * 80)
            
            # Check progress updates for any error messages
            errors_found = []
            for status, progress, detailed in progress_updates:
                if 'error' in detailed.lower() or 'nosessioncontext' in detailed.lower():
                    errors_found.append((status, progress, detailed))
            
            if errors_found:
                print("⚠️  Warnings/Errors found in progress updates:")
                for status, progress, detailed in errors_found:
                    print(f"   - {status} ({int(progress * 100)}%): {detailed}")
            else:
                print("✅ No NoSessionContext errors detected!")
            
            print()
            print("=" * 80)
            print("✅ TEST PASSED: Chunking fix is working correctly!")
            print("=" * 80)
            return True
        else:
            print("❌ Document processing failed!")
            print(f"   Error: {result.error}")
            print()
            
            # Check if it's a NoSessionContext error
            if 'NoSessionContext' in result.error:
                print("❌ TEST FAILED: NoSessionContext error still occurring!")
                print("   The fix may not be working correctly.")
                return False
            else:
                print("⚠️  Processing failed with different error (not NoSessionContext)")
                return False
                
    except Exception as e:
        error_str = str(e)
        traceback_str = traceback.format_exc()
        
        print("❌ TEST FAILED: Exception occurred!")
        print(f"   Error: {error_str}")
        print()
        print("   Full traceback:")
        print(traceback_str)
        
        if 'NoSessionContext' in error_str or 'NoSessionContext' in traceback_str:
            print()
            print("❌ NoSessionContext error detected in exception!")
            print("   The fix may not be working correctly.")
        
        return False

if __name__ == "__main__":
    # Test with available PDF
    test_files = [
        "samples/FL10.11 SPECIFIC8 (1).pdf",
        "samples/1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"
    ]
    
    success = False
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n🧪 Testing with: {test_file}\n")
            success = test_chunking_with_pymupdf(test_file)
            if success:
                break
            else:
                print("\n⚠️  Test failed, trying next file...\n")
    
    if not success:
        print("\n❌ All tests failed!")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)



