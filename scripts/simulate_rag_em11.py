import sys
import os
import logging

# Add project root to path
sys.path.append('/home/senarios/Desktop/aris')

from services.retrieval.engine import RetrievalEngine
from shared.config.config import ARISConfig

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simulate_rag")

def simulate():
    engine = RetrievalEngine()
    
    question = "¿Cómo se puede limpiar la superficie de la capa de calentamiento?"
    doc_name = "EM11, top seal.pdf"
    
    # We want to see how it retrieves and cites
    # Note: We are using the server's OpenSearch if possible, or we might need to mock retrieval
    # For now, let's just see how it handles the metadata extraction IF it had chunks
    
    print(f"Simulating query: {question}")
    print(f"Document: {doc_name}")
    
    # Let's try to find if there are any indexed chunks for this doc in the local/server environment
    # Since I don't have easy access to OpenSearch from here, I will check the engine's internal methods
    
    from langchain.docstore.document import Document
    
    # Create a mock retrieved document from Page 5
    mock_doc = Document(
        page_content="--- Page 5 ---\nSe abre la estación y se observa que la Ropex tiene restos de plástico en dos de los anillos y suciedad entre las bolsas 2 y 3. Se limpian...",
        metadata={
            "source": doc_name,
            "page": 5,
            "pages": 14
        }
    )
    
    page, page_confidence = engine._extract_page_number(mock_doc, mock_doc.page_content)
    print(f"Mock Doc (Page 5 marker): Extracted Page={page}, Confidence={page_confidence}")
    
    # Create a mock retrieved document with NO marker but page in metadata
    mock_doc_2 = Document(
        page_content="Se limpian los restos de plástico...",
        metadata={
            "source": doc_name,
            "page": 5,
            "pages": 14
        }
    )
    page_2, page_conf_2 = engine._extract_page_number(mock_doc_2, mock_doc_2.page_content)
    print(f"Mock Doc (No marker, metadata 5): Extracted Page={page_2}, Confidence={page_conf_2}")

    # Let's see if there's any logic that ADDS to the page number
    # Search for "page +" or "page + 1" in engine.py
    
simulate()
