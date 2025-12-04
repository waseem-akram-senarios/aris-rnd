# ARIS RAG FastAPI Service

FastAPI REST API for the ARIS RAG system providing CRUD operations for document management and querying.

## Quick Start

### Installation

```bash
pip install fastapi uvicorn python-multipart
```

### Run the API

```bash
# Development
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Access Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

- `GET /` - API information
- `GET /health` - Health check
- `POST /documents` - Upload and process document
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get document by ID
- `DELETE /documents/{id}` - Delete document
- `POST /query` - Query documents
- `GET /stats` - Get system statistics

## Configuration

Set environment variables in `.env`:

```env
OPENAI_API_KEY=your_key_here
VECTOR_STORE_TYPE=faiss
CHUNKING_STRATEGY=balanced
```

See [docs/API_USAGE.md](../docs/API_USAGE.md) for detailed documentation.

