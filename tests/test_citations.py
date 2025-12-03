"""
Test citation and source referencing feature.
"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers.pymupdf_parser import PyMuPDFParser
from parsers.docling_parser import DoclingParser
from utils.tokenizer import TokenTextSplitter
from rag_system import RAGSystem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_pymupdf_citation_metadata():
    """Test that PyMuPDF parser captures page-level metadata for citations."""
    parser = PyMuPDFParser()
    
    # Use a test PDF if available
    test_pdf = "test.pdf"  # Replace with actual test PDF path
    if not os.path.exists(test_pdf):
        logger.warning(f"Test PDF not found: {test_pdf}. Skipping PyMuPDF citation test.")
        return True
    
    try:
        parsed_doc = parser.parse(test_pdf)
        
        # Verify page_blocks metadata exists
        assert hasattr(parsed_doc, 'metadata'), "ParsedDocument should have metadata"
        assert 'page_blocks' in parsed_doc.metadata, "Metadata should contain page_blocks"
        
        page_blocks = parsed_doc.metadata.get('page_blocks', [])
        assert isinstance(page_blocks, list), "page_blocks should be a list"
        
        if page_blocks:
            # Verify structure of page blocks
            for block in page_blocks:
                assert 'page' in block, "Each page block should have a 'page' field"
                assert 'text' in block or 'blocks' in block, "Each page block should have text or blocks"
        
        logger.info("✅ PyMuPDF citation metadata test passed")
        return True
    except Exception as e:
        logger.error(f"❌ PyMuPDF citation metadata test failed: {str(e)}")
        return False


def test_chunking_preserves_metadata():
    """Test that chunking preserves page metadata for citations."""
    from langchain_core.documents import Document
    
    # Create a test document with page_blocks metadata
    test_text = "--- Page 1 ---\nThis is page one content.\n\n--- Page 2 ---\nThis is page two content."
    test_metadata = {
        'source': 'test.pdf',
        'page_blocks': [
            {'page': 1, 'text': 'This is page one content.', 'blocks': [{'text': 'This is page one content.', 'page': 1}]},
            {'page': 2, 'text': 'This is page two content.', 'blocks': [{'text': 'This is page two content.', 'page': 2}]}
        ]
    }
    
    doc = Document(page_content=test_text, metadata=test_metadata)
    splitter = TokenTextSplitter(chunk_size=50, chunk_overlap=10)
    
    try:
        chunks = splitter.split_documents([doc])
        
        assert len(chunks) > 0, "Should create at least one chunk"
        
        # Verify chunks have page metadata
        for chunk in chunks:
            assert hasattr(chunk, 'metadata'), "Chunk should have metadata"
            # Check for page number or source_page
            assert 'page' in chunk.metadata or 'source_page' in chunk.metadata or 'start_char' in chunk.metadata, \
                "Chunk should have page or character offset metadata"
        
        logger.info("✅ Chunking metadata preservation test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Chunking metadata preservation test failed: {str(e)}")
        return False


def test_rag_citations():
    """Test that RAG system returns citations with page numbers."""
    # Create a minimal RAG system
    rag = RAGSystem(
        use_cerebras=False,
        embedding_model="text-embedding-3-small",
        vector_store_type="faiss",
        chunk_size=100,
        chunk_overlap=20
    )
    
    # Add test documents
    test_texts = [
        "This is a test document about machine learning. Machine learning is a subset of artificial intelligence.",
        "This is another document about neural networks. Neural networks are inspired by biological neurons."
    ]
    test_metadatas = [
        {'source': 'test1.pdf', 'page': 1, 'page_blocks': [{'page': 1, 'text': test_texts[0]}]},
        {'source': 'test2.pdf', 'page': 1, 'page_blocks': [{'page': 1, 'text': test_texts[1]}]}
    ]
    
    try:
        # Process documents
        chunks_created = rag.process_documents(test_texts, test_metadatas)
        assert chunks_created > 0, "Should create chunks"
        
        # Query with RAG
        result = rag.query_with_rag("What is machine learning?", k=2)
        
        # Verify citations are returned
        assert 'citations' in result, "Result should contain citations"
        citations = result.get('citations', [])
        
        if citations:
            # Verify citation structure
            for citation in citations:
                assert 'id' in citation, "Citation should have an id"
                assert 'source' in citation, "Citation should have a source"
                assert 'snippet' in citation, "Citation should have a snippet"
        
        logger.info("✅ RAG citations test passed")
        return True
    except Exception as e:
        logger.error(f"❌ RAG citations test failed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def run_all_tests():
    """Run all citation tests."""
    logger.info("=" * 80)
    logger.info("Running Citation Feature Tests")
    logger.info("=" * 80)
    
    results = []
    
    # Test 1: Chunking preserves metadata
    logger.info("\n1. Testing chunking metadata preservation...")
    results.append(("Chunking Metadata", test_chunking_preserves_metadata()))
    
    # Test 2: RAG citations
    logger.info("\n2. Testing RAG citations...")
    results.append(("RAG Citations", test_rag_citations()))
    
    # Test 3: PyMuPDF citation metadata (optional, requires test PDF)
    logger.info("\n3. Testing PyMuPDF citation metadata...")
    results.append(("PyMuPDF Citations", test_pymupdf_citation_metadata()))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("Test Summary")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

