"""
Server-based Parser Test for ARIS RAG System.

Tests all parsers on the deployed server:
1. docling - Advanced document parser
2. ocrmypdf - OCR with PDF handling
3. pymupdf - Fast PDF parser
4. textract - AWS Textract (if configured)
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
SERVER_URL = "http://44.221.84.58:8500"
TEST_FILES_DIR = Path(__file__).parent.parent / "docs" / "testing"

# Parsers to test
PARSERS = ["docling", "ocrmypdf", "pymupdf"]  # textract requires AWS setup

# Test document - use a single Spanish document
TEST_DOC = Path(__file__).parent.parent / "docs" / "testing" / "clientSpanishDocs" / "EM10, degasing.pdf"

OUTPUT_DIR = Path(__file__).parent / "parser_test_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ParserTester:
    """Test all parsers on the deployed server."""
    
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.results = {
            "test_timestamp": datetime.now().isoformat(),
            "server_url": server_url,
            "parsers": {},
            "summary": {}
        }
    
    def check_server_health(self) -> bool:
        """Check if server is healthy."""
        print(f"\n🔍 Checking server health at {self.server_url}...")
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            health = response.json()
            print(f"   ✅ Server status: {health.get('status', 'unknown')}")
            return True
        except Exception as e:
            print(f"   ❌ Server health check failed: {e}")
            return False
    
    def upload_document(self, file_path: str, parser: str, language: str = "spa") -> Dict[str, Any]:
        """Upload a document with specific parser."""
        file_name = os.path.basename(file_path)
        print(f"\n   📤 Uploading with parser={parser}...")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f, 'application/pdf')}
                data = {
                    'parser_preference': parser,
                    'language': language
                }
                
                start_time = time.time()
                response = requests.post(
                    f"{self.server_url}/documents",
                    files=files,
                    data=data,
                    timeout=600
                )
                upload_time = time.time() - start_time
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    return {
                        "success": True, 
                        "data": result, 
                        "upload_time": upload_time
                    }
                else:
                    return {
                        "success": False, 
                        "error": response.text[:500],
                        "status_code": response.status_code
                    }
                    
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def wait_for_processing(self, document_id: str, max_wait: int = 120) -> Dict[str, Any]:
        """Wait for document to finish processing."""
        print(f"      ⏳ Waiting for processing (max {max_wait}s)...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(
                    f"{self.server_url}/documents/{document_id}",
                    timeout=30
                )
                if response.status_code == 200:
                    doc = response.json()
                    status = doc.get("status", "unknown")
                    
                    if status == "success":
                        return {"success": True, "data": doc}
                    elif status == "failed":
                        return {"success": False, "error": doc.get("error", "Processing failed")}
                    
                time.sleep(5)
            except Exception as e:
                time.sleep(5)
        
        return {"success": False, "error": "Timeout waiting for processing"}
    
    def get_document_images(self, document_id: str) -> List[Dict]:
        """Get images for a document."""
        try:
            response = requests.get(
                f"{self.server_url}/documents/{document_id}/images",
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("images", [])
            return []
        except:
            return []
    
    def query_document(self, question: str, document_id: str) -> Dict[str, Any]:
        """Query a specific document."""
        try:
            response = requests.post(
                f"{self.server_url}/query",
                json={
                    "question": question,
                    "document_id": document_id,
                    "k": 5,
                    "response_language": "Spanish"
                },
                timeout=120
            )
            if response.status_code == 200:
                return response.json()
            return {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def test_parser(self, parser_name: str, test_file: str) -> Dict[str, Any]:
        """Test a single parser."""
        print(f"\n{'='*60}")
        print(f"🔧 Testing Parser: {parser_name.upper()}")
        print(f"{'='*60}")
        print(f"   File: {os.path.basename(test_file)}")
        
        result = {
            "parser": parser_name,
            "test_file": os.path.basename(test_file),
            "upload": None,
            "processing": None,
            "document_details": None,
            "images": None,
            "query_test": None,
            "overall_status": "failed"
        }
        
        # Upload document
        upload_result = self.upload_document(test_file, parser_name)
        result["upload"] = upload_result
        
        if not upload_result.get("success"):
            print(f"   ❌ Upload failed: {upload_result.get('error', 'Unknown error')[:100]}")
            return result
        
        document_id = upload_result["data"].get("document_id")
        print(f"   ✅ Upload successful: {document_id[:12]}...")
        print(f"      Upload time: {upload_result.get('upload_time', 0):.2f}s")
        
        # Wait for processing
        processing_result = self.wait_for_processing(document_id)
        result["processing"] = processing_result
        
        if not processing_result.get("success"):
            print(f"   ❌ Processing failed: {processing_result.get('error', 'Unknown error')[:100]}")
            return result
        
        doc_details = processing_result.get("data", {})
        result["document_details"] = doc_details
        
        print(f"   ✅ Processing complete:")
        print(f"      Parser used: {doc_details.get('parser_used', 'N/A')}")
        print(f"      Status: {doc_details.get('status', 'N/A')}")
        print(f"      Chunks: {doc_details.get('chunks_created', 0)}")
        print(f"      Tokens: {doc_details.get('tokens_extracted', 0):,}")
        print(f"      Pages: {doc_details.get('pages', 'N/A')}")
        print(f"      Extraction: {doc_details.get('extraction_percentage', 0)*100:.1f}%")
        print(f"      Images detected: {doc_details.get('images_detected', False)}")
        print(f"      Image count: {doc_details.get('image_count', 0)}")
        print(f"      Images stored: {doc_details.get('images_stored', 0)}")
        print(f"      Processing time: {doc_details.get('processing_time', 0):.2f}s")
        
        # Get images
        images = self.get_document_images(document_id)
        result["images"] = {
            "count": len(images),
            "with_ocr": sum(1 for img in images if img.get("ocr_text", ""))
        }
        print(f"      Images retrieved: {len(images)}")
        
        # Query test
        query_result = self.query_document(
            "¿Cuáles son los pasos principales del proceso?",
            document_id
        )
        result["query_test"] = {
            "success": "error" not in query_result,
            "answer_length": len(query_result.get("answer", "")),
            "citations": len(query_result.get("citations", []))
        }
        
        if result["query_test"]["success"]:
            print(f"   ✅ Query test passed:")
            print(f"      Answer length: {result['query_test']['answer_length']} chars")
            print(f"      Citations: {result['query_test']['citations']}")
        else:
            print(f"   ⚠️ Query test issues: {query_result.get('error', 'Unknown')[:100]}")
        
        # Overall status
        if (doc_details.get("status") == "success" and 
            doc_details.get("chunks_created", 0) > 0):
            result["overall_status"] = "success"
            print(f"\n   ✅ Parser {parser_name} WORKING CORRECTLY")
        else:
            print(f"\n   ⚠️ Parser {parser_name} has issues")
        
        return result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run tests for all parsers."""
        print("\n" + "="*70)
        print("🔬 SERVER PARSER TESTS")
        print("="*70)
        print(f"📡 Server: {self.server_url}")
        print(f"📁 Test file: {TEST_DOC.name}")
        print(f"🔧 Parsers to test: {', '.join(PARSERS)}")
        
        if not self.check_server_health():
            return {"error": "Server not healthy"}
        
        if not TEST_DOC.exists():
            print(f"❌ Test file not found: {TEST_DOC}")
            return {"error": "Test file not found"}
        
        # Test each parser
        for parser in PARSERS:
            parser_result = self.test_parser(parser, str(TEST_DOC))
            self.results["parsers"][parser] = parser_result
        
        # Generate summary
        self.generate_summary()
        
        # Save results
        self.save_results()
        
        # Print final report
        self.print_report()
        
        return self.results
    
    def generate_summary(self):
        """Generate test summary."""
        working = []
        failed = []
        
        for parser, result in self.results["parsers"].items():
            if result.get("overall_status") == "success":
                working.append(parser)
            else:
                failed.append(parser)
        
        self.results["summary"] = {
            "total_parsers": len(PARSERS),
            "working_parsers": working,
            "failed_parsers": failed,
            "success_rate": len(working) / len(PARSERS) * 100 if PARSERS else 0
        }
    
    def save_results(self):
        """Save results to file."""
        output_file = OUTPUT_DIR / f"parser_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Results saved to: {output_file}")
    
    def print_report(self):
        """Print final test report."""
        print("\n" + "="*70)
        print("📊 PARSER TEST REPORT")
        print("="*70)
        
        summary = self.results.get("summary", {})
        
        print(f"\n📈 Summary:")
        print(f"   Parsers tested: {summary.get('total_parsers', 0)}")
        print(f"   Working: {', '.join(summary.get('working_parsers', [])) or 'None'}")
        print(f"   Failed: {', '.join(summary.get('failed_parsers', [])) or 'None'}")
        print(f"   Success rate: {summary.get('success_rate', 0):.1f}%")
        
        print("\n📋 Detailed Results:")
        for parser, result in self.results["parsers"].items():
            status_emoji = "✅" if result.get("overall_status") == "success" else "❌"
            doc = result.get("document_details", {})
            print(f"\n   {status_emoji} {parser.upper()}:")
            print(f"      Chunks: {doc.get('chunks_created', 0)}")
            print(f"      Tokens: {doc.get('tokens_extracted', 0):,}")
            print(f"      Extraction: {doc.get('extraction_percentage', 0)*100:.1f}%")
            print(f"      Images: {doc.get('image_count', 0)} detected, {doc.get('images_stored', 0)} stored")
            print(f"      Time: {doc.get('processing_time', 0):.2f}s")
        
        print("\n" + "="*70)


def main():
    """Run parser tests."""
    tester = ParserTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()

