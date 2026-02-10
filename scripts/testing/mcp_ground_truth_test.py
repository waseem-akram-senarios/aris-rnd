import fitz  # PyMuPDF
import sys
import os
import logging
import json
import time

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger("ground_truth")

from services.mcp.engine import MCPEngine

import re

def normalize_text(text):
    """Remove markers, punctuation and extra whitespace for fuzzy matching."""
    # Remove markdown/Docling markers
    text = re.sub(r'[#\*_`\-]', ' ', text)
    # Keep only alphanumeric and spaces
    text = re.sub(r'[^a-z0-9 ]', ' ', text.lower())
    # Normalize whitespace
    return ' '.join(text.split())

def find_actual_pages(pdf_path, snippet):
    """Search for snippet in PDF with lenient normalization."""
    if not os.path.exists(pdf_path):
        return []
        
    doc = fitz.open(pdf_path)
    found_pages = []
    
    # Pre-process snippet: take multiple small chunks to increase hit rate
    clean_snippet = normalize_text(snippet)
    words = clean_snippet.split()
    
    if len(words) < 3:
        doc.close()
        return []
        
    # Try 3 different windows of 5 words each
    search_windows = []
    if len(words) >= 5:
        search_windows.append(" ".join(words[len(words)//4 : len(words)//4 + 5]))
        search_windows.append(" ".join(words[len(words)//2 : len(words)//2 + 5]))
        search_windows.append(" ".join(words[len(words)-6 : len(words)-1]))
    else:
        search_windows.append(" ".join(words))

    for i in range(len(doc)):
        page_text = normalize_text(doc[i].get_text("text"))
        for window in search_windows:
            if window and window in page_text:
                found_pages.append(i + 1)
                break
                
    doc.close()
    return sorted(list(set(found_pages)))


def run_ground_truth_test():
    engine = MCPEngine()
    
    questions = [
        # EM10 Questions
        "How do I adjust the air level if it is too high in the bag?",
        "What happens if individual bars collide with the general bar?",
        "What are the markers on the bars for?",
        
        # EM11 Questions
        "What parameters should be adjusted for the top seal?",
        "How to clean the vacuum suction cups?",
        "Explain the adjustment of the cutting height.",
        
        # VUORMAR Questions
        "List the safety instructions for the motor drum.",
        "How to enable manual mode in VUORMAR?",
        "What to do if the air pressure does not increase?",
        "How to activate the 'rearm' function?",
        
        # Cross-document
        "Compare the cleaning procedures in EM10 and VUORMAR."
    ]
    
    results = []
    summary = {
        "total_citations": 0,
        "exact_matches": 0,
        "offset_1": 0,
        "offset_gt1": 0,
        "not_found": 0
    }

    print("\n" + "="*100)
    print(f"{'QUESTION':<40} | {'DOC':<20} | {'PRED':<4} | {'ACTUAL':<8} | {'STATUS'}")
    print("-" * 100)

    for q in questions:
        logger.info(f"Querying: {q}")
        try:
            res = engine.search(query=q, k=5, use_agentic_rag=True)
            if not res.get("success"):
                continue
                
            citations = res.get("results", [])
            for cit in citations:
                summary["total_citations"] += 1
                doc_name = cit.get("source")
                pred_page = cit.get("page")
                snippet = cit.get("content", "")
                
                # Resolve PDF path
                # Try original name, then try with (spa), then try recursive search
                possible_names = [doc_name]
                if "(" not in doc_name:
                    base, ext = os.path.splitext(doc_name)
                    possible_names.append(f"{base}(spa){ext}")
                
                pdf_path = None
                search_dirs = ["docs/testing/clientSpanishDocs", "docs", "/app/docs"]
                
                for p_name in possible_names:
                    for s_dir in search_dirs:
                        candidate = os.path.join(s_dir, p_name)
                        if os.path.exists(candidate):
                            pdf_path = candidate
                            break
                    if pdf_path: break
                
                if not pdf_path:
                    # Final attempt: global recursive search
                    for root, dirs, files in os.walk("/app"):
                        for p_name in possible_names:
                            if p_name in files:
                                pdf_path = os.path.join(root, p_name)
                                break
                        if pdf_path: break
                
                if not pdf_path:
                    logger.warning(f"Could not find PDF file for: {doc_name} (checked {possible_names})")
                    continue
                
                actual_pages = find_actual_pages(pdf_path, snippet)
                
                status = "UNKNOWN"
                offset = 999
                
                if not actual_pages:
                    status = "NOT_FOUND"
                    summary["not_found"] += 1
                elif pred_page in actual_pages:
                    status = "✅ MATCH"
                    summary["exact_matches"] += 1
                    offset = 0
                else:
                    # Calculate min offset
                    offsets = [abs(p - pred_page) for p in actual_pages]
                    min_offset = min(offsets)
                    offset = min_offset
                    if min_offset == 1:
                        status = "⚠️ OFFSET_1"
                        summary["offset_1"] += 1
                    else:
                        status = f"❌ DRIFT_{min_offset}"
                        summary["offset_gt1"] += 1
                
                short_q = q[:37] + "..." if len(q) > 40 else q
                actual_str = ",".join(map(str, actual_pages)) if actual_pages else "N/A"
                print(f"{short_q:<40} | {doc_name[:20]:<20} | {pred_page:<4} | {actual_str:<8} | {status}")
                
                results.append({
                    "question": q,
                    "document": doc_name,
                    "predicted_page": pred_page,
                    "actual_pages": actual_pages,
                    "status": status,
                    "offset": offset if offset != 999 else None
                })
        except Exception as e:
            logger.error(f"Error processing question '{q}': {e}")

    print("-" * 100)
    print("\nFINAL ACCURACY SUMMARY:")
    print(f"Total Citations Verified: {summary['total_citations']}")
    print(f"Exact Page Matches:      {summary['exact_matches']} ({summary['exact_matches']/summary['total_citations'] * 100 if summary['total_citations'] > 0 else 0:.1f}%)")
    print(f"1-Page Offsets:           {summary['offset_1']} ({summary['offset_1']/summary['total_citations'] * 100 if summary['total_citations'] > 0 else 0:.1f}%)")
    print(f"Large Drift (>1 page):    {summary['offset_gt1']} ({summary['offset_gt1']/summary['total_citations'] * 100 if summary['total_citations'] > 0 else 0:.1f}%)")
    print(f"Snippet Not Found:        {summary['not_found']} ({summary['not_found']/summary['total_citations'] * 100 if summary['total_citations'] > 0 else 0:.1f}%)")
    print("="*100)

    # Save to report
    os.makedirs("reports", exist_ok=True)
    with open("reports/mcp_ground_truth_accuracy.json", "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "details": results
        }, f, indent=2)

if __name__ == "__main__":
    run_ground_truth_test()

