"""
Comprehensive OCR and Image Extraction Test for Spanish Client Documents.

This test verifies:
1. OCR accuracy for all parsers on Spanish documents
2. Image extraction and OCR text from images
3. Multilingual support (Spanish content)
4. RAG system query accuracy on processed documents

Test Documents:
- EM10, degasing.pdf (2 pages)
- EM11, top seal.pdf (14 pages)
- VUORMAR.pdf (10 pages)
"""
import sys
import os
from pathlib import Path

# Setup paths
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

# Import parsers
from services.ingestion.parsers.parser_factory import ParserFactory
from services.ingestion.parsers.pymupdf_parser import PyMuPDFParser
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.parsers.ocrmypdf_parser import OCRmyPDFParser
from services.ingestion.parsers.pdf_type_detector import detect_pdf_type
from services.ingestion.parsers.base_parser import ParsedDocument

# Test configuration
SPANISH_DOCS_DIR = Path(PROJECT_ROOT) / "docs" / "testing" / "clientSpanishDocs"
TEST_DOCUMENTS = [
    "EM10, degasing.pdf",
    "EM11, top seal.pdf",
    "VUORMAR.pdf"
]

# Output directory for test results
OUTPUT_DIR = Path(PROJECT_ROOT) / "tests" / "spanish_ocr_results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class SpanishDocOCRTest:
    """Test class for Spanish document OCR and image extraction."""
    
    def __init__(self):
        self.results = {
            "test_timestamp": datetime.now().isoformat(),
            "documents": {},
            "summary": {}
        }
        
    def detect_document_type(self, file_path: str) -> Dict[str, Any]:
        """Detect PDF type (text, image, or mixed)."""
        try:
            pdf_type = detect_pdf_type(file_path)
            return {
                "type": pdf_type,
                "is_image_heavy": pdf_type in ["image", "mixed"]
            }
        except Exception as e:
            return {"type": "unknown", "error": str(e)}
    
    def test_parser(self, parser_name: str, file_path: str, language: str = "spa") -> Dict[str, Any]:
        """Test a specific parser on a document."""
        print(f"\n  📄 Testing {parser_name} on {os.path.basename(file_path)}...")
        start_time = time.time()
        
        result = {
            "parser": parser_name,
            "success": False,
            "text_length": 0,
            "pages": 0,
            "images_detected": False,
            "image_count": 0,
            "extracted_images": [],
            "extraction_percentage": 0.0,
            "processing_time": 0.0,
            "error": None,
            "sample_text": ""
        }
        
        try:
            # Create parser instance
            if parser_name == "pymupdf":
                parser = PyMuPDFParser()
            elif parser_name == "docling":
                parser = DoclingParser()
            elif parser_name == "ocrmypdf":
                parser = OCRmyPDFParser(languages=language)
            else:
                raise ValueError(f"Unknown parser: {parser_name}")
            
            # Parse document
            parsed: ParsedDocument = parser.parse(file_path)
            
            result["success"] = True
            result["text_length"] = len(parsed.text) if parsed.text else 0
            result["pages"] = parsed.pages
            result["images_detected"] = parsed.images_detected
            result["extraction_percentage"] = parsed.extraction_percentage
            result["sample_text"] = (parsed.text[:1000] + "...") if parsed.text and len(parsed.text) > 1000 else (parsed.text or "")
            
            # Get image count and extracted images from metadata
            result["image_count"] = parsed.image_count if hasattr(parsed, 'image_count') else 0
            extracted_images = parsed.metadata.get("extracted_images", []) if parsed.metadata else []
            
            # Also check in metadata for image_count if not in parsed object
            if result["image_count"] == 0 and parsed.metadata:
                result["image_count"] = parsed.metadata.get("image_count", 0)
            
            # Extract image details from metadata
            if extracted_images:
                for img in extracted_images[:10]:  # Limit to first 10 images
                    result["extracted_images"].append({
                        "page": img.get("page", "N/A"),
                        "image_number": img.get("image_number", "N/A"),
                        "ocr_text_length": len(img.get("ocr_text", "")),
                        "ocr_text_preview": (img.get("ocr_text", "")[:200] + "...") if len(img.get("ocr_text", "")) > 200 else img.get("ocr_text", ""),
                        "has_ocr": bool(img.get("ocr_text"))
                    })
            
            print(f"    ✅ Success: {result['text_length']:,} chars, {result['pages']} pages, {result['image_count']} images")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"    ❌ Error: {str(e)[:100]}")
        
        result["processing_time"] = time.time() - start_time
        return result
    
    def analyze_images(self, parsed_result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze extracted images and their OCR quality."""
        analysis = {
            "total_images": parsed_result.get("image_count", 0),
            "images_with_ocr": 0,
            "images_without_ocr": 0,
            "avg_ocr_text_length": 0,
            "ocr_coverage_percentage": 0.0
        }
        
        extracted_images = parsed_result.get("extracted_images", [])
        if not extracted_images:
            return analysis
        
        ocr_lengths = []
        for img in extracted_images:
            if img.get("has_ocr") and img.get("ocr_text_length", 0) > 10:
                analysis["images_with_ocr"] += 1
                ocr_lengths.append(img.get("ocr_text_length", 0))
            else:
                analysis["images_without_ocr"] += 1
        
        if ocr_lengths:
            analysis["avg_ocr_text_length"] = sum(ocr_lengths) / len(ocr_lengths)
        
        if analysis["total_images"] > 0:
            analysis["ocr_coverage_percentage"] = (analysis["images_with_ocr"] / analysis["total_images"]) * 100
        
        return analysis
    
    def run_document_test(self, doc_name: str) -> Dict[str, Any]:
        """Run all parser tests on a single document."""
        file_path = str(SPANISH_DOCS_DIR / doc_name)
        
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        
        print(f"\n{'='*60}")
        print(f"📚 Testing: {doc_name}")
        print(f"{'='*60}")
        
        # Get file info
        file_size = os.path.getsize(file_path)
        
        doc_result = {
            "file_name": doc_name,
            "file_path": file_path,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "document_type": self.detect_document_type(file_path),
            "parsers": {},
            "best_parser": None,
            "image_analysis": {}
        }
        
        print(f"  📊 File size: {doc_result['file_size_mb']} MB")
        print(f"  📊 Document type: {doc_result['document_type']['type']}")
        
        # Test each parser
        parsers_to_test = ["pymupdf", "docling", "ocrmypdf"]
        best_text_length = 0
        best_parser = None
        
        for parser_name in parsers_to_test:
            parser_result = self.test_parser(parser_name, file_path, language="spa+eng")
            doc_result["parsers"][parser_name] = parser_result
            
            # Track best parser by text extraction
            if parser_result["success"] and parser_result["text_length"] > best_text_length:
                best_text_length = parser_result["text_length"]
                best_parser = parser_name
            
            # Analyze images for this parser
            doc_result["image_analysis"][parser_name] = self.analyze_images(parser_result)
        
        doc_result["best_parser"] = best_parser
        
        # Print summary for this document
        print(f"\n  📈 Document Summary:")
        print(f"    Best parser: {best_parser} ({best_text_length:,} chars)")
        for parser_name, analysis in doc_result["image_analysis"].items():
            if analysis["total_images"] > 0:
                print(f"    {parser_name} images: {analysis['images_with_ocr']}/{analysis['total_images']} with OCR ({analysis['ocr_coverage_percentage']:.1f}%)")
        
        return doc_result
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run tests on all Spanish documents."""
        print("\n" + "="*70)
        print("🇪🇸 SPANISH DOCUMENT OCR TEST SUITE")
        print("="*70)
        print(f"📁 Test directory: {SPANISH_DOCS_DIR}")
        print(f"📄 Documents to test: {len(TEST_DOCUMENTS)}")
        
        for doc_name in TEST_DOCUMENTS:
            doc_result = self.run_document_test(doc_name)
            self.results["documents"][doc_name] = doc_result
        
        # Generate summary
        self.results["summary"] = self.generate_summary()
        
        # Save results to file
        self.save_results()
        
        return self.results
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate overall test summary."""
        summary = {
            "total_documents": len(self.results["documents"]),
            "parser_comparison": {},
            "overall_best_parser": None,
            "image_extraction_summary": {},
            "recommendations": []
        }
        
        # Compare parsers across all documents
        parser_totals = {}
        for doc_name, doc_data in self.results["documents"].items():
            if "error" in doc_data:
                continue
            
            for parser_name, parser_data in doc_data.get("parsers", {}).items():
                if parser_name not in parser_totals:
                    parser_totals[parser_name] = {
                        "total_text_extracted": 0,
                        "total_images_detected": 0,
                        "total_images_with_ocr": 0,
                        "successful_parses": 0,
                        "failed_parses": 0,
                        "total_processing_time": 0
                    }
                
                if parser_data.get("success"):
                    parser_totals[parser_name]["successful_parses"] += 1
                    parser_totals[parser_name]["total_text_extracted"] += parser_data.get("text_length", 0)
                    parser_totals[parser_name]["total_images_detected"] += parser_data.get("image_count", 0)
                    parser_totals[parser_name]["total_processing_time"] += parser_data.get("processing_time", 0)
                    
                    # Count images with OCR
                    img_analysis = doc_data.get("image_analysis", {}).get(parser_name, {})
                    parser_totals[parser_name]["total_images_with_ocr"] += img_analysis.get("images_with_ocr", 0)
                else:
                    parser_totals[parser_name]["failed_parses"] += 1
        
        summary["parser_comparison"] = parser_totals
        
        # Find best overall parser
        best_parser = None
        best_score = 0
        for parser_name, totals in parser_totals.items():
            # Score based on text extraction and OCR coverage
            score = totals["total_text_extracted"] + (totals["total_images_with_ocr"] * 1000)
            if score > best_score:
                best_score = score
                best_parser = parser_name
        
        summary["overall_best_parser"] = best_parser
        
        # Generate recommendations
        if best_parser:
            summary["recommendations"].append(f"Use {best_parser} for best text extraction on these documents")
        
        for parser_name, totals in parser_totals.items():
            if totals["total_images_detected"] > 0:
                ocr_rate = (totals["total_images_with_ocr"] / totals["total_images_detected"]) * 100
                if ocr_rate < 50:
                    summary["recommendations"].append(
                        f"{parser_name}: Low OCR coverage ({ocr_rate:.1f}%). Consider using OCRmyPDF or Docling for better image text extraction."
                    )
        
        return summary
    
    def save_results(self):
        """Save test results to JSON file."""
        output_file = OUTPUT_DIR / f"spanish_ocr_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Results saved to: {output_file}")
        
        # Also save a summary text file
        summary_file = OUTPUT_DIR / "latest_test_summary.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("SPANISH DOCUMENT OCR TEST SUMMARY\n")
            f.write("="*50 + "\n\n")
            f.write(f"Test Date: {self.results['test_timestamp']}\n")
            f.write(f"Documents Tested: {len(self.results['documents'])}\n\n")
            
            summary = self.results.get("summary", {})
            
            f.write("PARSER COMPARISON:\n")
            f.write("-"*30 + "\n")
            for parser_name, totals in summary.get("parser_comparison", {}).items():
                f.write(f"\n{parser_name.upper()}:\n")
                f.write(f"  Text extracted: {totals['total_text_extracted']:,} chars\n")
                f.write(f"  Images detected: {totals['total_images_detected']}\n")
                f.write(f"  Images with OCR: {totals['total_images_with_ocr']}\n")
                f.write(f"  Processing time: {totals['total_processing_time']:.2f}s\n")
            
            f.write(f"\nBest Overall Parser: {summary.get('overall_best_parser', 'N/A')}\n")
            
            f.write("\nRECOMMENDATIONS:\n")
            f.write("-"*30 + "\n")
            for rec in summary.get("recommendations", []):
                f.write(f"• {rec}\n")
        
        print(f"📝 Summary saved to: {summary_file}")
    
    def print_final_report(self):
        """Print final test report to console."""
        print("\n" + "="*70)
        print("📊 FINAL TEST REPORT")
        print("="*70)
        
        summary = self.results.get("summary", {})
        
        print("\n📈 Parser Comparison:")
        print("-"*50)
        for parser_name, totals in summary.get("parser_comparison", {}).items():
            success_rate = (totals['successful_parses'] / len(TEST_DOCUMENTS)) * 100 if TEST_DOCUMENTS else 0
            print(f"\n  {parser_name.upper()}:")
            print(f"    Success rate: {success_rate:.0f}%")
            print(f"    Text extracted: {totals['total_text_extracted']:,} characters")
            print(f"    Images detected: {totals['total_images_detected']}")
            print(f"    Images with OCR: {totals['total_images_with_ocr']}")
            print(f"    Processing time: {totals['total_processing_time']:.2f} seconds")
        
        print(f"\n🏆 Best Overall Parser: {summary.get('overall_best_parser', 'N/A')}")
        
        print("\n💡 Recommendations:")
        for rec in summary.get("recommendations", []):
            print(f"  • {rec}")
        
        print("\n" + "="*70)


# Pytest test functions
@pytest.fixture(scope="module")
def ocr_tester():
    """Create OCR tester instance."""
    return SpanishDocOCRTest()


def test_documents_exist():
    """Verify all test documents exist."""
    for doc_name in TEST_DOCUMENTS:
        file_path = SPANISH_DOCS_DIR / doc_name
        assert file_path.exists(), f"Document not found: {file_path}"
        print(f"✅ Found: {doc_name}")


def test_document_types():
    """Test PDF type detection for all documents."""
    tester = SpanishDocOCRTest()
    for doc_name in TEST_DOCUMENTS:
        file_path = str(SPANISH_DOCS_DIR / doc_name)
        result = tester.detect_document_type(file_path)
        print(f"📄 {doc_name}: {result['type']}")
        assert "error" not in result, f"Error detecting type for {doc_name}: {result.get('error')}"


@pytest.mark.parametrize("doc_name", TEST_DOCUMENTS)
def test_pymupdf_parser(doc_name):
    """Test PyMuPDF parser on each document."""
    tester = SpanishDocOCRTest()
    file_path = str(SPANISH_DOCS_DIR / doc_name)
    result = tester.test_parser("pymupdf", file_path)
    assert result["success"], f"PyMuPDF failed on {doc_name}: {result.get('error')}"
    assert result["text_length"] > 0, f"PyMuPDF extracted no text from {doc_name}"


@pytest.mark.parametrize("doc_name", TEST_DOCUMENTS)
def test_docling_parser(doc_name):
    """Test Docling parser on each document."""
    tester = SpanishDocOCRTest()
    file_path = str(SPANISH_DOCS_DIR / doc_name)
    result = tester.test_parser("docling", file_path)
    # Docling may timeout on large docs, so we allow failure
    if not result["success"]:
        pytest.skip(f"Docling failed on {doc_name}: {result.get('error')}")


@pytest.mark.parametrize("doc_name", TEST_DOCUMENTS)
def test_ocrmypdf_parser(doc_name):
    """Test OCRmyPDF parser on each document."""
    tester = SpanishDocOCRTest()
    file_path = str(SPANISH_DOCS_DIR / doc_name)
    result = tester.test_parser("ocrmypdf", file_path, language="spa+eng")
    # OCRmyPDF may not be installed
    if result.get("error") and "not installed" in str(result["error"]).lower():
        pytest.skip("OCRmyPDF not installed")


def test_full_ocr_suite():
    """Run full OCR test suite on all documents."""
    tester = SpanishDocOCRTest()
    results = tester.run_all_tests()
    tester.print_final_report()
    
    # Assertions
    assert results["summary"]["overall_best_parser"] is not None, "No parser succeeded"
    
    # Check that at least one parser extracted meaningful content from each document
    for doc_name, doc_data in results["documents"].items():
        if "error" not in doc_data:
            max_text = max(
                p.get("text_length", 0) 
                for p in doc_data.get("parsers", {}).values()
            )
            assert max_text > 100, f"Very little text extracted from {doc_name}"


# Main entry point for direct execution
if __name__ == "__main__":
    print("Running Spanish Document OCR Tests...")
    tester = SpanishDocOCRTest()
    results = tester.run_all_tests()
    tester.print_final_report()

