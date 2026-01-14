"""
Comprehensive R&D Test for Spanish Documents
Tests multiple parsers, cross-language queries, and parameters to find optimal defaults
"""

import os
import sys
import time
import json
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import statistics

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE_URL = "http://44.221.84.58:8500"

@dataclass
class TestConfig:
    """Test configuration"""
    parser: str
    search_mode: str
    semantic_weight: float
    k: int
    auto_translate: bool
    temperature: float

@dataclass
class TestResult:
    """Test result"""
    config: TestConfig
    query: str
    query_language: str
    document_name: str
    citations_count: int
    avg_similarity: float
    max_similarity: float
    response_time: float
    answer_quality: float
    answer: str
    error: str = None

class SpanishDocTester:
    """Comprehensive tester for Spanish documents"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[TestResult] = []
        
    def upload_document(self, file_path: str, parser: str) -> Dict:
        """Upload document with specific parser"""
        url = f"{self.base_url}/documents"
        
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/pdf')}
            data = {'parser_preference': parser}
            
            try:
                response = requests.post(url, files=files, data=data, timeout=300)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                return {"error": str(e)}
    
    def query_with_config(self, question: str, document_id: str, config: TestConfig) -> Dict:
        """Query with specific configuration"""
        url = f"{self.base_url}/query"
        
        payload = {
            "question": question,
            "k": config.k,
            "search_mode": config.search_mode,
            "use_hybrid_search": (config.search_mode == "hybrid"),
            "semantic_weight": config.semantic_weight,
            "auto_translate": config.auto_translate,
            "temperature": config.temperature,
            "document_id": document_id,
            "active_sources": [document_id]
        }
        
        try:
            start_time = time.time()
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            result['response_time'] = time.time() - start_time
            return result
        except Exception as e:
            return {"error": str(e), "answer": "", "citations": [], "response_time": 0}
    
    def evaluate_answer(self, answer: str, query: str, expected_keywords: List[str] = None) -> float:
        """Evaluate answer quality (0-100)"""
        if not answer or len(answer.strip()) < 20:
            return 0.0
        
        # Check for error indicators
        error_phrases = [
            "i don't know", "i cannot", "no information", "not found",
            "check the manual", "no se encuentra", "no disponible"
        ]
        
        answer_lower = answer.lower()
        for phrase in error_phrases:
            if phrase in answer_lower:
                return 20.0
        
        # Check for expected keywords
        score = 50.0  # Base score for valid answer
        
        if expected_keywords:
            found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
            score += (found / len(expected_keywords)) * 30
        
        # Length and detail score
        if len(answer) > 100:
            score += 10
        if len(answer) > 200:
            score += 10
        
        return min(100.0, score)
    
    def run_comprehensive_test(self, docs_dir: str) -> Dict:
        """Run comprehensive test suite"""
        print("=" * 80)
        print("🔬 COMPREHENSIVE R&D TEST - SPANISH DOCUMENTS")
        print("=" * 80)
        
        # Test configurations
        test_configs = [
            # Hybrid with different weights
            TestConfig("pymupdf", "hybrid", 0.7, 15, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.5, 15, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 15, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.3, 15, True, 0.2),
            
            # Different k values
            TestConfig("pymupdf", "hybrid", 0.4, 10, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 15, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 25, True, 0.2),
            
            # Different search modes
            TestConfig("pymupdf", "semantic", 1.0, 20, True, 0.2),
            TestConfig("pymupdf", "keyword", 0.0, 20, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.2),
            
            # Auto-translate on/off
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.2),
            TestConfig("pymupdf", "hybrid", 0.4, 20, False, 0.2),
            
            # Different parsers (with best params so far)
            TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.2),
            TestConfig("docling", "hybrid", 0.4, 20, True, 0.2),
            TestConfig("ocrmypdf", "hybrid", 0.4, 20, True, 0.2),
            TestConfig("llama-scan", "hybrid", 0.4, 20, True, 0.2),
        ]
        
        # Test queries
        test_queries = [
            {
                "spanish": "¿Dónde está el email y contacto de Vuormar?",
                "english": "Where is the email and contact of Vuormar?",
                "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono"]
            },
            {
                "spanish": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
                "english": "How to increase or decrease the levels of air in bag?",
                "keywords": ["aire", "air", "bolsa", "bag", "aumentar", "increase"]
            },
            {
                "spanish": "¿Cuál es el procedimiento de mantenimiento?",
                "english": "What is the maintenance procedure?",
                "keywords": ["mantenimiento", "maintenance", "procedimiento", "procedure"]
            }
        ]
        
        # Find PDF files
        pdf_files = []
        if os.path.exists(docs_dir):
            for file in os.listdir(docs_dir):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(docs_dir, file))
        
        if not pdf_files:
            print(f"❌ No PDF files found in {docs_dir}")
            return {"error": "No PDF files found"}
        
        print(f"\n📚 Found {len(pdf_files)} PDF file(s)")
        for pdf in pdf_files:
            print(f"   - {os.path.basename(pdf)}")
        
        # Upload documents with different parsers
        uploaded_docs = {}
        parsers = ["pymupdf", "docling", "ocrmypdf", "llama-scan"]
        
        for pdf_path in pdf_files[:2]:  # Test first 2 documents
            doc_name = os.path.basename(pdf_path)
            print(f"\n📄 Processing: {doc_name}")
            
            for parser in parsers:
                print(f"   🔧 Uploading with {parser}...")
                result = self.upload_document(pdf_path, parser)
                
                if "error" in result:
                    print(f"      ❌ Error: {result['error']}")
                    continue
                
                doc_id = result.get('document_id')
                if doc_id:
                    key = f"{doc_name}_{parser}"
                    uploaded_docs[key] = {
                        'document_id': doc_id,
                        'document_name': doc_name,
                        'parser': parser,
                        'chunks': result.get('chunks_created', 0)
                    }
                    print(f"      ✅ Uploaded: {doc_id} ({result.get('chunks_created', 0)} chunks)")
                
                time.sleep(2)  # Rate limiting
        
        if not uploaded_docs:
            print("❌ No documents uploaded successfully")
            return {"error": "No documents uploaded"}
        
        print(f"\n✅ Successfully uploaded {len(uploaded_docs)} document variants")
        
        # Run tests
        print("\n" + "=" * 80)
        print("🧪 RUNNING TESTS")
        print("=" * 80)
        
        for doc_key, doc_info in list(uploaded_docs.items())[:4]:  # Test first 4 variants
            doc_id = doc_info['document_id']
            doc_name = doc_info['document_name']
            parser = doc_info['parser']
            
            print(f"\n📄 Testing: {doc_name} (Parser: {parser})")
            print("-" * 80)
            
            # Test relevant configs for this parser
            relevant_configs = [c for c in test_configs if c.parser == parser or parser == "pymupdf"]
            
            for config in relevant_configs[:8]:  # Limit tests per document
                for query_set in test_queries:
                    # Test both Spanish and English
                    for lang, query in [("spanish", query_set["spanish"]), ("english", query_set["english"])]:
                        print(f"\n   🔍 Config: {config.search_mode}, k={config.k}, sw={config.semantic_weight}, at={config.auto_translate}")
                        print(f"      Query ({lang}): {query[:50]}...")
                        
                        result = self.query_with_config(query, doc_id, config)
                        
                        if "error" in result:
                            print(f"      ❌ Error: {result['error']}")
                            continue
                        
                        citations = result.get('citations', [])
                        similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                        avg_sim = sum(similarities) / len(similarities) if similarities else 0
                        max_sim = max(similarities) if similarities else 0
                        
                        answer = result.get('answer', '')
                        quality = self.evaluate_answer(answer, query, query_set['keywords'])
                        
                        test_result = TestResult(
                            config=config,
                            query=query,
                            query_language=lang,
                            document_name=doc_name,
                            citations_count=len(citations),
                            avg_similarity=avg_sim,
                            max_similarity=max_sim,
                            response_time=result.get('response_time', 0),
                            answer_quality=quality,
                            answer=answer[:100] + "..." if len(answer) > 100 else answer
                        )
                        
                        self.results.append(test_result)
                        
                        print(f"      📊 Citations: {len(citations)}, Avg Sim: {avg_sim:.1f}%, Quality: {quality:.1f}%")
                        
                        time.sleep(1)  # Rate limiting
        
        # Analyze results
        return self.analyze_results()
    
    def analyze_results(self) -> Dict:
        """Analyze test results and find best configuration"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        print("\n" + "=" * 80)
        print("📊 ANALYSIS & RECOMMENDATIONS")
        print("=" * 80)
        
        # Group by configuration parameter
        by_parser = {}
        by_search_mode = {}
        by_semantic_weight = {}
        by_k = {}
        by_auto_translate = {}
        
        for result in self.results:
            config = result.config
            
            # By parser
            parser = config.parser
            if parser not in by_parser:
                by_parser[parser] = []
            by_parser[parser].append(result.answer_quality)
            
            # By search mode
            mode = config.search_mode
            if mode not in by_search_mode:
                by_search_mode[mode] = []
            by_search_mode[mode].append(result.answer_quality)
            
            # By semantic weight
            sw = config.semantic_weight
            if sw not in by_semantic_weight:
                by_semantic_weight[sw] = []
            by_semantic_weight[sw].append(result.answer_quality)
            
            # By k
            k = config.k
            if k not in by_k:
                by_k[k] = []
            by_k[k].append(result.answer_quality)
            
            # By auto_translate
            at = config.auto_translate
            if at not in by_auto_translate:
                by_auto_translate[at] = []
            by_auto_translate[at].append(result.answer_quality)
        
        # Calculate averages
        print("\n🔧 PARSER PERFORMANCE:")
        parser_avg = {}
        for parser, qualities in by_parser.items():
            avg = statistics.mean(qualities)
            parser_avg[parser] = avg
            print(f"   {parser:15s}: {avg:5.1f}% (tests: {len(qualities)})")
        
        print("\n🔍 SEARCH MODE PERFORMANCE:")
        mode_avg = {}
        for mode, qualities in by_search_mode.items():
            avg = statistics.mean(qualities)
            mode_avg[mode] = avg
            print(f"   {mode:15s}: {avg:5.1f}% (tests: {len(qualities)})")
        
        print("\n⚖️  SEMANTIC WEIGHT PERFORMANCE:")
        sw_avg = {}
        for sw, qualities in by_semantic_weight.items():
            avg = statistics.mean(qualities)
            sw_avg[sw] = avg
            print(f"   {sw:15.1f}: {avg:5.1f}% (tests: {len(qualities)})")
        
        print("\n📏 K VALUE PERFORMANCE:")
        k_avg = {}
        for k, qualities in by_k.items():
            avg = statistics.mean(qualities)
            k_avg[k] = avg
            print(f"   {k:15d}: {avg:5.1f}% (tests: {len(qualities)})")
        
        print("\n🌐 AUTO-TRANSLATE PERFORMANCE:")
        at_avg = {}
        for at, qualities in by_auto_translate.items():
            avg = statistics.mean(qualities)
            at_avg[at] = avg
            status = "Enabled" if at else "Disabled"
            print(f"   {status:15s}: {avg:5.1f}% (tests: {len(qualities)})")
        
        # Find best configuration
        best_parser = max(parser_avg.items(), key=lambda x: x[1])[0] if parser_avg else "pymupdf"
        best_mode = max(mode_avg.items(), key=lambda x: x[1])[0] if mode_avg else "hybrid"
        best_sw = max(sw_avg.items(), key=lambda x: x[1])[0] if sw_avg else 0.4
        best_k = max(k_avg.items(), key=lambda x: x[1])[0] if k_avg else 20
        best_at = max(at_avg.items(), key=lambda x: x[1])[0] if at_avg else True
        
        print("\n" + "=" * 80)
        print("🏆 RECOMMENDED DEFAULT CONFIGURATION")
        print("=" * 80)
        
        print(f"\n✅ Best Parser: {best_parser} ({parser_avg.get(best_parser, 0):.1f}%)")
        print(f"✅ Best Search Mode: {best_mode} ({mode_avg.get(best_mode, 0):.1f}%)")
        print(f"✅ Best Semantic Weight: {best_sw} ({sw_avg.get(best_sw, 0):.1f}%)")
        print(f"✅ Best K Value: {best_k} ({k_avg.get(best_k, 0):.1f}%)")
        print(f"✅ Best Auto-Translate: {'Enabled' if best_at else 'Disabled'} ({at_avg.get(best_at, 0):.1f}%)")
        
        recommendations = {
            "best_parser": best_parser,
            "best_search_mode": best_mode,
            "best_semantic_weight": best_sw,
            "best_k": best_k,
            "best_auto_translate": best_at,
            "parser_performance": parser_avg,
            "search_mode_performance": mode_avg,
            "semantic_weight_performance": sw_avg,
            "k_performance": k_avg,
            "auto_translate_performance": at_avg,
            "total_tests": len(self.results)
        }
        
        return recommendations
    
    def save_results(self, filename: str = None):
        """Save results to JSON"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rnd_spanish_test_results_{timestamp}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results],
            "analysis": self.analyze_results()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive R&D test for Spanish documents")
    parser.add_argument("--docs-dir", default="docs/testing/clientSpanishDocs", help="Directory with Spanish PDFs")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the API")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    tester = SpanishDocTester(base_url=args.url)
    
    try:
        recommendations = tester.run_comprehensive_test(args.docs_dir)
        
        if args.save:
            tester.save_results()
        
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

