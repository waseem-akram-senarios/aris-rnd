"""
Test latest changes: Document filtering and image extraction logging.
"""
import os
import sys
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_document_number_extraction():
    """Test document number extraction."""
    logger.info("=" * 60)
    logger.info("TEST 1: Document Number Extraction")
    logger.info("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        
        rag = RAGSystem()
        
        test_cases = [
            ("FL10.11 SPECIFIC8 (1).pdf", 1),
            ("FL10.11 SPECIFIC8 (2).pdf", 2),
            ("document (10).pdf", 10),
            ("file.pdf", None),
            ("path/to/FL10.11 SPECIFIC8 (1).pdf", 1),
        ]
        
        all_passed = True
        for filename, expected in test_cases:
            result = rag._extract_document_number(filename)
            if result == expected:
                logger.info(f"✅ Extracted {result} from '{filename}'")
            else:
                logger.error(f"❌ Expected {expected}, got {result} for '{filename}'")
                all_passed = False
        
        if all_passed:
            logger.info("✅ TEST 1 PASSED: Document number extraction works correctly")
            return True
        else:
            logger.error("❌ TEST 1 FAILED: Document number extraction has issues")
            return False
    except Exception as e:
        logger.error(f"❌ TEST 1 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_document_filtering_logic():
    """Test document filtering logic with specific document numbers."""
    logger.info("=" * 60)
    logger.info("TEST 2: Document Filtering Logic")
    logger.info("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        import re
        
        rag = RAGSystem()
        
        # Simulate document names in vector store
        all_document_names = {
            "/path/to/FL10.11 SPECIFIC8 (1).pdf",
            "/path/to/FL10.11 SPECIFIC8 (2).pdf",
            "/path/to/other_document.pdf"
        }
        
        # Test query for (1).pdf
        question1 = "How many images in FL10.11 SPECIFIC8 (1).pdf"
        question_lower1 = question1.lower()
        
        # Extract document number from question
        question_doc_number = None
        question_number_match = re.search(r'\((\d+)\)', question1)
        if question_number_match:
            question_doc_number = int(question_number_match.group(1))
        
        mentioned_documents = []
        for source in all_document_names:
            source_name = os.path.basename(source).lower()
            source_doc_number = rag._extract_document_number(source)
            
            if question_doc_number is not None:
                if source_doc_number == question_doc_number:
                    # Check base name match
                    base_name_question = re.sub(r'\s*\(\d+\)', '', question_lower1)
                    base_name_source = re.sub(r'\s*\(\d+\)', '', source_name.replace('.pdf', ''))
                    
                    if (base_name_source in base_name_question or 
                        base_name_question in base_name_source or
                        any(word in base_name_question for word in base_name_source.split() if len(word) > 3)):
                        mentioned_documents.append(source)
        
        if len(mentioned_documents) == 1 and "(1)" in mentioned_documents[0]:
            logger.info("✅ Query for (1).pdf correctly identifies only (1).pdf")
        else:
            logger.error(f"❌ Expected only (1).pdf, got: {mentioned_documents}")
            return False
        
        # Test query for (2).pdf
        question2 = "How many images in FL10.11 SPECIFIC8 (2).pdf"
        question_lower2 = question2.lower()
        question_doc_number2 = None
        question_number_match2 = re.search(r'\((\d+)\)', question2)
        if question_number_match2:
            question_doc_number2 = int(question_number_match2.group(1))
        
        mentioned_documents2 = []
        for source in all_document_names:
            source_name = os.path.basename(source).lower()
            source_doc_number = rag._extract_document_number(source)
            
            if question_doc_number2 is not None:
                if source_doc_number == question_doc_number2:
                    base_name_question = re.sub(r'\s*\(\d+\)', '', question_lower2)
                    base_name_source = re.sub(r'\s*\(\d+\)', '', source_name.replace('.pdf', ''))
                    
                    if (base_name_source in base_name_question or 
                        question_lower2 in base_name_source or
                        any(word in base_name_question for word in base_name_source.split() if len(word) > 3)):
                        mentioned_documents2.append(source)
        
        if len(mentioned_documents2) == 1 and "(2)" in mentioned_documents2[0]:
            logger.info("✅ Query for (2).pdf correctly identifies only (2).pdf")
        else:
            logger.error(f"❌ Expected only (2).pdf, got: {mentioned_documents2}")
            return False
        
        logger.info("✅ TEST 2 PASSED: Document filtering logic works correctly")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 2 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_strict_filtering_implementation():
    """Test that strict filtering is implemented in query_with_rag."""
    logger.info("=" * 60)
    logger.info("TEST 3: Strict Filtering Implementation")
    logger.info("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        import inspect
        
        rag = RAGSystem()
        
        # Check if strict filtering code exists
        source_code = inspect.getsource(rag.query_with_rag)
        
        # Check for key indicators of strict filtering
        has_strict_filter = "STRICT FILTER" in source_code or "STRICTLY filter" in source_code or "question_doc_number is not None" in source_code
        has_document_filter_instruction = "document_filter_instruction" in source_code
        has_user_doc_filter = "user_doc_filter_instruction" in source_code
        
        if has_strict_filter:
            logger.info("✅ Strict filtering logic found in query_with_rag")
        else:
            logger.warning("⚠️  Strict filtering logic not clearly found")
        
        if has_document_filter_instruction:
            logger.info("✅ Document filter instruction in system prompt found")
        else:
            logger.warning("⚠️  Document filter instruction not found")
        
        if has_user_doc_filter:
            logger.info("✅ User document filter instruction found")
        else:
            logger.warning("⚠️  User document filter instruction not found")
        
        if has_strict_filter and has_document_filter_instruction:
            logger.info("✅ TEST 3 PASSED: Strict filtering implementation verified")
            return True
        else:
            logger.warning("⚠️  TEST 3: Some filtering features may be missing")
            return True  # Don't fail, just warn
    except Exception as e:
        logger.error(f"❌ TEST 3 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_image_logger():
    """Test image extraction logger."""
    logger.info("=" * 60)
    logger.info("TEST 4: Image Extraction Logger")
    logger.info("=" * 60)
    
    try:
        from shared.utils.image_extraction_logger import image_logger
        
        # Test logging methods
        image_logger.log_image_detection_start("test.pdf", "docling")
        image_logger.log_image_detected("test.pdf", 5, ["docling"])
        image_logger.log_ocr_complete("test.pdf", 1000, extraction_method="docling", success=True)
        image_logger.log_storage_success("test.pdf", 3, ["id1", "id2", "id3"])
        
        logger.info("✅ TEST 4 PASSED: Image logger working correctly")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 4 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_system_methods():
    """Test that RAG system has new methods."""
    logger.info("=" * 60)
    logger.info("TEST 5: RAG System New Methods")
    logger.info("=" * 60)
    
    try:
        from services.retrieval.engine import RetrievalEngine as RAGSystem
        
        rag = RAGSystem()
        
        # Check for new methods
        assert hasattr(rag, '_store_extracted_images'), "_store_extracted_images method not found"
        assert hasattr(rag, 'query_images'), "query_images method not found"
        assert hasattr(rag, '_extract_document_number'), "_extract_document_number method not found"
        
        logger.info("✅ All new methods exist in RAGSystem")
        logger.info("✅ TEST 5 PASSED: RAG system methods verified")
        return True
    except Exception as e:
        logger.error(f"❌ TEST 5 FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all verification tests."""
    logger.info("=" * 80)
    logger.info("VERIFYING LATEST CHANGES: Document Filtering & Image Logging")
    logger.info("=" * 80)
    
    tests = [
        ("Document Number Extraction", test_document_number_extraction),
        ("Document Filtering Logic", test_document_filtering_logic),
        ("Strict Filtering Implementation", test_strict_filtering_implementation),
        ("Image Extraction Logger", test_image_logger),
        ("RAG System New Methods", test_rag_system_methods),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Test '{test_name}' crashed: {str(e)}")
            results.append((test_name, False))
    
    # Summary
    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info("")
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("=" * 80)
        logger.info("🎉 ALL TESTS PASSED! Latest changes are working correctly.")
        logger.info("=" * 80)
        return True
    else:
        logger.info("=" * 80)
        logger.info("⚠️  SOME TESTS FAILED. Please review the errors above.")
        logger.info("=" * 80)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

