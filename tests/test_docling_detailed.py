#!/usr/bin/env python3
"""
Detailed test script for Docling parser with full logging.
"""
import os
import sys
import time
import logging

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docling_detailed(pdf_path):
    """Test Docling parser with detailed logging."""
    print("=" * 70)
    print("DOCLING DETAILED TEST WITH LOGGING")
    print("=" * 70)
    print()
    
    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}")
        return False
    
    file_size = os.path.getsize(pdf_path)
    print(f"📄 Testing with: {os.path.basename(pdf_path)}")
    print(f"   File size: {file_size / 1024:.2f} KB")
    print()
    
    try:
        print("🔧 Step 1: Importing Docling...")
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        print("✅ Docling imported successfully")
        print()
        
        print("🔧 Step 2: Creating DocumentConverter...")
        try:
            from docling.datamodel.pipeline_options import PipelineOptions
            from docling.datamodel.document_converter_config import DocumentConverterConfig
            
            # Create minimal config
            pipeline_options = PipelineOptions()
            if hasattr(pipeline_options, 'document_timeout'):
                pipeline_options.document_timeout = 30  # 30 seconds
            if hasattr(pipeline_options, 'do_ocr'):
                pipeline_options.do_ocr = False
            if hasattr(pipeline_options, 'do_table_structure'):
                pipeline_options.do_table_structure = False
            if hasattr(pipeline_options, 'do_vision'):
                pipeline_options.do_vision = False
            if hasattr(pipeline_options, 'enable_remote_services'):
                pipeline_options.enable_remote_services = False
            
            config = DocumentConverterConfig()
            if hasattr(config, 'pipeline_options'):
                config.pipeline_options = pipeline_options
            
            converter = DocumentConverter(config=config)
            print("✅ DocumentConverter created with optimized config")
        except Exception as e:
            print(f"⚠️  Config creation failed, using default: {e}")
            converter = DocumentConverter()
        print()
        
        print("🔧 Step 3: Testing conversion with first 5 pages only...")
        print("   (This will help us see if Docling works at all)")
        print()
        
        start_time = time.time()
        
        try:
            # Try with just first 5 pages to test if it works
            result = converter.convert(pdf_path, max_num_pages=5)
            elapsed = time.time() - start_time
            
            print(f"✅ Conversion completed in {elapsed:.2f} seconds!")
            print()
            
            # Check result structure
            print("🔍 Step 4: Analyzing result structure...")
            print(f"   Result type: {type(result)}")
            print(f"   Result attributes: {[x for x in dir(result) if not x.startswith('_')][:10]}")
            
            if hasattr(result, 'document'):
                doc = result.document
                print(f"   Document type: {type(doc)}")
                print(f"   Document attributes: {[x for x in dir(doc) if not x.startswith('_')][:15]}")
                
                # Try to extract text
                print()
                print("🔍 Step 5: Testing text extraction methods...")
                
                text = ""
                methods_tried = []
                
                # Try export_to_markdown
                if hasattr(doc, 'export_to_markdown'):
                    try:
                        text = doc.export_to_markdown()
                        methods_tried.append("export_to_markdown: ✅")
                        print(f"   ✅ export_to_markdown: {len(text)} chars")
                    except Exception as e:
                        methods_tried.append(f"export_to_markdown: ❌ {str(e)[:50]}")
                        print(f"   ❌ export_to_markdown: {str(e)[:100]}")
                
                # Try export_to_text
                if not text and hasattr(doc, 'export_to_text'):
                    try:
                        text = doc.export_to_text()
                        methods_tried.append("export_to_text: ✅")
                        print(f"   ✅ export_to_text: {len(text)} chars")
                    except Exception as e:
                        methods_tried.append(f"export_to_text: ❌ {str(e)[:50]}")
                        print(f"   ❌ export_to_text: {str(e)[:100]}")
                
                # Try get_text
                if not text and hasattr(doc, 'get_text'):
                    try:
                        text = doc.get_text()
                        methods_tried.append("get_text: ✅")
                        print(f"   ✅ get_text: {len(text)} chars")
                    except Exception as e:
                        methods_tried.append(f"get_text: ❌ {str(e)[:50]}")
                        print(f"   ❌ get_text: {str(e)[:100]}")
                
                # Try text attribute
                if not text and hasattr(doc, 'text'):
                    try:
                        text = doc.text
                        methods_tried.append("text attribute: ✅")
                        print(f"   ✅ text attribute: {len(text)} chars")
                    except Exception as e:
                        methods_tried.append(f"text attribute: ❌ {str(e)[:50]}")
                        print(f"   ❌ text attribute: {str(e)[:100]}")
                
                print()
                print("=" * 70)
                print("TEXT EXTRACTION RESULTS:")
                print("=" * 70)
                if text:
                    print(f"✅ Successfully extracted {len(text)} characters")
                    print(f"   Preview (first 300 chars):")
                    print(f"   {text[:300]}...")
                    print()
                    print("✅ DOCLING IS WORKING!")
                else:
                    print("❌ No text extracted with any method")
                    print("   Methods tried:")
                    for method in methods_tried:
                        print(f"     - {method}")
                    print()
                    print("⚠️  Docling converted but couldn't extract text")
            else:
                print("⚠️  Result has no 'document' attribute")
                print(f"   Result: {result}")
            
            return True
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ Conversion failed after {elapsed:.2f} seconds")
            print(f"   Error type: {type(e).__name__}")
            print(f"   Error message: {str(e)}")
            import traceback
            print()
            print("Full traceback:")
            traceback.print_exc()
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    # Use the smaller PDF for testing
    test_file = "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf"
    
    if not os.path.exists(test_file):
        print(f"❌ File not found: {test_file}")
        return
    
    success = test_docling_detailed(test_file)
    
    if success:
        print("\n🎉 Docling test completed - check results above!")
    else:
        print("\n⚠️  Docling test encountered issues - see logs above")


if __name__ == "__main__":
    main()






