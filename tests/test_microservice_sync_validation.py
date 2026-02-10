import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from services.gateway.service import GatewayService
from services.retrieval.main import app as retrieval_app
from services.ingestion.main import app as ingestion_app
from shared.schemas import QueryRequest

@pytest.mark.asyncio
async def test_gateway_query_tracing_and_params():
    """Test that GatewayService.query_with_rag sends tracing headers and multilingual params."""
    service = GatewayService()
    service.retrieval_url = "http://retrieval:8502"
    
    # Mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "answer": "test answer",
        "sources": [],
        "citations": [],
        "num_chunks_used": 0,
        "response_time": 0.1,
        "context_tokens": 0,
        "response_tokens": 0,
        "total_tokens": 0
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        
        # Now query_with_rag is async, so we await it
        result = await service.query_with_rag(
            question="¿Qué es ARIS?",
            response_language="Spanish",
            auto_translate=True,
            filter_language="spa"
        )
        
        # Verify outgoing call
        args, kwargs = mock_post.call_args
        url = args[0]
        payload = kwargs["json"]
        headers = kwargs["headers"]
        
        assert url == "http://retrieval:8502/query"
        assert payload["response_language"] == "Spanish"
        assert payload["auto_translate"] is True
        assert payload["filter_language"] == "spa"
        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) > 0

def test_retrieval_endpoint_sync():
    """Test that Retrieval Service endpoint correctly receives and processes multilingual params."""
    from services.retrieval.main import get_engine, app
    
    mock_engine = MagicMock()
    mock_engine.query_with_rag.return_value = {
        "answer": "mocked",
        "sources": [],
        "citations": [],
        "num_chunks_used": 0,
        "response_time": 0.0,
        "context_tokens": 0,
        "response_tokens": 0,
        "total_tokens": 0
    }
    
    # Use dependency_overrides for reliable mocking in FastAPI
    app.dependency_overrides[get_engine] = lambda: mock_engine
    
    try:
        with TestClient(app) as client:
            response = client.post(
                "/query",
                json={
                    "question": "test query",
                    "response_language": "French",
                    "auto_translate": True,
                    "filter_language": "fra"
                },
                headers={"X-Request-ID": "test-trace-id"}
            )
            
            assert response.status_code == 200
            # Verify engine was called with correct params
            mock_engine.query_with_rag.assert_called()
            call_kwargs = mock_engine.query_with_rag.call_args[1]
            assert call_kwargs["response_language"] == "French"
            assert call_kwargs["auto_translate"] is True
            assert call_kwargs["filter_language"] == "fra"
    finally:
        # Clear overrides to avoid affecting other tests
        app.dependency_overrides = {}

def test_ingestion_endpoint_sync():
    """Test that Ingestion Service endpoint correctly receives and processes language parameter."""
    with patch("services.ingestion.main.get_processor") as mock_get_processor:
        mock_processor = MagicMock()
        mock_get_processor.return_value = mock_processor
        
        # Mock file for upload
        from io import BytesIO
        file_content = b"multilingual content"
        file = BytesIO(file_content)
        
        with TestClient(ingestion_app) as client:
            response = client.post(
                "/ingest",
                files={"file": ("test.txt", file, "text/plain")},
                data={"language": "spa"},
                headers={"X-Request-ID": "ingest-trace-id"}
            )
            
            assert response.status_code == 201
            assert response.json()["status"] == "processing"

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
