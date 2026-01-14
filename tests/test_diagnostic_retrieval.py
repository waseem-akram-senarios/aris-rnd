"""
Diagnostic test to see what chunks are being retrieved
"""
import requests
import json

BASE_URL = "http://44.221.84.58:8500"

def query_rag_detailed(question, document_id, k=20):
    """Query with more chunks and show details"""
    url = f"{BASE_URL}/query"
    payload = {
        "question": question,
        "k": k,  # Get more chunks
        "search_mode": "hybrid",
        "use_hybrid_search": True,
        "semantic_weight": 0.4,
        "auto_translate": True,
        "document_id": document_id,
        "active_sources": [document_id]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "answer": "", "citations": []}

def main():
    print("=" * 80)
    print("🔍 DIAGNOSTIC RETRIEVAL TEST")
    print("=" * 80)
    
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
        elif hasattr(doc, '__dict__'):
            doc = doc.__dict__
        
        if isinstance(doc, dict) and 'VUORMAR.pdf' in doc.get('document_name', ''):
            vuormar_doc = doc
            break
    
    if not vuormar_doc:
        print("❌ VUORMAR.pdf not found")
        return
    
    doc_id = vuormar_doc.get('document_id')
    print(f"\n📄 Testing with: {vuormar_doc.get('document_name')} (ID: {doc_id})")
    print(f"   Parser: {vuormar_doc.get('parser_used', 'unknown')}")
    print(f"   Chunks: {vuormar_doc.get('chunks_created', 0)}")
    
    # Test queries
    test_queries = [
        {
            "query": "Where is the email and contact of Vuormar?",
            "lang": "English",
            "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono"]
        },
        {
            "query": "¿Dónde está el email y contacto de Vuormar?",
            "lang": "Spanish",
            "keywords": ["email", "correo", "contact", "contacto", "phone", "teléfono"]
        }
    ]
    
    for test in test_queries:
        print("\n" + "=" * 80)
        print(f"🔍 Query ({test['lang']}): {test['query']}")
        print("=" * 80)
        
        result = query_rag_detailed(test['query'], doc_id, k=20)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            continue
        
        citations = result.get('citations', [])
        print(f"\n📊 Retrieved {len(citations)} citations")
        
        # Show top citations with content
        for i, cite in enumerate(citations[:5], 1):
            print(f"\n--- Citation {i} ---")
            print(f"Source: {cite.get('source', 'Unknown')}")
            print(f"Page: {cite.get('page', 'N/A')}")
            print(f"Similarity: {cite.get('similarity_percentage', 0):.1f}%")
            
            # Check if content contains keywords
            snippet = cite.get('snippet', '') or cite.get('full_text', '')
            snippet_lower = snippet.lower()
            
            found_keywords = [kw for kw in test['keywords'] if kw in snippet_lower]
            if found_keywords:
                print(f"✅ Found keywords: {', '.join(found_keywords)}")
            else:
                print(f"❌ No keywords found")
            
            # Show snippet
            if len(snippet) > 300:
                print(f"Content: {snippet[:300]}...")
            else:
                print(f"Content: {snippet}")
        
        # Show answer
        answer = result.get('answer', '')
        print(f"\n🤖 Answer ({len(answer)} chars):")
        if len(answer) > 200:
            print(f"{answer[:200]}...")
        else:
            print(answer)

if __name__ == "__main__":
    main()

