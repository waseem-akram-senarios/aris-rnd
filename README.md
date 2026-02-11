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
          │  18 tools for AI-agent access    │
          │  SSE + HTTP REST (FastMCP)       │
          └──────────────────────────────────┘
```

### Service Summary

| Service       | Port | Role                                                     |
|---------------|------|----------------------------------------------------------|
| **Gateway**   | 8500 | API gateway & orchestrator. Routes requests, manages document registry, coordinates sync between services. |
| **Ingestion** | 8501 | Document processing pipeline. Parses (Docling, PyMuPDF, LlamaScan, OCRmyPDF, Textract), chunks, embeds, and indexes into OpenSearch. |
| **Retrieval** | 8502 | Query engine. Semantic/hybrid search, FlashRank reranking, image retrieval, and LLM answer generation. |
| **MCP**       | 8503 | Model Context Protocol server. Exposes 18 tools so AI agents (Claude, Cursor, etc.) can ingest, search, and manage RAG documents. |
| **UI**        | 80   | Streamlit web interface. Document Q&A, Admin Management, and MCP Client dashboards. |

All five services run from a **single Docker image** (`aris-microservice:latest`); the `SERVICE_TYPE` environment variable selects which service starts via the entrypoint script.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- `.env` file (see [Environment Variables](#environment-variables))
- (Optional) Ollama with `llava:latest` for vision-based parsing

### 1. Build & Run (Docker Compose)

```bash
# Build the image and start all services
docker compose build
docker compose up -d

# Verify health
docker compose ps
curl http://localhost:8500/health   # Gateway
curl http://localhost:8501/health   # Ingestion
curl http://localhost:8502/health   # Retrieval
curl http://localhost:8503/health   # MCP
curl http://localhost:80/_stcore/health  # UI
```

### 2. Run Locally (Without Docker)

```bash
# Install dependencies
pip install -r shared/config/requirements.txt

# Start all services
./scripts/start_microservices.sh

# Or start individually
PYTHONPATH=. python3 -m services.ingestion.main   # :8501
PYTHONPATH=. python3 -m services.retrieval.main    # :8502
PYTHONPATH=. INGESTION_SERVICE_URL=http://localhost:8501 \
             RETRIEVAL_SERVICE_URL=http://localhost:8502 \
             python3 -m services.gateway.main      # :8500
streamlit run app.py --server.port 80              # UI
python3 -m services.mcp.main                       # :8503
```

---

## Deployment

### Deploy to Server (EC2)

The deployment script handles rsync, Docker build, and health checks in one step:

```bash
# Configure target server (defaults: 44.221.84.58, ec2-user, /opt/aris-rag)
export SERVER_IP=<your-ip>
export SERVER_USER=ec2-user
export SERVER_DIR=/opt/aris-rag

# Deploy
./scripts/deploy-microservices.sh
```

**What it does:**

1. Syncs code to the server via `rsync` (excludes `.git`, `venv`, `data/`, `tests/`)
2. Verifies `.env` is present on the server
3. Stops old containers
4. Installs host dependencies (Tesseract OCR, Ollama, `llava:latest`)
5. Builds the Docker image on the server
6. Starts all services via `docker compose up -d`
7. Runs health checks on all five services
8. Runs parser health check

### Docker Compose Files

| File                      | Purpose                                |
|---------------------------|----------------------------------------|
| `docker-compose.yml`     | **Microservices** — 5 separate containers with health checks and dependency ordering |
| `docker-compose.prod.yml`| **Monolith** (legacy) — single container exposing Streamlit + FastAPI |

---

## Microservices Detail

### Gateway (`:8500`)

The single entry point for all client requests. Manages the document registry and delegates work to Ingestion and Retrieval.

**Key endpoints:**

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

Full API docs at `http://localhost:8500/docs` (Swagger UI).

### Ingestion (`:8501`)

Processes uploaded documents through a configurable parsing pipeline.

**Parsers available:**

| Parser     | Strengths                             |
|------------|---------------------------------------|
| Docling    | High-quality PDF extraction           |
| PyMuPDF    | Fast, general-purpose PDF parsing     |
| LlamaScan  | Vision-model parsing via Ollama/LLaVA |
| OCRmyPDF   | Scanned PDF → searchable text         |
| Textract   | AWS Textract for enterprise OCR       |
| Text       | Plain text / Markdown ingestion       |

**Pipeline:** Parse → Chunk (semantic, by-page, or fixed-size) → Embed (OpenAI `text-embedding-3-large`) → Index (OpenSearch)

### Retrieval (`:8502`)

Handles all query logic with a refactored mixin-based architecture:

- **Hybrid search** — combines BM25 keyword + vector similarity
- **FlashRank reranking** — cross-encoder `ms-marco-MiniLM-L-12-v2`
- **Image search** — retrieve and query document images
- **Answer generation** — OpenAI GPT-4o / Cerebras Llama-3.3-70B
- **Multi-language** — query in any language; auto-translates if needed

### MCP Server (`:8503`)

Exposes 18 tools via the Model Context Protocol (SSE transport) so AI agents can operate on the RAG system:

| Category         | Tools                                                                 |
|------------------|-----------------------------------------------------------------------|
| **Search**       | `rag_quick_query`, `rag_research_query`, `rag_search`                |
| **Documents**    | `rag_ingest`, `rag_upload_document`, `rag_list_documents`, `rag_get_document`, `rag_update_document`, `rag_delete_document` |
| **Indexes**      | `rag_list_indexes`, `rag_get_index_info`, `rag_delete_index`         |
| **Chunks**       | `rag_list_chunks`, `rag_get_chunk`, `rag_create_chunk`, `rag_update_chunk`, `rag_delete_chunk` |
| **System**       | `rag_get_stats`                                                      |

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

### Streamlit UI (`:80`)

| Page                  | Path             | Description                                       |
|-----------------------|------------------|---------------------------------------------------|
| **Document Q&A**      | `/`              | Upload documents, ask questions, view answers      |
| **Admin Management**  | `/Admin_Management` | Manage indexes, documents, system settings      |
| **MCP Client**        | `/MCP_Client`    | Full MCP tool UI — Search, Documents, Ingest, Indexes, Chunks, System, History |

---

## Project Structure

```
aris/
├── services/
│   ├── gateway/          # API Gateway — orchestration, routing, document registry
│   │   └── main.py
│   ├── ingestion/        # Document processing — parsing, chunking, embedding
│   │   ├── main.py
│   │   └── processor.py
│   ├── retrieval/        # Query engine — search, rerank, answer generation
│   │   ├── main.py
│   │   └── engine.py     # Refactored with mixin architecture
│   ├── mcp/              # MCP Server — 18 AI-agent tools
│   │   ├── main.py
│   │   └── engine.py
│   └── language/         # Language detection & translation utilities
│
├── shared/
│   ├── config/
│   │   ├── settings.py           # ARISConfig — central configuration
│   │   ├── requirements.txt      # Python dependencies
│   │   └── accuracy_config.py    # Search accuracy tuning
│   ├── schemas.py                # Pydantic request/response models
│   └── utils/
│       ├── chunking.py           # Document chunking strategies
│       ├── embeddings.py         # OpenAI embedding client
│       ├── ocr.py                # OCR utilities (Tesseract, EasyOCR)
│       ├── s3.py                 # AWS S3 integration
│       ├── sync.py               # Cross-service sync manager
│       └── tokenizer.py          # Token counting
│
├── api/                  # Legacy monolith API (FastAPI + Streamlit wrappers)
├── pages/                # Streamlit pages (Admin, MCP Client)
├── app.py                # Streamlit main app entry point
├── mcp_server.py         # Standalone MCP server entry point
│
├── vectorstores/         # OpenSearch / FAISS integration
├── storage/              # Document registry (JSON-based)
├── scripts/
│   ├── deploy-microservices.sh      # Server deployment (rsync + docker)
│   ├── start_microservices.sh       # Local startup (all services)
│   ├── docker_entrypoint.sh         # Container entrypoint (SERVICE_TYPE routing)
│   └── install_parser_dependencies.sh
│
├── tests/
│   ├── unit/             # Unit tests
│   ├── integration/      # Parser, processor, RAG integration
│   ├── e2e/              # Microservice integration & error scenarios
│   ├── functional/       # Agentic RAG, upload, query flows
│   ├── api_tests/        # API endpoint tests
│   ├── mcp/              # MCP server tests
│   ├── ui/               # UI automation
│   ├── ui_playwright/    # Playwright browser tests for MCP Client
│   ├── performance/      # Load, scalability tests
│   ├── security/         # Auth, validation, upload security
│   ├── smoke/            # Quick startup checks
│   └── sanity/           # Critical path verification
│
├── Dockerfile            # Multi-stage build (builder → runtime)
├── docker-compose.yml    # Microservices orchestration (5 containers)
├── docker-compose.prod.yml # Legacy monolith config
├── pytest.ini            # Test configuration
└── .env                  # Environment variables (not committed)
```

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=sk-...

# AWS OpenSearch (Required for vector search)
AWS_OPENSEARCH_DOMAIN=https://your-opensearch-domain
AWS_OPENSEARCH_INDEX=aris-documents
AWS_OPENSEARCH_ACCESS_KEY_ID=AKIA...
AWS_OPENSEARCH_SECRET_ACCESS_KEY=...
AWS_OPENSEARCH_REGION=us-east-2

# AWS S3 (Optional — document backup)
ENABLE_S3_STORAGE=true
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET_NAME=your-bucket

# Cerebras (Optional — alternative LLM)
CEREBRAS_API_KEY=...

# Ollama (Optional — vision-based parsing)
OLLAMA_SERVER_URL=http://host.docker.internal:11434
LLAMA_SCAN_MODEL=llava:latest

# Vector Store Type
VECTOR_STORE_TYPE=opensearch   # or "faiss" for local
```

---

## Testing

### Run All Tests

```bash
python3 tests/run_all_tests.py
```

### Run by Category

```bash
python3 tests/run_unit_tests.py          # Unit tests
python3 tests/run_integration_tests.py   # Integration tests
python3 tests/run_quick_tests.py         # Smoke + sanity
python3 tests/run_performance_tests.py   # Load tests
```

### Playwright UI Tests (MCP Client)

```bash
pip install pytest-playwright
playwright install chromium

pytest tests/ui_playwright/ -v
```

### Test with Coverage

```bash
python3 tests/run_tests_with_coverage.py
```

---

## Tech Stack

| Layer           | Technology                                                |
|-----------------|-----------------------------------------------------------|
| **API**         | FastAPI, Uvicorn                                          |
| **UI**          | Streamlit                                                 |
| **MCP**         | FastMCP (SSE transport)                                   |
| **LLMs**        | OpenAI GPT-4o / GPT-4o-mini, Cerebras Llama-3.3-70B      |
| **Embeddings**  | OpenAI `text-embedding-3-large` (3072-dim)                |
| **Vector Store**| AWS OpenSearch (primary), FAISS (fallback)                |
| **Reranking**   | FlashRank `ms-marco-MiniLM-L-12-v2`                      |
| **Parsing**     | Docling, PyMuPDF, OCRmyPDF, Tesseract, LlamaScan (LLaVA) |
| **Storage**     | AWS S3, local filesystem                                  |
| **Container**   | Docker, Docker Compose                                    |
| **Language**    | Python 3.10                                               |
| **Testing**     | pytest, Playwright                                        |

---

## Key Scripts

| Script                                  | Description                                    |
|-----------------------------------------|------------------------------------------------|
| `scripts/deploy-microservices.sh`       | Full server deployment (rsync → build → up)    |
| `scripts/start_microservices.sh`        | Start all services locally (no Docker)         |
| `scripts/docker_entrypoint.sh`          | Container entrypoint — routes by SERVICE_TYPE  |
| `scripts/install_parser_dependencies.sh`| Install system-level parser dependencies       |

---

## Docker Details

### Single Image, Multiple Services

The `Dockerfile` builds one image with all service code. At runtime, the entrypoint reads `SERVICE_TYPE` and starts the appropriate process:

| SERVICE_TYPE | Process                                              |
|--------------|------------------------------------------------------|
| `gateway`    | `uvicorn services.gateway.main:app --port 8500`      |
| `ingestion`  | `uvicorn services.ingestion.main:app --port 8501`    |
| `retrieval`  | `uvicorn services.retrieval.main:app --port 8502`    |
| `mcp`        | `python3 -m services.mcp.main` (port 8503)           |
| `ui`         | `streamlit run app.py --server.port 80`              |

### Health Checks

All services expose `/health` endpoints. Docker Compose uses `wget`-based health checks with 30s intervals and dependency ordering:

```
UI → Gateway → Ingestion + Retrieval
MCP → Ingestion + Retrieval
```

### Volumes

| Mount            | Purpose                      |
|------------------|------------------------------|
| `./storage`      | Document registry            |
| `./data`         | Uploaded documents           |
| `./vectorstore`  | Local FAISS indexes          |
| `./logs`         | Service logs                 |

---

## Contributing

1. Create a feature branch from `main`
2. Make changes and add tests
3. Run `pytest tests/` to verify
4. Push and create a pull request

---

**Last Updated:** February 2026  

**Repositories:**
- [GitHub](https://github.com/waseem-akram-senarios/aris-rnd) · [Bitbucket](https://bitbucket.org/intelycx/intelycx-aris)
