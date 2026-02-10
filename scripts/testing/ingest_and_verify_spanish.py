import sys
import os
import time
import logging

# Add project root to path
sys.path.append(os.getcwd())

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from services.ingestion.processor import DocumentProcessor
from services.ingestion.engine import IngestionEngine
from services.retrieval.engine import RetrievalEngine
from shared.config.settings import ARISConfig

def main():
    logger.info("Initializing engines...")
    # Initialize Ingestion Engine
    ingest_engine = IngestionEngine(
        vector_store_type="opensearch",
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
    )
    processor = DocumentProcessor(ingest_engine)
    
    # Initialize Retrieval Engine (for verification)
    retrieval_engine = RetrievalEngine(
        vector_store_type="opensearch",
        opensearch_index=ARISConfig.AWS_OPENSEARCH_INDEX
    )

    docs_dir = "docs/testing/clientSpanishDocs"
    files = [
        "EM10, degasing.pdf",
        "EM11, top seal.pdf",
        "VUORMAR.pdf"
    ]
    
    # 1. Ingest Documents
    logger.info("="*50)
    logger.info("STARTING INGESTION (Parser: Docling)")
    logger.info("="*50)
    
    processed_docs = []
    
    for filename in files:
        file_path = os.path.abspath(os.path.join(docs_dir, filename))
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            continue
            
        logger.info(f"Processing: {filename}")
        try:
            # Enforce Docling for best accuracy as requested
            result = processor.process_document(
                file_path=file_path,
                parser_preference="docling", 
                language="spa", # Specify Spanish
                is_update=True  # Overwrite if exists
            )
            processed_docs.append(filename)
            logger.info(f"Successfully processed {filename}: {result}")
        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            import traceback
            logger.error(traceback.format_exc())

    # 2. Verify Page Numbers via Retrieval
    logger.info("\n" + "="*50)
    logger.info("VERIFYING PAGE NUMBERS")
    logger.info("="*50)
    
    queries = [
        # Query for EM10 - targeted at specific content
        {
            "filename": "EM10, degasing.pdf",
            "query": "degasing procedure", 
            "expected_page_range": None
        },
         {
            "filename": "EM10, degasing.pdf",
            "query": "limpiar", # "clean" in Spanish
            "expected_page_range": None
        },
        # Query for EM11
        {
            "filename": "EM11, top seal.pdf",
            "query": "top seal parameters",
            "expected_page_range": None
        },
        # Query for VUORMAR
        {
            "filename": "VUORMAR.pdf",
            "query": "instrucciones de seguridad", # Safety instructions
            "expected_page_range": None
        }
    ]
    
    for q in queries:
        logger.info(f"\nQuerying: '{q['query']}' (Target: {q['filename']})")
        
        # Verify Retrieval Engine can find the doc and pages
        try:
            # Force mapping refresh
            if hasattr(retrieval_engine, '_check_and_reload_document_index_map'):
                retrieval_engine._check_and_reload_document_index_map()
                
            # Filter by specific document to test extraction from that doc
            active_sources = [q['filename']]
            
            result = retrieval_engine.query_with_rag(
                question=q['query'],
                k=5,
                active_sources=active_sources,
                search_mode="hybrid"
            )
            
            logger.info("Citations found:")
            citations = result.get('citations', [])
            for i, cit in enumerate(citations):
                page = cit.get('page')
                source = cit.get('source')
                snippet = cit.get('snippet', '')[:100].replace('\n', ' ')
                
                logger.info(f"  [{i+1}] Page {page} | Source: {source} | Snippet: {snippet}...")
                
                if page is None:
                    logger.error("  ❌ FAILURE: Page number is None!")
                else:
                    logger.info("  ✅ Page number present")
                    
        except Exception as e:
            logger.error(f"Query failed: {e}")

if __name__ == "__main__":
    main()
