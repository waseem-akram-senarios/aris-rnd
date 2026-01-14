"""
Quick Cross-Language Test - Tests key scenarios
"""
import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://44.221.84.58:8500"

def get_documents():
    """Get available documents"""
    try:
        response = requests.get(f"{BASE_URL}/documents", timeout=30)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and "documents" in data:
            return data["documents"]
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error: {e}")
        return []

def query_rag(question, document_id=None, auto_translate=True, search_mode="hybrid"):
    """Query RAG system"""
    url = f"{BASE_URL}/query"
    payload = {
        "question": question,
        "k": 10,
        "search_mode": search_mode,
        "use_hybrid_search": (search_mode == "hybrid"),
        "semantic_weight": 0.7,
        "auto_translate": auto_translate
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

def main():
    print("=" * 80)
    print("🔬 QUICK CROSS-LANGUAGE TEST")
    print("=" * 80)
    
    # Get documents
    docs = get_documents()
    print(f"\n📚 Found {len(docs)} document(s)")
    
    # Find Spanish/Vuormar documents
    spanish_docs = []
    for doc in docs:
        # Normalize to dict
        if hasattr(doc, 'dict'):
            doc = doc.dict()
        elif hasattr(doc, '__dict__'):
            doc = doc.__dict__
        elif not isinstance(doc, dict):
            continue
        
        doc_name = doc.get('document_name', '').lower()
        if 'vuormar' in doc_name or 'spanish' in doc_name:
            spanish_docs.append(doc)
            print(f"   ✅ {doc.get('document_name')} (ID: {doc.get('document_id')})")
    
    if not spanish_docs:
        print("   ⚠️  No Spanish/Vuormar documents found. Using first document...")
        if docs:
            doc = docs[0]
            if hasattr(doc, 'dict'):
                doc = doc.dict()
            elif hasattr(doc, '__dict__'):
                doc = doc.__dict__
            spanish_docs = [doc] if isinstance(doc, dict) else []
    
    if not spanish_docs:
        print("❌ No documents available for testing")
        return
    
    # Test queries
    test_queries = [
        {
            "query": "¿Dónde está el email y contacto de Vuormar?",
            "lang": "Spanish",
            "type": "Same-language"
        },
        {
            "query": "Where is the email and contact of Vuormar?",
            "lang": "English",
            "type": "Cross-language"
        },
        {
            "query": "How to increase or decrease the levels of air in bag?",
            "lang": "English",
            "type": "Cross-language"
        },
        {
            "query": "¿Cómo aumentar o disminuir los niveles de aire en la bolsa?",
            "lang": "Spanish",
            "type": "Same-language"
        }
    ]
    
    print("\n" + "=" * 80)
    print("🧪 TESTING QUERIES")
    print("=" * 80)
    
    for doc in spanish_docs[:1]:  # Test first document only
        doc_id = doc.get('document_id')
        doc_name = doc.get('document_name')
        
        print(f"\n📄 Document: {doc_name}")
        print("-" * 80)
        
        for test in test_queries:
            print(f"\n🔍 Query ({test['type']}): {test['query']}")
            
            # Test with auto_translate=True
            result = query_rag(test['query'], doc_id, auto_translate=True, search_mode="hybrid")
            
            if "error" in result:
                print(f"   ❌ Error: {result['error']}")
            else:
                answer = result.get('answer', '')[:150]
                citations = result.get('citations', [])
                similarities = [c.get('similarity_percentage', 0) for c in citations if c.get('similarity_percentage')]
                avg_sim = sum(similarities) / len(similarities) if similarities else 0
                
                print(f"   ✅ Answer: {answer}...")
                print(f"   📊 Citations: {len(citations)}, Avg Similarity: {avg_sim:.1f}%")
                
                # Check answer quality
                answer_lower = answer.lower()
                if any(phrase in answer_lower for phrase in ["i don't know", "cannot", "no information", "check the manual"]):
                    print(f"   ⚠️  Low quality answer detected")
                elif len(answer) < 50:
                    print(f"   ⚠️  Very short answer")
                else:
                    print(f"   ✅ Answer looks good")
            
            print()

if __name__ == "__main__":
    main()

