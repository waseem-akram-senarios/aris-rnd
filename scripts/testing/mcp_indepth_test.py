import sys
import os
import logging
import json
import time

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging with detailed format
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger("indepth_test")

from services.mcp.engine import MCPEngine
from shared.config.settings import ARISConfig

def run_indepth_matrix():
    logger.info("🚀 INITIALIZING IN-DEPTH MCP TEST MATRIX")
    engine = MCPEngine()
    
    test_cases = [
        # 1. TECHNICAL PRECISION (Specific detail)
        {
            "id": "T1",
            "category": "Technical Detail",
            "description": "Extracting specific machine parameters from EM11 (Spanish)",
            "query": "What are the specific parameters or measurements for the 'top seal' in EM11?",
            "filters": {"source": "EM11, top seal.pdf"},
            "expected_keywords": ["medidas", "barra", "ajuste", "rotulador"]
        },
        # 2. CROSS-LANGUAGE ACCURACY (English query -> Spanish doc)
        {
            "id": "T2",
            "category": "Cross-Language",
            "description": "English query for safety procedures in VUORMAR",
            "query": "List the safety maintenance steps for the motor drum according to VUORMAR.",
            "filters": {"source": "VUORMAR.pdf"},
            "expected_keywords": ["seguridad", "mantenimiento", "limpieza"]
        },
        # 3. AGENTIC RAG / MULTI-DOC (Synthesis)
        {
            "id": "T3",
            "category": "Agentic RAG",
            "description": "Comparative question requiring data from EM10 and EM11",
            "query": "Compare the cleaning or maintenance routines described in EM10 and EM11 manuals.",
            "filters": None, # Global search
            "agentic": True,
            "expected_docs": ["EM10, degasing.pdf", "EM11, top seal.pdf"]
        },
        # 4. PROCEDURAL LOGIC
        {
            "id": "T4",
            "category": "Procedural Logic",
            "description": "Troubleshooting question about air levels",
            "query": "Explain how to adjust the air level if it is too high in the bag for the degasing system.",
            "filters": {"source": "EM10, degasing.pdf"},
            "expected_keywords": ["subir", "bajar", "aire", "nivel"]
        }
    ]
    
    results = []
    
    print("\n" + "="*80)
    print(f"{'ID':<4} | {'CATEGORY':<20} | {'STATUS':<10} | {'PAGES':<10} | {'SUBCONF':<10}")
    print("-" * 80)
    
    for tc in test_cases:
        logger.info(f"--- Executing Test {tc['id']}: {tc['description']} ---")
        start_time = time.time()
        
        try:
            # Execute MCP Search Tool Simulation
            res = engine.search(
                query=tc['query'],
                filters=tc['filters'],
                k=10,
                search_mode="hybrid",
                use_agentic_rag=tc.get("agentic", True),
                include_answer=True
            )
            
            duration = time.time() - start_time
            
            if not res.get("success"):
                logger.error(f"Test {tc['id']} failed: {res.get('message')}")
                print(f"{tc['id']:<4} | {tc['category']:<20} | {'FAILED':<10} | {'N/A':<10} | {'N/A':<10}")
                results.append({"id": tc['id'], "status": "failed", "error": res.get("message")})
                continue
                
            # Analysis
            citations = res.get("results", [])
            pages = sorted(list(set([str(c.get("page", "?")) for c in citations])))
            
            # Check for multi-doc synthesis if needed
            found_docs = list(set([c.get("source") for c in citations]))
            doc_verification = "PASS"
            if tc.get("expected_docs"):
                missing = [d for d in tc["expected_docs"] if d not in found_docs]
                if missing:
                    doc_verification = f"PARTIAL (Missing {missing})"
            
            # Confidence check
            top_confidence = citations[0].get("confidence", 0) if citations else 0
            
            status = "PASS" if top_confidence > 50 else "WEAK"
            
            print(f"{tc['id']:<4} | {tc['category']:<20} | {status:<10} | {', '.join(pages):<10} | {top_confidence:>8.1f}%")
            
            results.append({
                "id": tc['id'],
                "category": tc['category'],
                "status": status,
                "duration": duration,
                "pages": pages,
                "confidence": top_confidence,
                "found_docs": found_docs,
                "answer_preview": res.get("answer", "")[:100] + "..."
            })
            
            # Log full answer for inspectability
            logger.info(f"Answer {tc['id']}: {res.get('answer')}")
            
        except Exception as e:
            logger.error(f"Exception in test {tc['id']}: {e}", exc_info=True)
            print(f"{tc['id']:<4} | {tc['category']:<20} | {'ERROR':<10} | {'N/A':<10} | {'N/A':<10}")
            results.append({"id": tc['id'], "status": "error", "error": str(e)})

    print("="*80)
    
    # Save detailed JSON report
    report_path = "reports/mcp_indepth_report.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total": len(test_cases),
                "passed": len([r for r in results if r.get("status") == "PASS"]),
                "failed": len([r for r in results if r.get("status") in ["failed", "error"]])
            },
            "details": results
        }, f, indent=2)
    
    logger.info(f"✅ In-depth test report saved to {report_path}")

if __name__ == "__main__":
    run_indepth_matrix()
