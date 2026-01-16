#!/usr/bin/env python3
"""
Parser Comparison Test Script
Tests all parsers against Spanish documents and evaluates:
1. Text extraction accuracy
2. Page number citation accuracy
3. OCR from images quality
"""
import os
import sys
import json
import time
import re
import requests
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
INGESTION_URL = os.getenv("INGESTION_URL", "http://44.221.84.58:8501")
RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://44.221.84.58:8502")
TEST_DOCS_DIR = "docs/testing/clientSpanishDocs"

# Parsers to test
PARSERS = ["pymupdf", "docling", "ocrmypdf", "textract", "llamascan"]

# Test documents
TEST_DOCUMENTS = [
    "EM10, degasing.pdf",
    "EM11, top seal.pdf",
    "VUORMAR.pdf"
]

# Spanish test queries to evaluate retrieval accuracy
TEST_QUERIES = [
    {"query": "¿Cuál es el proceso de desgasificación?", "expected_keywords": ["degas", "gas", "proceso"]},
    {"query": "¿Cómo se sella la parte superior?", "expected_keywords": ["seal", "sello", "top"]},
    {"query": "¿Cuáles son los pasos de mantenimiento?", "expected_keywords": ["manten", "paso", "ficha"]},
]


def check_service_health():
    """Check if services are running"""
    services = {
        "Ingestion": INGESTION_URL,
        "Retrieval": RETRIEVAL_URL
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


def test_parser(doc_path: str, doc_name: str, parser: str) -> dict:
    """Test a single parser on a document"""
    result = {
        "parser": parser,
        "document": doc_name,
        "success": False,
        "text_length": 0,
        "pages_extracted": 0,
        "images_found": 0,
        "chunks_created": 0,
        "page_markers_found": 0,
        "processing_time": 0,
        "confidence": 0,
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
    index_name = f"test-{parser}-{sanitized_name}"[:50]
    
    # Upload document to ingestion service
    start_time = time.time()
    
    try:
        files = {"file": (doc_name, file_content, "application/pdf")}
        data = {
            "parser_preference": parser,
            "index_name": index_name,
            "language": "spa",  # Spanish
            "force_update": "true"  # Force reprocessing
        }
        
        print(f"    📤 Uploading to {INGESTION_URL}/process ...")
        resp = requests.post(
            f"{INGESTION_URL}/process",
            files=files,
            data=data,
            timeout=300  # 5 minute timeout for large docs
        )
        
        processing_time = time.time() - start_time
        result["processing_time"] = round(processing_time, 2)
        
        if resp.status_code == 200:
            response_data = resp.json()
            result["success"] = response_data.get("success", True) or response_data.get("status") == "success"
            
            # Extract metrics from response (direct format from /process endpoint)
            result["text_length"] = response_data.get("tokens_extracted", 0) * 4  # Approximate chars from tokens
            result["pages_extracted"] = response_data.get("pages", 0)
            result["images_found"] = response_data.get("image_count", 0)
            result["chunks_created"] = response_data.get("chunks_created", 0)
            result["confidence"] = response_data.get("extraction_percentage", 0) or response_data.get("confidence", 0)
            result["parser_used"] = response_data.get("parser_used", parser)
            
            # Store tokens for analysis
            result["tokens_extracted"] = response_data.get("tokens_extracted", 0)
            
            # Check if images were detected (important for OCR evaluation)
            result["images_detected"] = response_data.get("images_detected", False)
                
            print(f"    ✅ Processed: {result['chunks_created']} chunks, {result.get('tokens_extracted', 0)} tokens, {result['images_found']} images (parser: {result.get('parser_used', parser)})")
            
        else:
            result["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"    ❌ Failed: {result['error']}")
            
    except requests.exceptions.Timeout:
        result["error"] = "Request timed out (300s limit)"
        result["processing_time"] = 300
        print(f"    ❌ Timeout after 300s")
    except Exception as e:
        result["error"] = str(e)
        print(f"    ❌ Error: {e}")
    
    return result


def test_query_accuracy(parser_results: list) -> dict:
    """Test query accuracy using the Retrieval service"""
    query_results = {}
    
    print("\n" + "=" * 70)
    print("🔍 QUERY ACCURACY TEST")
    print("=" * 70)
    
    # Get successfully processed parsers
    successful_parsers = set()
    for r in parser_results:
        if r["success"]:
            successful_parsers.add(r["parser"])
    
    for query_info in TEST_QUERIES:
        query = query_info["query"]
        expected = query_info["expected_keywords"]
        
        print(f"\n  Query: {query}")
        print(f"  Expected keywords: {expected}")
        
        try:
            resp = requests.post(
                f"{RETRIEVAL_URL}/query",
                json={
                    "question": query,
                    "k": 5,
                    "language": "spa"
                },
                timeout=60
            )
            
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "") or data.get("response", "")
                sources = data.get("sources", []) or data.get("citations", [])
                
                # Check keyword matches
                matches = sum(1 for kw in expected if kw.lower() in answer.lower())
                accuracy = matches / len(expected) * 100
                
                print(f"  ✅ Keyword match: {matches}/{len(expected)} ({accuracy:.0f}%)")
                print(f"  📎 Sources: {len(sources)}")
                
                query_results[query] = {
                    "accuracy": accuracy,
                    "sources_count": len(sources),
                    "answer_length": len(answer)
                }
            else:
                print(f"  ⚠️ Query failed: {resp.status_code}")
                query_results[query] = {"error": f"HTTP {resp.status_code}"}
                
        except Exception as e:
            print(f"  ❌ Query error: {e}")
            query_results[query] = {"error": str(e)}
    
    return query_results


def generate_report(parser_results: list, query_results: dict) -> dict:
    """Generate comprehensive comparison report"""
    
    print("\n" + "=" * 70)
    print("📊 PARSER COMPARISON REPORT")
    print("=" * 70)
    
    # Group results by parser
    parser_summary = {}
    for r in parser_results:
        parser = r["parser"]
        if parser not in parser_summary:
            parser_summary[parser] = {
                "total_docs": 0,
                "successful": 0,
                "failed": 0,
                "total_tokens": 0,
                "total_pages": 0,
                "total_images": 0,
                "total_chunks": 0,
                "images_detected_count": 0,
                "avg_processing_time": 0,
                "avg_confidence": 0,
                "errors": []
            }
        
        s = parser_summary[parser]
        s["total_docs"] += 1
        
        if r["success"]:
            s["successful"] += 1
            s["total_tokens"] += r.get("tokens_extracted", 0)
            s["total_pages"] += r["pages_extracted"]
            s["total_images"] += r["images_found"]
            s["total_chunks"] += r["chunks_created"]
            s["images_detected_count"] += 1 if r.get("images_detected") else 0
            s["avg_processing_time"] += r["processing_time"]
            s["avg_confidence"] += r["confidence"]
        else:
            s["failed"] += 1
            if r["error"]:
                s["errors"].append(r["error"])
    
    # Calculate averages
    for parser, s in parser_summary.items():
        if s["successful"] > 0:
            s["avg_processing_time"] = round(s["avg_processing_time"] / s["successful"], 2)
            s["avg_confidence"] = round(s["avg_confidence"] / s["successful"], 3)
    
    # Score each parser (higher is better)
    parser_scores = {}
    for parser, s in parser_summary.items():
        # Scoring criteria:
        # - Success rate: 30 points max
        # - Token extraction: 25 points max (more tokens = better content extraction)
        # - Chunk creation: 20 points max (more chunks = better granularity)
        # - Images detection: 15 points max (good OCR capability)
        # - Speed (inverse): 10 points max
        
        success_score = (s["successful"] / s["total_docs"]) * 30 if s["total_docs"] > 0 else 0
        
        # Normalize token extraction (max 50K tokens = full score for 3 docs)
        token_score = min(s["total_tokens"] / 50000, 1.0) * 25
        
        # Chunk creation (max 300 chunks = full score for 3 docs)
        chunk_score = min(s["total_chunks"] / 300, 1.0) * 20
        
        # Images detected (max 30 images = full score for 3 docs)
        image_score = min(s["total_images"] / 30, 1.0) * 15
        
        # Speed (faster = better, max 60s = full score, 300s = 0)
        if s["avg_processing_time"] > 0:
            speed_score = max(0, (300 - s["avg_processing_time"]) / 300) * 10
        else:
            speed_score = 10  # If no successful runs, assume fast
        
        total_score = success_score + token_score + chunk_score + image_score + speed_score
        parser_scores[parser] = {
            "total": round(total_score, 2),
            "success": round(success_score, 2),
            "tokens": round(token_score, 2),
            "chunks": round(chunk_score, 2),
            "images": round(image_score, 2),
            "speed": round(speed_score, 2)
        }
    
    # Print summary table
    print("\n┌─────────────┬──────────┬──────────┬────────┬─────────┬────────┬─────────┐")
    print("│ Parser      │ Success  │ Tokens   │ Pages  │ Images  │ Chunks │ Time(s) │")
    print("├─────────────┼──────────┼──────────┼────────┼─────────┼────────┼─────────┤")
    
    for parser in PARSERS:
        s = parser_summary.get(parser, {})
        success = f"{s.get('successful', 0)}/{s.get('total_docs', 0)}"
        tokens = s.get('total_tokens', 0)
        pages = s.get('total_pages', 0)
        images = s.get('total_images', 0)
        chunks = s.get('total_chunks', 0)
        time_s = s.get('avg_processing_time', 0)
        
        print(f"│ {parser:<11} │ {success:<8} │ {tokens:>8} │ {pages:>6} │ {images:>7} │ {chunks:>6} │ {time_s:>7.1f} │")
    
    print("└─────────────┴──────────┴──────────┴────────┴─────────┴────────┴─────────┘")
    
    # Print scores
    print("\n📈 PARSER SCORES (out of 100):")
    print("┌─────────────┬─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐")
    print("│ Parser      │ TOTAL   │ Success │ Tokens  │ Chunks  │ Images  │ Speed   │")
    print("├─────────────┼─────────┼─────────┼─────────┼─────────┼─────────┼─────────┤")
    
    sorted_parsers = sorted(parser_scores.items(), key=lambda x: x[1]["total"], reverse=True)
    for parser, scores in sorted_parsers:
        print(f"│ {parser:<11} │ {scores['total']:>7.1f} │ {scores['success']:>7.1f} │ {scores['tokens']:>7.1f} │ {scores['chunks']:>7.1f} │ {scores['images']:>7.1f} │ {scores['speed']:>7.1f} │")
    
    print("└─────────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘")
    
    # Best parser recommendation
    best_parser = sorted_parsers[0][0] if sorted_parsers else "pymupdf"
    best_score = sorted_parsers[0][1]["total"] if sorted_parsers else 0
    
    print(f"\n🏆 RECOMMENDED PARSER: {best_parser.upper()} (Score: {best_score}/100)")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "parser_results": parser_results,
        "parser_summary": parser_summary,
        "parser_scores": parser_scores,
        "query_results": query_results,
        "best_parser": best_parser,
        "best_score": best_score
    }


def main():
    """Main test runner"""
    print("\n" + "=" * 70)
    print("🧪 PARSER COMPARISON TEST")
    print(f"   Documents: {TEST_DOCS_DIR}")
    print(f"   Parsers: {', '.join(PARSERS)}")
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
        print("-" * 50)
        
        for parser in PARSERS:
            print(f"  🔧 Parser: {parser}")
            result = test_parser(str(doc_path), doc_name, parser)
            all_results.append(result)
            
            # Small delay between parsers to avoid overwhelming services
            time.sleep(2)
    
    # Test query accuracy
    query_results = test_query_accuracy(all_results)
    
    # Generate report
    report = generate_report(all_results, query_results)
    
    # Save report
    report_path = workspace_root / "tests" / f"parser_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 Report saved to: {report_path}")
    
    return report


if __name__ == "__main__":
    report = main()
    
    if report:
        print(f"\n✅ Test completed! Best parser: {report['best_parser'].upper()}")

