import os
import logging
from services.mcp.engine import MCPEngine
from shared.config.settings import ARISConfig

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_mcp_accuracy():
    print("\n========================================")
    print("  MCP ACCURACY VERIFICATION TEST")
    print("========================================")
    
    print(f"\n[CONFIG] SIMPLE_QUERY_MODEL: {ARISConfig.SIMPLE_QUERY_MODEL}")
    print(f"[CONFIG] DEEP_QUERY_MODEL: {ARISConfig.DEEP_QUERY_MODEL}")
    
    # Initialize MCP engine
    mcp_engine = MCPEngine()
    
    # TEST 1: Simple Query (rag_quick_query simulation)
    print("\n--- TEST 1: rag_quick_query (Simple Mode) ---")
    simple_query = "What is the degassing process for EM10?"
    print(f"Query: {simple_query}")
    
    try:
        simple_result = mcp_engine.search(
            query=simple_query,
            k=5,
            search_mode="hybrid",
            use_agentic_rag=False,
            include_answer=True
        )
        
        if simple_result.get('success'):
            print(f"✅ Simple Mode SUCCESS")
            print(f"   Answer Length: {len(simple_result.get('answer', ''))} chars")
            print(f"   Sources: {simple_result.get('sources', [])}")
            print(f"   Citations: {len(simple_result.get('citations', []))}")
        else:
            print(f"❌ Simple Mode FAILED: {simple_result.get('error')}")
    except Exception as e:
        print(f"❌ Simple Mode ERROR: {e}")
    
    # TEST 2: Agentic Query (rag_research_query simulation)
    print("\n--- TEST 2: rag_research_query (Agentic Mode) ---")
    complex_query = "Explain the full maintenance procedure for EM10 including degassing and top seal maintenance. What are the key steps and safety precautions?"
    print(f"Query: {complex_query[:80]}...")
    
    try:
        agentic_result = mcp_engine.search(
            query=complex_query,
            k=15,
            search_mode="hybrid",
            use_agentic_rag=True,
            include_answer=True
        )
        
        if agentic_result.get('success'):
            print(f"✅ Agentic Mode SUCCESS")
            print(f"   Answer Length: {len(agentic_result.get('answer', ''))} chars")
            print(f"   Sources: {agentic_result.get('sources', [])}")
            print(f"   Citations: {len(agentic_result.get('citations', []))}")
            print(f"   Sub-Queries: {agentic_result.get('sub_queries', 'N/A')}")
        else:
            print(f"❌ Agentic Mode FAILED: {agentic_result.get('error')}")
    except Exception as e:
        print(f"❌ Agentic Mode ERROR: {e}")
    
    print("\n========================================")
    print("  VERIFICATION COMPLETE")
    print("========================================")

if __name__ == "__main__":
    test_mcp_accuracy()
