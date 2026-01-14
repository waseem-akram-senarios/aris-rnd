"""
Quick R&D test to find best parameters for Spanish documents
Tests key parameter combinations to quickly identify optimal defaults
"""

import requests
import time
import json
from typing import Dict, List
from dataclasses import dataclass
import statistics

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
    
    error_phrases = ["i don't know", "no information", "not found", "check the manual", "no se encuentra"]
    answer_lower = answer.lower()
    
    for phrase in error_phrases:
        if phrase in answer_lower:
            return 20.0
    
    score = 50.0
    if keywords:
        found = sum(1 for kw in keywords if kw.lower() in answer_lower)
        score += (found / len(keywords)) * 30
    
    if len(answer) > 100:
        score += 10
    if len(answer) > 200:
        score += 10
    
    return min(100.0, score)

def main():
    print("=" * 80)
    print("🔬 QUICK R&D PARAMETER TEST")
    print("=" * 80)
    
    # Get Spanish documents
    docs = get_documents()
    spanish_docs = []
    for doc in docs:
        if hasattr(doc, 'dict'):
            doc = doc.dict()
        elif hasattr(doc, '__dict__'):
            doc = doc.__dict__
        
        if isinstance(doc, dict):
            doc_name = doc.get('document_name', '').lower()
            if 'vuormar' in doc_name or 'em10' in doc_name or 'em11' in doc_name:
                spanish_docs.append(doc)
    
    if not spanish_docs:
        print("❌ No Spanish documents found")
        return
    
    print(f"\n📚 Found {len(spanish_docs)} Spanish document(s)")
    for doc in spanish_docs[:3]:
        print(f"   - {doc.get('document_name')} (Parser: {doc.get('parser_used', 'unknown')})")
    
    # Test configurations - key parameter combinations
    test_configs = [
        # Semantic weight variations (hybrid mode)
        TestConfig("hybrid", 0.7, 20, True),  # Default
        TestConfig("hybrid", 0.5, 20, True),  # Balanced
        TestConfig("hybrid", 0.4, 20, True),  # Keyword-focused (cross-language optimized)
        TestConfig("hybrid", 0.3, 20, True),  # Very keyword-focused
        
        # K value variations (with best semantic weight)
        TestConfig("hybrid", 0.4, 10, True),
        TestConfig("hybrid", 0.4, 15, True),
        TestConfig("hybrid", 0.4, 20, True),
        TestConfig("hybrid", 0.4, 25, True),
        
        # Search mode variations
        TestConfig("semantic", 1.0, 20, True),
        TestConfig("keyword", 0.0, 20, True),
        TestConfig("hybrid", 0.4, 20, True),
        
        # Auto-translate on/off
        TestConfig("hybrid", 0.4, 20, True),
        TestConfig("hybrid", 0.4, 20, False),
    ]
    
    # Test queries
    test_queries = [
        {
            "spanish": "¿Dónde está el email y contacto de Vuormar?",
            "english": "Where is the email and contact of Vuormar?",
            "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono", "mattia"]
        },
        {
            "spanish": "¿Cómo aumentar o disminuir los niveles de aire?",
            "english": "How to increase or decrease the air levels?",
            "keywords": ["aire", "air", "aumentar", "increase", "disminuir", "decrease"]
        }
    ]
    
    # Run tests
    results = []
    
    for doc in spanish_docs[:2]:  # Test first 2 documents
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        
        print(f"\n📄 Testing: {doc_name}")
        print("-" * 80)
        
        for config in test_configs:
            for query_set in test_queries:
                # Test both Spanish and English
                for lang, query in [("Spanish", query_set["spanish"]), ("English", query_set["english"])]:
                    result = query_with_config(query, doc_id, config)
                    
                    if "error" in result:
                        continue
                    
                    citations = result.get('citations', [])
                    similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                    avg_sim = sum(similarities) / len(similarities) if similarities else 0
                    
                    answer = result.get('answer', '')
                    quality = evaluate_answer(answer, query_set['keywords'])
                    
                    results.append({
                        'config': config,
                        'query_lang': lang,
                        'citations': len(citations),
                        'avg_similarity': avg_sim,
                        'quality': quality,
                        'response_time': result.get('response_time', 0)
                    })
                    
                    print(f"   {config.search_mode:8s} sw={config.semantic_weight:.1f} k={config.k:2d} at={str(config.auto_translate):5s} | "
                          f"{lang:7s} | Cites:{len(citations):2d} Sim:{avg_sim:5.1f}% Quality:{quality:5.1f}%")
                    
                    time.sleep(0.5)
    
    # Analyze results
    print("\n" + "=" * 80)
    print("📊 ANALYSIS")
    print("=" * 80)
    
    # Group by parameter
    by_semantic_weight = {}
    by_k = {}
    by_search_mode = {}
    by_auto_translate = {}
    
    for r in results:
        config = r['config']
        quality = r['quality']
        
        # By semantic weight
        sw = config.semantic_weight
        if sw not in by_semantic_weight:
            by_semantic_weight[sw] = []
        by_semantic_weight[sw].append(quality)
        
        # By k
        k = config.k
        if k not in by_k:
            by_k[k] = []
        by_k[k].append(quality)
        
        # By search mode
        mode = config.search_mode
        if mode not in by_search_mode:
            by_search_mode[mode] = []
        by_search_mode[mode].append(quality)
        
        # By auto_translate
        at = config.auto_translate
        if at not in by_auto_translate:
            by_auto_translate[at] = []
        by_auto_translate[at].append(quality)
    
    print("\n⚖️  SEMANTIC WEIGHT (Hybrid Mode):")
    sw_results = []
    for sw in sorted(by_semantic_weight.keys(), reverse=True):
        qualities = by_semantic_weight[sw]
        avg = statistics.mean(qualities)
        sw_results.append((sw, avg))
        print(f"   {sw:.1f}: {avg:5.1f}% (tests: {len(qualities)})")
    
    print("\n📏 K VALUE:")
    k_results = []
    for k in sorted(by_k.keys()):
        qualities = by_k[k]
        avg = statistics.mean(qualities)
        k_results.append((k, avg))
        print(f"   {k:2d}: {avg:5.1f}% (tests: {len(qualities)})")
    
    print("\n🔍 SEARCH MODE:")
    mode_results = []
    for mode in by_search_mode.keys():
        qualities = by_search_mode[mode]
        avg = statistics.mean(qualities)
        mode_results.append((mode, avg))
        print(f"   {mode:10s}: {avg:5.1f}% (tests: {len(qualities)})")
    
    print("\n🌐 AUTO-TRANSLATE:")
    at_results = []
    for at in [True, False]:
        if at in by_auto_translate:
            qualities = by_auto_translate[at]
            avg = statistics.mean(qualities)
            at_results.append((at, avg))
            status = "Enabled" if at else "Disabled"
            print(f"   {status:10s}: {avg:5.1f}% (tests: {len(qualities)})")
    
    # Find best
    best_sw = max(sw_results, key=lambda x: x[1])[0]
    best_k = max(k_results, key=lambda x: x[1])[0]
    best_mode = max(mode_results, key=lambda x: x[1])[0]
    best_at = max(at_results, key=lambda x: x[1])[0] if at_results else True
    
    print("\n" + "=" * 80)
    print("🏆 RECOMMENDED DEFAULTS")
    print("=" * 80)
    
    print(f"\n✅ Search Mode: {best_mode}")
    print(f"✅ Semantic Weight: {best_sw}")
    print(f"✅ K Value: {best_k}")
    print(f"✅ Auto-Translate: {'Enabled' if best_at else 'Disabled'}")
    
    # Save recommendations
    recommendations = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "best_search_mode": best_mode,
        "best_semantic_weight": best_sw,
        "best_k": best_k,
        "best_auto_translate": best_at,
        "semantic_weight_performance": {str(k): v for k, v in sw_results},
        "k_performance": {str(k): v for k, v in k_results},
        "search_mode_performance": {k: v for k, v in mode_results},
        "total_tests": len(results)
    }
    
    filename = f"rnd_recommendations_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    print(f"\n💾 Recommendations saved to: {filename}")
    print("\n✅ Test complete!")

if __name__ == "__main__":
    main()

