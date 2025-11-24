#!/usr/bin/env python3
"""
Automated test script for testing PDF processing.
Tests the entire pipeline: parsing, chunking, and vectorstore creation.
"""
import os
import sys
import traceback
from pathlib import Path

def test_pdf_processing(pdf_path: str):
    """Test PDF processing with full pipeline."""
    print("=" * 80)
    print(f"Testing PDF: {pdf_path}")
    print("=" * 80)
    print()
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"❌ ERROR: File not found: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    print(f"📄 File size: {file_size / (1024*1024):.2f} MB")
    print()
    
    # Test 1: Parse PDF
    print("Step 1: Testing PDF Parsing...")
    print("-" * 80)
    try:
        from parsers.parser_factory import ParserFactory
        
        with open(pdf_path, 'rb') as f:
            file_content = f.read()
        
        parsed_doc = ParserFactory.parse_with_fallback(
            pdf_path,
            file_content,
            preferred_parser=None  # Auto mode
        )
        
        print(f"✅ Parsing successful!")
        print(f"   - Parser used: {parsed_doc.parser_used}")
        print(f"   - Pages: {parsed_doc.pages}")
        print(f"   - Text length: {len(parsed_doc.text):,} characters")
        print(f"   - Extraction %: {parsed_doc.extraction_percentage * 100:.1f}%")
        print(f"   - Confidence: {parsed_doc.confidence:.2f}")
        print(f"   - Images detected: {parsed_doc.images_detected}")
        
        if not parsed_doc.text or len(parsed_doc.text.strip()) == 0:
            print("⚠️  WARNING: Parsed text is empty!")
            print("   This PDF appears to be image-based (scanned).")
            print("   Options:")
            print("   1. Use Textract parser (requires AWS credentials)")
            print("   2. Use OCR software to convert images to text first")
            print()
            print("   Continuing test to see what happens with empty text...")
            # Don't return False - continue to see what happens
        
        print()
    except Exception as e:
        print(f"❌ Parsing failed: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Test 2: Tokenization and Chunking
    print("Step 2: Testing Tokenization and Chunking...")
    print("-" * 80)
    try:
        from utils.tokenizer import TokenTextSplitter
        
        splitter = TokenTextSplitter(
            chunk_size=384,
            chunk_overlap=75,
            model_name="text-embedding-3-small"
        )
        
        # Count tokens
        token_count = splitter.count_tokens(parsed_doc.text)
        print(f"✅ Token counting successful!")
        print(f"   - Total tokens: {token_count:,}")
        
        # Split into chunks
        text_chunks = splitter.split_text(parsed_doc.text)
        print(f"✅ Text splitting successful!")
        print(f"   - Number of chunks: {len(text_chunks)}")
        
        if len(text_chunks) == 0:
            print("⚠️  WARNING: No chunks created!")
            return False
        
        # Check chunk sizes
        chunk_tokens = [splitter.count_tokens(chunk) for chunk in text_chunks]
        print(f"   - Min tokens per chunk: {min(chunk_tokens)}")
        print(f"   - Max tokens per chunk: {max(chunk_tokens)}")
        print(f"   - Avg tokens per chunk: {sum(chunk_tokens) / len(chunk_tokens):.1f}")
        print()
        
    except Exception as e:
        print(f"❌ Tokenization/Chunking failed: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Test 3: Document Processing (with LangChain Documents)
    print("Step 3: Testing Document Processing...")
    print("-" * 80)
    try:
        try:
            from langchain.docstore.document import Document
        except ImportError:
            from langchain_core.documents import Document
        
        # Create Document object
        doc = Document(
            page_content=parsed_doc.text,
            metadata={
                'source': pdf_path,
                'parser_used': parsed_doc.parser_used,
                'pages': parsed_doc.pages
            }
        )
        
        # Split documents
        chunks = splitter.split_documents([doc])
        print(f"✅ Document splitting successful!")
        print(f"   - Number of document chunks: {len(chunks)}")
        
        if len(chunks) == 0:
            print("⚠️  WARNING: No document chunks created!")
            return False
        
        # Validate chunks
        valid_chunks = []
        for i, chunk in enumerate(chunks):
            if chunk is None:
                print(f"⚠️  WARNING: Chunk {i} is None")
                continue
            if not hasattr(chunk, 'page_content'):
                print(f"⚠️  WARNING: Chunk {i} missing page_content")
                continue
            if not chunk.page_content or not chunk.page_content.strip():
                print(f"⚠️  WARNING: Chunk {i} is empty")
                continue
            valid_chunks.append(chunk)
        
        print(f"   - Valid chunks: {len(valid_chunks)}/{len(chunks)}")
        
        if len(valid_chunks) == 0:
            print("❌ ERROR: No valid chunks!")
            return False
        
        print()
    except Exception as e:
        print(f"❌ Document processing failed: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Test 4: RAG System Processing
    print("Step 4: Testing RAG System Processing...")
    print("-" * 80)
    try:
        from rag_system import RAGSystem
        from metrics.metrics_collector import MetricsCollector
        
        metrics_collector = MetricsCollector()
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics_collector,
            embedding_model="text-embedding-3-small"
        )
        
        # Process document
        stats = rag_system.add_documents_incremental(
            texts=[parsed_doc.text],
            metadatas=[{
                'source': os.path.basename(pdf_path),
                'parser_used': parsed_doc.parser_used,
                'pages': parsed_doc.pages,
                'images_detected': parsed_doc.images_detected,
                'extraction_percentage': parsed_doc.extraction_percentage
            }]
        )
        
        print(f"✅ RAG system processing successful!")
        print(f"   - Chunks created: {stats['chunks_created']}")
        print(f"   - Tokens added: {stats['tokens_added']:,}")
        print(f"   - Total chunks: {stats['total_chunks']}")
        print(f"   - Total tokens: {stats['total_tokens']:,}")
        print()
        
    except Exception as e:
        print(f"❌ RAG system processing failed: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Test 5: Query Test
    print("Step 5: Testing Query Functionality...")
    print("-" * 80)
    try:
        # Test query
        test_question = "What is this document about?"
        result = rag_system.query_with_rag(test_question, k=3, use_mmr=True)
        
        print(f"✅ Query successful!")
        print(f"   - Question: {test_question}")
        print(f"   - Answer length: {len(result['answer'])} characters")
        print(f"   - Chunks used: {result.get('num_chunks_used', 0)}")
        print(f"   - Context tokens: {result.get('context_tokens', 0):,}")
        print(f"   - Response tokens: {result.get('response_tokens', 0):,}")
        print(f"   - Total tokens: {result.get('total_tokens', 0):,}")
        print()
        
    except Exception as e:
        print(f"❌ Query failed: {str(e)}")
        print(f"   Traceback: {traceback.format_exc()}")
        return False
    
    # Summary
    print("=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - PDF parsed successfully using {parsed_doc.parser_used}")
    print(f"  - {len(text_chunks)} chunks created")
    print(f"  - {token_count:,} total tokens")
    print(f"  - Vectorstore created and queryable")
    print()
    
    return True


if __name__ == "__main__":
    # PDF file to test
    pdf_file = "1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"
    
    # Try to find the file in current directory or common locations
    if os.path.exists(pdf_file):
        pdf_path = pdf_file
    else:
        # Try to find it in the workspace
        workspace = Path(__file__).parent
        pdf_path = workspace / pdf_file
        if not pdf_path.exists():
            print(f"❌ ERROR: Could not find PDF file: {pdf_file}")
            print(f"   Please ensure the file is in the current directory or provide the full path.")
            sys.exit(1)
        pdf_path = str(pdf_path)
    
    success = test_pdf_processing(pdf_path)
    sys.exit(0 if success else 1)

