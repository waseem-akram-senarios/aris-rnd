#!/usr/bin/env python3
"""Test Docling with just 1 page to verify it works."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_1_page():
    """Test Docling with just 1 page."""
    test_file = "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf"
    test_file = os.path.abspath(test_file)
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        return False
    
    print(f"📄 File: {os.path.basename(test_file)}")
    print(f"   Size: {os.path.getsize(test_file) / 1024:.1f} KB")
    print()
    
    print("=" * 70)
    print("TESTING DOCLING WITH 1 PAGE ONLY")
    print("=" * 70)
    print()
    
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PipelineOptions
        
        # Create converter with minimal config
        pipeline_options = PipelineOptions()
        if hasattr(pipeline_options, 'do_ocr'):
            pipeline_options.do_ocr = False
        if hasattr(pipeline_options, 'do_table_structure'):
            pipeline_options.do_table_structure = False
        
        try:
            from docling.datamodel.document_converter_config import DocumentConverterConfig
            config = DocumentConverterConfig()
            if hasattr(config, 'pipeline_options'):
                config.pipeline_options = pipeline_options
            converter = DocumentConverter(config=config)
        except:
            converter = DocumentConverter()
        
        print("✅ Converter created")
        print("📖 Converting first page only (max_num_pages=1)...")
        print()
        
        start = time.time()
        result = converter.convert(test_file, max_num_pages=1)
        elapsed = time.time() - start
        
        print(f"✅ Conversion completed in {elapsed:.2f} seconds!")
        print()
        
        if hasattr(result, 'document'):
            doc = result.document
            
            # Try to get text
            text = ""
            if hasattr(doc, 'export_to_markdown'):
                try:
                    text = doc.export_to_markdown()
                    print(f"✅ Text extracted via export_to_markdown: {len(text)} chars")
                except Exception as e:
                    print(f"❌ export_to_markdown failed: {e}")
            
            if not text and hasattr(doc, 'export_to_text'):
                try:
                    text = doc.export_to_text()
                    print(f"✅ Text extracted via export_to_text: {len(text)} chars")
                except Exception as e:
                    print(f"❌ export_to_text failed: {e}")
            
            if not text and hasattr(doc, 'get_text'):
                try:
                    text = doc.get_text()
                    print(f"✅ Text extracted via get_text: {len(text)} chars")
                except Exception as e:
                    print(f"❌ get_text failed: {e}")
            
            if text:
                print()
                print("=" * 70)
                print("TEXT SAMPLE (first 300 chars):")
                print("=" * 70)
                print(text[:300])
                print()
                print("=" * 70)
                print("✅ DOCLING IS WORKING! Text extracted successfully.")
                print("=" * 70)
                return True
            else:
                print("❌ No text extracted")
                return False
        else:
            print("❌ No document in result")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_1_page()
    sys.exit(0 if success else 1)

