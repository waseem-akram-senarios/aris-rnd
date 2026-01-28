import sys
import os

# Add project root to path
sys.path.append('/home/senarios/Desktop/aris')

from services.ingestion.parsers.pymupdf_parser import PyMuPDFParser

parser = PyMuPDFParser()
doc_path = "/home/senarios/Desktop/aris/docs/testing/clientSpanishDocs/EM11, top seal.pdf"

parsed = parser.parse(doc_path)
print(f"Parser Used: {parsed.parser_used}")
print(f"Total Pages in ParsedDoc: {parsed.pages}")

# Check page_blocks
page_blocks = parsed.metadata.get('page_blocks', [])
print(f"Total page_blocks: {len(page_blocks)}")

for i, block in enumerate(page_blocks[:10]):
    print(f"Block {i}: Type={block.get('type')}, Page={block.get('page')}, Start={block.get('start_char')}, End={block.get('end_char')}")

# Find "limpiar"
search_term = "limpiar"
print(f"\nSearching for '{search_term}'...")
import re
for i, block in enumerate(page_blocks):
    if block.get('text') and search_term.lower() in block['text'].lower():
        print(f"FOUND in Block {i} (Page {block.get('page')}): Type={block.get('type')}")
        idx = block['text'].lower().find(search_term.lower())
        print(f"  Snippet: {block['text'][max(0, idx-50):idx+100]}")
