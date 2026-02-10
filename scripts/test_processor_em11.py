import sys
import os

# Add project root to path
sys.path.append('/home/senarios/Desktop/aris')

# Mock what we need from docling if it is being imported
sys.modules['docling'] = os.mock = type('Module', (), {})

from services.ingestion.parsers.pymupdf_parser import PyMuPDFParser

parser = PyMuPDFParser()
doc_path = "/home/senarios/Desktop/aris/docs/testing/clientSpanishDocs/EM11, top seal.pdf"
parsed_doc = parser.parse(doc_path)

page_blocks = parsed_doc.metadata.get('page_blocks', [])
for i, block in enumerate(page_blocks):
    if block.get('text') and "limpiar" in block['text'].lower():
         print(f"BLOCK {i} on PAGE {block.get('page')} contains 'limpiar'")

