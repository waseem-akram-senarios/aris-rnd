# ARIS RAG System - Architecture Documentation

**Version:** 1.0.0  
**Date:** 2025-12-31  
**Architecture Type:** Microservices with Shared Storage

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Microservices Architecture](#microservices-architecture)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Storage Systems](#storage-systems)
6. [API Endpoints](#api-endpoints)
7. [Configuration Management](#configuration-management)
8. [Deployment Architecture](#deployment-architecture)
9. [Synchronization & State Management](#synchronization--state-management)

---

## 1. System Overview

ARIS (Advanced Retrieval and Intelligence System) is a **microservices-based RAG (Retrieval-Augmented Generation) system** designed for document processing, semantic search, and AI-powered question answering.

### Key Features

- **Microservices Architecture**: 4 independent services (Ingestion, Retrieval, Gateway, UI)
- **Multi-Parser Support**: PyMuPDF, Docling, LlamaScan, OCRmyPDF, Textract
- **Hybrid Search**: Semantic + Keyword search with OpenSearch
- **Agentic RAG**: Multi-query decomposition and synthesis
- **S3 Integration**: Document backup and registry synchronization
- **Real-time Processing**: Asynchronous document ingestion with progress tracking
- **Metrics Collection**: Comprehensive analytics for processing and queries

### Technology Stack

- **Backend**: FastAPI (Python 3.10+)
- **Frontend**: Streamlit
- **Vector Store**: AWS OpenSearch (primary), FAISS (local fallback)
- **Storage**: AWS S3, Local filesystem
- **LLM**: OpenAI GPT-4o, Cerebras Llama-3.3-70b
- **Embeddings**: OpenAI text-embedding-3-large
- **Containerization**: Docker, Docker Compose
- **Reranking**: FlashRank Cross-Encoder

---

## 2. Microservices Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                           │
│                    Streamlit UI (Port 80)                        │
│                    api/app.py                                    │
└────────────────────────────┬──────────────────────────────────────┘
                             │
                             │ HTTP Requests
                             │
┌────────────────────────────▼──────────────────────────────────────┐
│                    Gateway Service (Port 8500)                     │
│              services/gateway/main.py                             │
│              services/gateway/service.py                          │
│  • Request Routing                                                │
│  • Service Orchestration                                         │
│  • Metrics Aggregation                                           │
│  • Status Polling                                                 │
└──────────────┬───────────────────────────────┬────────────────────┘
               │                               │
               │ HTTP                          │ HTTP
               │                               │
┌──────────────▼──────────┐      ┌─────────────▼──────────────┐
│   Ingestion Service     │      │   Retrieval Service        │
│   (Port 8501)           │      │   (Port 8502)              │
│                         │      │                            │
│ • Document Upload       │      │ • Query Processing         │
│ • Parsing               │      │ • Semantic Search           │
│ • Chunking              │      │ • Reranking                │
│ • Embedding             │      │ • Answer Synthesis          │
│ • Indexing              │      │ • Citation Generation      │
│ • Progress Tracking     │      │ • Image Search             │
└──────────────┬──────────┘      └─────────────┬──────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Shared Storage    │
                    │                     │
                    │ • Document Registry │
                    │ • Index Map         │
                    │ • Vector Store      │
                    │ • S3 Backend        │
                    └─────────────────────┘
```

### Service Responsibilities

#### 1. **Ingestion Service** (`services/ingestion/`)
- **Purpose**: Document processing and indexing
- **Port**: 8501
- **Key Components**:
  - `IngestionEngine`: Core processing logic
  - `DocumentProcessor`: Orchestrates parsing, chunking, embedding
  - `parsers/`: Multi-parser system with fallback strategy
- **Responsibilities**:
  - Accept document uploads (PDF, TXT, DOCX)
  - Parse documents using appropriate parser
  - Chunk documents with token-aware splitting
  - Generate embeddings (OpenAI text-embedding-3-large)
  - Index chunks into OpenSearch
  - Update document registry
  - Track processing progress
  - Support custom OpenSearch index names

#### 2. **Retrieval Service** (`services/retrieval/`)
- **Purpose**: Query processing and answer generation
- **Port**: 8502
- **Key Components**:
  - `RetrievalEngine`: Core RAG logic
- **Responsibilities**:
  - Execute semantic/keyword/hybrid search
  - Rerank results using FlashRank
  - Generate answers using LLM (OpenAI/Cerebras)
  - Generate citations with page numbers
  - Support Agentic RAG (multi-query decomposition)
  - Image search via OCR text
  - Dynamic document index map reloading
  - S3 pre-signed URL generation for citations

#### 3. **Gateway Service** (`services/gateway/`)
- **Purpose**: API gateway and orchestrator
- **Port**: 8500
- **Key Components**:
  - `GatewayService`: Request routing and orchestration
- **Responsibilities**:
  - Route requests to appropriate microservices
  - Aggregate metrics from Ingestion and Retrieval
  - Poll ingestion status for progress updates
  - Provide unified API interface
  - Handle document registry operations
  - Proxy index management operations
  - Health checks and synchronization status

#### 4. **UI Service** (`api/app.py`)
- **Purpose**: Streamlit web interface
- **Port**: 80
- **Key Components**:
  - `ServiceContainer`: Proxies to Gateway Service
- **Responsibilities**:
  - Document upload interface
  - Query interface with advanced options
  - Metrics dashboard
  - Document library browser
  - Real-time processing status
  - Citation display with S3 preview links

---

## 3. Component Details

### 3.1 Shared Components

#### **Configuration** (`shared/config/settings.py`)
- **ARISConfig**: Centralized configuration class
- **Key Settings**:
  - Model selection (OpenAI/Cerebras)
  - Embedding model (text-embedding-3-large)
  - Chunking parameters (size: 512, overlap: 128)
  - Retrieval parameters (k: 15, reranking enabled)
  - Hybrid search weights (semantic: 0.75, keyword: 0.25)
  - Agentic RAG settings (max_sub_queries: 4)
  - S3 configuration
  - OpenSearch configuration

#### **Schemas** (`shared/schemas.py`)
- **Request Models**:
  - `QueryRequest`: Query parameters
  - `ImageQueryRequest`: Image search parameters
- **Response Models**:
  - `QueryResponse`: Query results with citations
  - `ImageQueryResponse`: Image search results
  - `DocumentMetadata`: Document information
  - `Citation`: Source citation with page numbers

#### **S3 Service** (`shared/utils/s3_service.py`)
- **Purpose**: AWS S3 integration
- **Features**:
  - Document upload/download
  - Registry synchronization
  - Pre-signed URL generation
  - Public URL generation

### 3.2 Storage Systems

#### **Document Registry** (`storage/document_registry.py`)
- **Purpose**: Metadata storage for all processed documents
- **Location**: `storage/document_registry.json`
- **Features**:
  - Thread-safe operations (file locking)
  - S3 synchronization (upload on save, download on startup)
  - Version tracking
  - Document metadata: ID, name, status, chunks, timestamps, S3 URLs

#### **Document Index Map** (`vectorstore/document_index_map.json`)
- **Purpose**: Maps document names to OpenSearch indexes
- **Format**: `{document_name: opensearch_index_name}`
- **Synchronization**: Shared volume across all services
- **Reloading**: Retrieval service checks modification time and reloads dynamically

#### **Vector Store** (`vectorstores/opensearch_store.py`)
- **Type**: AWS OpenSearch Service
- **Features**:
  - Semantic search
  - Keyword search (BM25)
  - Hybrid search (weighted combination)
  - Bulk operations (batch size: 1000)
  - Multi-index support
  - Incremental updates

#### **S3 Storage**
- **Bucket**: `intelycx-waseem-s3-bucket` (configurable)
- **Structure**:
  - `documents/{document_id}/{filename}`: Original documents
  - `configs/document_registry.json`: Registry backup
- **Features**:
  - Automatic document backup on ingestion
  - Registry sync for multi-instance deployments
  - Pre-signed URLs for secure document access

### 3.3 Parser System

#### **Parser Factory** (`services/ingestion/parsers/parser_factory.py`)
- **Strategy**: Fallback chain with automatic selection
- **Parsers** (in order of preference):
  1. **PyMuPDF**: Fast text extraction (default)
  2. **Docling**: Structured documents, tables, layouts
  3. **LlamaScan**: Advanced parsing with OCR
  4. **OCRmyPDF**: OCR for scanned PDFs
  5. **Textract**: AWS OCR service
  6. **Text Parser**: Plain text fallback

#### **Parser Features**:
- Page-level metadata extraction
- Image extraction with OCR text
- Table extraction (Docling)
- Layout preservation
- Character offset tracking for accurate page mapping

### 3.4 RAG Pipeline

#### **Query Processing Flow**:
1. **Query Reception**: Gateway → Retrieval Service
2. **Document Filtering**: Active sources or document_id filtering
3. **Index Map Reload**: Check and reload if modified
4. **Search Execution**:
   - Semantic search (vector similarity)
   - Keyword search (BM25) if hybrid enabled
   - Hybrid combination with weights
5. **Reranking**: FlashRank Cross-Encoder (top 15 → top 8)
6. **Agentic RAG** (optional):
   - Query decomposition into sub-queries
   - Parallel sub-query execution
   - Deduplication of results
   - Context aggregation
7. **Answer Generation**: LLM synthesis with context
8. **Citation Generation**:
   - Extract source, page, snippet
   - Generate S3 pre-signed URLs
   - Merge duplicate citations

---

## 4. Data Flow

### 4.1 Document Ingestion Flow

```
User Upload (UI)
    │
    ▼
Gateway Service (/documents)
    │
    ▼
Ingestion Service (/ingest)
    │
    ├─► Save to data/uploads/
    ├─► Generate document_id (UUID)
    ├─► Register in document_registry (status: "processing")
    │
    ▼
DocumentProcessor.process_document()
    │
    ├─► ParserFactory.parse_with_fallback()
    │   ├─► Try PyMuPDF
    │   ├─► Fallback to Docling if needed
    │   └─► Extract text, images, metadata
    │
    ├─► IngestionEngine.process_documents()
    │   ├─► Chunk documents (RecursiveCharacterTextSplitter)
    │   ├─► Assign page numbers (_assign_metadata_to_chunks)
    │   ├─► Generate embeddings (batch size: 1000)
    │   ├─► Upload to S3 (if enabled)
    │   └─► Index to OpenSearch (bulk size: 1000)
    │
    ├─► Update document_registry
    │   ├─► Set status: "success"
    │   ├─► Store chunks_created, metadata
    │   ├─► Save S3 URL
    │   └─► Sync to S3
    │
    └─► Update document_index_map
        └─► Map document_name → opensearch_index
```

### 4.2 Query Processing Flow

```
User Query (UI)
    │
    ▼
Gateway Service (/query)
    │
    ▼
Retrieval Service (/query)
    │
    ├─► Check and reload document_index_map
    ├─► Determine active_sources (filtering)
    │
    ▼
RetrievalEngine.query_with_rag()
    │
    ├─► Search Phase
    │   ├─► Semantic search (OpenSearch)
    │   ├─► Keyword search (if hybrid)
    │   └─► Combine results (weighted)
    │
    ├─► Reranking Phase (FlashRank)
    │   └─► Top 15 → Top 8
    │
    ├─► Agentic RAG (optional)
    │   ├─► Decompose query into sub-queries
    │   ├─► Execute sub-queries in parallel
    │   ├─► Deduplicate results
    │   └─► Aggregate context
    │
    ├─► Generation Phase
    │   ├─► Build context from chunks
    │   ├─► Call LLM (OpenAI/Cerebras)
    │   └─► Extract answer
    │
    └─► Citation Phase
        ├─► Extract source, page, snippet
        ├─► Generate S3 pre-signed URLs
        └─► Merge duplicates
```

### 4.3 Image Search Flow

```
User Image Query (UI)
    │
    ▼
Gateway Service (query_images_only)
    │
    ▼
Retrieval Service (/query/images)
    │
    ▼
RetrievalEngine.query_images()
    │
    ├─► Search OCR text in image metadata
    ├─► Rank by semantic similarity
    └─► Return image results with page numbers
```

---

## 5. Storage Systems

### 5.1 Local Storage Structure

```
aris/
├── data/
│   └── uploads/          # Original uploaded documents
├── storage/
│   ├── document_registry.json      # Document metadata
│   └── document_registry.json.version  # Version tracking
├── vectorstore/
│   └── document_index_map.json    # Document → Index mapping
└── logs/                           # Service logs
```

### 5.2 S3 Storage Structure

```
s3://intelycx-waseem-s3-bucket/
├── documents/
│   └── {document_id}/
│       └── {filename}              # Original documents
└── configs/
    └── document_registry.json      # Registry backup
```

### 5.3 OpenSearch Index Structure

- **Index Naming**: `aris-doc-{document_id}` or custom `{index_name}`
- **Document Schema**:
  ```json
  {
    "content": "chunk text",
    "metadata": {
      "source": "document_name.pdf",
      "page": 1,
      "chunk_index": 0,
      "s3_url": "s3://bucket/documents/doc_id/file.pdf",
      "token_count": 150
    },
    "vector": [0.123, 0.456, ...]  // 3072-dim embedding
  }
  ```

---

## 6. API Endpoints

### 6.1 Gateway Service (Port 8500)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with registry sync status |
| `/documents` | GET | List all documents |
| `/documents/{id}` | GET | Get document metadata |
| `/documents` | POST | Upload document (async) |
| `/query` | POST | Query RAG system |
| `/sync/status` | GET | Check synchronization status |

### 6.2 Ingestion Service (Port 8501)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with registry/index map status |
| `/ingest` | POST | Ingest document (async, returns immediately) |
| `/process` | POST | Process document (synchronous) |
| `/status/{document_id}` | GET | Get processing status |
| `/metrics` | GET | Get processing metrics |
| `/indexes/{name}/exists` | GET | Check if index exists |
| `/indexes/{base_name}/next-available` | GET | Get next available index name |

### 6.3 Retrieval Service (Port 8502)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with index map status |
| `/query` | POST | Execute RAG query |
| `/query/images` | POST | Search for images |
| `/metrics` | GET | Get retrieval metrics |

### 6.4 UI Service (Port 80)

- **Streamlit Web Interface**: Interactive UI for document upload and querying
- **No REST API**: Uses Gateway Service via `ServiceContainer`

---

## 7. Configuration Management

### 7.1 Environment Variables

**Core Configuration** (`.env`):
```bash
# API Keys
OPENAI_API_KEY=sk-...
CEREBRAS_API_KEY=...
USE_CEREBRAS=false

# Models
EMBEDDING_MODEL=text-embedding-3-large
OPENAI_MODEL=gpt-4o
CEREBRAS_MODEL=llama-3.3-70b

# Vector Store
VECTOR_STORE_TYPE=opensearch
AWS_OPENSEARCH_DOMAIN=intelycx-waseem-os
AWS_OPENSEARCH_INDEX=aris-rag-index
AWS_OPENSEARCH_ACCESS_KEY_ID=...
AWS_OPENSEARCH_SECRET_ACCESS_KEY=...
AWS_OPENSEARCH_REGION=us-east-2

# S3 Storage
ENABLE_S3_STORAGE=true
AWS_S3_BUCKET=intelycx-waseem-s3-bucket
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Chunking
DEFAULT_CHUNK_SIZE=512
DEFAULT_CHUNK_OVERLAP=128

# Retrieval
DEFAULT_RETRIEVAL_K=15
ENABLE_RERANKING=true
DEFAULT_USE_HYBRID_SEARCH=true
DEFAULT_SEMANTIC_WEIGHT=0.75

# Agentic RAG
DEFAULT_USE_AGENTIC_RAG=true
DEFAULT_MAX_SUB_QUERIES=4
```

### 7.2 Service-Specific Configuration

**Docker Compose** (`docker-compose.yml`):
- Environment variables injected per service
- Shared volumes mounted:
  - `./storage:/app/storage`
  - `./vectorstore:/app/vectorstore`
  - `./data:/app/data`
  - `./logs:/app/logs`

---

## 8. Deployment Architecture

### 8.1 Docker Compose Services

```yaml
services:
  ingestion:    # Port 8501
  retrieval:    # Port 8502
  gateway:      # Port 8500
  ui:           # Port 80
```

### 8.2 Service Dependencies

```
ui → gateway (depends_on: service_healthy)
gateway → ingestion (depends_on: service_healthy)
gateway → retrieval (depends_on: service_healthy)
```

### 8.3 Health Checks

All services implement `/health` endpoints:
- **Ingestion**: Checks registry and index map accessibility
- **Retrieval**: Checks registry, index map, and reloads index map
- **Gateway**: Checks registry and index map, lists documents
- **UI**: Streamlit health check on `/_stcore/health`

### 8.4 Deployment Process

1. **Build**: `docker-compose build`
2. **Start**: `docker-compose up -d`
3. **Health Check**: Wait for all services to be healthy
4. **Verify**: Check `/health` endpoints

---

## 9. Synchronization & State Management

### 9.1 Document Registry Synchronization

**Mechanism**:
- **Local**: File-based JSON with file locking (`fcntl`)
- **S3 Sync**: 
  - Upload on every save
  - Download on startup (if enabled)
- **Version Tracking**: `.version` file with timestamp

**Thread Safety**:
- File locking prevents concurrent write conflicts
- Atomic writes (temp file + rename)

### 9.2 Document Index Map Synchronization

**Mechanism**:
- **Shared Volume**: All services mount `./vectorstore`
- **Dynamic Reloading**: Retrieval service checks `mtime` and reloads if modified
- **Update Source**: Ingestion service writes on document processing

**Reload Trigger**:
```python
# In RetrievalEngine.query_with_rag()
self._check_and_reload_document_index_map()  # Checks mtime
```

### 9.3 S3 Synchronization

**Document Backup**:
- Uploaded during ingestion
- Stored at `s3://bucket/documents/{document_id}/{filename}`
- S3 URL stored in document registry

**Registry Backup**:
- Uploaded after every registry save
- Stored at `s3://bucket/configs/document_registry.json`
- Downloaded on service startup

### 9.4 Processing State Management

**Ingestion Progress Tracking**:
- State stored in `DocumentProcessor._processing_states`
- Exposed via `/status/{document_id}` endpoint
- Gateway polls this endpoint for UI updates

**State Structure**:
```python
{
    "document_id": "...",
    "status": "processing" | "success" | "failed",
    "progress": 0.0-1.0,
    "message": "...",
    "chunks_created": 0
}
```

---

## 10. Key Design Patterns

### 10.1 Microservices Pattern
- **Separation of Concerns**: Each service has a single responsibility
- **Independent Scaling**: Services can be scaled independently
- **Service Discovery**: Via Docker Compose service names

### 10.2 Gateway Pattern
- **Single Entry Point**: Gateway routes all requests
- **Request Aggregation**: Combines results from multiple services
- **Protocol Translation**: HTTP → Internal service calls

### 10.3 Factory Pattern
- **Parser Factory**: Selects appropriate parser based on document type
- **Fallback Strategy**: Automatic parser fallback on failure

### 10.4 Strategy Pattern
- **Chunking Strategies**: Multiple chunking algorithms
- **Search Strategies**: Semantic, keyword, hybrid
- **Reranking Strategies**: FlashRank integration

### 10.5 Observer Pattern
- **Progress Callbacks**: Real-time progress updates during ingestion
- **Metrics Collection**: Event-driven metrics gathering

---

## 11. Performance Optimizations

### 11.1 Batch Processing
- **Embedding Batch Size**: 1000 chunks per batch
- **OpenSearch Bulk Size**: 1000 documents per bulk operation
- **Parallel Processing**: ThreadPoolExecutor for I/O operations

### 11.2 Caching
- **Document Index Map**: Cached in memory, reloaded on file change
- **Embeddings**: Cached per chunk (no duplicate embedding generation)

### 11.3 Async Operations
- **Document Ingestion**: Asynchronous with background tasks
- **Query Processing**: Async HTTP calls between services
- **S3 Operations**: Async uploads/downloads

---

## 12. Error Handling & Resilience

### 12.1 Parser Fallback
- Automatic fallback to next parser on failure
- Logs parser attempts and failures

### 12.2 Service Health Checks
- All services implement health endpoints
- Docker Compose monitors health status
- Unhealthy services are restarted

### 12.3 Graceful Degradation
- S3 operations fail gracefully if disabled
- OpenSearch fallback to FAISS (if configured)
- Registry sync failures don't block operations

---

## 13. Security Considerations

### 13.1 API Security
- **CORS**: Enabled for all origins (configurable)
- **API Keys**: Stored in environment variables
- **S3 Access**: Pre-signed URLs for document access (1-hour expiry)

### 13.2 Data Security
- **File Locking**: Prevents concurrent access conflicts
- **Atomic Writes**: Prevents data corruption
- **S3 Encryption**: AWS S3 server-side encryption

---

## 14. Monitoring & Observability

### 14.1 Metrics Collection
- **Processing Metrics**: Document processing times, chunk counts
- **Query Metrics**: Query times, token usage, chunk retrieval
- **Cost Metrics**: API call costs (OpenAI/Cerebras)
- **Parser Comparison**: Parser performance metrics

### 14.2 Logging
- **Structured Logging**: JSON-formatted logs
- **Service-Specific Logs**: Separate log files per service
- **Log Levels**: INFO, WARNING, ERROR, DEBUG

### 14.3 Health Monitoring
- **Health Endpoints**: `/health` on all services
- **Synchronization Status**: `/sync/status` on Gateway
- **Docker Health Checks**: Automatic service restart on failure

---

## 15. Future Enhancements

### Planned Improvements
1. **API Authentication**: API key authentication for endpoints
2. **Process Isolation**: ProcessPoolExecutor for CPU-intensive parsing
3. **Distributed Tracing**: OpenTelemetry integration
4. **Rate Limiting**: Request rate limiting per user/service
5. **Database Backend**: Replace JSON files with PostgreSQL/MongoDB
6. **Caching Layer**: Redis for query result caching
7. **Load Balancing**: Multiple instances with load balancer

---

## 16. Conclusion

The ARIS RAG System is a **production-ready microservices architecture** designed for scalability, reliability, and high accuracy. It leverages:

- **Microservices**: Independent, scalable services
- **Shared Storage**: Synchronized state via volumes and S3
- **Advanced RAG**: Hybrid search, reranking, Agentic RAG
- **Multi-Parser Support**: Robust document parsing with fallbacks
- **S3 Integration**: Document backup and registry synchronization
- **Real-time Processing**: Asynchronous ingestion with progress tracking

The architecture supports both **local development** and **cloud deployment** with AWS services (OpenSearch, S3).

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-12-31  
**Maintained By**: ARIS Development Team
