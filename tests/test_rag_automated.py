#!/usr/bin/env python3
"""
Automated RAG System Testing
Tests all RAG options systematically on the server
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector
from utils.chunking_strategies import get_all_strategies, get_chunking_params

load_dotenv()

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_test(name):
    print(f"{Colors.BOLD}🧪 {name}{Colors.END}")

def print_success(msg):
    print(f"{Colors.GREEN}   ✅ {msg}{Colors.END}")

def print_warning(msg):
    print(f"{Colors.YELLOW}   ⚠️  {msg}{Colors.END}")

def print_error(msg):
    print(f"{Colors.RED}   ❌ {msg}{Colors.END}")

def print_info(msg):
    print(f"{Colors.BLUE}   ℹ️  {msg}{Colors.END}")

class RAGTestSuite:
    """Comprehensive RAG system test suite"""
    
    def __init__(self, test_file: str):
        self.test_file = Path(test_file)
        self.results = {
            'chunking_strategies': {},
            'embedding_models': {},
            'parsers': {},
            'vector_stores': {},
            'queries': {}
        }
        self.test_queries = [
            "What is this document about?",
            "What are the main topics?",
            "Summarize the key points"
        ]
        
    def test_chunking_strategy(self, strategy_name: str) -> bool:
        """Test a chunking strategy"""
        print_test(f"Chunking Strategy: {strategy_name.title()}")
        
        try:
            # Get chunking parameters
            if strategy_name.lower() == "custom":
                chunk_size, chunk_overlap = 512, 100
            else:
                chunk_size, chunk_overlap = get_chunking_params(strategy_name.lower())
            
            # Create RAG system with strategy
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            # Process document
            processor = DocumentProcessor(rag_system)
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            start_time = time.time()
            result = processor.process_document(
                file_path=str(self.test_file),
                file_content=file_content,
                file_name=self.test_file.name,
                parser_preference="pymupdf"  # Use fast parser for testing
            )
            process_time = time.time() - start_time
            
            if result and result.status == 'success':
                # Count chunks
                if rag_system.vectorstore:
                    chunks = rag_system.vectorstore.similarity_search("test", k=1000)
                    chunk_count = len(chunks)
                else:
                    chunk_count = result.chunks_created
                
                print_success(f"Processed: {chunk_count} chunks in {process_time:.2f}s")
                print_info(f"Chunk size: {chunk_size}, Overlap: {chunk_overlap}")
                return True
            else:
                print_error(f"Processing failed: {result.error if result else 'Unknown error'}")
                return False
                
        except Exception as e:
            print_error(f"Test failed: {str(e)}")
            return False
    
    def test_embedding_model(self, embedding_model: str) -> bool:
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
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            result = processor.process_document(
                file_path=str(self.test_file),
                file_content=file_content,
                file_name=self.test_file.name,
                parser_preference="pymupdf"
            )
            
            if result and result.status == 'success' and rag_system.vectorstore:
                # Test retrieval
                query = "What is this document about?"
                docs = rag_system.vectorstore.similarity_search(query, k=3)
                
                if docs:
                    print_success(f"Embedding working: Retrieved {len(docs)} documents")
                    return True
                else:
                    print_warning("No documents retrieved")
                    return False
            else:
                print_error("Document processing failed")
                return False
                
        except Exception as e:
            print_error(f"Test failed: {str(e)}")
            return False
    
    def test_parser(self, parser_name: str) -> bool:
        """Test a parser"""
        print_test(f"Parser: {parser_name.title()}")
        
        try:
            from parsers.parser_factory import ParserFactory
            
            # Read file
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            # Parse
            start_time = time.time()
            parsed_doc = ParserFactory.parse_document(
                file_path=str(self.test_file),
                file_content=file_content,
                preferred_parser=parser_name if parser_name != "auto" else None
            )
            parse_time = time.time() - start_time
            
            if parsed_doc and parsed_doc.text and len(parsed_doc.text) > 0:
                text_length = len(parsed_doc.text)
                extraction_rate = parsed_doc.extraction_percentage if hasattr(parsed_doc, 'extraction_percentage') else 0
                
                print_success(f"Parsed: {text_length} chars in {parse_time:.2f}s")
                if extraction_rate > 0:
                    print_info(f"Extraction rate: {extraction_rate:.1f}%")
                return True
            else:
                print_warning("Parser returned empty result")
                return False
                
        except Exception as e:
            print_error(f"Parser test failed: {str(e)}")
            return False
    
    def test_vector_store(self, vector_store_type: str) -> bool:
        """Test a vector store"""
        print_test(f"Vector Store: {vector_store_type.upper()}")
        
        try:
            metrics = MetricsCollector()
            
            # Check for OpenSearch credentials
            if vector_store_type.lower() == "opensearch":
                if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
                    print_warning("OpenSearch credentials not found, skipping")
                    return None  # Skip, not a failure
            
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
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            result = processor.process_document(
                file_path=str(self.test_file),
                file_content=file_content,
                file_name=self.test_file.name,
                parser_preference="pymupdf"
            )
            
            if result and result.status == 'success' and rag_system.vectorstore:
                # Test query
                query = "What is this document about?"
                docs = rag_system.vectorstore.similarity_search(query, k=3)
                
                if docs:
                    print_success(f"Vector store working: Retrieved {len(docs)} documents")
                    return True
                else:
                    print_warning("No documents retrieved")
                    return False
            else:
                print_error("Document processing failed")
                return False
                
        except Exception as e:
            print_error(f"Vector store test failed: {str(e)}")
            return False
    
    def test_query_functionality(self) -> bool:
        """Test query functionality"""
        print_test("Query Functionality")
        
        try:
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=384,
                chunk_overlap=75
            )
            
            # Process document first
            processor = DocumentProcessor(rag_system)
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            result = processor.process_document(
                file_path=str(self.test_file),
                file_content=file_content,
                file_name=self.test_file.name,
                parser_preference="pymupdf"
            )
            
            if not result or result.status != 'success' or not rag_system.vectorstore:
                print_error("Could not process document for query testing")
                return False
            
            # Test queries
            all_passed = True
            for query in self.test_queries:
                try:
                    # Test retrieval
                    docs = rag_system.vectorstore.similarity_search(query, k=3)
                    if docs:
                        # Test query_with_rag
                        result = rag_system.query_with_rag(query, k=3)
                        if result and result.get("answer"):
                            print_success(f"Query: '{query[:50]}...' - Answer generated")
                        else:
                            print_warning(f"Query: '{query[:50]}...' - No answer")
                            all_passed = False
                    else:
                        print_warning(f"Query: '{query[:50]}...' - No documents retrieved")
                        all_passed = False
                except Exception as e:
                    print_error(f"Query failed: {str(e)}")
                    all_passed = False
            
            return all_passed
            
        except Exception as e:
            print_error(f"Query test failed: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        print_header("RAG System - Automated Testing")
        
        if not self.test_file.exists():
            print_error(f"Test file not found: {self.test_file}")
            return
        
        print_info(f"Test file: {self.test_file}")
        print_info(f"File size: {self.test_file.stat().st_size / 1024:.2f} KB\n")
        
        # Test Chunking Strategies
        print_header("TEST 1: Chunking Strategies")
        strategies = ["precise", "balanced", "comprehensive", "custom"]
        for strategy in strategies:
            self.results['chunking_strategies'][strategy] = self.test_chunking_strategy(strategy)
            time.sleep(1)
        
        # Test Embedding Models
        print_header("TEST 2: Embedding Models")
        embedding_models = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"]
        for model in embedding_models:
            self.results['embedding_models'][model] = self.test_embedding_model(model)
            time.sleep(1)
        
        # Test Parsers
        print_header("TEST 3: Parsers")
        parsers = ["pymupdf", "docling", "auto"]
        for parser in parsers:
            self.results['parsers'][parser] = self.test_parser(parser)
            time.sleep(1)
        
        # Test Vector Stores
        print_header("TEST 4: Vector Stores")
        vector_stores = ["faiss"]
        if os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
            vector_stores.append("opensearch")
        
        for vs in vector_stores:
            result = self.test_vector_store(vs)
            if result is not None:  # None means skipped
                self.results['vector_stores'][vs] = result
            time.sleep(1)
        
        # Test Queries
        print_header("TEST 5: Query Functionality")
        self.results['queries']['all'] = self.test_query_functionality()
        
        # Print Summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print_header("TEST SUMMARY")
        
        total_tests = 0
        passed_tests = 0
        
        print(f"\n{Colors.BOLD}Chunking Strategies:{Colors.END}")
        for strategy, success in self.results['chunking_strategies'].items():
            total_tests += 1
            if success:
                passed_tests += 1
            status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
            print(f"   {status} {strategy.title()}")
        
        print(f"\n{Colors.BOLD}Embedding Models:{Colors.END}")
        for model, success in self.results['embedding_models'].items():
            total_tests += 1
            if success:
                passed_tests += 1
            status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
            print(f"   {status} {model}")
        
        print(f"\n{Colors.BOLD}Parsers:{Colors.END}")
        for parser, success in self.results['parsers'].items():
            total_tests += 1
            if success:
                passed_tests += 1
            status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
            print(f"   {status} {parser.title()}")
        
        print(f"\n{Colors.BOLD}Vector Stores:{Colors.END}")
        for vs, success in self.results['vector_stores'].items():
            total_tests += 1
            if success:
                passed_tests += 1
            status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
            print(f"   {status} {vs.upper()}")
        
        print(f"\n{Colors.BOLD}Queries:{Colors.END}")
        for query_type, success in self.results['queries'].items():
            total_tests += 1
            if success:
                passed_tests += 1
            status = f"{Colors.GREEN}✅{Colors.END}" if success else f"{Colors.RED}❌{Colors.END}"
            print(f"   {status} {query_type.title()}")
        
        print(f"\n{Colors.BOLD}Overall Results:{Colors.END}")
        print(f"   Tests Passed: {Colors.GREEN}{passed_tests}/{total_tests}{Colors.END}")
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"   Success Rate: {Colors.GREEN}{success_rate:.1f}%{Colors.END}")
        
        if passed_tests == total_tests:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ All tests passed!{Colors.END}\n")
        else:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed. Check output above.{Colors.END}\n")

def main():
    # Find test file
    test_file = None
    samples_dir = Path("samples")
    
    if samples_dir.exists():
        pdf_files = list(samples_dir.glob("*.pdf"))
        if pdf_files:
            test_file = pdf_files[0]  # Use first PDF found
    
    if not test_file or not test_file.exists():
        print_error("No test PDF file found in samples/ directory")
        print_info("Please add a PDF file to samples/ directory")
        return
    
    # Run tests
    suite = RAGTestSuite(str(test_file))
    suite.run_all_tests()

if __name__ == "__main__":
    main()






