# ARIS RAG System - Comprehensive Codebase Study

**Date:** 2025-01-XX  
**System:** ARIS (Advanced Retrieval and Intelligence System)  
**Architecture:** Pure Microservices-based RAG System (Monolithic Components Removed)

---

## Executive Summary

ARIS is a **production-ready, pure microservices-based RAG (Retrieval-Augmented Generation) system** designed for document processing, semantic search, and AI-powered question answering. The system demonstrates sophisticated architecture patterns, robust error handling, and comprehensive feature sets. All monolithic components have been removed in favor of a clean microservices architecture.

### Key Highlights

- **4 Independent Microservices**: Ingestion, Retrieval, Gateway, UI
- **No Monolithic Components**: All functionality routed through microservices
- **Multi-Parser Support**: PyMuPDF, Docling, LlamaScan, OCRmyPDF, Textract with intelligent fallback
- **Hybrid Search**: Semantic + Keyword search with OpenSearch
- **Agentic RAG**: Multi-query decomposition and synthesis
- **S3 Integration**: Document backup and registry synchronization
- **Real-time Processing**: Asynchronous document ingestion with progress tracking
- **Advanced Features**: OCR, image search, page-level queries, citation generation

---

## Architecture Overview

### Microservices Structure

```
┌─────────────────────────────────────────────────────────┐
│                    UI Service (Port 80)                 │
│              Streamlit Interface (api/app.py)            │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ HTTP Requests
                     │
┌────────────────────▼────────────────────────────────────┐
│              Gateway Service (Port 8500)                 │
│         services/gateway/main.py + service.py           │
│  • Request Routing & Orchestration                      │
│  • Metrics Aggregation                                  │
│  • Status Polling                                       │
└──────────────┬───────────────────────┬──────────────────┘
               │                       │
               │ HTTP                  │ HTTP
               │                       │
┌──────────────▼──────────┐  ┌────────▼──────────────┐
│   Ingestion Service     │  │   Retrieval Service   │
│   (Port 8501)           │  │   (Port 8502)         │
│                         │  │                       │
│ • Document Upload       │  │ • Query Processing    │
│ • Parsing               │  │ • Semantic Search     │
│ • Chunking              │  │ • Reranking           │
│ • Embedding             │  │ • Answer Synthesis    │
│ • Indexing              │  │ • Citation Generation │
│ • Progress Tracking     │  │ • Image Search        │
└──────────────┬──────────┘  └────────┬──────────────┘
               │                      │
               └──────────┬───────────┘
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
- **Key Components**:
  - `IngestionEngine`: Core processing logic with adaptive chunking
  - `DocumentProcessor`: Orchestrates parsing, chunking, embedding
  - `parsers/`: Multi-parser system with intelligent fallback
- **Features**:
  - Accepts PDF, TXT, DOCX, DOC
  - Token-aware chunking with configurable size/overlap
  - Batch embedding generation (1000 chunks/batch)
  - OpenSearch indexing with per-document indexes
  - Progress tracking with callbacks
  - Adaptive chunking for large documents

#### 2. **Retrieval Service** (`services/retrieval/`)
- **Purpose**: Query processing and answer generation
- **Key Components**:
  - `RetrievalEngine`: Core RAG logic with Agentic RAG support
- **Features**:
  - Semantic/keyword/hybrid search
  - FlashRank reranking (top 15 → top 8)
  - Agentic RAG with query decomposition
  - Citation generation with page numbers
  - Image search via OCR text
  - Dynamic index map reloading

#### 3. **Gateway Service** (`services/gateway/`)
- **Purpose**: API gateway and orchestrator
- **Key Components**:
  - `GatewayService`: Request routing and orchestration
- **Features**:
  - Routes requests to appropriate microservices
  - Aggregates metrics from Ingestion and Retrieval
  - Polls ingestion status for progress updates
  - Fallback to direct processing if services unavailable
  - Unified API interface

#### 4. **UI Service** (`api/app.py`)
- **Purpose**: Streamlit web interface
- **Key Components**:
  - `ServiceContainer`: Proxies to Gateway Service
- **Features**:
  - Document upload interface
  - Query interface with advanced options
  - Metrics dashboard
  - Document library browser
  - Real-time processing status

---

## Core Components Deep Dive

### 1. Parser System (`services/ingestion/parsers/`)

**Architecture**: Factory pattern with intelligent fallback chain

**Parsers** (in order of preference):
1. **PyMuPDF**: Fast text extraction (default, fastest)
2. **Docling**: Structured documents, tables, layouts, OCR
3. **LlamaScan**: Advanced parsing with OCR via Ollama
4. **OCRmyPDF**: OCR for scanned PDFs
5. **Textract**: AWS OCR service
6. **Text Parser**: Plain text fallback

**Fallback Strategy**:
- Detects PDF type (text-based vs image-heavy)
- For image-heavy PDFs: Prefers Docling for OCR capabilities
- Compares extraction quality (character count, confidence)
- Falls back gracefully on timeout/failure
- Supports explicit parser selection (no fallback)

**Key Features**:
- Page-level metadata extraction
- Image extraction with OCR text
- Table extraction (Docling)
- Character offset tracking for accurate page mapping
- Progress callbacks for long operations

### 2. Document Processing Pipeline

**Flow**:
```
Upload → Parser Selection → Text Extraction → Chunking → Embedding → Indexing
```

**Chunking Strategy**:
- **Token-aware splitting**: Uses `RecursiveCharacterTextSplitter` with tiktoken
- **Default**: 512 tokens chunk size, 128 tokens overlap
- **Adaptive chunking**: Automatically upscales for very large documents
  - If estimated chunks > 200 and chunk_size ≤ 512
  - Adjusts to target ~200 chunks max
  - Preserves overlap ratio
- **Page mapping**: Uses character offsets to assign accurate page numbers

**Embedding**:
- **Model**: OpenAI `text-embedding-3-large` (3072 dimensions)
- **Batch size**: 1000 chunks per batch
- **Progress tracking**: Real-time updates during embedding

**Indexing**:
- **OpenSearch**: Per-document indexes (`aris-doc-{document_id}`)
- **Bulk operations**: 5000 documents per bulk operation
- **Document index map**: Maps document names to OpenSearch indexes
- **Synchronization**: Shared volume across services

### 3. Retrieval & RAG Pipeline

**Query Processing Flow**:
1. **Document Filtering**: Active sources or document_id filtering
2. **Index Map Reload**: Checks modification time and reloads if changed
3. **Search Execution**:
   - Semantic search (vector similarity)
   - Keyword search (BM25) if hybrid enabled
   - Hybrid combination with weights (default: 0.75 semantic, 0.25 keyword)
4. **Reranking**: FlashRank Cross-Encoder (top 15 → top 8)
5. **Agentic RAG** (optional):
   - Query decomposition into sub-queries (max 4)
   - Parallel sub-query execution
   - Deduplication of results (threshold: 0.95)
   - Context aggregation
6. **Answer Generation**: LLM synthesis with context
7. **Citation Generation**:
   - Extract source, page, snippet
   - Generate S3 pre-signed URLs
   - Merge duplicate citations

**Search Modes**:
- **Semantic**: Pure vector similarity search
- **Keyword**: BM25 keyword search
- **Hybrid**: Weighted combination (default, best accuracy)

**Reranking**:
- **Model**: FlashRank `ms-marco-MiniLM-L-12-v2`
- **Process**: Retrieves top 15, reranks to top 8
- **Fallback**: Returns raw results if reranking fails

### 4. Storage Systems

#### Document Registry (`storage/document_registry.py`)
- **Purpose**: Metadata storage for all processed documents
- **Location**: `storage/document_registry.json`
- **Features**:
  - Thread-safe operations (file locking with `fcntl`)
  - S3 synchronization (upload on save, download on startup)
  - Version tracking with history
  - Document metadata: ID, name, status, chunks, timestamps, S3 URLs
  - Filename to document_id resolution

#### Document Index Map (`vectorstore/document_index_map.json`)
- **Purpose**: Maps document names to OpenSearch indexes
- **Format**: `{document_name: opensearch_index_name}`
- **Synchronization**: Shared volume across all services
- **Reloading**: Retrieval service checks modification time and reloads dynamically

#### Vector Store (`vectorstores/opensearch_store.py`)
- **Type**: AWS OpenSearch Service
- **Features**:
  - Semantic search
  - Keyword search (BM25)
  - Hybrid search (weighted combination)
  - Bulk operations (batch size: 1000)
  - Multi-index support
  - Per-document indexes

#### S3 Storage
- **Bucket**: `intelycx-waseem-s3-bucket` (configurable)
- **Structure**:
  - `documents/{document_id}/{filename}`: Original documents
  - `configs/document_registry.json`: Registry backup
- **Features**:
  - Automatic document backup on ingestion
  - Registry sync for multi-instance deployments
  - Pre-signed URLs for secure document access (1-hour expiry)

### 5. Configuration Management

**Centralized Config** (`shared/config/settings.py`):
- **ARISConfig**: Single source of truth for all settings
- **Environment Variables**: Loaded via `.env` file
- **Key Settings**:
  - Model selection (OpenAI/Cerebras)
  - Embedding model (text-embedding-3-large)
  - Chunking parameters (size: 512, overlap: 128)
  - Retrieval parameters (k: 15, reranking enabled)
  - Hybrid search weights (semantic: 0.75, keyword: 0.25)
  - Agentic RAG settings (max_sub_queries: 4)
  - S3 configuration
  - OpenSearch configuration

**Service-Specific Configuration**:
- Docker Compose injects environment variables per service
- Shared volumes mounted for state synchronization

---

## API Endpoints

### Gateway Service (Port 8500)
- `GET /health` - Health check with registry sync status
- `GET /documents` - List all documents
- `GET /documents/{id}` - Get document metadata
- `POST /documents` - Upload document (async)
- `POST /query` - Query RAG system
- `GET /sync/status` - Check synchronization status

### Ingestion Service (Port 8501)
- `GET /health` - Health check with registry/index map status
- `POST /ingest` - Ingest document (async, returns immediately)
- `POST /process` - Process document (synchronous)
- `GET /status/{document_id}` - Get processing status
- `GET /metrics` - Get processing metrics
- `GET /indexes/{name}/exists` - Check if index exists
- `GET /indexes/{base_name}/next-available` - Get next available index name

### Retrieval Service (Port 8502)
- `GET /health` - Health check with index map status
- `POST /query` - Execute RAG query
- `POST /query/images` - Search for images
- `GET /metrics` - Get retrieval metrics

### Unified FastAPI (api/main.py)
- `POST /query` - Unified query endpoint with focus options
- `POST /documents/upload-s3` - Upload with S3 storage
- `GET /documents/{id}/download` - Download from S3
- `GET /settings` - Get all system settings
- `PUT /settings` - Update system settings
- `GET /library` - Get document library
- `GET /metrics` - Get R&D metrics

---

## Key Design Patterns

### 1. Microservices Pattern
- **Separation of Concerns**: Each service has a single responsibility
- **Independent Scaling**: Services can be scaled independently
- **Service Discovery**: Via Docker Compose service names

### 2. Gateway Pattern
- **Single Entry Point**: Gateway routes all requests
- **Request Aggregation**: Combines results from multiple services
- **Protocol Translation**: HTTP → Internal service calls
- **Fallback**: Direct processing if services unavailable

### 3. Factory Pattern
- **Parser Factory**: Selects appropriate parser based on document type
- **Fallback Strategy**: Automatic parser fallback on failure
- **Vector Store Factory**: Creates appropriate vector store implementation

### 4. Strategy Pattern
- **Chunking Strategies**: Multiple chunking algorithms
- **Search Strategies**: Semantic, keyword, hybrid
- **Reranking Strategies**: FlashRank integration

### 5. Observer Pattern
- **Progress Callbacks**: Real-time progress updates during ingestion
- **Metrics Collection**: Event-driven metrics gathering

---

## Performance Optimizations

### 1. Batch Processing
- **Embedding Batch Size**: 1000 chunks per batch
- **OpenSearch Bulk Size**: 5000 documents per bulk operation
- **Parallel Processing**: ThreadPoolExecutor for I/O operations

### 2. Caching
- **Document Index Map**: Cached in memory, reloaded on file change
- **Embeddings**: Cached per chunk (no duplicate embedding generation)

### 3. Async Operations
- **Document Ingestion**: Asynchronous with background tasks
- **Query Processing**: Async HTTP calls between services
- **S3 Operations**: Async uploads/downloads

### 4. Adaptive Chunking
- **Large Document Detection**: Automatically adjusts chunk size
- **Target**: ~200 chunks max for very large documents
- **Preserves**: Overlap ratio and context continuity

---

## Error Handling & Resilience

### 1. Parser Fallback
- Automatic fallback to next parser on failure
- Logs parser attempts and failures
- Graceful degradation with best available result

### 2. Service Health Checks
- All services implement health endpoints
- Docker Compose monitors health status
- Unhealthy services are restarted

### 3. Graceful Degradation
- S3 operations fail gracefully if disabled
- OpenSearch fallback to FAISS (if configured)
- Registry sync failures don't block operations
- Gateway falls back to direct processing if services unavailable

### 4. Timeout Handling
- Parser timeouts (Docling: 30 minutes default)
- Query timeouts (60-120 seconds)
- Processing timeouts (1 hour for very large documents)

---

## Security Considerations

### 1. API Security
- **CORS**: Enabled for all origins (configurable)
- **API Keys**: Stored in environment variables
- **S3 Access**: Pre-signed URLs for document access (1-hour expiry)

### 2. Data Security
- **File Locking**: Prevents concurrent access conflicts (`fcntl`)
- **Atomic Writes**: Prevents data corruption (temp file + rename)
- **S3 Encryption**: AWS S3 server-side encryption

---

## Monitoring & Observability

### 1. Metrics Collection
- **Processing Metrics**: Document processing times, chunk counts
- **Query Metrics**: Query times, token usage, chunk retrieval
- **Cost Metrics**: API call costs (OpenAI/Cerebras)
- **Parser Comparison**: Parser performance metrics

### 2. Logging
- **Structured Logging**: JSON-formatted logs
- **Service-Specific Logs**: Separate log files per service
- **Log Levels**: INFO, WARNING, ERROR, DEBUG

### 3. Health Monitoring
- **Health Endpoints**: `/health` on all services
- **Synchronization Status**: `/sync/status` on Gateway
- **Docker Health Checks**: Automatic service restart on failure

---

## Code Quality Observations

### Strengths

1. **Comprehensive Error Handling**: Extensive try-catch blocks with fallbacks
2. **Type Safety**: Pydantic models for request/response validation
3. **Documentation**: Extensive docstrings and comments
4. **Modularity**: Clear separation of concerns
5. **Configuration Management**: Centralized config with environment variables
6. **Thread Safety**: File locking for concurrent access
7. **Progress Tracking**: Real-time updates for long operations
8. **Adaptive Behavior**: Intelligent chunking and parser selection

### Areas for Improvement

1. **Code Duplication**: Some logic duplicated between services
2. **Test Coverage**: Could benefit from more unit tests
3. **API Authentication**: Currently no authentication (mentioned in future enhancements)
4. **Rate Limiting**: No rate limiting per user/service
5. **Distributed Tracing**: No OpenTelemetry integration
6. **Database Backend**: JSON files could be replaced with PostgreSQL/MongoDB

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Frontend**: Streamlit
- **Vector Store**: AWS OpenSearch (primary), FAISS (local fallback)
- **Storage**: AWS S3, Local filesystem
- **LLM**: OpenAI GPT-4o, Cerebras Llama-3.3-70b
- **Embeddings**: OpenAI text-embedding-3-large
- **Containerization**: Docker, Docker Compose
- **Reranking**: FlashRank Cross-Encoder

### Libraries
- **LangChain**: Document processing and chunking
- **PyMuPDF**: Fast PDF parsing
- **Docling**: Advanced PDF parsing with OCR
- **OpenSearch-py**: Vector store client
- **Boto3**: AWS services integration
- **Tiktoken**: Token counting

---

## Deployment Architecture

### Docker Compose Services
- **ingestion**: Port 8501
- **retrieval**: Port 8502
- **gateway**: Port 8500
- **ui**: Port 80

### Service Dependencies
```
ui → gateway (depends_on: service_healthy)
gateway → ingestion (depends_on: service_healthy)
gateway → retrieval (depends_on: service_healthy)
```

### Health Checks
All services implement `/health` endpoints with Docker health checks:
- **Ingestion**: Checks registry and index map accessibility
- **Retrieval**: Checks registry, index map, and reloads index map
- **Gateway**: Checks registry and index map, lists documents
- **UI**: Streamlit health check on `/_stcore/health`

---

## Future Enhancements (from Architecture Doc)

1. **API Authentication**: API key authentication for endpoints
2. **Process Isolation**: ProcessPoolExecutor for CPU-intensive parsing
3. **Distributed Tracing**: OpenTelemetry integration
4. **Rate Limiting**: Request rate limiting per user/service
5. **Database Backend**: Replace JSON files with PostgreSQL/MongoDB
6. **Caching Layer**: Redis for query result caching
7. **Load Balancing**: Multiple instances with load balancer

---

## Conclusion

The ARIS RAG System is a **sophisticated, production-ready microservices architecture** that demonstrates:

- **Scalability**: Independent services that can scale independently
- **Reliability**: Comprehensive error handling and fallback mechanisms
- **Flexibility**: Multiple parsers, search modes, and configuration options
- **Performance**: Batch processing, caching, and adaptive optimizations
- **Observability**: Comprehensive metrics and logging
- **Security**: File locking, atomic writes, S3 encryption

The codebase shows mature software engineering practices with clear architecture, extensive documentation, and thoughtful design patterns. The system is well-positioned for production deployment and future enhancements.

---

**Document Version**: 2.0.0  
**Last Updated**: 2025-01-XX  
**Study Conducted By**: AI Codebase Analysis

---

## Migration Notes

**Monolithic Architecture Removed (2025-01-XX):**
- Removed `api/rag_system.py` (6000+ line monolithic class)
- Removed `rag_system.py` (root level re-export)
- All functionality now routes through microservices:
  - `api/app.py` → `ServiceContainer` → `GatewayService` → `IngestionService`/`RetrievalService`
  - `api/main.py` → `ServiceContainer` → `GatewayService` → Microservices
- Test files updated to use `RetrievalEngine` instead of `RAGSystem`
- GatewayService provides compatibility layer for seamless migration

