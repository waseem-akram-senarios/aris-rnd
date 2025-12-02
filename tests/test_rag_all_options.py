#!/usr/bin/env python3
"""
Comprehensive RAG System Test - All Options
Tests all combinations of parsers, chunking strategies, vector stores, and models
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector
from utils.chunking_strategies import get_all_strategies, get_chunking_params

load_dotenv()

# Test configuration
TEST_PDF = "samples/1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf"
SAMPLE_QUERIES = [
    "What is this document about?",
    "What are the key specifications?",
    "What is the main topic?"
]

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_test(test_name):
    print(f"{Colors.BOLD}🧪 Testing: {test_name}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}   ✅ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}   ⚠️  {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}   ❌ {msg}{Colors.END}")

def test_parser(parser_name, test_file):
    """Test a specific parser"""
    print_test(f"Parser: {parser_name}")
    
    try:
        from parsers.parser_factory import ParserFactory
        
        parser = ParserFactory.get_parser(test_file, parser_name)
        if parser is None:
            print_warning(f"Parser {parser_name} not available")
            return False
        
        # Read file
        with open(test_file, 'rb') as f:
            file_content = f.read()
        
        # Parse
        start_time = time.time()
        result = parser.parse(test_file, file_content)
        parse_time = time.time() - start_time
        
        if result and result.text:
            text_length = len(result.text)
            print_success(f"Parsed successfully: {text_length} characters in {parse_time:.2f}s")
            return True
        else:
            print_warning(f"Parser returned empty result")
            return False
            
    except Exception as e:
        print_error(f"Parser failed: {str(e)}")
        return False

def test_chunking_strategy(strategy_name, rag_system, test_file):
    """Test a chunking strategy"""
    print_test(f"Chunking Strategy: {strategy_name}")
    
    try:
        # Get chunking parameters
        if strategy_name.lower() == "custom":
            chunk_size, chunk_overlap = 512, 100
        else:
            chunk_size, chunk_overlap = get_chunking_params(strategy_name.lower())
        
        # Update RAG system chunking
        rag_system.chunk_size = chunk_size
        rag_system.chunk_overlap = chunk_overlap
        rag_system.text_splitter = rag_system.text_splitter.__class__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=rag_system.embedding_model
        )
        
        # Process document
        processor = DocumentProcessor(rag_system)
        with open(test_file, 'rb') as f:
            file_content = f.read()
        
        result = processor.process_document(
            file_path=test_file,
            file_content=file_content,
            preferred_parser="pymupdf"  # Use fast parser for testing
        )
        
        if result and result.success:
            chunks_count = len(rag_system.vectorstore.similarity_search("test", k=1000)) if rag_system.vectorstore else 0
            print_success(f"Chunked successfully: {chunks_count} chunks (size: {chunk_size}, overlap: {chunk_overlap})")
            return True
        else:
            print_warning(f"Chunking failed")
            return False
            
    except Exception as e:
        print_error(f"Chunking failed: {str(e)}")
        return False

def test_vector_store(vector_store_type, test_file):
    """Test a vector store"""
    print_test(f"Vector Store: {vector_store_type.upper()}")
    
    try:
        metrics = MetricsCollector()
        
        # Create RAG system with vector store
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics,
            embedding_model="text-embedding-3-small",
            openai_model="gpt-3.5-turbo",
            vector_store_type=vector_store_type.lower(),
            chunk_size=384,
            chunk_overlap=75
        )
        
        # Process document
        processor = DocumentProcessor(rag_system)
        with open(test_file, 'rb') as f:
            file_content = f.read()
        
        result = processor.process_document(
            file_path=test_file,
            file_content=file_content,
            preferred_parser="pymupdf"
        )
        
        if result and result.success and rag_system.vectorstore:
            # Test query
            query = "What is this document about?"
            docs = rag_system.vectorstore.similarity_search(query, k=3)
            
            if docs:
                print_success(f"Vector store working: Retrieved {len(docs)} documents")
                return True
            else:
                print_warning(f"No documents retrieved")
                return False
        else:
            print_warning(f"Document processing failed")
            return False
            
    except Exception as e:
        print_error(f"Vector store test failed: {str(e)}")
        return False

def test_embedding_model(embedding_model, test_file):
    """Test an embedding model"""
    print_test(f"Embedding Model: {embedding_model}")
    
    try:
        metrics = MetricsCollector()
        
        rag_system = RAGSystem(
            use_cerebras=False,
            metrics_collector=metrics,
            embedding_model=embedding_model,
            openai_model="gpt-3.5-turbo",
            vector_store_type="faiss",
            chunk_size=384,
            chunk_overlap=75
        )
        
        # Process document
        processor = DocumentProcessor(rag_system)
        with open(test_file, 'rb') as f:
            file_content = f.read()
        
        result = processor.process_document(
            file_path=test_file,
            file_content=file_content,
            preferred_parser="pymupdf"
        )
        
        if result and result.success:
            # Test query
            query = "What is this document about?"
            docs = rag_system.vectorstore.similarity_search(query, k=3)
            
            if docs:
                print_success(f"Embedding model working: Retrieved {len(docs)} documents")
                return True
            else:
                print_warning(f"No documents retrieved")
                return False
        else:
            print_warning(f"Document processing failed")
            return False
            
    except Exception as e:
        print_error(f"Embedding model test failed: {str(e)}")
        return False

def test_query(rag_system, query):
    """Test query functionality"""
    try:
        if not rag_system.vectorstore:
            return False
        
        # Test retrieval
        docs = rag_system.vectorstore.similarity_search(query, k=3)
        
        if docs:
            # Test answer generation
            answer = rag_system.query(query)
            if answer and len(answer) > 0:
                return True
        return False
        
    except Exception as e:
        print_error(f"Query test failed: {str(e)}")
        return False

def main():
    print_header("RAG System - Comprehensive Options Test")
    
    # Check for test file
    test_file = Path(TEST_PDF)
    if not test_file.exists():
        print_error(f"Test file not found: {TEST_PDF}")
        print("Available sample files:")
        samples_dir = Path("samples")
        if samples_dir.exists():
            for f in samples_dir.glob("*.pdf"):
                print(f"   - {f}")
        return
    
    print(f"Using test file: {test_file}")
    print(f"File size: {test_file.stat().st_size / 1024:.2f} KB\n")
    
    results = {
        'parsers': {},
        'chunking': {},
        'vector_stores': {},
        'embedding_models': {},
        'queries': {}
    }
    
    # Test Parsers
    print_header("TEST 1: Parsers")
    parsers = ["pymupdf", "docling", "textract", "auto"]
    for parser in parsers:
        results['parsers'][parser] = test_parser(parser, str(test_file))
        time.sleep(1)  # Brief pause between tests
    
    # Test Chunking Strategies
    print_header("TEST 2: Chunking Strategies")
    metrics = MetricsCollector()
    rag_system = RAGSystem(
        use_cerebras=False,
        metrics_collector=metrics,
        vector_store_type="faiss",
        chunk_size=384,
        chunk_overlap=75
    )
    
    strategies = ["precise", "balanced", "comprehensive", "custom"]
    for strategy in strategies:
        results['chunking'][strategy] = test_chunking_strategy(strategy, rag_system, str(test_file))
        time.sleep(1)
    
    # Test Vector Stores
    print_header("TEST 3: Vector Stores")
    vector_stores = ["faiss"]
    # Only test OpenSearch if credentials available
    if os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
        vector_stores.append("opensearch")
    
    for vs in vector_stores:
        results['vector_stores'][vs] = test_vector_store(vs, str(test_file))
        time.sleep(1)
    
    # Test Embedding Models
    print_header("TEST 4: Embedding Models")
    embedding_models = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
    for model in embedding_models:
        results['embedding_models'][model] = test_embedding_model(model, str(test_file))
        time.sleep(1)
    
    # Test Queries
    print_header("TEST 5: Query Functionality")
    metrics = MetricsCollector()
    rag_system = RAGSystem(
        use_cerebras=False,
        metrics_collector=metrics,
        vector_store_type="faiss",
        chunk_size=384,
        chunk_overlap=75
    )
    
    # Process document first
    processor = DocumentProcessor(rag_system)
    with open(test_file, 'rb') as f:
        file_content = f.read()
    
    result = processor.process_document(
        file_path=str(test_file),
        file_content=file_content,
        preferred_parser="pymupdf"
    )
    
    if result and result.success:
        for query in SAMPLE_QUERIES:
            print_test(f"Query: {query}")
            success = test_query(rag_system, query)
            results['queries'][query] = success
            time.sleep(1)
    else:
        print_error("Could not process document for query testing")
    
    # Print Summary
    print_header("TEST SUMMARY")
    
    print(f"\n{Colors.BOLD}Parsers:{Colors.END}")
    for parser, success in results['parsers'].items():
        status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
        print(f"   {status} {parser}")
    
    print(f"\n{Colors.BOLD}Chunking Strategies:{Colors.END}")
    for strategy, success in results['chunking'].items():
        status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
        print(f"   {status} {strategy}")
    
    print(f"\n{Colors.BOLD}Vector Stores:{Colors.END}")
    for vs, success in results['vector_stores'].items():
        status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
        print(f"   {status} {vs}")
    
    print(f"\n{Colors.BOLD}Embedding Models:{Colors.END}")
    for model, success in results['embedding_models'].items():
        status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
        print(f"   {status} {model}")
    
    print(f"\n{Colors.BOLD}Queries:{Colors.END}")
    for query, success in results['queries'].items():
        status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
        print(f"   {status} {query[:50]}...")
    
    # Calculate totals
    total_tests = sum(len(v) for v in results.values())
    passed_tests = sum(sum(1 for s in v.values() if s) for v in results.values())
    
    print(f"\n{Colors.BOLD}Overall:{Colors.END}")
    print(f"   Tests Passed: {passed_tests}/{total_tests}")
    print(f"   Success Rate: {(passed_tests/total_tests*100):.1f}%")
    
    print(f"\n{Colors.GREEN}✅ Testing complete!{Colors.END}\n")

if __name__ == "__main__":
    main()

