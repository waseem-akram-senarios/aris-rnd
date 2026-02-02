import fitz  # PyMuPDF
import sys
import os

def find_snippet_page(pdf_path, search_snippet):
    """
    Search all pages of a PDF to find where a snippet actually exists.
    """
    if not os.path.exists(pdf_path):
        return f"Error: File {pdf_path} not found"
        
    doc = fitz.open(pdf_path)
    found_pages = []
    
    clean_search = search_snippet.lower().strip()
    # Use a small unique part of the snippet for searching
    search_term = clean_search[:50] if len(clean_search) > 50 else clean_search
    
    for i in range(len(doc)):
        text = doc[i].get_text("text").lower()
        if search_term in text:
            found_pages.append(i + 1)
            
    doc.close()
    return found_pages

if __name__ == "__main__":
    verifications = [
        {
            "path": "docs/testing/clientSpanishDocs/VUORMAR.pdf",
            "predicted": 7,
            "snippet": "Tarjeta mototambor cinta salida"
        },
        {
            "path": "docs/testing/clientSpanishDocs/EM10, degasing.pdf",
            "predicted": 1,
            "snippet": "Ajuste aire en bolsa"
        }
    ]
    
    print("\n" + "="*70)
    print(f"{'DOCUMENT':<25} | {'PREDICTED':<10} | {'ACTUAL':<10} | {'STATUS'}")
    print("-" * 70)
    
    for v in verifications:
        actual_pages = find_snippet_page(v["path"], v["snippet"])
        status = "✅ MATCH" if v["predicted"] in actual_pages else "❌ MISMATCH"
        actual_str = ", ".join(map(str, actual_pages)) if actual_pages else "NOT FOUND"
        print(f"{os.path.basename(v['path']):<25} | {v['predicted']:<10} | {actual_str:<10} | {status}")
    
    print("-" * 70)
    print("\nChecking VUORMAR.pdf Page 1 content for index analysis:")
    doc = fitz.open("docs/testing/clientSpanishDocs/VUORMAR.pdf")
    print(f"Page 1 Text Preview: {doc[0].get_text('text')[:300].replace(os.linesep, ' ')}")
    doc.close()
    print("="*70)


