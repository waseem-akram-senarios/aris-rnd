import unittest
from unittest.mock import MagicMock, patch, mock_open
import os
import sys
import fitz

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ingestion.parsers.pymupdf_parser import PyMuPDFParser
from services.ingestion.parsers.docling_parser import DoclingParser
from services.ingestion.parsers.ocrmypdf_parser import OCRmyPDFParser
from services.ingestion.parsers.llama_scan_parser import LlamaScanParser

class TestPageNumberExtraction(unittest.TestCase):
    """
    Verify that ALL parsers correctly structure page metadata (page_blocks, offsets)
    which is critical for RetrievalEngine to find the correct page.
    """

    def setUp(self):
        # Create a real dummy PDF for parsers that check file existence
        self.dummy_pdf_path = "test_dummy.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Content on page 1")
        doc.save(self.dummy_pdf_path)
        doc.close()

    def tearDown(self):
        if os.path.exists(self.dummy_pdf_path):
            os.remove(self.dummy_pdf_path)

    def test_pymupdf_page_extraction(self):
        """Test PyMuPDF - Real execution on dummy file"""
        print("\n--- Testing PyMuPDF Page Extraction ---")
        parser = PyMuPDFParser()
        result = parser.parse(self.dummy_pdf_path)
        
        # VERIFY
        self.assertIn("--- Page 1 ---", result.text)
        self.assertIn("page_blocks", result.metadata)
        
        blocks = result.metadata["page_blocks"]
        # Check we have at least one page block
        page_blocks = [b for b in blocks if b['type'] == 'page']
        self.assertTrue(len(page_blocks) >= 1)
        self.assertEqual(page_blocks[0]["page"], 1)
        self.assertIn("start_char", page_blocks[0])
        print("✅ PyMuPDF: Metadata contains correct page_blocks")

    def test_docling_page_extraction_logic(self):
        """Test Docling Logic - Mocking internals"""
        print("\n--- Testing Docling Page Extraction Logic ---")
        parser = DoclingParser()
        
        # Mock DocumentConverter
        with patch.object(parser, 'DocumentConverter') as MockConverter:
            mock_instance = MockConverter.return_value
            mock_result = MagicMock()
            
            # Setup mock document structure
            mock_doc = MagicMock()
            mock_doc.pages = {1: MagicMock()} 
            mock_result.document = mock_doc
            
            mock_instance.convert.return_value = mock_result
            
            # Mock _extract_text_per_page
            with patch.object(parser, '_extract_text_per_page') as mock_extract:
                mock_extract.return_value = (
                    "--- Page 1 ---\nDocling Content", 
                    [{
                        'type': 'page',
                        'page': 1, 
                        'text': "Docling Content", 
                        'start_char': 0, 
                        'end_char': 30
                    }], 
                    True
                )
                
                result = parser.parse(self.dummy_pdf_path)
                
                # VERIFY
                self.assertIn("page_blocks", result.metadata)
                blocks = result.metadata["page_blocks"]
                self.assertEqual(blocks[0]["page"], 1)
                print("✅ Docling: Page extraction logic verified")

    def test_ocrmypdf_page_extraction_logic(self):
        """Test OCRMyPDF Logic - Mocking external calls"""
        print("\n--- Testing OCRMyPDF Page Extraction Logic ---")
        
        # Mock availability
        with patch.object(OCRmyPDFParser, 'is_available', return_value=True):
            parser = OCRmyPDFParser()
            
            # Mock ocrmypdf.ocr (the main library call)
            # We need to patch where it's imported in the module, or sys.modules
            with patch.dict('sys.modules', {'ocrmypdf': MagicMock()}):
                # Also patch the actual import inside the method if needed, 
                # but simplest is to patch subprocess/execution flow
                
                # Patch tempfile and fitz to simulate output read
                with patch('tempfile.NamedTemporaryFile') as mock_temp, \
                     patch('fitz.open') as mock_fitz_open:
                    
                    # Mock fitz opening the "OCR processed" file
                    mock_doc = MagicMock()
                    mock_page = MagicMock()
                    mock_page.get_text.return_value = "OCR Text"
                    mock_doc.__len__.return_value = 1
                    mock_doc.__getitem__.return_value = mock_page
                    mock_fitz_open.return_value = mock_doc
                    
                    # Patch the internal ocrmypdf.ocr call inside the method
                    # Since we can't easily reach into the method's local import, 
                    # we rely on the fact that the code does: import ocrmypdf -> ocrmypdf.ocr(...)
                    # We can patch 'services.ingestion.parsers.ocrmypdf_parser.ocrmypdf' if it was global,
                    # but it's local. 
                    # Instead, we'll patch the run mechanism or wrap the whole parse method testing logic structure?
                    # Better: Patch 'ocrmypdf.ocr' by mocking the module before import
                    
                    # Actually, let's patch the specific call inside the module context if possible
                    # or just verify logic flow.
                    
                    # Let's try patching the class method that does the work if we split it?
                    # No, let's just use sys.modules patch above and ensure fitz returns text.
                    
                    # We also need to mock os.unlink to avoid errors deleting fake temp files
                    with patch('os.unlink'):
                         result = parser.parse(self.dummy_pdf_path)

                    self.assertIn("--- Page 1 ---", result.text)
                    self.assertEqual(result.metadata['page_blocks'][0]['page'], 1)
                    print("✅ OCRMyPDF: Logic verified")

    def test_llamascan_page_extraction_logic(self):
        """Test LlamaScan Logic"""
        print("\n--- Testing LlamaScan Page Extraction Logic ---")
        with patch.object(LlamaScanParser, 'is_available', return_value=True):
            parser = LlamaScanParser()
            
            with patch.object(parser, '_ollama_generate', return_value="Vision Text"):
                result = parser.parse(self.dummy_pdf_path)
                
                self.assertIn("--- Page 1 ---", result.text)
                self.assertEqual(result.metadata['page_blocks'][0]['page'], 1)
                print("✅ LlamaScan: Logic verified")

if __name__ == '__main__':
    unittest.main()
