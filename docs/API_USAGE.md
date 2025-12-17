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
- `use_hybrid_search` (boolean, optional): Use hybrid search combining semantic and keyword search
- `semantic_weight` (float, optional): Weight for semantic search in hybrid mode (0.0-1.0)
- `search_mode` (string, optional): Search mode - 'semantic', 'keyword', or 'hybrid'
- `use_agentic_rag` (boolean, optional): Use Agentic RAG with query decomposition
- `temperature` (float, optional): Temperature for LLM response (0.0-2.0)
- `max_tokens` (integer, optional): Maximum tokens for LLM response (1-4000)

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

### Update Document

**PUT** `/documents/{document_id}`

Update document metadata.

**Request Body:**
```json
{
  "document_name": "updated_name.pdf",
  "status": "success",
  "error": null
}
```

**Parameters:**
- `document_name` (string, optional): Updated document name
- `status` (string, optional): Updated status
- `error` (string, optional): Updated error message

**Response (200 OK):**
```json
{
  "document_id": "uuid-here",
  "document_name": "updated_name.pdf",
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
- `400`: No update fields provided
- `500`: Update error

### Delete Document

**DELETE** `/documents/{document_id}`

Delete a document completely from the system. This removes:
- Document metadata from registry
- Document chunks from vectorstore (FAISS or OpenSearch)
- Document images from images index (OpenSearch only)

**Response (204 No Content):**

**Error Responses:**
- `404`: Document not found
- `500`: Deletion error

### Get Document Images

**GET** `/documents/{document_id}/images?limit=100`

Get all images for a specific document (OpenSearch only).

**Parameters:**
- `limit` (integer, optional): Maximum number of images to return (default: 100)

**Response (200 OK):**
```json
{
  "document_id": "uuid-here",
  "document_name": "example.pdf",
  "images": [
    {
      "image_id": "example_pdf_image_1",
      "source": "example.pdf",
      "image_number": 1,
      "page": 5,
      "ocr_text": "Extracted text from image...",
      "metadata": {
        "drawer_references": ["D1", "D2"],
        "part_numbers": ["PN123"],
        "tools_found": ["screwdriver"]
      },
      "score": null
    }
  ],
  "total": 1
}
```

**Error Responses:**
- `404`: Document not found
- `400`: OpenSearch not configured or document has no name
- `500`: Retrieval error

### Query Images

**POST** `/query/images`

Query images directly in the images index (OpenSearch only).

**Request Body:**
```json
{
  "question": "Find images with part numbers",
  "source": "example.pdf",
  "k": 5
}
```

**Parameters:**
- `question` (string, required): Search query for images
- `source` (string, optional): Document source to filter by
- `k` (integer, optional): Number of images to retrieve (1-50, default: 5)

**Response (200 OK):**
```json
{
  "images": [
    {
      "image_id": "example_pdf_image_1",
      "source": "example.pdf",
      "image_number": 1,
      "page": 5,
      "ocr_text": "Extracted text...",
      "metadata": {...},
      "score": 0.95
    }
  ],
  "total": 1
}
```

**Error Responses:**
- `400`: OpenSearch not configured
- `500`: Query error

### Get Single Image

**GET** `/images/{image_id}`

Get a single image by ID (OpenSearch only).

**Response (200 OK):**
```json
{
  "image_id": "example_pdf_image_1",
  "source": "example.pdf",
  "image_number": 1,
  "page": 5,
  "ocr_text": "Extracted text from image...",
  "metadata": {
    "drawer_references": ["D1"],
    "part_numbers": ["PN123"],
    "tools_found": []
  },
  "score": null
}
```

**Error Responses:**
- `404`: Image not found
- `400`: OpenSearch not configured
- `500`: Retrieval error

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

### Get Chunk Statistics

**GET** `/stats/chunks`

Get chunk token statistics.

**Response (200 OK):**
```json
{
  "total_chunks": 75,
  "chunk_size_stats": {
    "min": 100,
    "max": 500,
    "mean": 300,
    "median": 320
  },
  "token_stats": {
    "min_tokens": 50,
    "max_tokens": 250,
    "mean_tokens": 150,
    "median_tokens": 160
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
    "use_mmr": true,
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

#### Update Document

```bash
curl -X PUT "http://localhost:8000/documents/{document_id}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "success",
    "document_name": "updated_name.pdf"
  }'
```

#### Delete Document

```bash
curl -X DELETE "http://localhost:8000/documents/{document_id}"
```

#### Get Document Images

```bash
curl -X GET "http://localhost:8000/documents/{document_id}/images?limit=50"
```

#### Query Images

```bash
curl -X POST "http://localhost:8000/query/images" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Find images with part numbers",
    "source": "example.pdf",
    "k": 5
  }'
```

#### Get Single Image

```bash
curl -X GET "http://localhost:8000/images/{image_id}"
```

#### Get Chunk Statistics

```bash
curl -X GET "http://localhost:8000/stats/chunks"
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

