#!/usr/bin/env python3
"""
Direct test to verify image extraction and storage pipeline.
"""
import sys
import os
sys.path.insert(0, '.')

from parsers.docling_parser import DoclingParser
from ingestion.document_processor import DocumentProcessor
from services.retrieval.engine import RetrievalEngine as RAGSystem
from shared.config.settings import ARISConfig

def test_parser_extraction():
    """Test parser extraction directly"""
    print("="*80)
    print("TEST: Parser Image Extraction")
    print("="*80)
    
    doc_path = "FL10.11 SPECIFIC8 (1).pdf"
    if not os.path.exists(doc_path):
        print(f"❌ Document not found: {doc_path}")
        return None
    
    parser = DoclingParser()
    print(f"✅ Parser initialized")
    
    try:
        print(f"📄 Parsing document...")
        parsed_doc = parser.parse(doc_path)
        
        print(f"\n📊 Parser Results:")
        print(f"  Pages: {parsed_doc.pages}")
        print(f"  Images Detected: {parsed_doc.images_detected}")
        print(f"  Image Count: {parsed_doc.image_count}")
        print(f"  Text Length: {len(parsed_doc.text)}")
        
        # Check extracted_images
        extracted_images = parsed_doc.metadata.get('extracted_images', [])
        print(f"  Extracted Images Count: {len(extracted_images)}")
        
        if len(extracted_images) > 0:
            print(f"\n✅ extracted_images is populated!")
            print(f"  First image keys: {list(extracted_images[0].keys())}")
            print(f"  First image source: {extracted_images[0].get('source', 'MISSING')}")
            print(f"  First image number: {extracted_images[0].get('image_number', 'MISSING')}")
            print(f"  First image OCR length: {len(extracted_images[0].get('ocr_text', ''))}")
            return parsed_doc
        else:
            print(f"\n❌ extracted_images is EMPTY!")
            print(f"  This explains why images aren't being stored")
            return parsed_doc
    except Exception as e:
        print(f"❌ Parser error: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_storage_pipeline(parsed_doc):
    """Test storage pipeline"""
    print("\n" + "="*80)
    print("TEST: Storage Pipeline")
    print("="*80)
    
    if not parsed_doc:
        print("❌ No parsed document to test")
        return
    
    extracted_images = parsed_doc.metadata.get('extracted_images', [])
    if not extracted_images:
        print("❌ No extracted_images to store")
        return
    
    # Initialize RAG system
    rag_system = RAGSystem(
        vector_store_type=ARISConfig.VECTOR_STORE_TYPE,
        opensearch_domain=ARISConfig.AWS_OPENSEARCH_DOMAIN,
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
    )
    
    processor = DocumentProcessor(rag_system)
    
    print(f"✅ DocumentProcessor initialized")
    print(f"📦 Attempting to store {len(extracted_images)} images...")
    
    try:
        processor._store_images_in_opensearch(
            extracted_images,
            parsed_doc.metadata.get('source', 'test.pdf'),
            parsed_doc.parser_used
        )
        print(f"✅ Storage method completed without error")
    except Exception as e:
        print(f"❌ Storage error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    parsed_doc = test_parser_extraction()
    if parsed_doc:
        test_storage_pipeline(parsed_doc)

