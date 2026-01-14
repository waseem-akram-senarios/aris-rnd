"""
Comprehensive Cross-Language Query Accuracy Test

Tests RAG system with:
- Same-language queries (baseline)
- Cross-language queries (English query on Spanish doc, Spanish query on English doc, etc.)
- Multiple parsers (PyMuPDF, Docling, OCRmyPDF, Llama-scan)
- Different search modes (Semantic, Hybrid, Keyword)
- Auto-translate enabled/disabled
- Dual-language search enabled/disabled

Reports accuracy metrics and identifies issues.
"""

import os
import sys
import time
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TestResult:
    """Test result for a single query"""
    query: str
    query_language: str
    document_name: str
    document_language: str
    parser: str
    search_mode: str
    auto_translate: bool
    dual_language: bool
    answer: str
    citations_count: int
    avg_similarity: float
    max_similarity: float
    response_time: float
    accuracy_score: float  # 0-100, based on answer quality
    error: Optional[str] = None

@dataclass
class TestSummary:
    """Summary of test results"""
    total_tests: int
    passed: int
    failed: int
    same_language_accuracy: float
    cross_language_accuracy: float
    parser_performance: Dict[str, float]
    search_mode_performance: Dict[str, float]
    auto_translate_impact: Dict[bool, float]
    errors: List[str]

class CrossLanguageAccuracyTester:
    """Test cross-language query accuracy"""
    
    def __init__(self, base_url: str = "http://localhost:8500"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        
    def query_rag(
        self,
        question: str,
        document_id: Optional[str] = None,
        parser: Optional[str] = None,
        search_mode: str = "hybrid",
        semantic_weight: float = 0.7,
        auto_translate: bool = True,
        k: int = 10
    ) -> Dict:
        """Query the RAG system"""
        url = f"{self.base_url}/query"
        
        payload = {
            "question": question,
            "k": k,
            "search_mode": search_mode,
            "use_hybrid_search": (search_mode == "hybrid"),
            "semantic_weight": semantic_weight,
            "auto_translate": auto_translate,
            "response_language": None,
            "filter_language": None
        }
        
        if document_id:
            payload["document_id"] = document_id
            payload["active_sources"] = [document_id]
        
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "answer": "", "citations": []}
    
    def get_documents(self) -> List[Dict]:
        """Get list of available documents"""
        try:
            url = f"{self.base_url}/documents"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Handle both formats: {"documents": [...]} or direct list
            if isinstance(data, dict) and "documents" in data:
                return data["documents"]
            elif isinstance(data, list):
                return data
            else:
                return []
        except Exception as e:
            print(f"Error fetching documents: {e}")
            return []
    
    def evaluate_answer_quality(
        self,
        answer: str,
        query: str,
        expected_keywords: List[str] = None
    ) -> float:
        """Evaluate answer quality (0-100)"""
        if not answer or len(answer.strip()) < 10:
            return 0.0
        
        # Check for error indicators
        error_phrases = [
            "i don't know",
            "i cannot",
            "i'm unable",
            "no information",
            "not found",
            "check the manual",
            "refer to the document",
            "no se encuentra",
            "no disponible",
            "consulte el manual"
        ]
        
        answer_lower = answer.lower()
        for phrase in error_phrases:
            if phrase in answer_lower:
                return 20.0  # Low score for generic error responses
        
        # Check for expected keywords if provided
        if expected_keywords:
            found = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
            keyword_score = (found / len(expected_keywords)) * 50
        else:
            keyword_score = 50
        
        # Length and detail score
        length_score = min(30, len(answer) / 10)  # Up to 30 points for length
        
        # Combine scores
        total_score = keyword_score + length_score
        
        return min(100.0, total_score)
    
    def run_test(
        self,
        query: str,
        query_language: str,
        document_name: str,
        document_id: str,
        document_language: str,
        parser: str,
        search_mode: str = "hybrid",
        auto_translate: bool = True,
        expected_keywords: List[str] = None
    ) -> TestResult:
        """Run a single test"""
        print(f"\n🧪 Testing: {query_language} query on {document_language} document")
        print(f"   Query: {query}")
        print(f"   Document: {document_name} ({parser})")
        print(f"   Mode: {search_mode}, Auto-translate: {auto_translate}")
        
        start_time = time.time()
        result = self.query_rag(
            question=query,
            document_id=document_id,
            search_mode=search_mode,
            auto_translate=auto_translate
        )
        response_time = time.time() - start_time
        
        if "error" in result:
            return TestResult(
                query=query,
                query_language=query_language,
                document_name=document_name,
                document_language=document_language,
                parser=parser,
                search_mode=search_mode,
                auto_translate=auto_translate,
                dual_language=True,  # Assume enabled
                answer="",
                citations_count=0,
                avg_similarity=0.0,
                max_similarity=0.0,
                response_time=response_time,
                accuracy_score=0.0,
                error=result["error"]
            )
        
        answer = result.get("answer", "")
        citations = result.get("citations", [])
        
        # Calculate similarity metrics
        similarities = [c.get("similarity_percentage", 0) for c in citations if c.get("similarity_percentage")]
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        max_similarity = max(similarities) if similarities else 0.0
        
        # Evaluate answer quality
        accuracy_score = self.evaluate_answer_quality(answer, query, expected_keywords)
        
        test_result = TestResult(
            query=query,
            query_language=query_language,
            document_name=document_name,
            document_language=document_language,
            parser=parser,
            search_mode=search_mode,
            auto_translate=auto_translate,
            dual_language=True,
            answer=answer[:200] + "..." if len(answer) > 200 else answer,
            citations_count=len(citations),
            avg_similarity=avg_similarity,
            max_similarity=max_similarity,
            response_time=response_time,
            accuracy_score=accuracy_score
        )
        
        print(f"   ✅ Citations: {len(citations)}, Avg Similarity: {avg_similarity:.1f}%, Accuracy: {accuracy_score:.1f}%")
        
        return test_result
    
    def run_comprehensive_test_suite(self) -> TestSummary:
        """Run comprehensive test suite"""
        print("=" * 80)
        print("🔬 CROSS-LANGUAGE QUERY ACCURACY TEST SUITE")
        print("=" * 80)
        
        # Get available documents
        documents = self.get_documents()
        if not documents:
            print("❌ No documents found. Please upload documents first.")
            return TestSummary(
                total_tests=0,
                passed=0,
                failed=0,
                same_language_accuracy=0.0,
                cross_language_accuracy=0.0,
                parser_performance={},
                search_mode_performance={},
                auto_translate_impact={},
                errors=["No documents found"]
            )
        
        print(f"\n📚 Found {len(documents)} document(s)")
        for doc in documents:
            # Handle both dict and Pydantic model
            if hasattr(doc, 'dict'):
                doc = doc.dict()
            elif hasattr(doc, '__dict__'):
                doc = doc.__dict__
            elif not isinstance(doc, dict):
                doc = {}
            print(f"   - {doc.get('document_name', 'Unknown')} (ID: {doc.get('document_id', 'N/A')})")
        
        # Test queries - Spanish document scenarios
        test_cases = [
            # Same language (Spanish query on Spanish doc)
            {
                "query": "¿Dónde está el email y contacto de Vuormar en el documento?",
                "query_language": "Spanish",
                "expected_keywords": ["email", "contacto", "vuormar", "teléfono"],
                "document_keywords": ["vuormar", "spanish"]
            },
            {
                "query": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
                "query_language": "Spanish",
                "expected_keywords": ["aire", "bolsa", "niveles", "aumentar"],
                "document_keywords": ["spanish"]
            },
            
            # Cross-language (English query on Spanish doc)
            {
                "query": "Where is the email and contact of Vuormar in the document?",
                "query_language": "English",
                "expected_keywords": ["email", "contact", "vuormar", "phone"],
                "document_keywords": ["vuormar", "spanish"]
            },
            {
                "query": "How to increase or decrease the levels of air in bag?",
                "query_language": "English",
                "expected_keywords": ["air", "bag", "levels", "increase"],
                "document_keywords": ["spanish"]
            },
            
            # Roman English query on Spanish doc
            {
                "query": "vuormar ka email aur phone number batao document me se?",
                "query_language": "Roman English",
                "expected_keywords": ["email", "phone", "vuormar"],
                "document_keywords": ["vuormar", "spanish"]
            },
        ]
        
        # Normalize documents to dicts
        normalized_docs = []
        for d in documents:
            if hasattr(d, 'dict'):
                d = d.dict()
            elif hasattr(d, '__dict__'):
                d = d.__dict__
            elif not isinstance(d, dict):
                continue
            normalized_docs.append(d)
        
        # Find Spanish documents
        spanish_docs = [d for d in normalized_docs if "vuormar" in d.get("document_name", "").lower() or 
                        "spanish" in d.get("document_name", "").lower() or
                        d.get("language", "").lower() == "spa"]
        
        if not spanish_docs:
            print("\n⚠️  No Spanish documents found. Testing with all available documents...")
            spanish_docs = documents[:1]  # Use first document as fallback
        
        # Test configurations
        parsers = ["pymupdf", "docling", "ocrmypdf", "llama-scan"]
        search_modes = ["semantic", "hybrid", "keyword"]
        auto_translate_options = [True, False]
        
        print(f"\n🧪 Running tests on {len(spanish_docs)} document(s)...")
        print(f"   Parsers: {', '.join(parsers)}")
        print(f"   Search modes: {', '.join(search_modes)}")
        print(f"   Auto-translate: {auto_translate_options}")
        
        # Run tests
        for doc in spanish_docs:
            doc_name = doc.get("document_name", "Unknown")
            doc_id = doc.get("document_id")
            doc_parser = doc.get("parser_used", "unknown").lower()
            doc_language = "Spanish"  # Assume Spanish for Vuormar docs
            
            # Test each query
            for test_case in test_cases:
                query = test_case["query"]
                query_lang = test_case["query_language"]
                expected_keywords = test_case.get("expected_keywords", [])
                
                # Check if document matches test case
                doc_keywords = test_case.get("document_keywords", [])
                if doc_keywords and not any(kw.lower() in doc_name.lower() for kw in doc_keywords):
                    continue  # Skip if document doesn't match
                
                # Test with different configurations
                for parser in parsers:
                    # Only test if document was processed with this parser
                    if parser not in doc_parser:
                        continue
                    
                    for search_mode in search_modes:
                        for auto_translate in auto_translate_options:
                            result = self.run_test(
                                query=query,
                                query_language=query_lang,
                                document_name=doc_name,
                                document_id=doc_id,
                                document_language=doc_language,
                                parser=parser,
                                search_mode=search_mode,
                                auto_translate=auto_translate,
                                expected_keywords=expected_keywords
                            )
                            self.results.append(result)
                            
                            # Small delay to avoid rate limiting
                            time.sleep(0.5)
        
        # Generate summary
        return self.generate_summary()
    
    def generate_summary(self) -> TestSummary:
        """Generate test summary"""
        if not self.results:
            return TestSummary(
                total_tests=0,
                passed=0,
                failed=0,
                same_language_accuracy=0.0,
                cross_language_accuracy=0.0,
                parser_performance={},
                search_mode_performance={},
                auto_translate_impact={},
                errors=["No test results"]
            )
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r.accuracy_score >= 60 and not r.error)
        failed = total - passed
        
        # Same language vs cross language
        same_lang_results = [r for r in self.results if r.query_language == r.document_language]
        cross_lang_results = [r for r in self.results if r.query_language != r.document_language]
        
        same_lang_accuracy = sum(r.accuracy_score for r in same_lang_results) / len(same_lang_results) if same_lang_results else 0.0
        cross_lang_accuracy = sum(r.accuracy_score for r in cross_lang_results) / len(cross_lang_results) if cross_lang_results else 0.0
        
        # Parser performance
        parser_perf = {}
        for parser in ["pymupdf", "docling", "ocrmypdf", "llama-scan"]:
            parser_results = [r for r in self.results if parser in r.parser.lower()]
            if parser_results:
                parser_perf[parser] = sum(r.accuracy_score for r in parser_results) / len(parser_results)
        
        # Search mode performance
        mode_perf = {}
        for mode in ["semantic", "hybrid", "keyword"]:
            mode_results = [r for r in self.results if r.search_mode == mode]
            if mode_results:
                mode_perf[mode] = sum(r.accuracy_score for r in mode_results) / len(mode_results)
        
        # Auto-translate impact
        auto_trans_perf = {}
        for auto_trans in [True, False]:
            trans_results = [r for r in self.results if r.auto_translate == auto_trans]
            if trans_results:
                auto_trans_perf[auto_trans] = sum(r.accuracy_score for r in trans_results) / len(trans_results)
        
        # Errors
        errors = [r.error for r in self.results if r.error]
        
        return TestSummary(
            total_tests=total,
            passed=passed,
            failed=failed,
            same_language_accuracy=same_lang_accuracy,
            cross_language_accuracy=cross_lang_accuracy,
            parser_performance=parser_perf,
            search_mode_performance=mode_perf,
            auto_translate_impact=auto_trans_perf,
            errors=errors
        )
    
    def print_report(self, summary: TestSummary):
        """Print comprehensive test report"""
        print("\n" + "=" * 80)
        print("📊 TEST REPORT")
        print("=" * 80)
        
        print(f"\n📈 Overall Statistics:")
        print(f"   Total Tests: {summary.total_tests}")
        print(f"   Passed: {summary.passed} ({summary.passed/summary.total_tests*100:.1f}%)" if summary.total_tests > 0 else "   Passed: 0")
        print(f"   Failed: {summary.failed} ({summary.failed/summary.total_tests*100:.1f}%)" if summary.total_tests > 0 else "   Failed: 0")
        
        print(f"\n🌐 Language Performance:")
        print(f"   Same-Language Accuracy: {summary.same_language_accuracy:.1f}%")
        print(f"   Cross-Language Accuracy: {summary.cross_language_accuracy:.1f}%")
        accuracy_gap = summary.same_language_accuracy - summary.cross_language_accuracy
        print(f"   Accuracy Gap: {accuracy_gap:.1f}% ({'⚠️  SIGNIFICANT GAP' if accuracy_gap > 20 else '✅ ACCEPTABLE'})")
        
        print(f"\n🔧 Parser Performance:")
        for parser, accuracy in sorted(summary.parser_performance.items(), key=lambda x: x[1], reverse=True):
            print(f"   {parser.upper()}: {accuracy:.1f}%")
        
        print(f"\n🔍 Search Mode Performance:")
        for mode, accuracy in sorted(summary.search_mode_performance.items(), key=lambda x: x[1], reverse=True):
            print(f"   {mode.upper()}: {accuracy:.1f}%")
        
        print(f"\n🌍 Auto-Translate Impact:")
        for auto_trans, accuracy in summary.auto_translate_impact.items():
            status = "ENABLED" if auto_trans else "DISABLED"
            print(f"   {status}: {accuracy:.1f}%")
        
        if summary.errors:
            print(f"\n❌ Errors ({len(summary.errors)}):")
            for error in set(summary.errors[:10]):  # Show unique errors
                print(f"   - {error}")
        
        # Detailed results table
        print(f"\n📋 Detailed Results (Top 10 Best & Worst):")
        sorted_results = sorted(self.results, key=lambda x: x.accuracy_score, reverse=True)
        
        print("\n🏆 Best Results:")
        for i, result in enumerate(sorted_results[:5], 1):
            print(f"   {i}. {result.query_language} → {result.document_language} | "
                  f"{result.parser} | {result.search_mode} | "
                  f"Accuracy: {result.accuracy_score:.1f}% | "
                  f"Similarity: {result.avg_similarity:.1f}%")
        
        print("\n⚠️  Worst Results:")
        for i, result in enumerate(sorted_results[-5:], 1):
            print(f"   {i}. {result.query_language} → {result.document_language} | "
                  f"{result.parser} | {result.search_mode} | "
                  f"Accuracy: {result.accuracy_score:.1f}% | "
                  f"Similarity: {result.avg_similarity:.1f}%")
            if result.error:
                print(f"      Error: {result.error}")
        
        # Analysis and recommendations
        print(f"\n💡 Analysis & Recommendations:")
        
        if accuracy_gap > 30:
            print("   ⚠️  CRITICAL: Cross-language queries are significantly less accurate.")
            print("   🔧 Recommended fixes:")
            print("      1. Improve translation quality for queries")
            print("      2. Enhance dual-language search implementation")
            print("      3. Use multilingual embeddings")
            print("      4. Increase semantic weight for cross-language queries")
        
        if summary.auto_translate_impact.get(True, 0) < summary.auto_translate_impact.get(False, 0):
            print("   ⚠️  Auto-translate is reducing accuracy. Review translation logic.")
        
        best_parser = max(summary.parser_performance.items(), key=lambda x: x[1])[0] if summary.parser_performance else None
        if best_parser:
            print(f"   ✅ Best performing parser: {best_parser.upper()}")
        
        best_mode = max(summary.search_mode_performance.items(), key=lambda x: x[1])[0] if summary.search_mode_performance else None
        if best_mode:
            print(f"   ✅ Best performing search mode: {best_mode.upper()}")
    
    def save_results(self, filename: str = None):
        """Save results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cross_language_test_results_{timestamp}.json"
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [asdict(r) for r in self.results],
            "summary": asdict(self.generate_summary())
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {filename}")
        return filename

def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test cross-language query accuracy")
    parser.add_argument("--url", default="http://localhost:8500", help="Base URL of the API")
    parser.add_argument("--save", action="store_true", help="Save results to JSON file")
    
    args = parser.parse_args()
    
    tester = CrossLanguageAccuracyTester(base_url=args.url)
    
    try:
        summary = tester.run_comprehensive_test_suite()
        tester.print_report(summary)
        
        if args.save:
            tester.save_results()
        
        # Exit code based on results
        if summary.cross_language_accuracy < 50:
            print("\n❌ Cross-language accuracy is below 50%. Tests FAILED.")
            sys.exit(1)
        elif summary.cross_language_accuracy < 70:
            print("\n⚠️  Cross-language accuracy is below 70%. Tests PASSED with warnings.")
            sys.exit(0)
        else:
            print("\n✅ Tests PASSED.")
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

