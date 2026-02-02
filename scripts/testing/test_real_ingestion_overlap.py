
import sys
import os
import logging
try:
    from langchain.docstore.document import Document
except ImportError:
    from langchain_core.documents import Document

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from services.ingestion.engine import IngestionEngine
    from shared.config.settings import ARISConfig
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

# Mocking configuration to avoid needing real OpenSearch/AWS creds for this unit test
ARISConfig.AWS_OPENSEARCH_DOMAIN = "mock-domain"
ARISConfig.AWS_OPENSEARCH_INDEX = "mock-index"

def test_ingestion_overlap_logic():
    print("==================================================")
    print("TESTING INGESTION ENGINE PAGE ASSIGNMENT LOGIC")
    print("==================================================")
    
    # Initialize engine (mocking dependencies where possible)
    # We only need the _assign_metadata_to_chunks method, so minimal init is fine
    try:
        engine = IngestionEngine(opensearch_domain="mock-domain", vector_store_type="opensearch")
    except Exception as e:
        print(f"Engine init warning (expected if no AWS creds): {e}")
        # We can still test the method if we instantiate it or use it unbound if it was static (it's not)
        # But wait, the __init__ validation might block us.
        # Let's patch the __init__ or just mock the instance.
        class MockEngine(IngestionEngine):
            def __init__(self):
                pass
        engine = MockEngine()

    
    # Setup Data
    # Page 1: 0-1000
    # Page 2: 1000-2000
    # Page 3: 2000-3000
    page_blocks = [
        {'page': 1, 'start_char': 0, 'end_char': 1000},
        {'page': 2, 'start_char': 1000, 'end_char': 2000},
        {'page': 3, 'start_char': 2000, 'end_char': 3000}
    ]
    
    metadata = {
        'page_blocks': page_blocks,
        'source': 'test_doc.pdf'
    }
    
    # Test Cases
    chunks = []
    
    # Case 1: Chunk straddling Page 1 and 2 (mostly Page 1)
    # 0-900 (Page 1) -> Start 800, End 1100 (300 chars total)
    # 200 chars on P1 (800-1000), 100 chars on P2 (1000-1100) -> Expect Page 1
    c1 = Document(page_content="x"*300, metadata={'start_index': 800})
    chunks.append(c1)
    
    # Case 2: Chunk straddling Page 1 and 2 (mostly Page 2)
    # Start 950, End 1250 (300 chars)
    # 50 chars on P1 (950-1000), 250 chars on P2 (1000-1250) -> Expect Page 2
    c2 = Document(page_content="x"*300, metadata={'start_index': 950})
    chunks.append(c2)
    
    # Case 3: Chunk spanning 3 pages (mostly Page 2)
    # Start 900, End 2100 (1200 chars)
    # 100 on P1, 1000 on P2, 100 on P3 -> Expect Page 2
    c3 = Document(page_content="x"*1200, metadata={'start_index': 900})
    chunks.append(c3)

    # Run logic
    print("\nRunning `_assign_metadata_to_chunks`...")
    # We need to bind the method to our mock engine if we used the Mock class
    # Since we inherited, it should have the method.
    processed_chunks = engine._assign_metadata_to_chunks(chunks, metadata)
    
    # Validation
    failures = 0
    
    print("\nResults:")
    
    # Check Case 1
    p1 = processed_chunks[0].metadata['page']
    print(f"Case 1 (Mostly Page 1): Assigned Page {p1}")
    if p1 != 1:
        print("❌ FAILED: Expected Page 1")
        failures += 1
    else:
        print("✅ PASSED")

    # Check Case 2
    p2 = processed_chunks[1].metadata['page']
    print(f"Case 2 (Mostly Page 2): Assigned Page {p2}")
    if p2 != 2:
        print("❌ FAILED: Expected Page 2")
        failures += 1
    else:
        print("✅ PASSED")
        
    # Check Case 3
    p3 = processed_chunks[2].metadata['page']
    print(f"Case 3 (Span 3 pages, mostly 2): Assigned Page {p3}")
    if p3 != 2:
        print("❌ FAILED: Expected Page 2")
        failures += 1
    else:
        print("✅ PASSED")

    if failures == 0:
        print("\n🎉 ALL TESTS PASSED: The new overlap logic is working correctly in the actual class method.")
        sys.exit(0)
    else:
        print(f"\n❌ {failures} TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    test_ingestion_overlap_logic()
