"""
Comprehensive Server Parser Test for ARIS RAG System.

Tests ALL parsers on ALL documents in clientSpanishDocs directory via the server API.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configuration
INGESTION_SERVER_URL = "http://44.221.84.58:8501"  # Ingestion service
GATEWAY_SERVER_URL = "http://44.221.84.58:8500"   # Gateway service
TEST_FILES_DIR = Path(__file__).parent.parent / "docs" / "testing" / "clientSpanishDocs"

# All available parsers to test
PARSERS = [
    "pymupdf",      # Fast PDF parser (default)
    "docling",      # Advanced document parser with OCR
    "ocrmypdf",     # OCR with PDF handling
    "textract",     # AWS Textract (if configured)
    "llama-scan"    # Llama-Scan vision model (if configured)
]

OUTPUT_DIR = Path(__file__).parent / "parser_test_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ComprehensiveParserTester:
    """Test all parsers on all documents via server API."""
    
    def __init__(self, ingestion_url: str = INGESTION_SERVER_URL, gateway_url: str = GATEWAY_SERVER_URL):
        self.ingestion_url = ingestion_url
        self.gateway_url = gateway_url
        self.results = {
            "test_timestamp": datetime.now().isoformat(),
            "ingestion_server": ingestion_url,
            "gateway_server": gateway_url,
            "documents": {},
            "parsers": {},
            "summary": {}
        }
    
    def check_server_health(self) -> bool:
        """Check if ingestion server is healthy."""
        print(f"\n🔍 Checking ingestion server health at {self.ingestion_url}...")
        try:
            response = requests.get(f"{self.ingestion_url}/health", timeout=10)
            health = response.json()
            status = health.get('status', 'unknown')
            print(f"   ✅ Ingestion server status: {status}")
            
            # Also check gateway
            print(f"\n🔍 Checking gateway server health at {self.gateway_url}...")
            response = requests.get(f"{self.gateway_url}/health", timeout=10)
            gateway_health = response.json()
            print(f"   ✅ Gateway server status: {gateway_health.get('status', 'unknown')}")
            
            return True
        except Exception as e:
            print(f"   ❌ Server health check failed: {e}")
            return False
    
    def get_test_documents(self) -> List[Path]:
        """Get all PDF documents from test directory."""
        if not TEST_FILES_DIR.exists():
            print(f"❌ Test directory not found: {TEST_FILES_DIR}")
            return []
        
        pdf_files = list(TEST_FILES_DIR.glob("*.pdf"))
        print(f"\n📁 Found {len(pdf_files)} PDF documents:")
        for pdf in pdf_files:
            print(f"   - {pdf.name}")
        
        return pdf_files
    
    def upload_and_process_document(
        self, 
        file_path: Path, 
        parser: str, 
        language: str = "spa"
    ) -> Dict[str, Any]:
        """Upload and process a document with specific parser via ingestion API."""
        original_file_name = file_path.name
        # Use unique filename per parser to avoid duplicate detection
        file_name = f"{parser}_{original_file_name}"
        print(f"\n   📤 Uploading {original_file_name} with parser={parser} (as {file_name})...")
        
        result = {
            "parser": parser,
            "file": original_file_name,
            "upload_time": None,
            "processing_time": None,
            "success": False,
            "error": None,
            "document_id": None,
            "metadata": {}
        }
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f, 'application/pdf')}
                data = {
                    'parser_preference': parser,
                    'language': language
                }
                
                # Upload to ingestion service (use sync endpoint for immediate results)
                start_time = time.time()
                response = requests.post(
                    f"{self.ingestion_url}/process",  # Use sync endpoint
                    files=files,
                    data=data,
                    timeout=600  # 10 minutes timeout
                )
                upload_time = time.time() - start_time
                result["upload_time"] = upload_time
                
                if response.status_code in [200, 201]:
                    response_data = response.json()
                    status = response_data.get("status", "unknown")
                    
                    # Sync endpoint processes immediately, so we should have full results
                    
                    result["success"] = True
                    result["document_id"] = response_data.get("document_id")
                    result["metadata"] = {
                        "parser_used": response_data.get("parser_used"),
                        "pages": response_data.get("pages"),
                        "chunks_created": response_data.get("chunks_created", 0),
                        "tokens_extracted": response_data.get("tokens_extracted", 0),
                        "extraction_percentage": response_data.get("extraction_percentage", 0),
                        "images_detected": response_data.get("images_detected", False),
                        "image_count": response_data.get("image_count", 0),
                        "images_stored": response_data.get("images_stored", 0),
                        "processing_time": response_data.get("processing_time", 0),
                        "text_length": response_data.get("text_length", 0),
                        "confidence": response_data.get("confidence", 0),
                        "status": response_data.get("status", "unknown")
                    }
                    result["processing_time"] = response_data.get("processing_time", 0)
                    
                    print(f"   ✅ Upload successful (ID: {result['document_id'][:12]}...)")
                    print(f"      Upload time: {upload_time:.2f}s")
                    print(f"      Processing time: {result['processing_time']:.2f}s")
                    print(f"      Parser used: {result['metadata']['parser_used']}")
                    print(f"      Pages: {result['metadata']['pages']}")
                    print(f"      Chunks: {result['metadata']['chunks_created']}")
                    print(f"      Tokens: {result['metadata']['tokens_extracted']:,}")
                    print(f"      Extraction: {result['metadata']['extraction_percentage']*100:.1f}%")
                    print(f"      Images: {result['metadata']['image_count']} detected, {result['metadata']['images_stored']} stored")
                    
                else:
                    error_text = response.text[:500] if hasattr(response, 'text') else str(response)
                    result["error"] = f"HTTP {response.status_code}: {error_text}"
                    print(f"   ❌ Upload failed: {result['error']}")
                    
        except requests.exceptions.Timeout:
            result["error"] = "Timeout (exceeded 600s)"
            print(f"   ❌ Upload timeout")
        except Exception as e:
            result["error"] = str(e)
            print(f"   ❌ Upload error: {e}")
        
        return result
    
    def test_query_retrieval(self, document_id: str, question: str = "¿Cuáles son los pasos principales?") -> Dict[str, Any]:
        """Test query retrieval for a processed document."""
        try:
            response = requests.post(
                f"{self.gateway_url}/query",
                json={
                    "question": question,
                    "document_id": document_id,
                    "k": 5,
                    "response_language": "Spanish"
                },
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "answer_length": len(result.get("answer", "")),
                    "citations_count": len(result.get("citations", [])),
                    "num_chunks_used": result.get("num_chunks_used", 0)
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def test_parser_on_document(self, parser: str, document_path: Path) -> Dict[str, Any]:
        """Test a single parser on a single document."""
        print(f"\n{'='*70}")
        print(f"🔧 Testing: {parser.upper()} on {document_path.name}")
        print(f"{'='*70}")
        
        result = {
            "parser": parser,
            "document": document_path.name,
            "upload_result": None,
            "query_test": None,
            "overall_status": "failed"
        }
        
        # Upload and process
        upload_result = self.upload_and_process_document(document_path, parser)
        result["upload_result"] = upload_result
        
        if not upload_result.get("success"):
            print(f"   ❌ Test FAILED: {upload_result.get('error', 'Unknown error')}")
            return result
        
        # Test query if document was processed successfully
        document_id = upload_result.get("document_id")
        if document_id:
            print(f"\n   🔍 Testing query retrieval...")
            query_result = self.test_query_retrieval(document_id)
            result["query_test"] = query_result
            
            if query_result.get("success"):
                print(f"   ✅ Query test passed:")
                print(f"      Answer length: {query_result['answer_length']} chars")
                print(f"      Citations: {query_result['citations_count']}")
                print(f"      Chunks used: {query_result['num_chunks_used']}")
            else:
                print(f"   ⚠️ Query test failed: {query_result.get('error', 'Unknown')}")
        
        # Determine overall status
        metadata = upload_result.get("metadata", {})
        if (upload_result.get("success") and 
            metadata.get("chunks_created", 0) > 0 and
            metadata.get("extraction_percentage", 0) > 0):
            result["overall_status"] = "success"
            print(f"\n   ✅ {parser.upper()} WORKING CORRECTLY on {document_path.name}")
        else:
            print(f"\n   ⚠️ {parser.upper()} has issues with {document_path.name}")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run comprehensive tests for all parsers on all documents."""
        print("\n" + "="*70)
        print("🔬 COMPREHENSIVE SERVER PARSER TESTS")
        print("="*70)
        print(f"📡 Ingestion Server: {self.ingestion_url}")
        print(f"📡 Gateway Server: {self.gateway_url}")
        print(f"🔧 Parsers to test: {', '.join(PARSERS)}")
        
        # Check server health
        if not self.check_server_health():
            return {"error": "Server not healthy"}
        
        # Get test documents
        test_documents = self.get_test_documents()
        if not test_documents:
            return {"error": "No test documents found"}
        
        # Test each parser on each document
        for parser in PARSERS:
            parser_results = {}
            for doc_path in test_documents:
                doc_name = doc_path.name
                print(f"\n{'#'*70}")
                print(f"# Testing {parser.upper()} on {doc_name}")
                print(f"{'#'*70}")
                
                result = self.test_parser_on_document(parser, doc_path)
                parser_results[doc_name] = result
                
                # Small delay between tests
                time.sleep(2)
            
            self.results["parsers"][parser] = parser_results
        
        # Generate summary
        self.generate_summary()
        
        # Save results
        self.save_results()
        
        # Print final report
        self.print_report()
        
        return self.results
    
    def generate_summary(self):
        """Generate comprehensive test summary."""
        working_combinations = []
        failed_combinations = []
        
        for parser, doc_results in self.results["parsers"].items():
            for doc_name, result in doc_results.items():
                if result.get("overall_status") == "success":
                    working_combinations.append(f"{parser} on {doc_name}")
                else:
                    failed_combinations.append(f"{parser} on {doc_name}")
        
        total_tests = len(working_combinations) + len(failed_combinations)
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "successful_tests": len(working_combinations),
            "failed_tests": len(failed_combinations),
            "success_rate": (len(working_combinations) / total_tests * 100) if total_tests > 0 else 0,
            "working_combinations": working_combinations,
            "failed_combinations": failed_combinations,
            "parsers_tested": list(self.results["parsers"].keys())
        }
    
    def save_results(self):
        """Save results to JSON file."""
        output_file = OUTPUT_DIR / f"comprehensive_parser_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Results saved to: {output_file}")
    
    def print_report(self):
        """Print comprehensive test report."""
        print("\n" + "="*70)
        print("📊 COMPREHENSIVE PARSER TEST REPORT")
        print("="*70)
        
        summary = self.results.get("summary", {})
        
        print(f"\n📈 Overall Summary:")
        print(f"   Total tests: {summary.get('total_tests', 0)}")
        print(f"   Successful: {summary.get('successful_tests', 0)}")
        print(f"   Failed: {summary.get('failed_tests', 0)}")
        print(f"   Success rate: {summary.get('success_rate', 0):.1f}%")
        
        print(f"\n✅ Working Combinations:")
        for combo in summary.get('working_combinations', []):
            print(f"   ✓ {combo}")
        
        if summary.get('failed_combinations'):
            print(f"\n❌ Failed Combinations:")
            for combo in summary.get('failed_combinations', []):
                print(f"   ✗ {combo}")
        
        print(f"\n📋 Detailed Results by Parser:")
        for parser, doc_results in self.results["parsers"].items():
            print(f"\n   🔧 {parser.upper()}:")
            for doc_name, result in doc_results.items():
                status = "✅" if result.get("overall_status") == "success" else "❌"
                upload = result.get("upload_result", {})
                metadata = upload.get("metadata", {})
                
                print(f"      {status} {doc_name}:")
                if upload.get("success"):
                    print(f"         Pages: {metadata.get('pages', 'N/A')}")
                    print(f"         Chunks: {metadata.get('chunks_created', 0)}")
                    print(f"         Extraction: {metadata.get('extraction_percentage', 0)*100:.1f}%")
                    print(f"         Images: {metadata.get('image_count', 0)} detected")
                    print(f"         Processing time: {metadata.get('processing_time', 0):.2f}s")
                else:
                    print(f"         Error: {upload.get('error', 'Unknown')[:100]}")
        
        print("\n" + "="*70)


def main():
    """Run comprehensive parser tests."""
    tester = ComprehensiveParserTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()

