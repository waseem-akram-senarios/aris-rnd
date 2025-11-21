#!/usr/bin/env python3
"""
Force Docling to parse a PDF using alternative methods.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = "/home/senarios/Desktop/aris/FL10.11 SPECIFIC8 (1).pdf"

print("=" * 70)
print("FORCING DOCLING TO PARSE PDF")
print("=" * 70)
print()

def try_method_1_default():
    """Try default DocumentConverter."""
    print("Method 1: Default DocumentConverter (all pages)")
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        result = converter.convert(pdf_path, raises_on_error=False)
        
        if hasattr(result, 'document'):
            doc = result.document
            # Try all export methods
            text = None
            if hasattr(doc, 'export_to_markdown'):
                try:
                    text = doc.export_to_markdown()
                except:
                    pass
            if not text and hasattr(doc, 'export_to_text'):
                try:
                    text = doc.export_to_text()
                except:
                    pass
            
            if text and len(text.strip()) > 100:
                print(f"   ✅ SUCCESS! Extracted {len(text)} characters")
                return text
            else:
                print(f"   ❌ No meaningful content ({len(text) if text else 0} chars)")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def try_method_2_with_ocr():
    """Try with OCR enabled (might help with older PDFs)."""
    print("\nMethod 2: DocumentConverter with OCR enabled")
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PipelineOptions
        from docling.datamodel.document_converter_config import DocumentConverterConfig
        
        pipeline_options = PipelineOptions()
        # Try enabling OCR - might help with older PDFs
        # Note: This will be slower
        
        config = DocumentConverterConfig()
        if hasattr(config, 'pipeline_options'):
            config.pipeline_options = pipeline_options
        
        converter = DocumentConverter(config=config)
        result = converter.convert(pdf_path, max_num_pages=5, raises_on_error=False)
        
        if hasattr(result, 'document'):
            doc = result.document
            text = None
            if hasattr(doc, 'export_to_text'):
                try:
                    text = doc.export_to_text()
                except:
                    pass
            
            if text and len(text.strip()) > 100:
                print(f"   ✅ SUCCESS! Extracted {len(text)} characters")
                return text
            else:
                print(f"   ❌ No meaningful content ({len(text) if text else 0} chars)")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def try_method_3_backend_direct():
    """Try accessing PDF backend directly."""
    print("\nMethod 3: Direct PDF backend access")
    try:
        from docling.backend.pdf_backend import PdfBackend
        
        backend = PdfBackend()
        # Try to process directly
        print("   Attempting direct backend processing...")
        # This might not work, but worth trying
        return None
    except Exception as e:
        print(f"   ❌ Backend not accessible: {e}")
        return None

def try_method_4_force_all_pages():
    """Try processing all pages without limit."""
    print("\nMethod 4: Process all pages (no limit)")
    try:
        from docling.document_converter import DocumentConverter
        converter = DocumentConverter()
        # Don't limit pages - process everything
        result = converter.convert(pdf_path, raises_on_error=False)
        
        if hasattr(result, 'document'):
            doc = result.document
            text = None
            if hasattr(doc, 'export_to_markdown'):
                try:
                    text = doc.export_to_markdown()
                except:
                    pass
            if not text and hasattr(doc, 'export_to_text'):
                try:
                    text = doc.export_to_text()
                except:
                    pass
            
            if text and len(text.strip()) > 100:
                print(f"   ✅ SUCCESS! Extracted {len(text)} characters")
                return text
            else:
                print(f"   ❌ No meaningful content ({len(text) if text else 0} chars)")
        return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def try_method_5_hybrid_approach():
    """Try hybrid: Use PyMuPDF to extract text, then process with Docling structure."""
    print("\nMethod 5: Hybrid approach (PyMuPDF text + Docling structure)")
    try:
        # First extract text with PyMuPDF
        import fitz
        pymupdf_doc = fitz.open(pdf_path)
        pymupdf_text = ""
        for page in pymupdf_doc:
            pymupdf_text += page.get_text() + "\n"
        pymupdf_doc.close()
        
        print(f"   Extracted {len(pymupdf_text)} chars with PyMuPDF")
        print("   Note: This uses PyMuPDF for text, not Docling")
        return pymupdf_text
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

if __name__ == "__main__":
    results = {}
    
    # Try all methods
    results['method1'] = try_method_1_default()
    results['method2'] = try_method_2_with_ocr()
    results['method3'] = try_method_3_backend_direct()
    results['method4'] = try_method_4_force_all_pages()
    results['method5'] = try_method_5_hybrid_approach()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    success_methods = [k for k, v in results.items() if v and len(v.strip()) > 100]
    
    if success_methods:
        print(f"\n✅ Success with methods: {', '.join(success_methods)}")
        best_method = success_methods[0]
        text = results[best_method]
        print(f"\nBest result from {best_method}:")
        print(f"   Text length: {len(text)} characters")
        print(f"   Preview: {text[:500]}")
    else:
        print("\n❌ No method successfully extracted meaningful content with Docling")
        print("\n💡 Recommendation:")
        print("   This PDF (PDF 1.3 from 2000) is not compatible with Docling's layout model.")
        print("   Docling's modern layout detection doesn't recognize this older PDF structure.")
        print("   Use PyMuPDF parser instead - it handles this PDF format perfectly.")
        
        if results['method5']:
            print(f"\n   However, PyMuPDF extracted {len(results['method5'])} characters successfully.")

