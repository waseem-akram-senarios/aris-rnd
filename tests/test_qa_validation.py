"""
QA Validation Test - Verify Configuration and Real-World Performance
Based on QA team's finding that English queries score only 1.71/10
"""

import requests
import json
import time

BASE_URL = "http://44.221.84.58:8500"

def verify_configuration():
    """Check if optimized configuration is actually deployed"""
    print("=" * 80)
    print("🔍 CONFIGURATION VERIFICATION")
    print("=" * 80)
    
    # Test with a known query
    test_query = "Where is the email and contact of Vuormar?"
    
    # Get documents
    response = requests.get(f"{BASE_URL}/documents", timeout=30)
    docs = response.json()
    if isinstance(docs, dict) and "documents" in docs:
        docs = docs["documents"]
    
    # Find VUORMAR document
    vuormar_doc = None
    for doc in docs:
        if hasattr(doc, 'dict'):
            doc = doc.dict()
        if isinstance(doc, dict) and 'VUORMAR' in doc.get('document_name', '').upper():
            vuormar_doc = doc
            break
    
    if not vuormar_doc:
        print("❌ No VUORMAR document found")
        return
    
    doc_id = vuormar_doc.get('document_id')
    print(f"\n📄 Testing with: {vuormar_doc.get('document_name')}")
    print(f"   Document ID: {doc_id}")
    print(f"   Parser: {vuormar_doc.get('parser_used')}")
    print(f"   Chunks: {vuormar_doc.get('chunks_created')}")
    
    # Test different configurations to see what's actually being used
    test_configs = [
        {
            "name": "Optimized Config (Expected)",
            "k": 20,
            "semantic_weight": 0.4,
            "auto_translate": True,
            "search_mode": "hybrid"
        },
        {
            "name": "Old Config (Before Optimization)",
            "k": 15,
            "semantic_weight": 0.7,
            "auto_translate": True,
            "search_mode": "hybrid"
        },
        {
            "name": "No Auto-Translate",
            "k": 20,
            "semantic_weight": 0.4,
            "auto_translate": False,
            "search_mode": "hybrid"
        },
        {
            "name": "Higher K",
            "k": 30,
            "semantic_weight": 0.4,
            "auto_translate": True,
            "search_mode": "hybrid"
        },
        {
            "name": "Very Low Semantic Weight",
            "k": 20,
            "semantic_weight": 0.2,
            "auto_translate": True,
            "search_mode": "hybrid"
        },
    ]
    
    print("\n" + "=" * 80)
    print("🧪 TESTING CONFIGURATIONS")
    print("=" * 80)
    
    results = []
    
    for config in test_configs:
        print(f"\n🔧 Testing: {config['name']}")
        print(f"   k={config['k']}, sw={config['semantic_weight']}, at={config['auto_translate']}")
        
        payload = {
            "question": test_query,
            "k": config['k'],
            "search_mode": config['search_mode'],
            "use_hybrid_search": True,
            "semantic_weight": config['semantic_weight'],
            "auto_translate": config['auto_translate'],
            "temperature": 0.2,
            "document_id": doc_id,
            "active_sources": [doc_id]
        }
        
        try:
            response = requests.post(f"{BASE_URL}/query", json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            
            answer = result.get('answer', '')
            citations = result.get('citations', [])
            
            # Check if answer contains actual information
            answer_lower = answer.lower()
            has_email = 'mattia' in answer_lower or 'stellini' in answer_lower or '@' in answer_lower
            has_error = any(phrase in answer_lower for phrase in ['no information', 'not found', 'does not contain', 'check the manual'])
            
            print(f"   📊 Citations: {len(citations)}")
            print(f"   📧 Has Email Info: {'✅' if has_email else '❌'}")
            print(f"   ⚠️  Has Error Phrase: {'❌' if has_error else '✅'}")
            print(f"   📝 Answer ({len(answer)} chars): {answer[:150]}...")
            
            results.append({
                'config': config['name'],
                'citations': len(citations),
                'has_email': has_email,
                'has_error': has_error,
                'answer_length': len(answer)
            })
            
            time.sleep(1)
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Analysis
    print("\n" + "=" * 80)
    print("📊 ANALYSIS")
    print("=" * 80)
    
    working_configs = [r for r in results if r['has_email'] and not r['has_error']]
    failing_configs = [r for r in results if not r['has_email'] or r['has_error']]
    
    if working_configs:
        print(f"\n✅ Working Configurations ({len(working_configs)}):")
        for r in working_configs:
            print(f"   - {r['config']}")
    
    if failing_configs:
        print(f"\n❌ Failing Configurations ({len(failing_configs)}):")
        for r in failing_configs:
            print(f"   - {r['config']}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("💡 DIAGNOSIS")
    print("=" * 80)
    
    if len(working_configs) == 0:
        print("\n🚨 CRITICAL: ALL configurations failing!")
        print("   Possible causes:")
        print("   1. Document content issue (no email in document)")
        print("   2. Chunking breaking up email information")
        print("   3. Embeddings not matching English query")
        print("   4. Translation failing")
        print("\n   URGENT ACTIONS NEEDED:")
        print("   1. Verify document actually contains email")
        print("   2. Check chunk boundaries")
        print("   3. Increase k even more (try 30-40)")
        print("   4. Use keyword-only search for contact queries")
    elif len(working_configs) < len(test_configs):
        print(f"\n⚠️  Some configurations working ({len(working_configs)}/{len(test_configs)})")
        print("   Best configuration:")
        best = max(working_configs, key=lambda x: x['citations'])
        print(f"   - {best['config']}")
        print(f"   - Citations: {best['citations']}")
    else:
        print("\n✅ All configurations working!")
        print("   Issue may be:")
        print("   1. Different documents in QA testing")
        print("   2. Different queries")
        print("   3. UI not passing correct parameters")

if __name__ == "__main__":
    verify_configuration()

