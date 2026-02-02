from docling.document_converter import DocumentConverter
import os

def inspect_vuormar_content():
    path = "docs/testing/clientSpanishDocs/VUORMAR.pdf"
    if not os.path.exists(path):
        print("File not found")
        return

    converter = DocumentConverter()
    result = converter.convert(path)
    doc = result.document
    
    print(f"Document Pages: {len(doc.pages)}")
    
    # Try alternate extraction if page.export_to_text() fails
    full_text = doc.export_to_text()
    
    for k in sorted(doc.pages.keys()):
        p = doc.pages[k]
        pno = getattr(p, 'page_no', 'N/A')
        
        # In some versions of docling, page object doesn't have export_to_text directly
        # but we can check the blocks or use the global export
        text = ""
        if hasattr(p, 'blocks'):
            text = "\n".join([getattr(b, 'text', '') for b in p.blocks if hasattr(b, 'text')])
        
        snippet = text[:150].replace('\n', ' ')
        print(f"Logical {k} | Physical {pno} | Snippet: {snippet}")


if __name__ == "__main__":
    inspect_vuormar_content()
