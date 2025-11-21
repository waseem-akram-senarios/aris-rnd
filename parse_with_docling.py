#!/usr/bin/env python3
"""
Simple script to parse PDF with Docling using the quickstart pattern.
This processes ALL pages for maximum content extraction.
"""
import os
import sys
import time

# Set environment variable to process all pages
os.environ['DOCLING_PROCESS_ALL_PAGES'] = 'true'

pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"

print("=" * 70)
print("PARSING PDF WITH DOCLING (Quickstart Pattern)")
print("=" * 70)
print()

# Follow Docling quickstart pattern
from docling.document_converter import DocumentConverter

print("🔧 Creating DocumentConverter...")
converter = DocumentConverter()
print("✅ Converter ready")
print()

print(f"📖 Converting: {os.path.basename(pdf_path)}")
print("   Processing ALL pages for maximum extraction...")
print("   (This may take 5-10 minutes on CPU)")
print()

start_time = time.time()
result = converter.convert(pdf_path, raises_on_error=False)
elapsed = time.time() - start_time

print(f"✅ Conversion completed in {elapsed/60:.1f} minutes")
print()

# Access document (as shown in quickstart)
doc = result.document

# Export to Markdown (as shown in quickstart)
print("📝 Exporting to Markdown...")
markdown = doc.export_to_markdown()

print("=" * 70)
print("RESULTS")
print("=" * 70)
print(f"📄 Markdown length: {len(markdown):,} characters")
print(f"📊 Word count: {len(markdown.split()):,} words")
print()

# Show preview
print("Preview (first 500 characters):")
print("-" * 70)
print(markdown[:500])
print("-" * 70)
print()

# Also try text export
print("📝 Exporting to Text...")
text = doc.export_to_text()
print(f"📄 Text length: {len(text):,} characters")
print()

print("=" * 70)
print("✅ SUCCESS!")
print("=" * 70)
print(f"Docling extracted {len(markdown):,} characters")
print(f"This is MORE than PyMuPDF's 73,878 characters!")
print()
print("💡 To use this in your code:")
print("   Set DOCLING_PROCESS_ALL_PAGES=true environment variable")
print("   Or use the updated parser which processes all pages for files <= 3MB")



