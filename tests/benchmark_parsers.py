
import os
import sys
import time
import json
import logging
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import Parsers
try:
    from services.ingestion.parsers.pymupdf_parser import PyMuPDFParser
    from services.ingestion.parsers.docling_parser import DoclingParser
    from services.ingestion.parsers.llama_scan_parser import LlamaScanParser
    from services.ingestion.parsers.ocrmypdf_parser import OCRmyPDFParser
    from services.retrieval.engine import RetrievalEngine
except ImportError as e:
    logger.error(f"Failed to import services: {e}")
    sys.exit(1)

TEST_DOCS_DIR = "docs/testing/clientSpanishDocs"

def get_test_files():
    path = Path(TEST_DOCS_DIR)
    if not path.exists():
        logger.error(f"Test directory not found: {path}")
        return []
    return [str(p) for p in path.glob("*.pdf")]

def test_parser(parser_class, file_path, parser_name):
    logger.info(f"Testing {parser_name} on {os.path.basename(file_path)}...")
    start_time = time.time()
    
    try:
        parser = parser_class()
        # Mock dependencies if needed (e.g., LlamaScan might need connection)
        # For now, we try running it. If it fails due to missing service, we catch it.
        
        # Docling and OCRMyPDF might take time.
        
        # Parse
        with open(file_path, "rb") as f:
            content = f.read()
            
        # Most parsers take file_path and content
        # Note: DoclingParser.parse signature is (file_path, file_content...)
        # PyMuPDFParser.parse signature is (file_path, file_content...)
        
        # Helper to run parse
        if parser_name == "DoclingParser":
            # Docling might need specific args or mocks for heavy parts if we want to be fast, 
            # but user asked for "performance" so we should let it run.
             # Mock _verify_ocr_models to avoid download prompt if possible, or assume env is ready
            with patch.object(parser, '_verify_ocr_models', return_value=True):
                 parsed_doc = parser.parse(file_path, content)
        else:
            parsed_doc = parser.parse(file_path, content)
            
        elapsed = time.time() - start_time
        
        # Validation
        if not parsed_doc:
             return {"status": "FAILED", "reason": "No output", "time": elapsed}
             
        metadata = parsed_doc.metadata if hasattr(parsed_doc, 'metadata') else {}
        page_blocks = metadata.get('page_blocks', [])
        
        # Check Character Offsets
        blocks_with_offsets = 0
        valid_offsets = 0
        if page_blocks:
            for i, block in enumerate(page_blocks):
                start = block.get('start_char')
                end = block.get('end_char')
                
                if start is not None and end is not None:
                    blocks_with_offsets += 1
                    if end > start:
                        valid_offsets += 1
                    else:
                        logger.warning(f"[{parser_name}] Invalid offset in block {i}: start={start}, end={end}")

        if blocks_with_offsets > 0:
            offset_status = f"PASS ({valid_offsets}/{blocks_with_offsets})" if valid_offsets == blocks_with_offsets else f"FAIL ({valid_offsets}/{blocks_with_offsets})"
        else:
            offset_status = "NO OFFSETS"
        
        if not page_blocks: offset_status = "NO BLOCKS"
        
        return {
            "status": "SUCCESS",
            "time": elapsed,
            "pages": len(page_blocks),
            "offsets": offset_status,
            "metadata": metadata,
            "text_len": len(parsed_doc.page_content) if hasattr(parsed_doc, 'page_content') else 0,
            "parsed_doc": parsed_doc
        }
        
    except Exception as e:
        logger.error(f"Error testing {parser_name}: {e}")
        return {"status": "ERROR", "reason": str(e), "time": time.time() - start_time}

def verify_retrieval_extraction(engine_instance, parsed_result, parser_name):
    """
    Test if RetrievalEngine can extract page number from chunks.
    """
    if parsed_result['status'] != 'SUCCESS':
        return "N/A"
        
    doc = parsed_result['parsed_doc']
    # Ensure doc has metadata accessible as dict attribute or object attribute
    if not hasattr(doc, 'metadata'):
        doc.metadata = {}
        
    page_blocks = doc.metadata.get('page_blocks', [])
    if not page_blocks:
        return "FAIL (No Blocks)"
        
    # Sample 3 blocks (start, middle, end)
    indices = [0, len(page_blocks)//2, len(page_blocks)-1]
    results = []
    
    for idx in set(indices): # set to handle small docs
        if idx < len(page_blocks):
            block = page_blocks[idx]
            true_page = block.get('page')
            # Extract a chunk of text
            full_text = doc.text if hasattr(doc, 'text') else ""
            
            # If we have offsets, slice text
            chunk_text = ""
            start = block.get('start_char')
            end = block.get('end_char')
            
            if start is not None and end is not None and full_text:
                chunk_text = full_text[start:end][:200] # First 200 chars of block
            else:
                # Fallback to block['text']
                chunk_text = block.get('text', '')[:200]
            
            # Simulate a chunk object
            chunk_doc = MagicMock()
            chunk_doc.metadata = doc.metadata.copy()
            # If this chunk was created properly, it would have start_char/end_char of its own.
            # But the _extract_page_number uses doc.metadata (the PARENT doc metadata generally) 
            # AND the chunk text.
            # Wait, _extract_page_number takes (doc, chunk_text). 
            # 'doc' in that context usually refers to the CHUNK document which has metadata composed of parent metadata + specific chunk metdata.
            
            # Let's populate the mock chunk metadata with expected fields
            chunk_doc.metadata['start_char'] = start
            chunk_doc.metadata['end_char'] = end
            
            # CALL ENGINE
            try:
                extracted_page, conf = engine_instance._extract_page_number(chunk_doc, chunk_text)
                
                match = (extracted_page == true_page)
                results.append(match)
                logger.info(f"[{parser_name}] Page Check: True={true_page}, Extracted={extracted_page} (Conf={conf}) -> {'MATCH' if match else 'MISMATCH'}")
            except Exception as e:
                logger.error(f"Error in extraction check: {e}")
                results.append(False)

    if all(results) and results:
        return "PASS"
    elif any(results):
        return "PARTIAL"
    else:
        return "FAIL"

def main():
    files = get_test_files()
    if not files:
        logger.info("No files to test")
        return
        
    # Mocking RetrievalEngine to avoid heavy init
    with patch.object(RetrievalEngine, '__init__', return_value=None):
        engine = RetrievalEngine()
        # Mock logging inside engine if needed, or let it use default
        
    parsers = [
        ("PyMuPDF", PyMuPDFParser),
        ("Docling", DoclingParser),
        # ("LlamaScan", LlamaScanParser), # Might be slow/unavailable
        # ("OCRMyPDF", OCRMyPDFParser),   # Might be slow
    ]
    
    # Enable all parsers requested by user
    parsers = [
        ("PyMuPDF", PyMuPDFParser),
        ("Docling", DoclingParser),
        ("OCRMyPDF", OCRmyPDFParser),
        ("LlamaScan", LlamaScanParser)
    ]

    results_table = []
    
    for file_path in files:
        filename = os.path.basename(file_path)
        for name, cls in parsers:
            print(f"\n--- Testing {name} on {filename} ---")
            res = test_parser(cls, file_path, name)
            
            retrieval_status = "N/A"
            if res['status'] == 'SUCCESS':
                retrieval_status = verify_retrieval_extraction(engine, res, name)
            
            results_table.append({
                "File": filename,
                "Parser": name,
                "Time(s)": f"{res['time']:.2f}",
                "Status": res['status'],
                "Pages": res.get('pages', 0),
                "OffsetValidity": res.get('offsets', 'N/A'),
                "RetrievalAcc": retrieval_status
            })

    # Print markdown table
    print("\n\n### Benchmark Results")
    print("| File | Parser | Time(s) | Status | Pages | Offsets | Retrieval Accuracy |")
    print("|---|---|---|---|---|---|---|")
    for r in results_table:
        print(f"| {r['File']} | {r['Parser']} | {r['Time(s)']} | {r['Status']} | {r['Pages']} | {r['OffsetValidity']} | {r['RetrievalAcc']} |")

if __name__ == "__main__":
    main()
