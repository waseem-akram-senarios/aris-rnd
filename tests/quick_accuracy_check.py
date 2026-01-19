import os
import requests
import json
import time

BASE_URL = "http://44.221.84.58:8500"

def query_rag(question, document_name=None, document_id=None):
    url = f"{BASE_URL}/query"
    payload = {
        "question": question,
        "search_mode": "hybrid",
        "semantic_weight": 0.3, # Using the new default optimized for cross-language
        "k": 6,
        "auto_translate": True,
        "use_agentic_rag": True
    }
    # Use document_name for active_sources as index map is keyed by name
    if document_name:
        payload["active_sources"] = [document_name]
    if document_id:
        payload["document_id"] = document_id
        
    try:
        response = requests.post(url, json=payload, timeout=60)
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def evaluate_accuracy(result, expected_keywords):
    answer = result.get('answer', '').lower()
    citations = result.get('citations', [])
    
    found_keywords = [kw for kw in expected_keywords if kw.lower() in answer]
    keyword_score = (len(found_keywords) / len(expected_keywords)) * 100 if expected_keywords else 100
    
    # Check for citations
    citation_score = 100 if len(citations) > 0 else 0
    
    # Check for page numbers in citations (quality of metadata)
    has_pages = all(c.get('page') is not None and c.get('page') > 0 for c in citations)
    page_score = 100 if has_pages and len(citations) > 0 else 0
    
    return {
        "keyword_score": keyword_score,
        "citation_score": citation_score,
        "page_score": page_score,
        "found_keywords": found_keywords,
        "num_citations": len(citations)
    }

def main():
    print("🔍 RAG Accuracy Verification (Focused Test)")
    
    # 1. Get sample document
    try:
        docs_response = requests.get(f"{BASE_URL}/documents").json()
        if isinstance(docs_response, dict) and "documents" in docs_response:
            docs = docs_response["documents"]
        else:
            docs = docs_response
            
        if not docs or not isinstance(docs, list):
            print(f"❌ No valid documents list found. Response: {str(docs_response)[:100]}")
            return
        
        # Look for target documents - specifically picking the one we know has chunks
        target_doc_id = "01ca1eca-1d7a-497e-9b07-f34b123d6fca" # VUORMAR(spa).pdf with 100 chunks
        target_doc_name = "VUORMAR(spa).pdf"
            
        print(f"� Testing accuracy on document: {target_doc_name} (ID: {target_doc_id})")
        
        # 2. Run Test Queries
        test_queries = [
            {
                "query": "What is the email and contact of Vuormar?",
                "expected": ["email", "vuormar", "com", "contact"]
            },
            {
                "query": "¿Cuál es el procedimiento de degasado?",
                "expected": ["degasado", "aire", "bolsa", "presión"]
            }
        ]
        
        results = []
        for tq in test_queries:
            print(f"\n❓ Query: {tq['query']}")
            
            # Try Global Search First (No document_id)
            print("  🌐 Trying Global Search...")
            res_global = query_rag(tq['query'])
            eval_global = evaluate_accuracy(res_global, tq['expected'])
            print(f"    Global Citations: {eval_global['num_citations']} | Score: {eval_global['keyword_score']:.1f}%")
            if eval_global['num_citations'] > 0:
                print(f"    Sources found: {list(set([c.get('source') for c in res_global.get('citations', [])]))}")
            
            # Try Document-Specific Search
            print(f"  📄 Trying Document Search: {target_doc_name}...")
            res_doc = query_rag(tq['query'], document_name=target_doc_name, document_id=target_doc_id)

            eval_doc = evaluate_accuracy(res_doc, tq['expected'])
            print(f"    Doc-Specific Citations: {eval_doc['num_citations']} | Score: {eval_doc['keyword_score']:.1f}%")
            
            # Log the answer briefly
            if res_doc.get('answer'):
                print(f"    Answer: {res_doc['answer'][:150]}...")
            
            results.append(eval_doc)
            
        # 3. Summary
        if results:
            avg_keyword = sum(r['keyword_score'] for r in results) / len(results)
            print("\n" + "="*50)
            print("🎯 ACCURACY SUMMARY (Document Specific)")
            print("="*50)
            print(f"Overall Accuracy: {avg_keyword:.1f}%")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
