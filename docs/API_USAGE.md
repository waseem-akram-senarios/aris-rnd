# ARIS RAG API Usage Guide

This guide explains how to use the FastAPI REST API for the ARIS RAG system.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Starting the API](#starting-the-api)
- [Endpoints](#endpoints)
- [Examples](#examples)
- [Configuration](#configuration)

## Overview

The ARIS RAG API provides REST endpoints for:
- Uploading and processing documents
- Querying documents with natural language questions
- Managing document metadata
- Retrieving system statistics

## Installation

### Prerequisites

- Python 3.10 or higher
- All dependencies from `requirements.txt`
- FastAPI and Uvicorn (add to requirements if not present)

### Install FastAPI Dependencies

```bash
pip install fastapi uvicorn python-multipart
```

## Starting the API

### Development Mode

```bash
# From project root
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at `http://localhost:8000`

### Interactive API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Endpoints

### Health Check

**GET** `/health`

Check if the API is running.

**Response:**
```json
{
  "status": "healthy"
}
```

### Root

**GET** `/`

Get API information.

**Response:**
```json
{
  "message": "ARIS RAG API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

### Upload Document

**POST** `/documents`

Upload and process a document.

**Parameters:**
- `file` (multipart/form-data): The document file (PDF, TXT, DOCX, DOC)
- `parser` (form data, optional): Parser to use (`docling`, `pymupdf`, `textract`, `auto`). Default: `docling`

**Response (201 Created):**
```json
{
  "document_name": "example.pdf",
  "status": "success",
  "chunks_created": 15,
  "tokens_extracted": 5000,
  "parser_used": "docling",
  "processing_time": 120.5,
  "extraction_percentage": 0.95,
  "images_detected": false,
  "pages": 10,
  "error": null
}
```

**Error Responses:**
- `400`: Invalid file type or processing error
- `500`: Server error during processing

### List Documents

**GET** `/documents`

List all processed documents.

**Response (200 OK):**
```json
{
  "documents": [
    {
      "document_name": "example.pdf",
      "status": "success",
      "chunks_created": 15,
      "tokens_extracted": 5000,
      "parser_used": "docling",
      "processing_time": 120.5,
      "extraction_percentage": 0.95,
      "images_detected": false,
      "pages": 10,
      "error": null
    }
  ],
  "total": 1
}
```

### Get Document

**GET** `/documents/{document_id}`

Get metadata for a specific document.

**Response (200 OK):**
```json
{
  "document_name": "example.pdf",
  "status": "success",
  "chunks_created": 15,
  "tokens_extracted": 5000,
  "parser_used": "docling",
  "processing_time": 120.5,
  "extraction_percentage": 0.95,
  "images_detected": false,
  "pages": 10,
  "error": null
}
```

**Error Responses:**
- `404`: Document not found

### Delete Document

**DELETE** `/documents/{document_id}`

Delete a document's metadata.

**Note:** This removes metadata only. Vector store cleanup requires rebuilding the entire vectorstore, which is not implemented in the current version.

**Response (204 No Content):**

**Error Responses:**
- `404`: Document not found

### Query Documents

**POST** `/query`

Query the RAG system with a natural language question.

**Request Body:**
```json
{
  "question": "What is the main topic of the document?",
  "k": 6,
  "use_mmr": true
}
```

**Parameters:**
- `question` (string, required): The question to answer
- `k` (integer, optional): Number of chunks to retrieve (1-20, default: 6)
- `use_mmr` (boolean, optional): Use Maximum Marginal Relevance for diverse results (default: true)

**Response (200 OK):**
```json
{
  "answer": "The document discusses...",
  "sources": ["example.pdf"],
  "citations": [
    {
      "id": 1,
      "source": "example.pdf",
      "page": 5,
      "snippet": "The main topic is...",
      "full_text": "...",
      "source_location": "Page 5",
      "content_type": "text",
      "image_ref": null,
      "image_info": null
    }
  ],
  "num_chunks_used": 6,
  "response_time": 2.5,
  "context_tokens": 1500,
  "response_tokens": 300,
  "total_tokens": 1800
}
```

**Error Responses:**
- `400`: No documents processed yet
- `500`: Query processing error

### Get Statistics

**GET** `/stats`

Get system statistics and metrics.

**Response (200 OK):**
```json
{
  "rag_stats": {
    "total_documents": 5,
    "total_chunks": 75,
    "total_tokens": 25000,
    "estimated_embedding_cost_usd": 0.0005
  },
  "metrics": {
    "processing": {
      "total_documents": 5,
      "successful_documents": 5,
      "avg_processing_time": 120.5,
      "parser_statistics": {...}
    },
    "queries": {
      "total_queries": 10,
      "avg_response_time": 2.5,
      "api_usage": {"openai": 10}
    },
    "costs": {...},
    "parser_comparison": {...}
  }
}
```

## Examples

### Using cURL

#### Upload a Document

```bash
curl -X POST "http://localhost:8000/documents" \
  -F "file=@example.pdf" \
  -F "parser=docling"
```

#### Query Documents

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the main topic?",
    "k": 6,
    "use_mmr": true
  }'
```

#### List Documents

```bash
curl -X GET "http://localhost:8000/documents"
```

#### Get Statistics

```bash
curl -X GET "http://localhost:8000/stats"
```

### Using Python Requests

```python
import requests

# Upload document
with open("example.pdf", "rb") as f:
    files = {"file": ("example.pdf", f, "application/pdf")}
    data = {"parser": "docling"}
    response = requests.post("http://localhost:8000/documents", files=files, data=data)
    print(response.json())

# Query
query_data = {
    "question": "What is the main topic?",
    "k": 6,
    "use_mmr": True
}
response = requests.post("http://localhost:8000/query", json=query_data)
print(response.json())

# List documents
response = requests.get("http://localhost:8000/documents")
print(response.json())

# Get statistics
response = requests.get("http://localhost:8000/stats")
print(response.json())
```

### Using JavaScript/Fetch

```javascript
// Upload document
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('parser', 'docling');

fetch('http://localhost:8000/documents', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));

// Query
fetch('http://localhost:8000/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    question: 'What is the main topic?',
    k: 6,
    use_mmr: true
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## Configuration

### Environment Variables

The API uses the same environment variables as the Streamlit app:

**Required:**
- `OPENAI_API_KEY`: OpenAI API key for embeddings and LLM

**Optional:**
- `USE_CEREBRAS`: Set to `true` to use Cerebras API (default: `false`)
- `EMBEDDING_MODEL`: Embedding model name (default: `text-embedding-3-small`)
- `OPENAI_MODEL`: OpenAI model name (default: `gpt-3.5-turbo`)
- `CEREBRAS_MODEL`: Cerebras model name (default: `llama3.1-8b`)
- `VECTOR_STORE_TYPE`: Vector store type (`faiss` or `opensearch`, default: `faiss`)
- `CHUNKING_STRATEGY`: Chunking strategy (`precise`, `balanced`, `comprehensive`, default: `balanced`)
- `VECTORSTORE_PATH`: Path for FAISS vectorstore (default: `vectorstore`)
- `AWS_OPENSEARCH_DOMAIN`: OpenSearch domain (if using OpenSearch)
- `AWS_OPENSEARCH_INDEX`: OpenSearch index name (default: `aris-rag-index`)
- `AWS_OPENSEARCH_ACCESS_KEY_ID`: OpenSearch access key
- `AWS_OPENSEARCH_SECRET_ACCESS_KEY`: OpenSearch secret key
- `AWS_OPENSEARCH_REGION`: OpenSearch region (default: `us-east-2`)

### Example .env File

```env
OPENAI_API_KEY=your_key_here
USE_CEREBRAS=false
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_MODEL=gpt-3.5-turbo
VECTOR_STORE_TYPE=faiss
CHUNKING_STRATEGY=balanced
VECTORSTORE_PATH=vectorstore
```

## Error Handling

All endpoints return appropriate HTTP status codes:

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `204 No Content`: Successful deletion
- `400 Bad Request`: Invalid request (e.g., unsupported file type)
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

Error responses include a `detail` field with error information:

```json
{
  "detail": "Error message here"
}
```

## Notes

1. **Document Processing Time**: Processing large documents (especially with Docling parser) can take 5-10 minutes. The API will block until processing is complete.

2. **Vector Store Persistence**: FAISS vectorstores are automatically saved on shutdown and loaded on startup if the `VECTORSTORE_PATH` directory exists.

3. **Document Deletion**: Currently, document deletion only removes metadata. The vectorstore is not automatically cleaned up. To fully remove a document, you would need to rebuild the entire vectorstore.

4. **Concurrency**: The API processes documents synchronously. For production use with high concurrency, consider implementing background task processing (e.g., using Celery or FastAPI BackgroundTasks).

5. **CORS**: The API includes CORS middleware allowing all origins by default. Configure appropriately for production.

## Troubleshooting

### API won't start

- Check that all dependencies are installed: `pip install -r requirements.txt fastapi uvicorn`
- Verify environment variables are set correctly
- Check that port 8000 is not already in use

### Document upload fails

- Verify file type is supported (PDF, TXT, DOCX, DOC)
- Check that parser is available (e.g., Docling requires proper installation)
- Ensure OPENAI_API_KEY is set for embeddings

### Query returns "No documents processed"

- Upload at least one document before querying
- Check that document processing completed successfully (status: "success")

### Vectorstore not persisting

- Ensure `VECTORSTORE_PATH` directory exists and is writable
- Check file permissions
- Verify FAISS is being used (OpenSearch stores in cloud automatically)

