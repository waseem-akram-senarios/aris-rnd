# Mock Mode vs Real Mode Testing

## Overview

The test suite supports two modes:
1. **Full Mock Mode** (default) - All external services mocked
2. **Real Mode** - Uses actual services when available

## Full Mock Mode (Default)

### How It Works
- All fixtures in `tests/conftest.py` attempt to create real services first
- If any service fails to initialize, it automatically falls back to a fully-mocked version
- Mocks are provided by `tests/fixtures/mock_services.py`

### What's Mocked
- **OpenAI Embeddings**: Returns fixed 3072-dimensional vectors
- **OpenAI LLM**: Returns mock responses with configurable content
- **OpenSearch**: Mocked if not available
- **ServiceContainer**: Fully mocked with all nested attributes
- **DocumentRegistry**: Dynamic in-memory storage
- **RAGSystem**: Mocked query methods with realistic responses
- **DocumentProcessor**: Mocked processing methods

### Benefits
- Tests run fast (no API calls)
- No external dependencies required
- Deterministic results
- Can run in CI/CD without credentials

## Real Mode

### How to Enable
Set environment variables for real services:
```bash
export OPENAI_API_KEY="your-key"
export AWS_OPENSEARCH_DOMAIN="your-domain"
export AWS_OPENSEARCH_ACCESS_KEY_ID="your-key"
export AWS_OPENSEARCH_SECRET_ACCESS_KEY="your-secret"
```

### When Real Services Are Used
- If all required environment variables are set
- If all dependencies are installed
- If services are reachable
- Otherwise, automatically falls back to mocks

### Benefits
- Tests actual integration with real services
- Catches real API changes
- Validates actual behavior

## Mocked Endpoints and Logic

### API Endpoints (All Mocked)
- `/documents` - Document upload, list, delete
- `/query` - Text and image queries
- `/documents/{id}/images/*` - Image endpoints
- `/documents/{id}/storage/*` - Storage endpoints
- `/v1/*` - Focused API endpoints

### Service Methods (All Mocked)
- `ServiceContainer.query_text_only()` - Returns mock answer
- `ServiceContainer.query_images_only()` - Returns mock image results
- `RAGSystem.query_with_rag()` - Returns mock RAG response
- `RAGSystem.add_documents_incremental()` - Returns mock counts
- `DocumentRegistry.add_document()` - Stores in memory
- `DocumentRegistry.list_documents()` - Returns stored documents

## Switching Between Modes

### Force Mock Mode
Tests automatically use mocks if real services fail. No action needed.

### Force Real Mode
1. Set all required environment variables
2. Ensure all dependencies are installed
3. Ensure services are reachable
4. Real services will be used automatically

## Mock Response Examples

### Query Response
```python
{
    "answer": "Mocked answer from RAG system",
    "sources": ["test_document.pdf"],
    "citations": [...],
    "num_chunks_used": 1,
    "response_time": 0.5,
    "context_tokens": 100,
    "response_tokens": 50,
    "total_tokens": 150
}
```

### Document List Response
```python
{
    "documents": [...],
    "total": 0,  # Dynamic based on added documents
    "total_chunks": 0,
    "total_images": 0
}
```

## Customizing Mocks

To customize mock behavior, edit `tests/fixtures/mock_services.py`:
- `create_mock_service_container()` - Main mock factory
- Modify return values for specific test scenarios
- Add custom side_effect functions for dynamic behavior

## Best Practices

1. **Use mocks for unit/integration tests** - Fast and deterministic
2. **Use real services for E2E tests** - When you need actual integration validation
3. **Always add documents to registry** - API checks registry before allowing queries
4. **Mock external APIs** - OpenAI, OpenSearch, etc. should be mocked in tests
5. **Test error handling** - Use mocks to simulate error conditions

## Troubleshooting

### Tests failing with "No documents have been processed yet"
- **Solution**: Add documents to registry before querying:
  ```python
  service_container.document_registry.add_document(
      "doc-1",
      {"document_name": "test.pdf", "status": "completed", "chunks_created": 5}
  )
  ```

### Tests failing with attribute errors
- **Solution**: Ensure you're using the mock service container from fixtures

### Tests skipping unexpectedly
- **Solution**: All skips have been removed. If you see a skip, it's a bug - report it.

## Conclusion

The test suite now runs in full mock mode by default, ensuring:
- ✅ All tests run (no skips)
- ✅ Fast execution (no external API calls)
- ✅ Deterministic results
- ✅ No external dependencies required
- ✅ Easy to run in CI/CD

