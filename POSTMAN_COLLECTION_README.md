# ARIS Gateway API - Postman Collection

This Postman collection provides comprehensive testing for all ARIS RAG Gateway API endpoints.

## 📦 Files

1. **ARIS_Gateway_API.postman_collection.json** - Main Postman collection
2. **ARIS_Gateway_API_Environment.postman_environment.json** - Environment variables

## 🚀 Quick Start

### Import into Postman

1. Open Postman
2. Click **Import** button
3. Select both JSON files:
   - `ARIS_Gateway_API.postman_collection.json`
   - `ARIS_Gateway_API_Environment.postman_environment.json`
4. Select the environment: **ARIS Gateway API Environment**

### Configure Environment

The collection uses environment variables:
- `base_url`: `http://44.221.84.58:8500` (Gateway service)
- `document_id`: Will be auto-populated after document upload
- `ingestion_url`: `http://44.221.84.58:8501` (for reference)
- `retrieval_url`: `http://44.221.84.58:8502` (for reference)

## 📋 Endpoints

### 1. Health Check
- **Method**: GET
- **URL**: `{{base_url}}/health`
- **Description**: Check Gateway service health status
- **Expected Response**: 200 OK with service status

### 2. List Documents
- **Method**: GET
- **URL**: `{{base_url}}/documents`
- **Description**: Retrieve list of all documents
- **Expected Response**: 200 OK with documents array

### 3. Upload Document
- **Method**: POST
- **URL**: `{{base_url}}/documents`
- **Body**: Form-data
  - `file`: Document file (PDF, TXT, DOCX, DOC)
  - `parser_preference`: Optional (docling, pymupdf, ocrmypdf, textract)
  - `index_name`: Optional OpenSearch index name
- **Expected Response**: 201 Created with document_id

**Note**: After upload, copy the `document_id` from response and set it in the environment variable for testing "Get Document" endpoint.

### 4. Get Document
- **Method**: GET
- **URL**: `{{base_url}}/documents/{{document_id}}`
- **Description**: Get details of a specific document
- **Expected Response**: 200 OK with document details

### 5. Query RAG
- **Method**: POST
- **URL**: `{{base_url}}/query`
- **Body**: JSON
```json
{
    "question": "What is this document about?",
    "k": 6,
    "use_mmr": true,
    "use_hybrid_search": true,
    "semantic_weight": 0.7,
    "search_mode": "hybrid",
    "use_agentic_rag": false,
    "temperature": 0.0,
    "max_tokens": 1200,
    "document_id": null,
    "active_sources": null
}
```
- **Expected Response**: 200 OK with answer, citations, and sources

### 6. Sync Status
- **Method**: GET
- **URL**: `{{base_url}}/sync/status`
- **Description**: Get synchronization status
- **Expected Response**: 200 OK with sync status

## 🔧 Request Parameters

### Query RAG Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `question` | string | required | The question to answer |
| `k` | integer | 6 | Number of chunks to retrieve |
| `use_mmr` | boolean | true | Use Maximum Marginal Relevance |
| `use_hybrid_search` | boolean | true | Use hybrid search |
| `semantic_weight` | float | 0.7 | Weight for semantic search (0.0-1.0) |
| `search_mode` | string | "hybrid" | Search mode: "semantic", "keyword", or "hybrid" |
| `use_agentic_rag` | boolean | false | Use Agentic RAG |
| `temperature` | float | 0.0 | LLM temperature (0.0-2.0) |
| `max_tokens` | integer | 1200 | Maximum tokens for response |
| `document_id` | string | null | Filter to specific document |
| `active_sources` | array | null | Filter to specific document names |

## 📝 Example Workflow

1. **Health Check** - Verify service is running
2. **List Documents** - See existing documents
3. **Upload Document** - Upload a new document
   - Copy `document_id` from response
   - Set `{{document_id}}` in environment
4. **Get Document** - Verify document was uploaded
5. **Query RAG** - Ask questions about documents
6. **Sync Status** - Check synchronization status

## 🧪 Testing Tips

1. **Use Environment Variables**: Always use `{{base_url}}` instead of hardcoded URLs
2. **Save Responses**: Use Postman's "Save Response" to keep examples
3. **Test Scripts**: Add test scripts in Postman to validate responses
4. **Collection Runner**: Use Collection Runner to test all endpoints sequentially

## 🔍 Response Examples

### Health Check Response
```json
{
    "status": "healthy",
    "service": "gateway",
    "registry_accessible": true,
    "registry_document_count": 19,
    "index_map_accessible": true
}
```

### Query Response
```json
{
    "answer": "The document is about...",
    "sources": ["document1.pdf", "document2.pdf"],
    "citations": [
        {
            "id": 1,
            "source": "document1.pdf",
            "page": 1,
            "snippet": "Relevant text snippet...",
            "similarity_score": 0.95,
            "similarity_percentage": 100.0
        }
    ],
    "num_chunks_used": 6,
    "response_time": 2.5
}
```

## 🐛 Troubleshooting

- **Connection Error**: Check if Gateway service is running on port 8500
- **404 Not Found**: Verify document_id is correct and document exists
- **Timeout**: Large documents may take time to process
- **500 Error**: Check server logs for detailed error messages

## 📚 Additional Resources

- API Documentation: `http://44.221.84.58:8500/openapi.json`
- Gateway Service: Port 8500
- Ingestion Service: Port 8501
- Retrieval Service: Port 8502


