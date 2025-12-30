"""
Custom assertion functions for ARIS RAG System tests
"""
from typing import Dict, Any, List, Optional
from langchain_core.documents import Document


def assert_response_status(response, expected_status: int = 200):
    """Assert HTTP response has expected status code"""
    assert response.status_code == expected_status, \
        f"Expected status {expected_status}, got {response.status_code}: {response.text}"


def assert_json_response(response, expected_keys: Optional[List[str]] = None):
    """Assert response is valid JSON with expected keys"""
    assert response.headers.get("content-type", "").startswith("application/json"), \
        "Response is not JSON"
    
    data = response.json()
    assert isinstance(data, dict), "Response is not a dictionary"
    
    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Missing expected key: {key}"
    
    return data


def assert_document_structure(doc: Dict[str, Any], required_fields: Optional[List[str]] = None):
    """Assert document has required structure"""
    if required_fields is None:
        required_fields = ["document_id", "document_name", "status"]
    
    for field in required_fields:
        assert field in doc, f"Document missing required field: {field}"
        assert doc[field] is not None, f"Document field {field} is None"


def assert_chunk_valid(chunk: Document):
    """Assert chunk is valid"""
    assert hasattr(chunk, 'page_content'), "Chunk missing page_content"
    assert hasattr(chunk, 'metadata'), "Chunk missing metadata"
    assert isinstance(chunk.page_content, str), "page_content must be string"
    assert len(chunk.page_content.strip()) > 0, "page_content cannot be empty"
    assert isinstance(chunk.metadata, dict), "metadata must be dict"


def assert_query_result(result: Dict[str, Any]):
    """Assert query result has correct structure"""
    required_fields = ["answer", "sources", "citations"]
    for field in required_fields:
        assert field in result, f"Query result missing field: {field}"
    
    assert isinstance(result["answer"], str), "answer must be string"
    assert len(result["answer"]) > 0, "answer cannot be empty"
    assert isinstance(result["sources"], list), "sources must be list"
    assert isinstance(result["citations"], list), "citations must be list"
    
    # Assert all citations have valid page numbers
    for citation in result["citations"]:
        assert "page" in citation, "Citation missing 'page' field"
        page = citation.get("page")
        assert page is not None, "Citation page cannot be None"
        assert isinstance(page, int), f"Citation page must be integer, got {type(page)}"
        assert page >= 1, f"Citation page must be >= 1, got {page}"


def assert_performance_metric(
    elapsed_time: float,
    max_time: float,
    operation: str = "operation"
):
    """Assert performance metric meets requirement"""
    assert elapsed_time < max_time, \
        f"{operation} took {elapsed_time:.2f}s, expected < {max_time:.2f}s"


def assert_error_response(response, expected_status: int, expected_detail: Optional[str] = None):
    """Assert error response structure"""
    assert_response_status(response, expected_status)
    data = response.json()
    assert "detail" in data, "Error response missing 'detail' field"
    
    if expected_detail:
        assert expected_detail in data["detail"], \
            f"Expected '{expected_detail}' in error detail: {data['detail']}"


def assert_list_response(response, min_items: int = 0):
    """Assert list response structure"""
    assert_response_status(response, 200)
    data = response.json()
    assert isinstance(data, (list, dict)), "Response must be list or dict"
    
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, dict) and "documents" in data:
        items = data["documents"]
    else:
        items = data if isinstance(data, list) else []
    
    assert len(items) >= min_items, \
        f"Expected at least {min_items} items, got {len(items)}"
    
    return items
