"""
Focused R&D Test for Client Spanish Documents
Quick but comprehensive test focusing on key parameter combinations
"""

import os
import sys
import time
import json
import requests
from typing import Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime
import statistics

BASE_URL = "http://44.221.84.58:8500"
DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'testing', 'clientSpanishDocs')

@dataclass
class TestConfig:
    parser: str
    search_mode: str
    semantic_weight: float
    k: int
    auto_translate: bool
    temperature: float
    response_language: str = None

@dataclass
class TestResult:
    config: str
    query: str
    query_language: str
    document_name: str
    parser: str
    citations_count: int
    avg_similarity: float
    response_time: float
    answer_quality: float
    answer_length: int
    has_contact_info: bool = False
    error: str = None

def get_documents():
    """Get all documents from server"""
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "documents" in data:
            return data["documents"]
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"⚠️  Error getting documents: {e}")
        return []

def query_rag(question: str, document_id: str, document_name: str, config: TestConfig) -> Dict:
    """Query RAG system"""
    url = f"{BASE_URL}/query"
    payload = {
        "question": question,
        "k": min(config.k, 20),  # Enforce max k=20
        "search_mode": config.search_mode,
        "use_hybrid_search": (config.search_mode == "hybrid"),
        "semantic_weight": config.semantic_weight,
        "auto_translate": config.auto_translate,
        "temperature": config.temperature,
        "document_id": document_id,
        "active_sources": [document_name]  # Use document name
    }
    if config.response_language:
        payload["response_language"] = config.response_language
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            start = time.time()
            response = requests.post(url, json=payload, timeout=180)
            response.raise_for_status()
            result = response.json()
            result['response_time'] = time.time() - start
            return result
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print(f"      ⏳ Query timeout, retrying...")
                time.sleep(3)
                continue
            return {"error": "Query timeout after retries", "answer": "", "citations": [], "response_time": 0}
        except Exception as e:
            error_msg = str(e)
            if "timeout" in error_msg.lower() and attempt < max_retries - 1:
                time.sleep(3)
                continue
            return {"error": error_msg[:200], "answer": "", "citations": [], "response_time": 0}
    return {"error": "Failed after retries", "answer": "", "citations": [], "response_time": 0}

def evaluate_answer(answer: str, query: str) -> tuple:
    """Evaluate answer quality"""
    if not answer or len(answer.strip()) < 20:
        return 0.0, False
    
    answer_lower = answer.lower()
    
    # Error indicators
    error_phrases = ["i don't know", "i cannot", "no information", "not found", 
                     "check the manual", "no se encuentra", "no disponible"]
    for phrase in error_phrases:
        if phrase in answer_lower:
            return 20.0, False
    
    # Contact info detection
    has_contact = any(p in answer_lower for p in ["@", "email", "correo", "phone", "teléfono", "tel:"])
    
    # Quality score
    score = 50.0
    if len(answer) > 100:
        score += 20
    if len(answer) > 200:
        score += 15
    if len(answer) > 500:
        score += 5
    if has_contact:
        score += 10
    
    return min(100.0, score), has_contact

def main():
    print("=" * 100)
    print("🔬 FOCUSED R&D TEST - CLIENT SPANISH DOCUMENTS")
    print("=" * 100)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Get existing documents
    print("📚 Fetching documents from server...")
    all_docs = get_documents()
    
    # Find Spanish documents
    spanish_docs = []
    for doc in all_docs:
        if isinstance(doc, dict):
            doc_name = doc.get('document_name', '').lower()
            doc_id = doc.get('document_id')
            parser = doc.get('parser_used', 'unknown')
            chunks = doc.get('chunks_created', 0)
            
            if chunks > 0 and any(keyword in doc_name for keyword in ['vuormar', 'em10', 'em11', 'degasing', 'top seal']):
                spanish_docs.append({
                    'document_id': doc_id,
                    'document_name': doc.get('document_name'),
                    'parser': parser,
                    'chunks': chunks
                })
    
    if not spanish_docs:
        print("❌ No Spanish documents found on server")
        return
    
    print(f"✅ Found {len(spanish_docs)} document(s) ready for testing:")
    for doc in spanish_docs:
        print(f"   - {doc['document_name']} ({doc['parser']}, {doc['chunks']} chunks)")
    
    # Focused test configurations - key combinations (k max is 20 per schema)
    test_configs = [
        # Best known configs for cross-language
        TestConfig("pymupdf", "hybrid", 0.2, 15, True, 0.1, None),
        TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None),
        
        # Different semantic weights
        TestConfig("pymupdf", "hybrid", 0.1, 20, True, 0.1, None),
        TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None),
        TestConfig("pymupdf", "hybrid", 0.3, 20, True, 0.1, None),
        TestConfig("pymupdf", "hybrid", 0.4, 20, True, 0.1, None),
        
        # Search modes
        TestConfig("pymupdf", "semantic", 1.0, 20, True, 0.1, None),
        TestConfig("pymupdf", "keyword", 0.0, 20, True, 0.1, None),
        
        # Response language
        TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "Auto"),
        TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "Spanish"),
        TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, "English"),
        
        # Different parsers
        TestConfig("docling", "hybrid", 0.2, 20, True, 0.1, None),
        TestConfig("ocrmypdf", "hybrid", 0.2, 20, True, 0.1, None),
    ]
    
    # Key test queries
    test_queries = [
        {
            "spanish": "¿Dónde está el email y contacto de Vuormar?",
            "english": "Where is the email and contact of Vuormar?",
            "type": "contact"
        },
        {
            "spanish": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
            "english": "How to increase or decrease the levels of air in bag?",
            "type": "procedure"
        },
        {
            "spanish": "¿Qué es el degasado?",
            "english": "What is degassing?",
            "type": "definition"
        },
    ]
    
    results = []
    total_tests = len(spanish_docs) * len(test_configs) * len(test_queries) * 2  # Spanish + English
    test_count = 0
    
    print(f"\n🧪 Running {total_tests} focused tests...")
    print("=" * 100)
    
    for doc in spanish_docs[:3]:  # Test up to 3 documents
        doc_id = doc['document_id']
        doc_name = doc['document_name']
        parser = doc['parser']
        
        print(f"\n📄 Testing: {doc_name} ({parser})")
        print("-" * 100)
        
        # Filter configs for this parser
        relevant_configs = [c for c in test_configs if c.parser == parser or (parser == "pymupdf" and c.parser == "pymupdf")]
        if not relevant_configs:
            relevant_configs = [c for c in test_configs if c.parser == "pymupdf"]
        
        for config in relevant_configs[:10]:  # Limit to 10 configs per doc
            for query_set in test_queries:
                for lang, query in [("spanish", query_set["spanish"]), ("english", query_set["english"])]:
                    test_count += 1
                    print(f"\n[{test_count}/{total_tests}] {lang.upper()}: {query[:60]}...")
                    print(f"   Config: {config.search_mode}, k={config.k}, sw={config.semantic_weight:.2f}")
                    
                    result = query_rag(query, doc_id, doc_name, config)
                    
                    if "error" in result:
                        print(f"   ❌ Error: {result['error'][:100]}")
                        results.append(TestResult(
                            config=f"{config.search_mode}_k{config.k}_sw{config.semantic_weight}",
                            query=query,
                            query_language=lang,
                            document_name=doc_name,
                            parser=parser,
                            citations_count=0,
                            avg_similarity=0.0,
                            response_time=0.0,
                            answer_quality=0.0,
                            answer_length=0,
                            error=result['error']
                        ))
                        continue
                    
                    citations = result.get('citations', [])
                    similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                    avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
                    
                    answer = result.get('answer', '')
                    quality, has_contact = evaluate_answer(answer, query)
                    
                    results.append(TestResult(
                        config=f"{config.search_mode}_k{config.k}_sw{config.semantic_weight}",
                        query=query,
                        query_language=lang,
                        document_name=doc_name,
                        parser=parser,
                        citations_count=len(citations),
                        avg_similarity=avg_sim,
                        response_time=result.get('response_time', 0),
                        answer_quality=quality,
                        answer_length=len(answer),
                        has_contact_info=has_contact
                    ))
                    
                    print(f"   📊 Quality: {quality:.1f}%, Citations: {len(citations)}, Sim: {avg_sim:.1f}%, Time: {result.get('response_time', 0):.2f}s")
                    if has_contact:
                        print(f"   ✅ Contact info detected")
                    
                    time.sleep(0.5)  # Rate limiting
    
    # Analyze results
    print("\n" + "=" * 100)
    print("📊 ANALYSIS")
    print("=" * 100)
    
    valid_results = [r for r in results if not r.error]
    
    if not valid_results:
        print("❌ No valid results")
        return
    
    # Group by dimensions
    by_parser = {}
    by_lang = {}
    by_config = {}
    by_k = {}
    
    for r in valid_results:
        # By parser
        if r.parser not in by_parser:
            by_parser[r.parser] = []
        by_parser[r.parser].append(r)
        
        # By language
        if r.query_language not in by_lang:
            by_lang[r.query_language] = []
        by_lang[r.query_language].append(r)
        
        # By config
        if r.config not in by_config:
            by_config[r.config] = []
        by_config[r.config].append(r)
        
        # By k (extract from config)
        try:
            k_val = int(r.config.split('_k')[1].split('_')[0]) if '_k' in r.config else 0
            if k_val > 0:
                if k_val not in by_k:
                    by_k[k_val] = []
                by_k[k_val].append(r)
        except:
            pass
    
    print(f"\n✅ Analyzed {len(valid_results)} valid test results")
    
    # Best by parser
    print("\n📈 PERFORMANCE BY PARSER:")
    for parser, res in sorted(by_parser.items(), key=lambda x: statistics.mean([r.answer_quality for r in x[1]]), reverse=True):
        avg_quality = statistics.mean([r.answer_quality for r in res])
        avg_sim = statistics.mean([r.avg_similarity for r in res])
        print(f"   {parser.upper()}: Quality {avg_quality:.1f}%, Similarity {avg_sim:.1f}% ({len(res)} tests)")
    
    # Best by language
    print("\n🌐 PERFORMANCE BY QUERY LANGUAGE:")
    for lang, res in sorted(by_lang.items(), key=lambda x: statistics.mean([r.answer_quality for r in x[1]]), reverse=True):
        avg_quality = statistics.mean([r.answer_quality for r in res])
        avg_sim = statistics.mean([r.avg_similarity for r in res])
        contact_rate = sum(1 for r in res if r.has_contact_info) / len(res) * 100
        print(f"   {lang.upper()}: Quality {avg_quality:.1f}%, Similarity {avg_sim:.1f}%, Contact Rate {contact_rate:.1f}% ({len(res)} tests)")
    
    # Best configs
    print("\n🏆 TOP 10 CONFIGURATIONS:")
    best_configs = sorted(by_config.items(), key=lambda x: statistics.mean([r.answer_quality for r in x[1]]), reverse=True)[:10]
    for idx, (config, res) in enumerate(best_configs, 1):
        avg_quality = statistics.mean([r.answer_quality for r in res])
        print(f"   {idx}. {config}: Quality {avg_quality:.1f}% ({len(res)} tests)")
    
    # Best k
    print("\n📊 PERFORMANCE BY K VALUE:")
    for k, res in sorted(by_k.items()):
        if k > 0:
            avg_quality = statistics.mean([r.answer_quality for r in res])
            print(f"   K={k}: Quality {avg_quality:.1f}% ({len(res)} tests)")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"tests/client_spanish_docs_focused_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": timestamp,
            "total_tests": len(results),
            "valid_tests": len(valid_results),
            "results": [asdict(r) for r in results],
            "analysis": {
                "by_parser": {k: {
                    "avg_quality": statistics.mean([r.answer_quality for r in v]),
                    "avg_similarity": statistics.mean([r.avg_similarity for r in v]),
                    "count": len(v)
                } for k, v in by_parser.items()},
                "by_language": {k: {
                    "avg_quality": statistics.mean([r.answer_quality for r in v]),
                    "avg_similarity": statistics.mean([r.avg_similarity for r in v]),
                    "contact_rate": sum(1 for r in v if r.has_contact_info) / len(v) * 100,
                    "count": len(v)
                } for k, v in by_lang.items()},
                "best_configs": [
                    {"config": config, "avg_quality": statistics.mean([r.answer_quality for r in res]), "count": len(res)}
                    for config, res in best_configs
                ]
            }
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to: {results_file}")
    print("\n✅ TEST COMPLETE")

if __name__ == "__main__":
    main()

