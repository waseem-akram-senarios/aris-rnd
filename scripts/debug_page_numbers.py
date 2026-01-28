import fitz
doc_path = "/home/senarios/Desktop/aris/docs/testing/clientSpanishDocs/EM11, top seal.pdf"
doc = fitz.open(doc_path)
page_6 = doc[5]
print(f"--- PAGE 6 TEXT ---")
print(page_6.get_text())
