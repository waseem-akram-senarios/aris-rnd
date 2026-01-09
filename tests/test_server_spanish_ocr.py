"""
Server-based OCR and Image Extraction Test for Spanish Client Documents.

Tests the deployed server at http://44.221.84.58:8500 for:
1. Document upload and processing with OCR
2. Image extraction accuracy
3. Spanish content handling
4. RAG query accuracy

Test Documents:
- EM10, degasing.pdf (2 pages)
- EM11, top seal.pdf (14 pages)  
- VUORMAR.pdf (10 pages)
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
SPANISH_DOCS_DIR = Path(__file__).parent.parent / "docs" / "testing" / "clientSpanishDocs"

TEST_DOCUMENTS = [
    "EM10, degasing.pdf",
    "EM11, top seal.pdf",
    "VUORMAR.pdf"
]

# Output directory
OUTPUT_DIR = Path(__file__).parent / "server_ocr_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class ServerOCRTest:
    """Test OCR and image extraction on the deployed server."""
    
    def __init__(self, server_url: str = SERVER_URL):
        self.server_url = server_url
        self.results = {
            "test_timestamp": datetime.now().isoformat(),
            "server_url": server_url,
            "documents": {},
            "summary": {}
        }
    
    def check_server_health(self) -> Dict[str, Any]:
        """Check if server is healthy."""
        print(f"\n🔍 Checking server health at {self.server_url}...")
        try:
            response = requests.get(f"{self.server_url}/health", timeout=10)
            health = response.json()
            print(f"   ✅ Server status: {health.get('status', 'unknown')}")
            print(f"   📊 Documents in registry: {health.get('registry_document_count', 0)}")
            return {"healthy": True, "data": health}
        except Exception as e:
            print(f"   ❌ Server health check failed: {e}")
            return {"healthy": False, "error": str(e)}
    
    def get_existing_documents(self) -> List[Dict]:
        """Get list of already processed documents."""
        try:
            response = requests.get(f"{self.server_url}/documents", timeout=30)
            data = response.json()
            return data.get("documents", [])
        except Exception as e:
            print(f"   ⚠️ Could not fetch documents: {e}")
            return []
    
    def upload_document(self, file_path: str, parser: str = "docling", language: str = "spa") -> Dict[str, Any]:
        """Upload a document to the server for processing."""
        file_name = os.path.basename(file_path)
        print(f"\n📤 Uploading {file_name} with parser={parser}, language={language}...")
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_name, f, 'application/pdf')}
                data = {
                    'parser_preference': parser,
                    'language': language
                }
                
                response = requests.post(
                    f"{self.server_url}/documents",
                    files=files,
                    data=data,
                    timeout=600  # 10 minutes for large docs
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    print(f"   ✅ Upload successful: {result.get('document_id', 'N/A')[:12]}...")
                    return {"success": True, "data": result}
                else:
                    print(f"   ❌ Upload failed: {response.status_code} - {response.text[:200]}")
                    return {"success": False, "error": response.text}
                    
        except requests.exceptions.Timeout:
            print(f"   ⏱️ Upload timed out - document may still be processing")
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            print(f"   ❌ Upload error: {e}")
            return {"success": False, "error": str(e)}
    
    def get_document_details(self, document_id: str) -> Dict[str, Any]:
        """Get detailed information about a document."""
        try:
            response = requests.get(f"{self.server_url}/documents/{document_id}", timeout=30)
            if response.status_code == 200:
                return response.json()
            return {}
        except Exception as e:
            print(f"   ⚠️ Could not get document details: {e}")
            return {}
    
    def get_document_images(self, document_id: str) -> List[Dict]:
        """Get images for a specific document."""
        try:
            response = requests.get(f"{self.server_url}/documents/{document_id}/images", timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("images", [])
            return []
        except Exception as e:
            print(f"   ⚠️ Could not get images: {e}")
            return []
    
    def query_document(self, question: str, document_id: str = None, k: int = 6) -> Dict[str, Any]:
        """Query the RAG system."""
        try:
            payload = {
                "question": question,
                "k": k,
                "use_mmr": True,
                "response_language": "Spanish",
                "auto_translate": True
            }
            if document_id:
                payload["document_id"] = document_id
            
            response = requests.post(
                f"{self.server_url}/query",
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()
            return {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def get_vector_indexes(self) -> List[Dict]:
        """Get all vector indexes from the server."""
        try:
            response = requests.get(f"{self.server_url}/admin/vectors/indexes", timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get("indexes", [])
            return []
        except Exception as e:
            print(f"   ⚠️ Could not get vector indexes: {e}")
            return []
    
    def search_vectors_directly(self, query: str, k: int = 10) -> Dict[str, Any]:
        """Perform direct vector search."""
        try:
            response = requests.post(
                f"{self.server_url}/admin/vectors/search",
                json={
                    "query": query,
                    "k": k,
                    "use_hybrid": True,
                    "semantic_weight": 0.7
                },
                timeout=60
            )
            if response.status_code == 200:
                return response.json()
            return {"error": response.text}
        except Exception as e:
            return {"error": str(e)}
    
    def test_document(self, doc_name: str, upload_new: bool = False) -> Dict[str, Any]:
        """Test a single document's OCR and image extraction."""
        file_path = str(SPANISH_DOCS_DIR / doc_name)
        
        print(f"\n{'='*60}")
        print(f"📚 Testing: {doc_name}")
        print(f"{'='*60}")
        
        result = {
            "document_name": doc_name,
            "file_exists": os.path.exists(file_path),
            "upload_result": None,
            "document_details": None,
            "images": [],
            "image_analysis": {},
            "query_tests": [],
            "issues": []
        }
        
        if not result["file_exists"]:
            result["issues"].append(f"File not found: {file_path}")
            return result
        
        # Check if document already exists on server
        existing_docs = self.get_existing_documents()
        existing_doc = next((d for d in existing_docs if d.get("document_name") == doc_name), None)
        
        if existing_doc and not upload_new:
            print(f"   📄 Document already exists: {existing_doc.get('document_id', 'N/A')[:12]}...")
            result["document_details"] = existing_doc
            doc_id = existing_doc.get("document_id")
        elif upload_new or not existing_doc:
            # Upload document
            upload_result = self.upload_document(file_path, parser="docling", language="spa")
            result["upload_result"] = upload_result
            
            if upload_result.get("success"):
                doc_id = upload_result["data"].get("document_id")
                # Wait a bit for processing
                print(f"   ⏳ Waiting for processing to complete...")
                time.sleep(5)
                result["document_details"] = self.get_document_details(doc_id)
            else:
                result["issues"].append(f"Upload failed: {upload_result.get('error')}")
                return result
        else:
            doc_id = existing_doc.get("document_id")
        
        # Get document details
        if not result["document_details"]:
            result["document_details"] = self.get_document_details(doc_id)
        
        doc_details = result["document_details"]
        print(f"\n   📊 Document Details:")
        print(f"      Status: {doc_details.get('status', 'N/A')}")
        print(f"      Chunks: {doc_details.get('chunks_created', 0)}")
        print(f"      Images stored: {doc_details.get('images_stored', 0) or doc_details.get('image_count', 0)}")
        print(f"      Parser: {doc_details.get('parser_used', 'N/A')}")
        print(f"      Language: {doc_details.get('language', 'N/A')}")
        
        # Check for issues
        if doc_details.get('status') != 'success':
            result["issues"].append(f"Document status is not 'success': {doc_details.get('status')}")
        
        if doc_details.get('chunks_created', 0) == 0:
            result["issues"].append("No chunks created - OCR may have failed")
        
        # Get images
        images = self.get_document_images(doc_id)
        result["images"] = images
        
        print(f"\n   🖼️ Images Analysis:")
        print(f"      Total images retrieved: {len(images)}")
        
        # Analyze images
        images_with_ocr = 0
        total_ocr_length = 0
        for img in images:
            ocr_text = img.get("ocr_text", "")
            if ocr_text and len(ocr_text) > 10:
                images_with_ocr += 1
                total_ocr_length += len(ocr_text)
        
        result["image_analysis"] = {
            "total_images": len(images),
            "images_with_ocr": images_with_ocr,
            "total_ocr_length": total_ocr_length,
            "avg_ocr_length": total_ocr_length / images_with_ocr if images_with_ocr > 0 else 0,
            "ocr_coverage": (images_with_ocr / len(images) * 100) if images else 0
        }
        
        print(f"      Images with OCR text: {images_with_ocr}")
        print(f"      OCR coverage: {result['image_analysis']['ocr_coverage']:.1f}%")
        print(f"      Total OCR text length: {total_ocr_length:,} chars")
        
        if len(images) > 0 and images_with_ocr == 0:
            result["issues"].append("Images detected but no OCR text extracted")
        
        # Test queries
        print(f"\n   🔍 Query Tests:")
        test_queries = [
            "¿Cuáles son los pasos del proceso?",  # Spanish: What are the process steps?
            "What are the main specifications?",
            "Describe the equipment shown in the images"
        ]
        
        for query in test_queries:
            query_result = self.query_document(query, document_id=doc_id)
            
            test_result = {
                "query": query,
                "success": "error" not in query_result,
                "answer_length": len(query_result.get("answer", "")),
                "num_citations": len(query_result.get("citations", [])),
                "sources": query_result.get("sources", [])
            }
            result["query_tests"].append(test_result)
            
            status = "✅" if test_result["success"] and test_result["answer_length"] > 50 else "⚠️"
            print(f"      {status} '{query[:40]}...' -> {test_result['answer_length']} chars, {test_result['num_citations']} citations")
        
        return result
    
    def run_all_tests(self, upload_new: bool = False) -> Dict[str, Any]:
        """Run tests on all Spanish documents."""
        print("\n" + "="*70)
        print("🇪🇸 SERVER-BASED SPANISH DOCUMENT OCR TEST")
        print("="*70)
        print(f"📡 Server: {self.server_url}")
        print(f"📁 Documents: {len(TEST_DOCUMENTS)}")
        
        # Check server health
        health = self.check_server_health()
        if not health.get("healthy"):
            print("❌ Server is not healthy. Aborting tests.")
            return {"error": "Server not healthy"}
        
        self.results["server_health"] = health
        
        # Test each document
        for doc_name in TEST_DOCUMENTS:
            doc_result = self.test_document(doc_name, upload_new=upload_new)
            self.results["documents"][doc_name] = doc_result
        
        # Generate summary
        self.generate_summary()
        
        # Save results
        self.save_results()
        
        # Print final report
        self.print_report()
        
        return self.results
    
    def generate_summary(self):
        """Generate test summary."""
        total_docs = len(self.results["documents"])
        docs_with_issues = 0
        total_chunks = 0
        total_images = 0
        total_images_with_ocr = 0
        
        for doc_name, doc_data in self.results["documents"].items():
            if doc_data.get("issues"):
                docs_with_issues += 1
            
            details = doc_data.get("document_details", {})
            total_chunks += details.get("chunks_created", 0)
            
            img_analysis = doc_data.get("image_analysis", {})
            total_images += img_analysis.get("total_images", 0)
            total_images_with_ocr += img_analysis.get("images_with_ocr", 0)
        
        self.results["summary"] = {
            "total_documents": total_docs,
            "documents_with_issues": docs_with_issues,
            "total_chunks": total_chunks,
            "total_images": total_images,
            "images_with_ocr": total_images_with_ocr,
            "overall_ocr_coverage": (total_images_with_ocr / total_images * 100) if total_images > 0 else 0,
            "all_issues": []
        }
        
        # Collect all issues
        for doc_name, doc_data in self.results["documents"].items():
            for issue in doc_data.get("issues", []):
                self.results["summary"]["all_issues"].append(f"{doc_name}: {issue}")
    
    def save_results(self):
        """Save results to file."""
        output_file = OUTPUT_DIR / f"server_ocr_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n💾 Results saved to: {output_file}")
    
    def print_report(self):
        """Print final test report."""
        print("\n" + "="*70)
        print("📊 FINAL SERVER TEST REPORT")
        print("="*70)
        
        summary = self.results.get("summary", {})
        
        print(f"\n📈 Summary:")
        print(f"   Documents tested: {summary.get('total_documents', 0)}")
        print(f"   Documents with issues: {summary.get('documents_with_issues', 0)}")
        print(f"   Total chunks created: {summary.get('total_chunks', 0)}")
        print(f"   Total images: {summary.get('total_images', 0)}")
        print(f"   Images with OCR: {summary.get('images_with_ocr', 0)}")
        print(f"   Overall OCR coverage: {summary.get('overall_ocr_coverage', 0):.1f}%")
        
        if summary.get("all_issues"):
            print(f"\n⚠️ Issues Found:")
            for issue in summary["all_issues"]:
                print(f"   • {issue}")
        else:
            print(f"\n✅ No issues found!")
        
        print("\n" + "="*70)


def main():
    """Run server OCR tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test OCR on deployed server")
    parser.add_argument("--upload", action="store_true", help="Upload new documents (re-process)")
    parser.add_argument("--server", default=SERVER_URL, help="Server URL")
    args = parser.parse_args()
    
    tester = ServerOCRTest(server_url=args.server)
    tester.run_all_tests(upload_new=args.upload)


if __name__ == "__main__":
    main()

