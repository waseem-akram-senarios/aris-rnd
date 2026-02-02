import sys
import os
import logging
import json

# Add project root to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from services.mcp.engine import MCPEngine

def test_mcp_search():
    logger.info("Initializing MCPEngine...")
    engine = MCPEngine()
    
    # Test cases (similar to the ones used for direct verification)
    test_queries = [
        {
            "query": "instrucciones de seguridad",
            "filters": {"source": "VUORMAR.pdf"},
            "expected_doc": "VUORMAR.pdf"
        },
        {
            "query": "degasing procedure",
            "filters": {"source": "EM10, degasing.pdf"},
            "expected_doc": "EM10, degasing.pdf"
        }
    ]
    
    logger.info("\n" + "="*50)
    logger.info("STARTING MCP TOOL SEARCH VERIFICATION")
    logger.info("="*50)
    
    for tc in test_queries:
        logger.info(f"\nTesting MCP Search: '{tc['query']}' (Target: {tc['expected_doc']})")
        
        try:
            # Simulate mcp.tool call for rag_search
            result = engine.search(
                query=tc['query'],
                filters=tc['filters'],
                k=5,
                search_mode="hybrid",
                use_agentic_rag=True,
                include_answer=True
            )
            
            if not result.get("success"):
                logger.error(f"❌ MCP Search failed: {result.get('message')}")
                continue
                
            logger.info(f"✅ MCP Answer: {result.get('answer')[:150]}...")
            
            logger.info("MCP Formatted Results:")
            for i, res in enumerate(result.get("results", [])):
                page = res.get("page")
                source = res.get("source")
                confidence = res.get("confidence")
                snippet = res.get("snippet", "")[:100].replace('\n', ' ')
                
                logger.info(f"  [{i+1}] Page {page} | Confidence: {confidence}% | Source: {source} | Snippet: {snippet}...")
                
                if page is None:
                    logger.error(f"  ❌ FAILURE: Page number is None in result {i+1}!")
                elif source != tc['expected_doc']:
                    logger.warning(f"  ⚠️ Document mismatch: found {source} vs expected {tc['expected_doc']}")
                else:
                    logger.info(f"  ✅ Page {page} verified for {source}")
                    
        except Exception as e:
            logger.error(f"❌ MCP Search execution failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

if __name__ == "__main__":
    test_mcp_search()
