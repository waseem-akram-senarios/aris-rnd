# Simplified ARIS RAG API - Final Endpoints

## API Version: 1.0.0

### Core Endpoints
- `GET /` - API information
- `GET /health` - Health check

### Document Management (CRUD)
- `POST /documents` - Upload and process document
- `GET /documents` - List all documents
- `GET /documents/{document_id}` - Get document by ID
- `PUT /documents/{document_id}` - Update document metadata
- `DELETE /documents/{document_id}` - Delete document

### Query Endpoints
- `POST /query` - Query documents (simplified, works reliably)
  - Query all documents by default
  - Optional `document_id` to filter to specific document
  - Graceful fallback if filtering fails

### Image Endpoints
- `GET /documents/{document_id}/images` - Get all images for a document
- `GET /images/{image_id}` - Get single image by ID
- `POST /query/images` - Query images with semantic search

### Statistics
- `GET /stats` - Get comprehensive statistics (includes chunk stats)

## Removed Endpoints

The following endpoints have been removed to simplify the API:

- ❌ `GET /sync/status` - Internal operation
- ❌ `POST /sync/reload-vectorstore` - Internal operation
- ❌ `POST /sync/save-vectorstore` - Internal operation
- ❌ `POST /sync/reload-registry` - Internal operation
- ❌ `GET /stats/chunks` - Consolidated into `/stats`

## Query Endpoint - Simplified

### Before (Complex)
- 80+ lines of code
- Complex document_index_map lookups
- Multiple fallback strategies
- Hard to debug

### After (Simple)
- ~40 lines of code
- Simple filtering logic
- Graceful fallback
- Easy to understand

### Example Usage

**Query all documents:**
```json
{
    "question": "What is the main topic?",
    "k": 5
}
```

**Query specific document:**
```json
{
    "question": "What information is in this document?",
    "k": 5,
    "document_id": "your-document-id"
}
```

**Query with all parameters:**
```json
{
    "question": "What is the main topic?",
    "k": 6,
    "use_mmr": true,
    "use_hybrid_search": true,
    "semantic_weight": 0.7,
    "search_mode": "hybrid",
    "temperature": 0.7,
    "max_tokens": 1000,
    "document_id": "your-document-id"
}
```

## Benefits

1. **Simpler** - Fewer endpoints, easier to understand
2. **More Reliable** - Query works even when mappings fail
3. **RESTful** - Follows industry best practices
4. **Easier to Use** - Less complexity for API consumers
5. **Better Maintainability** - Less code, easier to debug

## Testing

Test the simplified API:
```bash
# Health check
curl http://44.221.84.58:8500/health

# Query (simple)
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "k": 5}'

# Query with document_id
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "k": 5, "document_id": "your-id"}'
```

Or use Swagger UI: http://44.221.84.58:8500/docs

