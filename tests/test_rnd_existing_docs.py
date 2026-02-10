"""
R&D Test using existing uploaded documents
Tests parameters on already-uploaded Spanish documents to find optimal defaults
"""

import requests
import time
import json
import statistics
from typing import Dict, List
from dataclasses import dataclass

BASE_URL = "http://44.221.84.58:8500"

@dataclass
class TestConfig:
    search_mode: str
    semantic_weight: float
    k: int
    auto_translate: bool

def get_documents():
    """Get available documents"""
    response = requests.get(f"{BASE_URL}/documents", timeout=30)
    data = response.json()
    if isinstance(data, dict) and "documents" in data:
        return data["documents"]
    return data if isinstance(data, list) else []

def query_with_config(question: str, document_id: str, config: TestConfig) -> Dict:
    """Query with specific configuration"""
    payload = {
        "question": question,
        "k": config.k,
        "search_mode": config.search_mode,
        "use_hybrid_search": (config.search_mode == "hybrid"),
        "semantic_weight": config.semantic_weight,
        "auto_translate": config.auto_translate,
        "temperature": 0.2,
        "document_id": document_id,
        "active_sources": [document_id]
    }
    
    try:
        start = time.time()
        response = requests.post(f"{BASE_URL}/query", json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        result['response_time'] = time.time() - start
        return result
    except Exception as e:
        return {"error": str(e), "answer": "", "citations": [], "response_time": 0}

def evaluate_answer(answer: str, keywords: List[str]) -> float:
    """Evaluate answer quality"""
    if not answer or len(answer.strip()) < 20:
        return 0.0
    
    error_phrases = ["i don't know", "no information", "not found", "check the manual", "no se encuentra", "no disponible", "consulte el manual"]
    answer_lower = answer.lower()
    
    for phrase in error_phrases:
        if phrase in answer_lower:
            return 25.0
    
    score = 50.0
    if keywords:
        found = sum(1 for kw in keywords if kw.lower() in answer_lower)
        score += (found / len(keywords)) * 35
    
    if len(answer) > 100:
        score += 8
    if len(answer) > 200:
        score += 7
    
    return min(100.0, score)

def main():
    print("=" * 80)
    print("🔬 R&D PARAMETER TEST - EXISTING DOCUMENTS")
    print("=" * 80)
    
    # Get documents
    docs = get_documents()
    
    # Find Spanish documents (VUORMAR, EM10, EM11)
    spanish_docs = []
    for doc in docs:
        if hasattr(doc, 'dict'):
            doc = doc.dict()
        elif hasattr(doc, '__dict__'):
            doc = doc.__dict__
        
        if isinstance(doc, dict):
            doc_name = doc.get('document_name', '').lower() if doc.get('document_name') else ''
            parser_used = doc.get('parser_used', 'unknown')
            parser = parser_used.lower() if parser_used else 'unknown'
            if 'vuormar' in doc_name or 'em10' in doc_name or 'em11' in doc_name:
                spanish_docs.append({
                    'document_id': doc.get('document_id'),
                    'document_name': doc.get('document_name'),
                    'parser': parser,
                    'chunks': doc.get('chunks_created', 0)
                })
    
    if not spanish_docs:
        print("❌ No Spanish documents found")
        return
    
    print(f"\n📚 Found {len(spanish_docs)} Spanish document variant(s)")
    
    # Group by parser
    by_parser = {}
    for doc in spanish_docs:
        parser = doc['parser']
        if parser not in by_parser:
            by_parser[parser] = []
        by_parser[parser].append(doc)
    
    print(f"\n📊 Documents by parser:")
    for parser, docs_list in by_parser.items():
        print(f"   {parser:12s}: {len(docs_list)} document(s)")
    
    # Select test documents (one per parser if possible)
    test_docs = []
    for parser in ['pymupdf', 'docling', 'ocrmypdf', 'llama-scan']:
        if parser in by_parser:
            test_docs.append(by_parser[parser][0])
    
    if not test_docs and spanish_docs:
        test_docs = spanish_docs[:4]
    
    print(f"\n📄 Testing with {len(test_docs)} document(s):")
    for doc in test_docs:
        print(f"   - {doc['document_name']} ({doc['parser']}, {doc['chunks']} chunks)")
    
    # Test configurations
    test_configs = [
        # Semantic weight variations (hybrid mode)
        TestConfig("hybrid", 0.7, 20, True),  # Default
        TestConfig("hybrid", 0.5, 20, True),  # Balanced
        TestConfig("hybrid", 0.4, 20, True),  # Cross-language optimized
        TestConfig("hybrid", 0.3, 20, True),  # Very keyword-focused
        
        # K value variations
        TestConfig("hybrid", 0.4, 10, True),
        TestConfig("hybrid", 0.4, 15, True),
        TestConfig("hybrid", 0.4, 20, True),
        TestConfig("hybrid", 0.4, 25, True),
        TestConfig("hybrid", 0.4, 30, True),
        
        # Search mode variations
        TestConfig("semantic", 1.0, 20, True),
        TestConfig("keyword", 0.0, 20, True),
        TestConfig("hybrid", 0.4, 20, True),
        
        # Auto-translate variations
        TestConfig("hybrid", 0.4, 20, True),
        TestConfig("hybrid", 0.4, 20, False),
    ]
    
    # Test queries
    test_queries = [
        {
            "spanish": "¿Dónde está el email y contacto de Vuormar?",
            "english": "Where is the email and contact of Vuormar?",
            "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono", "mattia", "stellini"]
        },
        {
            "spanish": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
            "english": "How to increase or decrease the air levels in the bag?",
            "keywords": ["aire", "air", "bolsa", "bag", "aumentar", "increase", "disminuir", "decrease", "nivel"]
        },
        {
            "spanish": "¿Cuál es el procedimiento de mantenimiento?",
            "english": "What is the maintenance procedure?",
            "keywords": ["mantenimiento", "maintenance", "procedimiento", "procedure", "limpieza", "cleaning"]
        }
    ]
    
    # Run tests
    print("\n" + "=" * 80)
    print("🧪 RUNNING TESTS")
    print("=" * 80)
    
    results = []
    test_count = 0
    
    for doc in test_docs:
        doc_id = doc['document_id']
        doc_name = doc['document_name']
        parser = doc['parser']
        
        print(f"\n📄 {doc_name} ({parser})")
        print("-" * 80)
        
        for config in test_configs:
            for query_set in test_queries[:2]:  # Test first 2 query types
                # Test both Spanish and English
                for lang, query in [("Spanish", query_set["spanish"]), ("English", query_set["english"])]:
                    result = query_with_config(query, doc_id, config)
                    
                    if "error" in result:
                        print(f"   ❌ Error: {result['error']}")
                        continue
                    
                    citations = result.get('citations', [])
                    similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                    avg_sim = sum(similarities) / len(similarities) if similarities else 0
                    max_sim = max(similarities) if similarities else 0
                    
                    answer = result.get('answer', '')
                    quality = evaluate_answer(answer, query_set['keywords'])
                    
                    results.append({
                        'parser': parser,
                        'config': config,
                        'query_lang': lang,
                        'citations': len(citations),
                        'avg_similarity': avg_sim,
                        'max_similarity': max_sim,
                        'quality': quality,
                        'response_time': result.get('response_time', 0),
                        'has_keywords': any(kw.lower() in answer.lower() for kw in query_set['keywords'])
                    })
                    
                    test_count += 1
                    status = "✅" if quality >= 60 else "⚠️" if quality >= 40 else "❌"
                    print(f"   {status} {config.search_mode:8s} sw={config.semantic_weight:.1f} k={config.k:2d} {lang:7s} | "
                          f"C:{len(citations):2d} S:{avg_sim:5.1f}% Q:{quality:5.1f}%")
                    
                    time.sleep(0.3)
    
    print(f"\n✅ Completed {test_count} tests")
    
    # Analyze results
    print("\n" + "=" * 80)
    print("📊 DETAILED ANALYSIS")
    print("=" * 80)
    
    # By parser
    by_parser_results = {}
    for r in results:
        parser = r['parser']
        if parser not in by_parser_results:
            by_parser_results[parser] = []
        by_parser_results[parser].append(r['quality'])
    
    print("\n🔧 PARSER PERFORMANCE:")
    parser_avgs = {}
    for parser in sorted(by_parser_results.keys()):
        qualities = by_parser_results[parser]
        avg = statistics.mean(qualities)
        parser_avgs[parser] = avg
        print(f"   {parser:12s}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # By semantic weight
    by_sw = {}
    for r in results:
        sw = r['config'].semantic_weight
        if sw not in by_sw:
            by_sw[sw] = []
        by_sw[sw].append(r['quality'])
    
    print("\n⚖️  SEMANTIC WEIGHT:")
    sw_avgs = []
    for sw in sorted(by_sw.keys(), reverse=True):
        qualities = by_sw[sw]
        avg = statistics.mean(qualities)
        sw_avgs.append((sw, avg))
        print(f"   {sw:.1f}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # By k value
    by_k = {}
    for r in results:
        k = r['config'].k
        if k not in by_k:
            by_k[k] = []
        by_k[k].append(r['quality'])
    
    print("\n📏 K VALUE:")
    k_avgs = []
    for k in sorted(by_k.keys()):
        qualities = by_k[k]
        avg = statistics.mean(qualities)
        k_avgs.append((k, avg))
        print(f"   {k:2d}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # By search mode
    by_mode = {}
    for r in results:
        mode = r['config'].search_mode
        if mode not in by_mode:
            by_mode[mode] = []
        by_mode[mode].append(r['quality'])
    
    print("\n🔍 SEARCH MODE:")
    mode_avgs = []
    for mode in sorted(by_mode.keys()):
        qualities = by_mode[mode]
        avg = statistics.mean(qualities)
        mode_avgs.append((mode, avg))
        print(f"   {mode:10s}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # By auto-translate
    by_at = {}
    for r in results:
        at = r['config'].auto_translate
        if at not in by_at:
            by_at[at] = []
        by_at[at].append(r['quality'])
    
    print("\n🌐 AUTO-TRANSLATE:")
    at_avgs = []
    for at in [True, False]:
        if at in by_at:
            qualities = by_at[at]
            avg = statistics.mean(qualities)
            at_avgs.append((at, avg))
            status = "Enabled" if at else "Disabled"
            print(f"   {status:10s}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # By language
    by_lang = {}
    for r in results:
        lang = r['query_lang']
        if lang not in by_lang:
            by_lang[lang] = []
        by_lang[lang].append(r['quality'])
    
    print("\n🌍 QUERY LANGUAGE:")
    for lang in sorted(by_lang.keys()):
        qualities = by_lang[lang]
        avg = statistics.mean(qualities)
        print(f"   {lang:10s}: {avg:5.1f}% ({len(qualities)} tests)")
    
    # Find best configuration
    best_parser = max(parser_avgs.items(), key=lambda x: x[1])[0] if parser_avgs else "pymupdf"
    best_sw = max(sw_avgs, key=lambda x: x[1])[0] if sw_avgs else 0.4
    best_k = max(k_avgs, key=lambda x: x[1])[0] if k_avgs else 20
    best_mode = max(mode_avgs, key=lambda x: x[1])[0] if mode_avgs else "hybrid"
    best_at = max(at_avgs, key=lambda x: x[1])[0] if at_avgs else True
    
    print("\n" + "=" * 80)
    print("🏆 RECOMMENDED DEFAULT CONFIGURATION")
    print("=" * 80)
    
    print(f"\n✅ Best Parser:         {best_parser} ({parser_avgs.get(best_parser, 0):.1f}%)")
    print(f"✅ Best Search Mode:    {best_mode} ({dict(mode_avgs).get(best_mode, 0):.1f}%)")
    print(f"✅ Best Semantic Weight: {best_sw} ({dict(sw_avgs).get(best_sw, 0):.1f}%)")
    print(f"✅ Best K Value:        {best_k} ({dict(k_avgs).get(best_k, 0):.1f}%)")
    print(f"✅ Best Auto-Translate: {'Enabled' if best_at else 'Disabled'} ({dict(at_avgs).get(best_at, 0):.1f}%)")
    
    # Configuration code
    print("\n📝 Configuration to update in shared/config/settings.py:")
    print("-" * 80)
    print(f"""
# Optimal settings for cross-language Spanish documents (based on R&D testing)
DEFAULT_SEARCH_MODE: str = '{best_mode}'
DEFAULT_RETRIEVAL_K: int = {best_k}
DEFAULT_SEMANTIC_WEIGHT: float = {best_sw}  # For cross-language queries
DEFAULT_KEYWORD_WEIGHT: float = {1.0 - best_sw}
# Auto-translate: {'Enabled' if best_at else 'Disabled'} in UI by default
    """)
    
    # Save results
    recommendations = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_tests": test_count,
        "best_parser": best_parser,
        "best_search_mode": best_mode,
        "best_semantic_weight": best_sw,
        "best_k": best_k,
        "best_auto_translate": best_at,
        "parser_performance": parser_avgs,
        "semantic_weight_performance": {str(k): v for k, v in sw_avgs},
        "k_performance": {str(k): v for k, v in k_avgs},
        "search_mode_performance": {k: v for k, v in mode_avgs},
        "auto_translate_performance": {str(k): v for k, v in at_avgs},
        "language_performance": {k: statistics.mean(v) for k, v in by_lang.items()}
    }
    
    filename = f"rnd_recommendations_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    print(f"\n💾 Results saved to: {filename}")
    print("\n✅ R&D Test Complete!")

if __name__ == "__main__":
    main()

