"""
Quick Test for Spanish Documents - Direct execution with immediate results
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://44.221.84.58:8500"

print("=" * 80)
print("🔬 QUICK SPANISH DOCUMENTS TEST")
print("=" * 80)

# Get documents
print("\n📚 Fetching documents...")
try:
    docs_resp = requests.get(f"{BASE_URL}/documents", timeout=60)
    docs_resp.raise_for_status()
    all_docs = docs_resp.json()
    if isinstance(all_docs, dict) and "documents" in all_docs:
        all_docs = all_docs["documents"]
except Exception as e:
    print(f"❌ Error fetching documents: {e}")
    import sys
    sys.exit(1)

spanish_docs = []
for doc in all_docs:
    if isinstance(doc, dict):
        name = doc.get('document_name', '').lower()
        if any(k in name for k in ['vuormar', 'em10', 'em11', 'degasing', 'top seal']) and doc.get('chunks_created', 0) > 0:
            spanish_docs.append(doc)

print(f"✅ Found {len(spanish_docs)} Spanish document(s)")
for doc in spanish_docs[:5]:
    print(f"   - {doc.get('document_name')} ({doc.get('parser_used', 'unknown')}, {doc.get('chunks_created', 0)} chunks)")

if not spanish_docs:
    print("❌ No documents found")
    import sys
    sys.exit(1)
    
    # Test configurations
    configs = [
        {"k": 15, "semantic_weight": 0.2, "search_mode": "hybrid", "auto_translate": True, "response_language": None},
        {"k": 20, "semantic_weight": 0.2, "search_mode": "hybrid", "auto_translate": True, "response_language": None},
        {"k": 20, "semantic_weight": 0.3, "search_mode": "hybrid", "auto_translate": True, "response_language": None},
        {"k": 20, "semantic_weight": 0.4, "search_mode": "hybrid", "auto_translate": True, "response_language": None},
    ]
    
    queries = [
        {"spanish": "¿Dónde está el email y contacto de Vuormar?", "english": "Where is the email and contact of Vuormar?"},
        {"spanish": "¿Cómo aumentar los niveles de aire?", "english": "How to increase air levels?"},
    ]
    
    results = []
    
    print(f"\n🧪 Testing {len(spanish_docs)} docs × {len(configs)} configs × {len(queries)} queries × 2 languages = {len(spanish_docs) * len(configs) * len(queries) * 2} tests")
    print("=" * 80)
    
    for doc in spanish_docs[:3]:
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        
        print(f"\n📄 {doc_name}")
        print("-" * 80)
        
        for config in configs:
            for query_set in queries:
                for lang, query in [("spanish", query_set["spanish"]), ("english", query_set["english"])]:
                    payload = {
                        "question": query,
                        "k": config["k"],
                        "search_mode": config["search_mode"],
                        "use_hybrid_search": True,
                        "semantic_weight": config["semantic_weight"],
                        "auto_translate": config["auto_translate"],
                        "document_id": doc_id,
                        "active_sources": [doc_name]
                    }
                    if config["response_language"]:
                        payload["response_language"] = config["response_language"]
                    
                    try:
                        resp = requests.post(f"{BASE_URL}/query", json=payload, timeout=120)
                        resp.raise_for_status()
                        result = resp.json()
                        
                        answer = result.get('answer', '')
                        citations = result.get('citations', [])
                        sims = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                        avg_sim = sum(sims) / len(sims) if sims else 0
                        
                        quality = 50.0
                        if len(answer) > 100:
                            quality += 20
                        if len(answer) > 200:
                            quality += 15
                        if any(p in answer.lower() for p in ["@", "email", "phone"]):
                            quality += 15
                        
                        results.append({
                            "doc": doc_name,
                            "lang": lang,
                            "query": query[:50],
                            "config": f"k={config['k']},sw={config['semantic_weight']}",
                            "quality": quality,
                            "similarity": avg_sim,
                            "citations": len(citations),
                            "answer_len": len(answer)
                        })
                        
                        print(f"   [{lang.upper()}] Quality: {quality:.1f}%, Sim: {avg_sim:.1f}%, Citations: {len(citations)}")
                        
                    except Exception as e:
                        print(f"   ❌ Error: {str(e)[:50]}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    
    if results:
        by_lang = {}
        by_config = {}
        
        for r in results:
            if r["lang"] not in by_lang:
                by_lang[r["lang"]] = []
            by_lang[r["lang"]].append(r)
            
            if r["config"] not in by_config:
                by_config[r["config"]] = []
            by_config[r["config"]].append(r)
        
        print("\nBy Language:")
        for lang, res in by_lang.items():
            avg_q = sum(r["quality"] for r in res) / len(res)
            avg_s = sum(r["similarity"] for r in res) / len(res)
            print(f"   {lang.upper()}: Quality {avg_q:.1f}%, Similarity {avg_s:.1f}% ({len(res)} tests)")
        
        print("\nBy Configuration:")
        for config, res in sorted(by_config.items(), key=lambda x: sum(r["quality"] for r in x[1]) / len(x[1]), reverse=True):
            avg_q = sum(r["quality"] for r in res) / len(res)
            print(f"   {config}: Quality {avg_q:.1f}% ({len(res)} tests)")
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = f"tests/spanish_docs_quick_results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump({"timestamp": timestamp, "results": results, "summary": {
                "by_language": {lang: {"avg_quality": sum(r["quality"] for r in res) / len(res), "count": len(res)} 
                              for lang, res in by_lang.items()},
                "by_config": {config: {"avg_quality": sum(r["quality"] for r in res) / len(res), "count": len(res)}
                            for config, res in by_config.items()}
            }}, f, indent=2)
        
        print(f"\n💾 Results saved to: {results_file}")
    else:
        print("❌ No results collected")
    
    print("\n✅ TEST COMPLETE")

