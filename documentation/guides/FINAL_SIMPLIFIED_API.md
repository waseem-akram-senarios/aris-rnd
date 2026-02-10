# Final Simplified ARIS RAG API

## API Version: 1.0.0

## Endpoints (7 Total - Minimal & Essential)

### Core (2)
- `GET /` - API information
- `GET /health` - Health check

### Documents (3)
- `POST /documents` - Upload and process document
- `GET /documents` - List all documents (includes all metadata)
- `DELETE /documents/{document_id}` - Delete document

### Query (2)
- `POST /query` - Query documents with natural language
  - Query all documents by default
  - Optional `document_id` to filter to specific document
  - Simple and reliable

- `POST /query/images` - Query images
  - Use `question` to search images semantically
  - Use empty `question` ("") and `source` to get all images for a document
  - Use `source` to filter by document name

## Removed Endpoints

All non-essential endpoints removed:

- ❌ `GET /documents/{id}` - Use `GET /documents` to list and filter
- ❌ `PUT /documents/{id}` - Not essential
- ❌ `GET /documents/{id}/images` - Use `POST /query/images` with empty question and source
- ❌ `GET /images/{id}` - Not essential
- ❌ `GET /stats` - Not essential (stats in document list)
- ❌ `GET /stats/chunks` - Consolidated
- ❌ `GET /sync/status` - Internal operation
- ❌ `POST /sync/reload-vectorstore` - Internal operation
- ❌ `POST /sync/save-vectorstore` - Internal operation
- ❌ `POST /sync/reload-registry` - Internal operation

## Usage Examples

### Upload Document
```bash
curl -X POST http://44.221.84.58:8500/documents \
  -F "file=@document.pdf" \
  -F "parser=docling"
```

### List Documents
```bash
curl http://44.221.84.58:8500/documents
```

### Query All Documents
```json
{
    "question": "What is the main topic?",
    "k": 5
}
```

### Query Specific Document
```json
{
    "question": "What information is in this document?",
    "k": 5,
    "document_id": "your-document-id"
}
```

### Get All Images for Document
```json
{
    "question": "",
    "source": "document_name.pdf",
    "k": 100
}
```

### Search Images Semantically
```json
{
    "question": "FILLING HANDLER",
    "k": 5
}
```

### Delete Document
```bash
curl -X DELETE http://44.221.84.58:8500/documents/{document_id}
```

## Benefits

1. **Minimal API** - Only 7 essential endpoints
2. **Simple** - Easy to understand and use
3. **Reliable** - Query works consistently
4. **RESTful** - Follows best practices
5. **Easy to Maintain** - Less code, fewer bugs

## Testing

Access Swagger UI: http://44.221.84.58:8500/docs

