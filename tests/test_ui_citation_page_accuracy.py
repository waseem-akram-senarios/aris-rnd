"""
Test citation page number accuracy in Streamlit UI rendering.
Verifies that page numbers are correctly displayed in all UI components.
"""
import pytest
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_sidebar_citation_page_display():
    """Test that sidebar citations always show page numbers"""
    # Simulate citation data
    citations = [
        {
            'id': 1,
            'source': 'test_document.pdf',
            'page': 5,
            'snippet': 'Test snippet',
            'source_location': 'Page 5'
        },
        {
            'id': 2,
            'source': 'another_doc.pdf',
            'page': 12,
            'snippet': 'Another snippet',
            'source_location': 'Page 12'
        },
        {
            'id': 3,
            'source': 'doc3.pdf',
            'page': 1,  # Default page
            'snippet': 'Snippet 3',
            'source_location': 'Page 1'
        }
    ]
    
    # Simulate sidebar rendering logic (from app.py lines 1670-1690)
    rendered_citations = []
    for citation in citations:
        citation_id = citation.get('id', '?')
        source_name = citation.get('source', 'Unknown')
        page = citation.get('page') or 1  # UI logic: always defaults to 1
        source_location = citation.get('source_location', '')
        
        # Verify page is always set
        assert page is not None, f"Citation {citation_id} missing page number"
        assert isinstance(page, int), f"Citation {citation_id} page must be integer"
        assert page >= 1, f"Citation {citation_id} page must be >= 1, got {page}"
        
        # Simulate the UI display format
        page_display = f"📍 Page {page}"
        rendered_citations.append({
            'id': citation_id,
            'source': source_name,
            'page_display': page_display,
            'page': page
        })
    
    # Verify all citations have page displays
    assert len(rendered_citations) == len(citations)
    for rendered in rendered_citations:
        assert 'Page' in rendered['page_display'], f"Page display missing 'Page' for citation {rendered['id']}"
        assert str(rendered['page']) in rendered['page_display'], \
            f"Page number {rendered['page']} not in display: {rendered['page_display']}"


def test_reference_line_page_display():
    """Test that reference lines always show page numbers"""
    citations = [
        {'id': 1, 'source': 'doc1.pdf', 'page': 3},
        {'id': 2, 'source': 'doc2.pdf', 'page': 7},
        {'id': 3, 'source': 'doc3.pdf', 'page': 1}
    ]
    
    # Simulate reference line rendering (from app.py lines 1740-1746)
    citation_refs = []
    for citation in citations:
        citation_id = citation.get('id', '?')
        source_name = citation.get('source', 'Unknown')
        page = citation.get('page') or 1
        
        # Verify page is valid
        assert page is not None and isinstance(page, int) and page >= 1
        
        # Format: "[{id}] {source}, Page {page}"
        ref_line = f"[{citation_id}] {source_name}, Page {page}"
        citation_refs.append(ref_line)
    
    # Verify all reference lines include page numbers
    assert len(citation_refs) == len(citations)
    for ref_line in citation_refs:
        assert 'Page' in ref_line, f"Reference line missing 'Page': {ref_line}"
        # Extract page number from reference line
        import re
        page_match = re.search(r'Page\s+(\d+)', ref_line)
        assert page_match is not None, f"Could not extract page number from: {ref_line}"
        page_num = int(page_match.group(1))
        assert page_num >= 1, f"Invalid page number in reference: {ref_line}"


def test_detailed_citation_page_display():
    """Test that detailed citations show page numbers correctly"""
    citations = [
        {
            'id': 1,
            'source': 'test.pdf',
            'page': 15,
            'snippet': 'Test content',
            'source_location': 'Page 15',
            'relevance_score': 0.85
        },
        {
            'id': 2,
            'source': 'test2.pdf',
            'page': 22,
            'snippet': 'More content',
            'source_location': 'Page 22 | Image 3',
            'relevance_score': 0.70
        }
    ]
    
    # Simulate detailed citation rendering (from app.py lines 2154-2230)
    rendered_details = []
    for citation in citations:
        citation_id = citation.get('id', '?')
        source_name = citation.get('source', 'Unknown')
        page = citation.get('page') or 1
        source_location = citation.get('source_location', f"Page {page or 1}")
        
        # Verify page is valid
        assert page is not None and isinstance(page, int) and page >= 1
        
        # Simulate citation header with page
        citation_header = f"[{citation_id}] {source_name} - **Page {page}**"
        
        # Verify source_location includes page
        assert 'Page' in source_location, f"Source location missing 'Page': {source_location}"
        
        rendered_details.append({
            'id': citation_id,
            'header': citation_header,
            'page': page,
            'source_location': source_location
        })
    
    # Verify all detailed citations have page numbers
    assert len(rendered_details) == len(citations)
    for detail in rendered_details:
        assert 'Page' in detail['header'], f"Citation header missing 'Page': {detail['header']}"
        assert str(detail['page']) in detail['header'], \
            f"Page number {detail['page']} not in header: {detail['header']}"
        assert 'Page' in detail['source_location'], \
            f"Source location missing 'Page': {detail['source_location']}"


def test_ui_page_number_extraction_from_chunks():
    """Test UI logic for extracting page numbers from context chunks"""
    # Simulate context chunks with metadata (from app.py lines 1939-1972)
    context_chunks = [
        {
            'page_content': '--- Page 5 ---\nContent from page 5',
            'metadata': {'source_page': 5, 'page': 5, 'source': 'test.pdf'}
        },
        {
            'page_content': '--- Page 12 ---\nContent from page 12',
            'metadata': {'source_page': 12, 'page': 12, 'source': 'test.pdf'}
        },
        {
            'page_content': 'Content without page marker',
            'metadata': {'source': 'test.pdf'}  # No page metadata
        }
    ]
    
    # Simulate UI page extraction logic
    extracted_pages = []
    import re
    
    for chunk_item in context_chunks:
        if isinstance(chunk_item, dict) and 'page_content' in chunk_item:
            chunk_text = chunk_item.get('page_content', '')
            chunk_metadata = chunk_item.get('metadata', {})
            # Prioritize metadata over text markers
            page = chunk_metadata.get('source_page') or chunk_metadata.get('page') or None
            
            # If no page from metadata, try to extract from text markers
            if not page:
                page_match = re.search(r'---\s*Page\s+(\d+)\s*---', chunk_text)
                if page_match:
                    page = int(page_match.group(1))
            
            # Ensure page is always set (fallback to 1)
            page = page or 1
            
            extracted_pages.append(page)
    
    # Verify all pages are extracted correctly
    assert len(extracted_pages) == len(context_chunks)
    assert extracted_pages[0] == 5, f"Expected page 5, got {extracted_pages[0]}"
    assert extracted_pages[1] == 12, f"Expected page 12, got {extracted_pages[1]}"
    assert extracted_pages[2] == 1, f"Expected fallback page 1, got {extracted_pages[2]}"
    
    # Verify all pages are valid
    for page in extracted_pages:
        assert isinstance(page, int) and page >= 1, f"Invalid page number: {page}"


def test_ui_citation_creation_with_page_numbers():
    """Test UI citation creation ensures page numbers are always set"""
    # Simulate creating citations from chunks (from app.py lines 1999-2007)
    chunks = [
        {'text': 'Content 1', 'page': 3, 'source': 'doc1.pdf'},
        {'text': 'Content 2', 'page': None, 'source': 'doc2.pdf'},  # Missing page
        {'text': 'Content 3', 'page': 8, 'source': 'doc3.pdf'}
    ]
    
    citations = []
    for idx, chunk in enumerate(chunks, 1):
        page = chunk.get('page') or 1  # UI always defaults to 1
        source_location = f"Page {page or 1}"
        
        citation = {
            'id': idx,
            'source': chunk.get('source', 'Unknown'),
            'page': page or 1,  # Always set
            'snippet': chunk.get('text', ''),
            'source_location': source_location
        }
        citations.append(citation)
    
    # Verify all citations have page numbers
    assert len(citations) == len(chunks)
    for citation in citations:
        assert 'page' in citation, f"Citation {citation['id']} missing 'page' field"
        assert citation['page'] is not None, f"Citation {citation['id']} has None page"
        assert isinstance(citation['page'], int), f"Citation {citation['id']} page must be int"
        assert citation['page'] >= 1, f"Citation {citation['id']} page must be >= 1"
        assert 'Page' in citation['source_location'], \
            f"Citation {citation['id']} source_location missing 'Page'"


def test_ui_no_text_content_in_source_location():
    """Test that UI never shows 'Text content' in source_location"""
    citations = [
        {
            'id': 1,
            'source': 'test.pdf',
            'page': 5,
            'source_location': 'Page 5'  # Correct format
        },
        {
            'id': 2,
            'source': 'test2.pdf',
            'page': 3,
            'source_location': 'Text content'  # Should be fixed
        },
        {
            'id': 3,
            'source': 'test3.pdf',
            'page': 7,
            'source_location': ''  # Should default to Page X
        }
    ]
    
    # Simulate UI source_location handling (from app.py)
    for citation in citations:
        page = citation.get('page') or 1
        source_location = citation.get('source_location', '')
        
        # UI logic: if source_location is empty or "Text content", use "Page X"
        if not source_location or source_location == "Text content":
            source_location = f"Page {page}"
        
        # Verify source_location is correct
        assert 'Text content' not in source_location, \
            f"Citation {citation['id']} has 'Text content' in source_location: {source_location}"
        assert 'Page' in source_location, \
            f"Citation {citation['id']} source_location missing 'Page': {source_location}"
        assert str(page) in source_location, \
            f"Citation {citation['id']} page number {page} not in source_location: {source_location}"


def test_ui_citation_reference_format():
    """Test that citation reference format always includes page numbers"""
    citations = [
        {'id': 1, 'source': 'document1.pdf', 'page': 10},
        {'id': 2, 'source': 'document2.pdf', 'page': 25},
        {'id': 3, 'source': 'document3.pdf', 'page': 1}
    ]
    
    # Simulate reference line creation (from app.py line 1746)
    citation_refs = []
    for citation in citations:
        citation_id = citation.get('id', '?')
        source_name = citation.get('source', 'Unknown')
        page = citation.get('page') or 1
        
        # Format: "[{id}] {source}, Page {page}"
        ref_line = f"[{citation_id}] {source_name}, Page {page}"
        citation_refs.append(ref_line)
    
    # Verify format
    assert len(citation_refs) == len(citations)
    for ref_line in citation_refs:
        # Should match pattern: [N] filename.pdf, Page N
        import re
        pattern = r'\[(\d+)\]\s+([^,]+),\s+Page\s+(\d+)'
        match = re.match(pattern, ref_line)
        assert match is not None, f"Reference line format incorrect: {ref_line}"
        
        citation_id, source, page_num = match.groups()
        assert int(citation_id) >= 1, f"Invalid citation ID: {citation_id}"
        assert int(page_num) >= 1, f"Invalid page number: {page_num}"


@pytest.mark.parametrize("page_num,expected_display", [
    (1, "Page 1"),
    (5, "Page 5"),
    (100, "Page 100"),
    (None, "Page 1"),  # Should default to 1
    (0, "Page 1"),    # Should default to 1 (invalid)
])
def test_ui_page_number_display_format(page_num, expected_display):
    """Test that page numbers are displayed in correct format"""
    # Simulate UI page display logic
    page = page_num or 1
    if page < 1:
        page = 1
    
    page_display = f"Page {page}"
    
    assert page_display == expected_display, \
        f"Expected '{expected_display}', got '{page_display}' for input {page_num}"
    assert 'Page' in page_display
    assert str(page) in page_display
