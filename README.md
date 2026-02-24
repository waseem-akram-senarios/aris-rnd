# ARIS RAG System

**Advanced Retrieval-Augmented Generation** platform built on a microservices architecture.
Ingest documents, run semantic search, and get AI-generated answers — all exposed through REST APIs, a Streamlit UI, and an MCP server for AI-agent integration.

---

## Architecture

```
                         ┌──────────────────────────┐
                         │    Streamlit UI (:80)     │
                         │  Document Q&A · MCP Client│
                         └────────────┬─────────────┘
                                      │
                  ┌───────────────────▼───────────────────┐
                  │         Gateway  (:8500)               │
                  │   Orchestrator · Document Registry      │
                  └──┬──────────────────────────────┬──────┘
                     │                              │
          ┌──────────▼──────────┐       ┌──────────▼──────────┐
          │  Ingestion (:8501)  │       │  Retrieval (:8502)  │
          │  Parse · Chunk      │       │  Search · Rerank    │
          │  Embed · Index      │       │  Answer Generation  │
          └──────────┬──────────┘       └──────────┬──────────┘
                     │                              │
                     └──────────┬───────────────────┘
                                │
               ┌────────────────▼────────────────┐
               │        Shared Storage           │
               │  AWS OpenSearch · S3 · Registry │
               └─────────────────────────────────┘

          ┌──────────────────────────────────┐
          │       MCP Server (:8503)         │
          │  7 tools · SSE + HTTP REST       │
          │  (FastMCP)                       │
          └──────────────────────────────────┘
```

### Service Summary

| Service       | Port | Role |
|---------------|------|------|
| **Gateway**   | 8500 | API gateway & orchestrator. Routes requests, manages document registry, coordinates sync. |
| **Ingestion** | 8501 | Document processing pipeline. Parses, chunks, embeds, and indexes into OpenSearch. |
| **Retrieval** | 8502 | Query engine. Semantic/hybrid search, FlashRank reranking, image retrieval, LLM answer generation. |
| **MCP**       | 8503 | Model Context Protocol server. 7 tools for AI agents (Claude, Cursor, etc.). |
| **UI**        | 80   | Streamlit web interface. Document Q&A, Admin Management, MCP Client. |

All five services run from a **single Docker image** (`aris-microservice:latest`); the `SERVICE_TYPE` environment variable selects which service starts.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- `.env` file (see [Environment Variables](#environment-variables))
- (Optional) Ollama with `llava:latest` for vision-based parsing

### Build & Run

```bash
docker compose build
docker compose up -d

# Verify health
curl http://localhost:8500/health   # Gateway
curl http://localhost:8501/health   # Ingestion
curl http://localhost:8502/health   # Retrieval
curl http://localhost:8503/health   # MCP
```

### Run Locally

```bash
pip install -r shared/config/requirements.txt
./scripts/start_microservices.sh
```

---

## Gateway API Endpoints (`:8500`)

| Method | Path                            | Description                      |
|--------|---------------------------------|----------------------------------|
| POST   | `/ingest`                       | Upload and ingest a document     |
| POST   | `/query`                        | RAG query (text + images)        |
| POST   | `/query/text`                   | Text-only query                  |
| POST   | `/query/images`                 | Image-only query                 |
| GET    | `/documents`                    | List all documents               |
| GET    | `/documents/{id}`               | Get document metadata            |
| PUT    | `/documents/{id}`               | Update document metadata         |
| DELETE | `/documents/{id}`               | Delete document from all stores  |
| GET    | `/documents/{id}/storage/status`| Storage status                   |
| GET    | `/documents/{id}/pages/{page}`  | Page content                     |
| GET    | `/health`                       | Service health                   |

Full Swagger docs at `http://localhost:8500/docs`.

---

## MCP Server Tools (`:8503`)

| Tool                      | Description                                          |
|---------------------------|------------------------------------------------------|
| `search_knowledge_base`   | Semantic/hybrid search with reranking and AI answers |
| `ingest_document`         | Upload and process a document into the RAG system    |
| `list_documents`          | List all ingested documents with metadata            |
| `get_document_status`     | Get detailed status of a specific document           |
| `delete_document`         | Remove a document from all stores                    |
| `manage_index`            | List, inspect, or delete OpenSearch indexes          |
| `get_system_stats`        | System statistics (documents, queries, costs)        |

**Connect from Claude Desktop / Cursor:**
```json
{
  "mcpServers": {
    "aris-rag": {
      "url": "http://localhost:8503/sse"
    }
  }
}
```

---

## Project Structure

```
aris-rag/
├── services/
│   ├── gateway/          # API Gateway — orchestration, routing, document registry
│   ├── ingestion/        # Document processing — parsing, chunking, embedding
│   ├── retrieval/        # Query engine — search, rerank, answer generation
│   ├── mcp/              # MCP Server — 7 AI-agent tools
│   └── language/         # Language detection & translation
│
├── shared/
│   ├── config/           # Settings, requirements, accuracy config
│   ├── schemas.py        # Pydantic request/response models
│   └── utils/            # Chunking, embeddings, OCR, S3, sync
│
├── api/                  # Streamlit API layer
├── pages/                # Streamlit pages (Admin, MCP Client)
├── app.py                # Streamlit entry point
├── vectorstores/         # OpenSearch / FAISS integration
├── storage/              # Document registry
├── metrics/              # RAG metrics collector
├── scripts/              # Deploy, entrypoint, parser setup
├── tests/                # Unit, integration, e2e, MCP, UI tests
├── docs/                 # API reference, accuracy guides
│
├── Dockerfile            # Multi-stage build
├── docker-compose.yml    # 5-container orchestration
├── pytest.ini
└── .env                  # Not committed
```

---

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# AWS OpenSearch
AWS_OPENSEARCH_DOMAIN=https://your-opensearch-domain
AWS_OPENSEARCH_INDEX=aris-documents
AWS_OPENSEARCH_ACCESS_KEY_ID=AKIA...
AWS_OPENSEARCH_SECRET_ACCESS_KEY=...
AWS_OPENSEARCH_REGION=us-east-2

# AWS S3 (Optional)
ENABLE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
S3_BUCKET_NAME=your-bucket

# Cerebras (Optional)
CEREBRAS_API_KEY=...

# Vector Store
VECTOR_STORE_TYPE=opensearch
```

---

## Tech Stack

| Layer           | Technology                                                |
|-----------------|-----------------------------------------------------------|
| **API**         | FastAPI, Uvicorn                                          |
| **UI**          | Streamlit                                                 |
| **MCP**         | FastMCP (SSE transport)                                   |
| **LLMs**        | OpenAI GPT-4o, Cerebras Llama-3.3-70B                    |
| **Embeddings**  | OpenAI `text-embedding-3-large` (3072-dim)                |
| **Vector Store**| AWS OpenSearch (primary), FAISS (fallback)                |
| **Reranking**   | FlashRank `ms-marco-MiniLM-L-12-v2`                      |
| **Parsing**     | Docling, PyMuPDF, OCRmyPDF, Tesseract, LlamaScan (LLaVA) |
| **Storage**     | AWS S3, local filesystem                                  |
| **Container**   | Docker, Docker Compose                                    |
| **Testing**     | pytest, Playwright                                        |

---

## Testing

```bash
pytest tests/ -v                       # All tests
pytest tests/unit/ -v                  # Unit tests
pytest tests/e2e/ -v                   # End-to-end
pytest tests/ui_playwright/ -v         # UI tests
```

---

**Last Updated:** February 2026

**Repository:** [Bitbucket](https://bitbucket.org/intelycx/aris-rag)
