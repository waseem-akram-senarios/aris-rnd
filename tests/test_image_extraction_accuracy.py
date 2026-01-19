#!/usr/bin/env python3
"""
Image Extraction & OCR Accuracy Test
Tests all parsers specifically for:
1. Image content extraction capability
2. OCR accuracy from images
3. Image metadata completeness
4. Overall accuracy scoring
"""
import os
import sys
import json
import time
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://44.221.84.58:8500")
INGESTION_URL = os.getenv("INGESTION_URL", "http://44.221.84.58:8501")
TEST_DOCS_DIR = "docs/testing/clientSpanishDocs"

# Parsers to test (focusing on those with OCR capabilities)
PARSERS = ["ocrmypdf", "docling", "llamascan", "textract", "pymupdf"]

# Test documents
TEST_DOCUMENTS = [
    "EM10, degasing.pdf",
    "EM11, top seal.pdf",
    "VUORMAR.pdf"
]


def check_service_health():
    """Check if services are running"""
    services = {
        "Gateway": GATEWAY_URL,
        "Ingestion": INGESTION_URL
    }
    
    print("\n" + "=" * 70)
    print("📡 SERVICE HEALTH CHECK")
    print("=" * 70)
    
    all_healthy = True
    for name, url in services.items():
        try:
            resp = requests.get(f"{url}/health", timeout=10)
            if resp.status_code == 200:
                print(f"  ✅ {name}: Healthy ({url})")
            else:
                print(f"  ⚠️ {name}: Status {resp.status_code}")
                all_healthy = False
        except Exception as e:
            print(f"  ❌ {name}: Not reachable - {e}")
            all_healthy = False
    
    return all_healthy


def analyze_image_quality(images: List[Dict]) -> Dict[str, Any]:
    """Analyze image extraction quality and OCR accuracy"""
    if not images:
        return {
            "total_images": 0,
            "with_ocr_text": 0,
            "ocr_coverage": 0.0,
            "avg_ocr_length": 0,
            "meaningful_ocr_count": 0,
            "with_page_info": 0,
            "with_metadata": 0,
            "ocr_quality_score": 0.0
        }
    
    total = len(images)
    with_ocr = 0
    with_page = 0
    with_metadata = 0
    meaningful_ocr = 0
    ocr_lengths = []
    
    for img in images:
        ocr_text = img.get('ocr_text', '') or img.get('text', '')
        page = img.get('page')
        metadata = img.get('metadata', {})
        
        if ocr_text and len(ocr_text.strip()) > 0:
            with_ocr += 1
            text_len = len(ocr_text.strip())
            ocr_lengths.append(text_len)
            
            # Check if OCR text is meaningful (has alphanumeric content)
            alnum_count = sum(1 for c in ocr_text[:200] if c.isalnum())
            if text_len > 20 and alnum_count > 10:
                meaningful_ocr += 1
        
        if page is not None and page > 0:
            with_page += 1
        
        if metadata:
            with_metadata += 1
    
    # Calculate OCR quality score (0-100)
    ocr_coverage = (with_ocr / total * 100) if total > 0 else 0
    meaningful_ratio = (meaningful_ocr / total * 100) if total > 0 else 0
    page_info_ratio = (with_page / total * 100) if total > 0 else 0
    metadata_ratio = (with_metadata / total * 100) if total > 0 else 0
    avg_ocr_length = sum(ocr_lengths) / len(ocr_lengths) if ocr_lengths else 0
    
    # Weighted score: OCR coverage (40%), meaningful OCR (30%), page info (15%), metadata (15%)
    ocr_quality_score = (
        ocr_coverage * 0.4 +
        meaningful_ratio * 0.3 +
        page_info_ratio * 0.15 +
        metadata_ratio * 0.15
    )
    
    return {
        "total_images": total,
        "with_ocr_text": with_ocr,
        "ocr_coverage": round(ocr_coverage, 2),
        "avg_ocr_length": round(avg_ocr_length, 2),
        "meaningful_ocr_count": meaningful_ocr,
        "meaningful_ocr_ratio": round(meaningful_ratio, 2),
        "with_page_info": with_page,
        "page_info_ratio": round(page_info_ratio, 2),
        "with_metadata": with_metadata,
        "metadata_ratio": round(metadata_ratio, 2),
        "ocr_quality_score": round(ocr_quality_score, 2)
    }


def test_parser_image_extraction(doc_path: str, doc_name: str, parser: str) -> Dict[str, Any]:
    """Test a parser's image extraction and OCR capabilities"""
    result = {
        "parser": parser,
        "document": doc_name,
        "success": False,
        "document_id": None,
        "processing_time": 0,
        "images_found": 0,
        "images_extracted": 0,
        "image_analysis": {},
        "text_extracted": 0,
        "chunks_created": 0,
        "error": None
    }
    
    # Read file content
    try:
        with open(doc_path, "rb") as f:
            file_content = f.read()
    except Exception as e:
        result["error"] = f"Failed to read file: {e}"
        return result
    
    # Create unique index name for this parser/doc combination
    sanitized_name = re.sub(r'[^a-z0-9]', '-', doc_name.lower().replace('.pdf', ''))
    index_name = f"test-img-{parser}-{sanitized_name}"[:50]
    
    # Upload and process document
    start_time = time.time()
    
    try:
        files = {"file": (doc_name, file_content, "application/pdf")}
        data = {
            "parser_preference": parser,
            "index_name": index_name,
            "language": "spa",  # Spanish
            "force_update": "true"
        }
        
        print(f"    📤 Processing with {parser}...")
        resp = requests.post(
            f"{INGESTION_URL}/process",
            files=files,
            data=data,
            timeout=600  # 10 minute timeout for OCR-heavy processing
        )
        
        processing_time = time.time() - start_time
        result["processing_time"] = round(processing_time, 2)
        
        if resp.status_code == 200:
            response_data = resp.json()
            result["success"] = response_data.get("success", True) or response_data.get("status") == "success"
            result["document_id"] = response_data.get("document_id")
            result["images_found"] = response_data.get("image_count", 0)
            result["text_extracted"] = response_data.get("tokens_extracted", 0) * 4  # Approximate chars
            result["chunks_created"] = response_data.get("chunks_created", 0)
            
            # If document_id not in response, try to find it from registry
            if not result["document_id"]:
                try:
                    from storage.document_registry import DocumentRegistry
                    from shared.config.settings import ARISConfig
                    registry = DocumentRegistry(ARISConfig.DOCUMENT_REGISTRY_PATH)
                    docs = registry.find_documents_by_name(doc_name)
                    if docs:
                        # Get the most recent one (should be the one we just processed)
                        result["document_id"] = docs[-1].get("document_id")
                        print(f"    ℹ️ Found document_id from registry: {result['document_id']}")
                except Exception as e:
                    print(f"    ⚠️ Could not find document_id from registry: {e}")
            
            print(f"    ✅ Processed: {result['chunks_created']} chunks, {result['images_found']} images found")
            
            # Wait a bit for indexing to complete
            time.sleep(5)
            
            # Get images from the document
            if result["document_id"]:
                try:
                    img_resp = requests.get(
                        f"{GATEWAY_URL}/documents/{result['document_id']}/images",
                        timeout=30
                    )
                    
                    if img_resp.status_code == 200:
                        images_data = img_resp.json()
                        images = images_data.get("images", [])
                        result["images_extracted"] = len(images)
                        
                        # Analyze image quality
                        result["image_analysis"] = analyze_image_quality(images)
                        
                        print(f"    📸 Images extracted: {len(images)}")
                        print(f"    📊 OCR Quality Score: {result['image_analysis'].get('ocr_quality_score', 0)}/100")
                        print(f"    📝 OCR Coverage: {result['image_analysis'].get('ocr_coverage', 0)}%")
                    else:
                        print(f"    ⚠️ Could not fetch images: HTTP {img_resp.status_code}")
                        result["image_analysis"] = analyze_image_quality([])
                        
                except Exception as e:
                    print(f"    ⚠️ Error fetching images: {e}")
                    result["image_analysis"] = analyze_image_quality([])
            else:
                result["image_analysis"] = analyze_image_quality([])
                
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"    ❌ Failed: {result['error']}")
            
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out (600s limit)"
        result["processing_time"] = 600
        print(f"    ❌ Timeout after 600s")
    except Exception as e:
        result["error"] = str(e)
        print(f"    ❌ Error: {e}")
    
    return result


def generate_accuracy_report(all_results: List[Dict]) -> Dict[str, Any]:
    """Generate comprehensive accuracy report focused on image extraction"""
    
    print("\n" + "=" * 70)
    print("📊 IMAGE EXTRACTION & OCR ACCURACY REPORT")
    print("=" * 70)
    
    # Group results by parser
    parser_summary = {}
    for r in all_results:
        parser = r["parser"]
        if parser not in parser_summary:
            parser_summary[parser] = {
                "total_docs": 0,
                "successful": 0,
                "failed": 0,
                "total_images_found": 0,
                "total_images_extracted": 0,
                "total_ocr_quality_score": 0,
                "total_ocr_coverage": 0,
                "total_meaningful_ocr": 0,
                "total_text_extracted": 0,
                "total_chunks": 0,
                "avg_processing_time": 0,
                "errors": []
            }
        
        s = parser_summary[parser]
        s["total_docs"] += 1
        
        if r["success"]:
            s["successful"] += 1
            s["total_images_found"] += r.get("images_found", 0)
            s["total_images_extracted"] += r.get("images_extracted", 0)
            
            img_analysis = r.get("image_analysis", {})
            s["total_ocr_quality_score"] += img_analysis.get("ocr_quality_score", 0)
            s["total_ocr_coverage"] += img_analysis.get("ocr_coverage", 0)
            s["total_meaningful_ocr"] += img_analysis.get("meaningful_ocr_count", 0)
            s["total_text_extracted"] += r.get("text_extracted", 0)
            s["total_chunks"] += r.get("chunks_created", 0)
            s["avg_processing_time"] += r.get("processing_time", 0)
        else:
            s["failed"] += 1
            if r.get("error"):
                s["errors"].append(r["error"])
    
    # Calculate averages
    for parser, s in parser_summary.items():
        if s["successful"] > 0:
            s["avg_ocr_quality_score"] = round(s["total_ocr_quality_score"] / s["successful"], 2)
            s["avg_ocr_coverage"] = round(s["total_ocr_coverage"] / s["successful"], 2)
            s["avg_processing_time"] = round(s["avg_processing_time"] / s["successful"], 2)
            s["avg_images_per_doc"] = round(s["total_images_extracted"] / s["successful"], 2)
        else:
            s["avg_ocr_quality_score"] = 0
            s["avg_ocr_coverage"] = 0
            s["avg_processing_time"] = 0
            s["avg_images_per_doc"] = 0
    
    # Calculate accuracy scores (0-100)
    parser_scores = {}
    for parser, s in parser_summary.items():
        # Scoring criteria (focused on image extraction):
        # - Success rate: 25 points max
        # - OCR Quality Score: 35 points max (most important for image extraction)
        # - OCR Coverage: 20 points max
        # - Images extracted: 15 points max
        # - Speed (inverse): 5 points max
        
        success_score = (s["successful"] / s["total_docs"]) * 25 if s["total_docs"] > 0 else 0
        
        # OCR Quality Score (0-100 scale, normalized to 35 points)
        ocr_quality_score = (s["avg_ocr_quality_score"] / 100) * 35
        
        # OCR Coverage (0-100%, normalized to 20 points)
        ocr_coverage_score = (s["avg_ocr_coverage"] / 100) * 20
        
        # Images extracted (normalized, max 20 images per doc = full score)
        image_score = min(s["avg_images_per_doc"] / 20, 1.0) * 15
        
        # Speed (faster = better, max 60s = full score, 600s = 0)
        if s["avg_processing_time"] > 0:
            speed_score = max(0, (600 - s["avg_processing_time"]) / 600) * 5
        else:
            speed_score = 5
        
        total_score = success_score + ocr_quality_score + ocr_coverage_score + image_score + speed_score
        parser_scores[parser] = {
            "total": round(total_score, 2),
            "success": round(success_score, 2),
            "ocr_quality": round(ocr_quality_score, 2),
            "ocr_coverage": round(ocr_coverage_score, 2),
            "images": round(image_score, 2),
            "speed": round(speed_score, 2)
        }
    
    # Print detailed summary table
    print("\n┌─────────────┬──────────┬──────────┬──────────────┬──────────────┬─────────────┬─────────┐")
    print("│ Parser      │ Success  │ Images   │ OCR Quality  │ OCR Coverage │ Avg Images │ Time(s) │")
    print("│             │          │ Extracted│ Score        │ (%)          │ Per Doc    │         │")
    print("├─────────────┼──────────┼──────────┼──────────────┼──────────────┼─────────────┼─────────┤")
    
    for parser in PARSERS:
        s = parser_summary.get(parser, {})
        success = f"{s.get('successful', 0)}/{s.get('total_docs', 0)}"
        images_ext = s.get('total_images_extracted', 0)
        ocr_quality = s.get('avg_ocr_quality_score', 0)
        ocr_cov = s.get('avg_ocr_coverage', 0)
        avg_img = s.get('avg_images_per_doc', 0)
        time_s = s.get('avg_processing_time', 0)
        
        print(f"│ {parser:<11} │ {success:<8} │ {images_ext:>8} │ {ocr_quality:>12.1f} │ {ocr_cov:>12.1f} │ {avg_img:>11.1f} │ {time_s:>7.1f} │")
    
    print("└─────────────┴──────────┴──────────┴──────────────┴──────────────┴─────────────┴─────────┘")
    
    # Print accuracy scores
    print("\n📈 IMAGE EXTRACTION ACCURACY SCORES (out of 100):")
    print("┌─────────────┬─────────┬─────────┬──────────────┬──────────────┬─────────┬─────────┐")
    print("│ Parser      │ TOTAL   │ Success │ OCR Quality  │ OCR Coverage │ Images  │ Speed   │")
    print("├─────────────┼─────────┼─────────┼──────────────┼──────────────┼─────────┼─────────┤")
    
    sorted_parsers = sorted(parser_scores.items(), key=lambda x: x[1]["total"], reverse=True)
    for parser, scores in sorted_parsers:
        print(f"│ {parser:<11} │ {scores['total']:>7.1f} │ {scores['success']:>7.1f} │ {scores['ocr_quality']:>12.1f} │ {scores['ocr_coverage']:>12.1f} │ {scores['images']:>7.1f} │ {scores['speed']:>7.1f} │")
    
    print("└─────────────┴─────────┴─────────┴──────────────┴──────────────┴─────────┴─────────┘")
    
    # Best parser recommendation
    best_parser = sorted_parsers[0][0] if sorted_parsers else "ocrmypdf"
    best_score = sorted_parsers[0][1]["total"] if sorted_parsers else 0
    
    print(f"\n🏆 BEST PARSER FOR IMAGE EXTRACTION: {best_parser.upper()}")
    print(f"   Total Accuracy Score: {best_score}/100")
    print(f"   OCR Quality: {parser_summary[best_parser].get('avg_ocr_quality_score', 0)}/100")
    print(f"   OCR Coverage: {parser_summary[best_parser].get('avg_ocr_coverage', 0)}%")
    print(f"   Avg Images Per Doc: {parser_summary[best_parser].get('avg_images_per_doc', 0)}")
    
    # Detailed recommendations
    print("\n📋 DETAILED RECOMMENDATIONS:")
    for parser, scores in sorted_parsers[:3]:  # Top 3
        s = parser_summary[parser]
        print(f"\n  {parser.upper()}:")
        print(f"    • Accuracy Score: {scores['total']}/100")
        print(f"    • OCR Quality: {s.get('avg_ocr_quality_score', 0)}/100")
        print(f"    • OCR Coverage: {s.get('avg_ocr_coverage', 0)}%")
        print(f"    • Success Rate: {s.get('successful', 0)}/{s.get('total_docs', 0)}")
        print(f"    • Processing Time: {s.get('avg_processing_time', 0)}s")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "parser_results": all_results,
        "parser_summary": parser_summary,
        "parser_scores": parser_scores,
        "best_parser": best_parser,
        "best_score": best_score
    }


def main():
    """Main test runner"""
    print("\n" + "=" * 70)
    print("🧪 IMAGE EXTRACTION & OCR ACCURACY TEST")
    print(f"   Documents: {TEST_DOCS_DIR}")
    print(f"   Parsers: {', '.join(PARSERS)}")
    print(f"   Focus: Image Content Extraction & OCR Accuracy")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Check services
    if not check_service_health():
        print("\n⚠️ Some services are not healthy. Continuing anyway...")
    
    # Find test documents
    workspace_root = Path(__file__).parent.parent
    docs_dir = workspace_root / TEST_DOCS_DIR
    
    if not docs_dir.exists():
        print(f"\n❌ Test documents directory not found: {docs_dir}")
        return
    
    # Run tests
    all_results = []
    
    for doc_name in TEST_DOCUMENTS:
        doc_path = docs_dir / doc_name
        
        if not doc_path.exists():
            print(f"\n⚠️ Document not found: {doc_path}")
            continue
        
        print(f"\n📄 Testing: {doc_name}")
        print("-" * 70)
        
        for parser in PARSERS:
            print(f"  🔧 Parser: {parser}")
            result = test_parser_image_extraction(str(doc_path), doc_name, parser)
            all_results.append(result)
            
            # Small delay between parsers
            time.sleep(3)
    
    # Generate report
    report = generate_accuracy_report(all_results)
    
    # Save report
    report_path = workspace_root / "tests" / f"image_extraction_accuracy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 Detailed report saved to: {report_path}")
    
    return report


if __name__ == "__main__":
    report = main()
    
    if report:
        print(f"\n✅ Test completed!")
        print(f"🏆 Best parser for image extraction: {report['best_parser'].upper()}")
        print(f"📊 Accuracy score: {report['best_score']}/100")

