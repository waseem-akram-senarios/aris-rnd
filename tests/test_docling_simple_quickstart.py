#!/usr/bin/env python3
"""
Test Docling using the simple quickstart pattern from documentation.
This follows the recommended Docling usage.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"

print("=" * 70)
print("DOCLING QUICKSTART PATTERN TEST")
print("=" * 70)
print()
print("Following Docling's recommended usage pattern:")
print("  from docling.document_converter import DocumentConverter")
print("  converter = DocumentConverter()")
print("  doc = converter.convert(source).document")
print("  print(doc.export_to_markdown())")
print()

try:
    from docling.document_converter import DocumentConverter
    
    print("🔧 Step 1: Creating DocumentConverter...")
    converter = DocumentConverter()
    print("✅ Converter created")
    print()
    
    print("📖 Step 2: Converting PDF to Docling document...")
    print(f"   File: {os.path.basename(pdf_path)}")
    print("   (Processing ALL pages for best extraction)")
    print()
    
    start_time = time.time()
    result = converter.convert(pdf_path, raises_on_error=False)
    elapsed = time.time() - start_time
    
    print(f"✅ Conversion completed in {elapsed:.2f} seconds")
    print()
    
    print("📄 Step 3: Accessing document...")
    doc = result.document
    print("✅ Document accessed")
    print()
    
    print("📝 Step 4: Exporting to Markdown...")
    try:
        markdown_text = doc.export_to_markdown()
        print(f"✅ Markdown export: {len(markdown_text):,} characters")
    except Exception as e:
        print(f"⚠️  Markdown export failed: {e}")
        markdown_text = None
    
    print()
    print("📝 Step 5: Exporting to Text...")
    try:
        text = doc.export_to_text()
        print(f"✅ Text export: {len(text):,} characters")
    except Exception as e:
        print(f"⚠️  Text export failed: {e}")
        text = None
    
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    if markdown_text and len(markdown_text.strip()) > 0:
        print(f"✅ Markdown: {len(markdown_text):,} characters")
        print(f"   Preview: {markdown_text[:200]}...")
    else:
        print("❌ Markdown: No content")
    
    if text and len(text.strip()) > 0:
        words = text.split()
        print(f"✅ Text: {len(text):,} characters, {len(words):,} words")
        print(f"   Preview: {text[:200]}...")
    else:
        print("❌ Text: No content")
    
    # Check document structure
    print()
    print("=" * 70)
    print("DOCUMENT STRUCTURE")
    print("=" * 70)
    if hasattr(doc, 'pages'):
        pages = doc.pages
        if isinstance(pages, dict):
            print(f"📄 Pages (dict): {len(pages)} pages")
        elif isinstance(pages, list):
            print(f"📄 Pages (list): {len(pages)} pages")
        else:
            print(f"📄 Pages: {pages}")
    
    if hasattr(doc, 'texts'):
        texts = doc.texts
        if isinstance(texts, list):
            print(f"📝 Texts: {len(texts)} text elements")
    
    if hasattr(doc, 'body'):
        body = doc.body
        if hasattr(body, 'children'):
            print(f"📑 Body children: {len(body.children)} elements")
    
    print()
    print("=" * 70)
    if (markdown_text and len(markdown_text.strip()) > 100) or (text and len(text.strip()) > 100):
        print("✅ SUCCESS! Docling extracted meaningful content!")
        print("=" * 70)
        print()
        print("💡 To use this in your parser:")
        print("   1. Set DOCLING_PROCESS_ALL_PAGES=true environment variable")
        print("   2. Or modify parser to process all pages for files <= 3MB")
        print("   3. Use doc.export_to_markdown() or doc.export_to_text()")
    else:
        print("❌ Docling extracted no meaningful content")
        print("=" * 70)
        print()
        print("💡 This PDF format may not be compatible with Docling's layout model.")
        print("   Consider using PyMuPDF parser instead.")
        
except Exception as e:
    print("=" * 70)
    print("❌ ERROR")
    print("=" * 70)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()



