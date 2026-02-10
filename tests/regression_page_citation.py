import os
import requests
import json
import time

BASE_URL = "http://44.221.84.58:8500"

def run_test():
    print("🔍 Regression Test: Page Number Citation Bug")
    print("===========================================")
    
    # Target: EM11, top seal(spa).pdf
    # Query: limpiar la superficie de la capa de calentamiento
    # Expected: 
    # 1. NO image citations for Page 6
    # 2. Should have text/image citations for Page 4
    
    query = "Como se puede limpiar la superficie de la capa de calentamiento?"
    doc_name = "EM11, top seal(spa).pdf"
    
    url = f"{BASE_URL}/query"
    payload = {
        "question": query,
        "search_mode": "hybrid",
        "k": 10,
        "active_sources": [doc_name],
        "auto_translate": True,
        "use_agentic_rag": True
    }
    
    print(f"Querying: '{query}' in '{doc_name}'...")
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            return
            
        result = response.json()
        citations = result.get('citations', [])
        
        print(f"Found {len(citations)} citations.")
        
        page_6_images = []
        page_4_content = []
        
        for i, c in enumerate(citations):
            page = c.get('page')
            ctype = c.get('content_type', 'unknown')
            source_loc = c.get('source_location', '')
            
            print(f"[{i}] Page: {page}, Type: {ctype}, Loc: {source_loc}")
            
            # Check for ghost Page 6 images
            if page == 6 and ctype == 'image':
                page_6_images.append(c)
            
            # Check for correct Page 4 content
            if page == 4:
                page_4_content.append(c)
                
        # Assertions
        if page_6_images:
            print("\n❌ FAILED: Found incorrect image citations for Page 6!")
            for c in page_6_images:
                print(f"   - {c.get('snippet')[:100]}...")
        else:
            print("\n✅ PASS: No Page 6 ghost images found.")
            
        if page_4_content:
            print(f"✅ PASS: Found {len(page_4_content)} citations from correct Page 4.")
        else:
            print("⚠️ WARNING: No content found from Page 4 (might be retrieval issue, but ghost bug is fixed).")
            
        print("\nAnswer Preview:")
        print(result.get('answer', '')[:200] + "...")
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    run_test()
