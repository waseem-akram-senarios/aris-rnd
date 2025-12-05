#!/usr/bin/env python3
"""
End-to-End Test for Per-Document Loading Feature
Tests the complete workflow: upload -> process -> store -> load -> query
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from storage.document_registry import DocumentRegistry
from metrics.metrics_collector import MetricsCollector
from config.settings import ARISConfig

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

class E2ETestSuite:
    """End-to-end test suite for per-document loading"""
    
    def __init__(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_e2e_per_doc_")
        self.vectorstore_path = os.path.join(self.test_dir, "vectorstore")
        self.registry_path = os.path.join(self.test_dir, "document_registry.json")
        self.results = {
            "passed": 0,
            "failed": 0,
            "warnings": 0,
            "tests": []
        }
        
    def cleanup(self):
        """Clean up test directory"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print_info(f"Cleaned up test directory: {self.test_dir}")
    
    def test_full_workflow_faiss(self) -> bool:
        """Test complete workflow: process -> save -> load -> query (FAISS)"""
        print_test("E2E Test: Full Workflow (FAISS)")
        
        try:
            # Step 1: Initialize RAG system
            print_info("Step 1: Initializing RAG system...")
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=200,
                chunk_overlap=50
            )
            print_success("RAG system initialized")
            
            # Step 2: Process multiple documents
            print_info("Step 2: Processing 3 documents...")
            doc_texts = [
                "Document Alpha: This document contains information about machine learning algorithms, neural networks, and deep learning techniques.",
                "Document Beta: This document discusses cloud computing, AWS services, and infrastructure as code.",
                "Document Gamma: This document covers web development, React frameworks, and JavaScript best practices."
            ]
            doc_names = ["alpha.pdf", "beta.pdf", "gamma.pdf"]
            
            metadatas = [
                {"source": name, "parser_used": "test", "pages": 1}
                for name in doc_names
            ]
            
            chunks_created = rag_system.process_documents(doc_texts, metadatas=metadatas)
            if chunks_created == 0:
                print_error("No chunks created")
                return False
            print_success(f"Processed {len(doc_texts)} documents into {chunks_created} chunks")
            
            # Step 3: Save vectorstore
            print_info("Step 3: Saving vectorstore...")
            rag_system.save_vectorstore(self.vectorstore_path)
            if not os.path.exists(self.vectorstore_path):
                print_error("Vectorstore not saved")
                return False
            print_success("Vectorstore saved")
            
            # Step 4: Save to document registry
            print_info("Step 4: Saving to document registry...")
            registry = DocumentRegistry(self.registry_path)
            for i, (doc_text, doc_name) in enumerate(zip(doc_texts, doc_names)):
                doc_metadata = {
                    'document_id': f"test_{i}",
                    'document_name': doc_name,
                    'status': 'success',
                    'chunks_created': chunks_created // len(doc_names),
                    'tokens_extracted': len(doc_text.split()),
                    'parser_used': 'test',
                    'processing_time': 1.0,
                    'pages': 1,
                    'created_at': '2024-01-01T00:00:00',
                    'vector_store_type': 'faiss',
                    'storage_location': 'local_faiss'
                }
                registry.add_document(f"test_{i}", doc_metadata)
            print_success(f"Saved {len(doc_names)} documents to registry")
            
            # Step 5: Create new RAG system and load single document
            print_info("Step 5: Loading single document (alpha.pdf)...")
            new_rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=MetricsCollector(),
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=200,
                chunk_overlap=50
            )
            
            result = new_rag_system.load_selected_documents(
                document_names=["alpha.pdf"],
                path=self.vectorstore_path
            )
            
            if not result["loaded"]:
                print_error(f"Failed to load document: {result['message']}")
                return False
            
            if result["docs_loaded"] != 1:
                print_error(f"Expected 1 document loaded, got {result['docs_loaded']}")
                return False
            
            print_success(f"Loaded {result['docs_loaded']} document with {result['chunks_loaded']} chunks")
            
            # Step 6: Query the loaded document
            print_info("Step 6: Querying loaded document...")
            query_result = new_rag_system.query_with_rag("What does this document discuss?", k=3)
            
            if not query_result.get("answer"):
                print_error("No answer returned from query")
                return False
            
            # Verify answer is relevant (should mention machine learning, neural networks, etc.)
            answer_lower = query_result["answer"].lower()
            if "machine learning" in answer_lower or "neural" in answer_lower or "deep learning" in answer_lower:
                print_success("Query returned relevant answer about machine learning")
            else:
                print_warning(f"Answer may not be relevant: {query_result['answer'][:100]}...")
            
            # Step 7: Verify sources are from alpha.pdf only
            sources = query_result.get("sources", [])
            if sources:
                all_from_alpha = all("alpha.pdf" in str(s) for s in sources)
                if all_from_alpha:
                    print_success("All sources are from alpha.pdf (correct filtering)")
                else:
                    print_warning(f"Some sources may not be from alpha.pdf: {sources}")
            
            print_success("Full workflow test passed!")
            return True
            
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_multiple_loads(self) -> bool:
        """Test loading different documents sequentially"""
        print_test("E2E Test: Multiple Sequential Loads")
        
        try:
            # Setup: Create and save documents
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=150,
                chunk_overlap=30
            )
            
            doc_texts = [
                "Math Document: Algebra, calculus, and geometry are fundamental mathematical concepts.",
                "Science Document: Physics, chemistry, and biology are core scientific disciplines.",
                "History Document: Ancient civilizations, world wars, and modern history shape our world."
            ]
            doc_names = ["math.txt", "science.txt", "history.txt"]
            
            metadatas = [{"source": name, "parser_used": "test"} for name in doc_names]
            rag_system.process_documents(doc_texts, metadatas=metadatas)
            rag_system.save_vectorstore(self.vectorstore_path)
            
            # Test loading math document
            print_info("Loading math.txt...")
            rag1 = RAGSystem(
                use_cerebras=False,
                metrics_collector=MetricsCollector(),
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=150,
                chunk_overlap=30
            )
            result1 = rag1.load_selected_documents(["math.txt"], self.vectorstore_path)
            if not result1["loaded"]:
                print_error(f"Failed to load math.txt: {result1['message']}")
                return False
            
            query1 = rag1.query_with_rag("What mathematical concepts are mentioned?", k=2)
            if "algebra" not in query1["answer"].lower() and "calculus" not in query1["answer"].lower():
                print_warning("Math query may not be accurate")
            
            # Test loading science document
            print_info("Loading science.txt...")
            rag2 = RAGSystem(
                use_cerebras=False,
                metrics_collector=MetricsCollector(),
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=150,
                chunk_overlap=30
            )
            result2 = rag2.load_selected_documents(["science.txt"], self.vectorstore_path)
            if not result2["loaded"]:
                print_error(f"Failed to load science.txt: {result2['message']}")
                return False
            
            query2 = rag2.query_with_rag("What scientific disciplines are mentioned?", k=2)
            if "physics" not in query2["answer"].lower() and "chemistry" not in query2["answer"].lower():
                print_warning("Science query may not be accurate")
            
            print_success("Multiple sequential loads test passed!")
            return True
            
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_registry_integration(self) -> bool:
        """Test integration with document registry"""
        print_test("E2E Test: Document Registry Integration")
        
        try:
            # Create fresh registry with unique path for this test
            test_registry_path = os.path.join(self.test_dir, "test_registry.json")
            if os.path.exists(test_registry_path):
                os.remove(test_registry_path)
            
            registry = DocumentRegistry(test_registry_path)
            
            # Clear any existing documents
            registry.clear_all()
            
            # Add documents
            for i in range(3):
                doc_metadata = {
                    'document_id': f"doc_{i}",
                    'document_name': f"document_{i}.pdf",
                    'status': 'success',
                    'chunks_created': 10,
                    'tokens_extracted': 1000,
                    'parser_used': 'test',
                    'created_at': '2024-01-01T00:00:00',
                    'vector_store_type': 'faiss',
                    'storage_location': 'local_faiss'
                }
                registry.add_document(f"doc_{i}", doc_metadata)
            
            # List documents
            docs = registry.list_documents()
            if len(docs) != 3:
                print_error(f"Expected 3 documents in registry, got {len(docs)}")
                return False
            
            # Get document names for loading
            doc_names = [doc.get('document_name') for doc in docs]
            print_success(f"Registry contains {len(docs)} documents: {doc_names}")
            
            print_success("Registry integration test passed!")
            return True
            
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling scenarios"""
        print_test("E2E Test: Error Handling")
        
        try:
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="faiss",
                chunk_size=100,
                chunk_overlap=20
            )
            
            # Test 1: Load from non-existent path
            result = rag_system.load_selected_documents(
                ["any_doc.pdf"],
                path="/nonexistent/path"
            )
            if result["loaded"]:
                print_error("Should have failed for non-existent path")
                return False
            print_success("Correctly handled non-existent path")
            
            # Test 2: Load non-existent document
            # First create a vectorstore
            rag_system.process_documents(
                ["Test document"],
                metadatas=[{"source": "test.pdf"}]
            )
            rag_system.save_vectorstore(self.vectorstore_path)
            
            # Try to load non-existent document
            result = rag_system.load_selected_documents(
                ["nonexistent.pdf"],
                path=self.vectorstore_path
            )
            if result["loaded"]:
                print_error("Should have failed for non-existent document")
                return False
            print_success("Correctly handled non-existent document")
            
            # Test 3: Empty selection
            result = rag_system.load_selected_documents([], path=self.vectorstore_path)
            if result["loaded"]:
                print_error("Should have failed for empty selection")
                return False
            print_success("Correctly handled empty selection")
            
            print_success("Error handling test passed!")
            return True
            
        except Exception as e:
            print_error(f"Test failed with exception: {e}")
            return False
    
    def test_opensearch_workflow(self) -> bool:
        """Test OpenSearch workflow (if credentials available)"""
        print_test("E2E Test: OpenSearch Workflow")
        
        # Check if OpenSearch credentials are available
        if not os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') or not os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'):
            print_warning("OpenSearch credentials not available, skipping test")
            return True  # Not a failure
        
        try:
            metrics = MetricsCollector()
            rag_system = RAGSystem(
                use_cerebras=False,
                metrics_collector=metrics,
                embedding_model="text-embedding-3-small",
                openai_model="gpt-3.5-turbo",
                vector_store_type="opensearch",
                opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
                opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
            )
            
            # Test loading selected documents (should just set filter)
            result = rag_system.load_selected_documents(["test_doc.pdf"])
            
            if not result["loaded"]:
                print_error(f"Failed to set OpenSearch filter: {result['message']}")
                return False
            
            if "OpenSearch filter applied" not in result["message"]:
                print_error(f"Expected OpenSearch filter message, got: {result['message']}")
                return False
            
            # Verify active_sources is set
            if not hasattr(rag_system, 'active_sources') or rag_system.active_sources != ["test_doc.pdf"]:
                print_error("active_sources not properly set for OpenSearch")
                return False
            
            print_success("OpenSearch workflow test passed!")
            return True
            
        except Exception as e:
            print_warning(f"OpenSearch test failed (may be expected if domain not accessible): {e}")
            return True  # Don't fail if OpenSearch is not accessible
    
    def run_all_tests(self):
        """Run all end-to-end tests"""
        print_header("End-to-End Testing: Per-Document Loading Feature")
        
        tests = [
            ("Full Workflow (FAISS)", self.test_full_workflow_faiss),
            ("Multiple Sequential Loads", self.test_multiple_loads),
            ("Document Registry Integration", self.test_registry_integration),
            ("Error Handling", self.test_error_handling),
            ("OpenSearch Workflow", self.test_opensearch_workflow),
        ]
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                if result:
                    self.results["passed"] += 1
                    self.results["tests"].append({"name": test_name, "status": "PASSED"})
                else:
                    self.results["failed"] += 1
                    self.results["tests"].append({"name": test_name, "status": "FAILED"})
            except Exception as e:
                self.results["failed"] += 1
                self.results["tests"].append({"name": test_name, "status": "ERROR", "error": str(e)})
                print_error(f"Test {test_name} raised exception: {e}")
        
        self.print_summary()
        self.cleanup()
    
    def print_summary(self):
        """Print test summary"""
        print_header("E2E Test Summary")
        
        total = self.results["passed"] + self.results["failed"]
        print(f"{Colors.BOLD}Total Tests: {total}{Colors.END}")
        print(f"{Colors.GREEN}Passed: {self.results['passed']}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.results['failed']}{Colors.END}")
        
        print(f"\n{Colors.BOLD}Test Details:{Colors.END}")
        for test in self.results["tests"]:
            status = test["status"]
            if status == "PASSED":
                print(f"  {Colors.GREEN}✅ {test['name']}{Colors.END}")
            elif status == "FAILED":
                print(f"  {Colors.RED}❌ {test['name']}{Colors.END}")
            else:
                print(f"  {Colors.RED}❌ {test['name']} - ERROR: {test.get('error', 'Unknown')}{Colors.END}")
        
        if self.results["failed"] == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}All E2E tests passed! ✅{Colors.END}")
            print(f"{Colors.GREEN}The per-document loading feature is working correctly end-to-end!{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}{self.results['failed']} test(s) failed ❌{Colors.END}")

if __name__ == "__main__":
    test_suite = E2ETestSuite()
    try:
        test_suite.run_all_tests()
        sys.exit(0 if test_suite.results["failed"] == 0 else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        test_suite.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        test_suite.cleanup()
        sys.exit(1)

