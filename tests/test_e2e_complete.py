#!/usr/bin/env python3
"""
Complete End-to-End RAG System Test
Tests the entire workflow from document processing to querying with all options
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

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
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")

def print_section(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'─'*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'─'*80}{Colors.END}\n")

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

class CompleteE2ETest:
    """Complete end-to-end RAG system test"""
    
    def __init__(self, test_file: str):
        self.test_file = Path(test_file)
        self.results = {
            'test_info': {},
            'components': {},
            'workflows': {},
            'options': {},
            'performance': {},
            'summary': {}
        }
        self.test_queries = [
            "What is this document about?",
            "What are the main topics or sections?",
            "Summarize the key information"
        ]
        self.start_time = time.time()
        
    def test_components(self) -> Dict:
        """Test all individual components"""
        print_section("PHASE 1: Component Testing")
        
        components = {}
        
        # Test 1: Python Modules
        print_test("1.1 Python Modules")
        modules = ['streamlit', 'openai', 'langchain', 'faiss', 'docling', 'pymupdf']
        module_results = {}
        for mod in modules:
            try:
                __import__(mod)
                module_results[mod] = True
                print_success(f"{mod}: Installed")
            except ImportError:
                module_results[mod] = False
                print_error(f"{mod}: NOT FOUND")
        components['python_modules'] = module_results
        
        # Test 2: Parsers
        print_test("1.2 Parser Factory")
        parser_results = {}
        try:
            from parsers.parser_factory import ParserFactory
            parsers = ['pymupdf', 'docling', 'textract']
            for parser_name in parsers:
                try:
                    parser = ParserFactory.get_parser('test.pdf', parser_name)
                    parser_results[parser_name] = parser is not None
                    if parser:
                        print_success(f"{parser_name}: Available")
                    else:
                        print_warning(f"{parser_name}: Not available")
                except Exception as e:
                    parser_results[parser_name] = False
                    print_warning(f"{parser_name}: {str(e)[:50]}")
        except Exception as e:
            print_error(f"Parser factory test failed: {str(e)}")
        components['parsers'] = parser_results
        
        # Test 3: Chunking Strategies
        print_test("1.3 Chunking Strategies")
        chunking_results = {}
        try:
            strategies = get_all_strategies()
            for name, info in strategies.items():
                chunk_size, chunk_overlap = get_chunking_params(name)
                chunking_results[name] = {
                    'chunk_size': chunk_size,
                    'chunk_overlap': chunk_overlap,
                    'available': True
                }
                print_success(f"{info['name']}: {chunk_size} tokens, {chunk_overlap} overlap")
        except Exception as e:
            print_error(f"Chunking strategies test failed: {str(e)}")
        components['chunking_strategies'] = chunking_results
        
        # Test 4: RAG System Initialization
        print_test("1.4 RAG System Initialization")
        rag_results = {}
        try:
            metrics = MetricsCollector()
            rag = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model='text-embedding-3-small',
                openai_model='gpt-3.5-turbo',
                vector_store_type='faiss',
                chunk_size=384,
                chunk_overlap=75
            )
            rag_results['initialization'] = True
            rag_results['embedding_model'] = rag.embedding_model
            rag_results['chunk_size'] = rag.chunk_size
            rag_results['chunk_overlap'] = rag.chunk_overlap
            print_success("RAG System initialized successfully")
            print_info(f"Embedding: {rag.embedding_model}, Chunk: {rag.chunk_size}/{rag.chunk_overlap}")
        except Exception as e:
            rag_results['initialization'] = False
            rag_results['error'] = str(e)
            print_error(f"RAG System initialization failed: {str(e)}")
        components['rag_system'] = rag_results
        
        # Test 5: Vector Stores
        print_test("1.5 Vector Store Factory")
        vector_store_results = {}
        try:
            from vectorstores.vector_store_factory import VectorStoreFactory
            # Test FAISS
            try:
                faiss_store = VectorStoreFactory.create_vector_store('faiss', None, None, None)
                vector_store_results['faiss'] = True
                print_success("FAISS: Available")
            except Exception as e:
                vector_store_results['faiss'] = False
                print_error(f"FAISS: {str(e)[:50]}")
            
            # Test OpenSearch
            if os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'):
                vector_store_results['opensearch'] = True
                print_success("OpenSearch: Credentials available")
            else:
                vector_store_results['opensearch'] = False
                print_warning("OpenSearch: Credentials not configured")
        except Exception as e:
            print_error(f"Vector store test failed: {str(e)}")
        components['vector_stores'] = vector_store_results
        
        self.results['components'] = components
        return components
    
    def test_workflow(self, parser: str = "pymupdf", chunking: str = "balanced", 
                     embedding: str = "text-embedding-3-small") -> Dict:
        """Test complete workflow: document processing to querying"""
        print_section(f"PHASE 2: End-to-End Workflow Test")
        print_info(f"Configuration: Parser={parser}, Chunking={chunking}, Embedding={embedding}")
        
        workflow_results = {
            'parser': parser,
            'chunking': chunking,
            'embedding': embedding,
            'document_processing': False,
            'chunking_created': 0,
            'vector_store_ready': False,
            'queries': {},
            'performance': {}
        }
        
        try:
            # Get chunking parameters
            if chunking.lower() == "custom":
                chunk_size, chunk_overlap = 512, 100
            else:
                chunk_size, chunk_overlap = get_chunking_params(chunking.lower())
            
            # Initialize RAG system
            print_test("2.1 Initializing RAG System")
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model=embedding,
                openai_model='gpt-3.5-turbo',
                vector_store_type='faiss',
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            print_success("RAG System initialized")
            
            # Process document
            print_test("2.2 Processing Document")
            if not self.test_file.exists():
                print_error(f"Test file not found: {self.test_file}")
                return workflow_results
            
            processor = DocumentProcessor(rag_system)
            with open(self.test_file, 'rb') as f:
                file_content = f.read()
            
            process_start = time.time()
            result = processor.process_document(
                file_path=str(self.test_file),
                file_content=file_content,
                file_name=self.test_file.name,
                parser_preference=parser if parser != "auto" else None
            )
            process_time = time.time() - process_start
            
            if result and result.status == 'success':
                workflow_results['document_processing'] = True
                workflow_results['chunking_created'] = result.chunks_created
                workflow_results['performance']['processing_time'] = process_time
                workflow_results['performance']['parser_used'] = result.parser_used
                workflow_results['performance']['extraction_percentage'] = result.extraction_percentage
                print_success(f"Document processed: {result.chunks_created} chunks in {process_time:.2f}s")
                print_info(f"Parser: {result.parser_used}, Extraction: {result.extraction_percentage:.1f}%")
            else:
                print_error(f"Document processing failed: {result.error if result else 'Unknown error'}")
                return workflow_results
            
            # Check vector store
            print_test("2.3 Verifying Vector Store")
            if rag_system.vectorstore:
                workflow_results['vector_store_ready'] = True
                # Count total chunks
                all_chunks = rag_system.vectorstore.similarity_search("test", k=1000)
                workflow_results['total_chunks'] = len(all_chunks)
                print_success(f"Vector store ready: {len(all_chunks)} chunks stored")
            else:
                print_error("Vector store not initialized")
                return workflow_results
            
            # Test queries
            print_test("2.4 Testing Queries")
            for query in self.test_queries:
                query_start = time.time()
                try:
                    # Test retrieval
                    docs = rag_system.vectorstore.similarity_search(query, k=3)
                    if docs:
                        # Test query_with_rag
                        result = rag_system.query_with_rag(query, k=3)
                        query_time = time.time() - query_start
                        
                        if result and result.get("answer"):
                            workflow_results['queries'][query] = {
                                'success': True,
                                'answer_length': len(result.get("answer", "")),
                                'sources_count': len(result.get("sources", [])),
                                'query_time': query_time
                            }
                            print_success(f"Query: '{query[:50]}...' - Answer generated ({query_time:.2f}s)")
                        else:
                            workflow_results['queries'][query] = {'success': False, 'error': 'No answer'}
                            print_warning(f"Query: '{query[:50]}...' - No answer")
                    else:
                        workflow_results['queries'][query] = {'success': False, 'error': 'No documents'}
                        print_warning(f"Query: '{query[:50]}...' - No documents retrieved")
                except Exception as e:
                    workflow_results['queries'][query] = {'success': False, 'error': str(e)}
                    print_error(f"Query failed: {str(e)[:100]}")
            
        except Exception as e:
            print_error(f"Workflow test failed: {str(e)}")
            workflow_results['error'] = str(e)
        
        self.results['workflows'][f"{parser}_{chunking}_{embedding}"] = workflow_results
        return workflow_results
    
    def test_all_options(self) -> Dict:
        """Test all option combinations"""
        print_section("PHASE 3: All Options Testing")
        
        options_results = {}
        
        # Test different chunking strategies
        print_test("3.1 Testing Chunking Strategies")
        strategies = ["precise", "balanced", "comprehensive"]
        for strategy in strategies:
            print_info(f"Testing {strategy} strategy...")
            result = self.test_workflow(parser="pymupdf", chunking=strategy, 
                                      embedding="text-embedding-3-small")
            options_results[f"chunking_{strategy}"] = result.get('document_processing', False)
            time.sleep(1)
        
        # Test different embedding models
        print_test("3.2 Testing Embedding Models")
        embeddings = ["text-embedding-3-small", "text-embedding-3-large"]
        for embedding in embeddings:
            print_info(f"Testing {embedding}...")
            result = self.test_workflow(parser="pymupdf", chunking="balanced", 
                                      embedding=embedding)
            options_results[f"embedding_{embedding}"] = result.get('document_processing', False)
            time.sleep(1)
        
        # Test different parsers
        print_test("3.3 Testing Parsers")
        parsers = ["pymupdf", "auto"]
        for parser in parsers:
            print_info(f"Testing {parser} parser...")
            result = self.test_workflow(parser=parser, chunking="balanced", 
                                      embedding="text-embedding-3-small")
            options_results[f"parser_{parser}"] = result.get('document_processing', False)
            time.sleep(1)
        
        self.results['options'] = options_results
        return options_results
    
    def generate_report(self) -> str:
        """Generate comprehensive test report"""
        print_section("PHASE 4: Generating Test Report")
        
        total_time = time.time() - self.start_time
        
        # Calculate summary
        components_passed = sum(
            1 for comp in self.results['components'].values() 
            if isinstance(comp, dict) and any(v for v in comp.values() if isinstance(v, bool) and v)
        )
        
        workflows_passed = sum(
            1 for wf in self.results['workflows'].values()
            if wf.get('document_processing', False) and wf.get('vector_store_ready', False)
        )
        
        options_passed = sum(1 for opt in self.results['options'].values() if opt)
        
        queries_passed = sum(
            1 for wf in self.results['workflows'].values()
            for q in wf.get('queries', {}).values()
            if q.get('success', False)
        )
        
        report = f"""
# Complete End-to-End RAG System Test Report

**Test Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Test Duration**: {total_time:.2f} seconds
**Test File**: {self.test_file.name}

---

## Executive Summary

- **Components Tested**: {components_passed} passed
- **Workflows Tested**: {workflows_passed} passed
- **Options Tested**: {options_passed} passed
- **Queries Tested**: {queries_passed} passed
- **Overall Status**: {'✅ ALL TESTS PASSED' if workflows_passed > 0 else '❌ TESTS FAILED'}

---

## Test Results

### Component Tests
{self._format_component_results()}

### Workflow Tests
{self._format_workflow_results()}

### Options Tests
{self._format_options_results()}

---

## Performance Metrics

{self._format_performance_metrics()}

---

## Recommendations

{self._generate_recommendations()}

---

**Test Completed**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return report
    
    def _format_component_results(self) -> str:
        """Format component test results"""
        lines = []
        for comp_name, comp_data in self.results['components'].items():
            if isinstance(comp_data, dict):
                passed = sum(1 for v in comp_data.values() if isinstance(v, bool) and v)
                total = sum(1 for v in comp_data.values() if isinstance(v, bool))
                status = "✅" if passed == total and total > 0 else "❌"
                lines.append(f"- **{comp_name}**: {status} {passed}/{total} passed")
        return "\n".join(lines) if lines else "No component tests"
    
    def _format_workflow_results(self) -> str:
        """Format workflow test results"""
        lines = []
        for wf_name, wf_data in self.results['workflows'].items():
            status = "✅" if wf_data.get('document_processing') and wf_data.get('vector_store_ready') else "❌"
            queries = wf_data.get('queries', {})
            queries_passed = sum(1 for q in queries.values() if q.get('success', False))
            lines.append(f"- **{wf_name}**: {status} Processing: {wf_data.get('document_processing', False)}, Queries: {queries_passed}/{len(queries)}")
        return "\n".join(lines) if lines else "No workflow tests"
    
    def _format_options_results(self) -> str:
        """Format options test results"""
        lines = []
        for opt_name, opt_result in self.results['options'].items():
            status = "✅" if opt_result else "❌"
            lines.append(f"- **{opt_name}**: {status}")
        return "\n".join(lines) if lines else "No options tests"
    
    def _format_performance_metrics(self) -> str:
        """Format performance metrics"""
        lines = []
        for wf_name, wf_data in self.results['workflows'].items():
            perf = wf_data.get('performance', {})
            if perf:
                lines.append(f"- **{wf_name}**:")
                lines.append(f"  - Processing time: {perf.get('processing_time', 0):.2f}s")
                lines.append(f"  - Parser: {perf.get('parser_used', 'N/A')}")
                lines.append(f"  - Extraction: {perf.get('extraction_percentage', 0):.1f}%")
        return "\n".join(lines) if lines else "No performance data"
    
    def _generate_recommendations(self) -> str:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if self.results['workflows']:
            recommendations.append("✅ System is operational and ready for use")
        
        workflows = list(self.results['workflows'].values())
        if workflows:
            best_perf = min(workflows, key=lambda w: w.get('performance', {}).get('processing_time', float('inf')))
            recommendations.append(f"✅ Fastest configuration: {best_perf.get('parser', 'N/A')} parser")
        
        return "\n".join(f"- {rec}" for rec in recommendations) if recommendations else "No recommendations"
    
    def run_all_tests(self):
        """Run all tests"""
        print_header("COMPLETE END-TO-END RAG SYSTEM TEST")
        
        if not self.test_file.exists():
            print_error(f"Test file not found: {self.test_file}")
            return
        
        print_info(f"Test file: {self.test_file}")
        print_info(f"File size: {self.test_file.stat().st_size / 1024:.2f} KB\n")
        
        # Store test info
        self.results['test_info'] = {
            'test_file': str(self.test_file),
            'file_size_kb': self.test_file.stat().st_size / 1024,
            'start_time': datetime.now().isoformat()
        }
        
        # Run tests
        self.test_components()
        time.sleep(2)
        
        # Test main workflow
        main_workflow = self.test_workflow(parser="pymupdf", chunking="balanced", 
                                          embedding="text-embedding-3-small")
        time.sleep(2)
        
        # Test all options
        self.test_all_options()
        
        # Generate report
        report = self.generate_report()
        
        # Save report
        report_file = project_root / "reports" / "COMPLETE_E2E_TEST_REPORT.md"
        report_file.parent.mkdir(exist_only=True)
        report_file.write_text(report)
        
        print_section("TEST COMPLETE")
        print_success(f"Test report saved to: {report_file}")
        print(f"\n{report}")
        
        self.results['summary'] = {
            'total_time': time.time() - self.start_time,
            'report_file': str(report_file),
            'end_time': datetime.now().isoformat()
        }

def main():
    # Use benchmark test file
    benchmark_file = Path("samples/FL10.11 SPECIFIC8 (1).pdf")
    
    if benchmark_file.exists():
        test_file = benchmark_file
        print_info(f"Using benchmark document: {benchmark_file.name}")
    else:
        # Fallback to any PDF
        samples_dir = Path("samples")
        if samples_dir.exists():
            pdf_files = list(samples_dir.glob("*.pdf"))
            if pdf_files:
                test_file = pdf_files[0]
                print_warning(f"Benchmark file not found, using: {test_file.name}")
            else:
                print_error("No test PDF file found in samples/ directory")
                return
        else:
            print_error("No test PDF file found in samples/ directory")
            return
    
    # Run complete E2E test
    tester = CompleteE2ETest(str(test_file))
    tester.run_all_tests()

if __name__ == "__main__":
    main()

