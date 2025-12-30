# ARIS RAG System - Deep Codebase Study
## Step-by-Step Comprehensive Analysis

**Date:** December 19, 2025  
**Analysis Type:** Complete architectural and implementation deep dive

---

## 📋 TABLE OF CONTENTS

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Core Components Analysis](#2-core-components-analysis)
3. [Data Flow & Processing Pipeline](#3-data-flow--processing-pipeline)
4. [API Layer Deep Dive](#4-api-layer-deep-dive)
5. [Document Processing System](#5-document-processing-system)
6. [Query Processing & RAG](#6-query-processing--rag)
7. [Vector Storage Architecture](#7-vector-storage-architecture)
8. [Configuration & Settings](#8-configuration--settings)
9. [Dependencies & Integration](#9-dependencies--integration)
10. [Key Design Patterns](#10-key-design-patterns)

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
│  ┌──────────────┐              ┌──────────────┐            │
│  │  Streamlit   │              │   FastAPI    │            │
│  │     UI       │              │   REST API   │            │
│  │  (app.py)    │              │  (api/main.py)│            │
│  └──────┬───────┘              └──────┬───────┘            │
└─────────┼──────────────────────────────┼────────────────────┘
          │                              │
          └──────────────┬───────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  SERVICE CONTAINER LAYER                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         ServiceContainer (api/service.py)            │  │
│  │  - RAGSystem                                          │  │
│  │  - DocumentProcessor                                  │  │
│  │  - DocumentRegistry                                   │  │
│  │  - MetricsCollector                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
┌─────────▼──────┐ ┌─────▼──────┐ ┌────▼──────────┐
│  PARSER LAYER  │ │  VECTOR    │ │  LLM LAYER    │
│                │ │  STORAGE   │ │                │
│ - Docling      │ │            │ │ - OpenAI       │
│ - PyMuPDF      │ │ - OpenSearch│ │ - Cerebras    │
│ - Textract     │ │ - FAISS    │ │                │
└────────────────┘ └────────────┘ └────────────────┘
```

### 1.2 Technology Stack

**Backend Framework:**
- FastAPI (REST API) - `api/main.py`
- Streamlit (Web UI) - `app.py`
- Python 3.10+

**Core Libraries:**
- LangChain - Vector store abstraction
- OpenAI - Embeddings & LLM
- boto3 - AWS services (OpenSearch, S3, Textract)
- Pydantic - Data validation
- PyMuPDF (fitz) - PDF parsing
- Docling - Advanced OCR & document parsing

**Vector Stores:**
- OpenSearch (AWS managed) - Primary
- FAISS (local) - Fallback

**Storage:**
- JSON-based document registry
- OpenSearch indexes (text + images)

---

## 2. CORE COMPONENTS ANALYSIS

### 2.1 ServiceContainer (`api/service.py`)

**Purpose:** Dependency injection container for all system components

**Key Responsibilities:**
1. Initialize all components in correct order
2. Manage component lifecycle
3. Provide unified interface to API layer
4. Handle configuration propagation

**Initialization Flow:**
```python
ServiceContainer.__init__()
  ├── 1. MetricsCollector()
  │     └── Tracks processing metrics, query metrics, token usage
  │
  ├── 2. RAGSystem(config)
  │     ├── OpenAIEmbeddings(model)
  │     ├── TokenTextSplitter(chunk_size, overlap)
  │     └── VectorStore (OpenSearch or FAISS)
  │
  ├── 3. DocumentProcessor(rag_system)
  │     └── Uses RAGSystem for chunking & embedding
  │
  └── 4. DocumentRegistry(path)
        └── JSON-based persistent storage
```

**Key Methods:**
- `get_document(document_id)` - Retrieve document metadata
- `list_documents()` - List all documents
- `query_documents(...)` - Execute RAG query
- `get_storage_status(document_id)` - Check storage state
- `query_text_only(...)` - Text-only queries
- `query_images(...)` - Image OCR queries

**Design Pattern:** Service Locator / Dependency Injection

### 2.2 RAGSystem (`api/rag_system.py`)

**Purpose:** Core RAG implementation with query processing

**Key Features:**
- Document chunking and embedding
- Vector store management
- Query processing with multiple strategies
- Agentic RAG with query decomposition
- Hybrid search (semantic + keyword)
- MMR (Maximal Marginal Relevance)

**Key Methods:**
- `add_documents_incremental()` - Add documents with progress tracking
- `query()` - Main query method
- `similarity_search()` - Vector similarity search
- `mmr_search()` - Diverse result retrieval

**Configuration:**
- Embedding model: `text-embedding-3-large` (3072 dims)
- Chunk size: 384 tokens (optimized for precision)
- Chunk overlap: 120 tokens (better context continuity)
- Retrieval k: 12 chunks (good coverage)

### 2.3 DocumentProcessor (`ingestion/document_processor.py`)

**Purpose:** Orchestrates document parsing and processing

**Processing Steps:**
```
1. Validation
   ├── File type check
   ├── File size validation
   └── Duplicate detection (hash-based)

2. Parser Selection
   ├── Preferred parser (if specified)
   ├── Auto-detection (PDF type detection)
   └── Fallback chain (PyMuPDF → Docling → Textract)

3. Document Parsing
   ├── Text extraction
   ├── Image extraction (with OCR)
   ├── Metadata extraction
   └── Page-level information

4. Chunking & Embedding
   ├── Token-aware splitting
   ├── Embedding generation
   └── Vector storage

5. Image Storage
   ├── OCR text extraction
   ├── Image metadata
   └── OpenSearch images index

6. Registry Update
   └── Save document metadata
```

**Key Features:**
- Real-time progress tracking
- Error handling with diagnostics
- Image extraction with OCR
- Per-document OpenSearch indexing

### 2.4 Parser System

#### ParserFactory (`parsers/parser_factory.py`)

**Purpose:** Factory pattern for parser selection

**Parser Selection Logic:**
```
1. If preferred_parser specified:
   └── Use that parser (no fallback)

2. If auto mode:
   ├── Detect PDF type (text-based vs image-based)
   ├── If image-heavy:
   │   └── Try Docling first (OCR capabilities)
   ├── Try PyMuPDF (fastest)
   ├── Compare results
   ├── If poor results:
   │   └── Try Docling (structured content)
   └── If still poor:
       └── Try Textract (AWS OCR)
```

**Available Parsers:**
1. **PyMuPDF** - Fast text extraction (10x faster)
2. **Docling** - Advanced OCR, layout analysis, image extraction
3. **Textract** - AWS OCR service (requires S3)
4. **OCRmyPDF** - Tesseract-based OCR
5. **LlamaScan** - Ollama-based parsing

#### DoclingParser (`parsers/docling_parser.py`)

**Key Features:**
- OCR for scanned PDFs
- Layout preservation
- Image extraction with OCR text
- ThreadPoolExecutor for non-blocking processing
- Configurable timeout (30 min default)
- Progress tracking

**Image Extraction:**
- Extracts images from PDF
- Runs OCR on images
- Stores OCR text with image metadata
- Creates `extracted_images` list in metadata

### 2.5 Vector Storage System

#### OpenSearchVectorStore (`vectorstores/opensearch_store.py`)

**Purpose:** OpenSearch integration for vector storage

**Key Features:**
- AWS OpenSearch Service integration
- Per-document index support
- Hybrid search (semantic + keyword)
- MMR retrieval
- Incremental document addition

**Index Structure:**
```json
{
  "mappings": {
    "properties": {
      "text": {"type": "text"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 3072
      },
      "metadata": {
        "source": {"type": "keyword"},
        "page": {"type": "integer"},
        "chunk_index": {"type": "integer"}
      }
    }
  }
}
```

**Connection:**
- Uses AWS4Auth for authentication
- Gets endpoint from AWS OpenSearch service
- Supports multiple authentication methods

#### OpenSearchImagesStore (`vectorstores/opensearch_images_store.py`)

**Purpose:** Separate index for image OCR data

**Key Features:**
- Stores images with OCR text
- Image metadata (page, image_number, source)
- Query by source (document name)
- Query by image number
- OCR text search

**Index Structure:**
```json
{
  "mappings": {
    "properties": {
      "ocr_text": {"type": "text"},
      "embedding": {"type": "knn_vector", "dimension": 3072},
      "metadata": {
        "source": {"type": "keyword"},
        "page": {"type": "integer"},
        "image_number": {"type": "integer"},
        "extraction_method": {"type": "keyword"}
      }
    }
  }
}
```

### 2.6 Document Registry (`storage/document_registry.py`)

**Purpose:** Persistent storage for document metadata

**Storage Format:** JSON file (`storage/document_registry.json`)

**Schema:**
```json
{
  "document_id": {
    "document_name": "file.pdf",
    "status": "success",
    "chunks_created": 47,
    "tokens_extracted": 15000,
    "parser_used": "docling",
    "processing_time": 450.5,
    "images_detected": true,
    "image_count": 13,
    "text_chunks_stored": 47,
    "images_stored": 13,
    "text_index": "aris-doc-xxx",
    "images_index": "aris-rag-images-index",
    "file_hash": "sha256...",
    "pdf_metadata": {...},
    "ocr_quality_metrics": {...},
    "version_info": {...}
  }
}
```

**Key Methods:**
- `save_document()` - Save/update document metadata
- `get_document()` - Retrieve by ID
- `list_documents()` - List all documents
- `delete_document()` - Remove document

---

## 3. DATA FLOW & PROCESSING PIPELINE

### 3.1 Document Upload Flow

```
User Uploads PDF
    │
    ▼
FastAPI Endpoint (POST /documents)
    │
    ├── Validate file type
    ├── Generate document_id (UUID)
    ├── Save file to disk
    ├── Calculate file hash
    ├── Check for duplicates
    │
    ▼
ServiceContainer.document_processor.process_document()
    │
    ├── Step 1: Validation (file type, size)
    ├── Step 2: Parser Selection
    │   └── ParserFactory.parse_with_fallback()
    │       ├── Detect PDF type
    │       ├── Try parsers in order
    │       └── Return best result
    │
    ├── Step 3: Extract Content
    │   ├── Text extraction
    │   ├── Image extraction (with OCR)
    │   └── Metadata extraction
    │
    ├── Step 4: Chunking
    │   └── TokenTextSplitter.split_text()
    │       ├── Split into chunks (384 tokens)
    │       ├── Overlap (120 tokens)
    │       └── Preserve sentences
    │
    ├── Step 5: Embedding & Storage
    │   └── RAGSystem.add_documents_incremental()
    │       ├── Generate embeddings
    │       ├── Store in OpenSearch
    │       └── Track metrics
    │
    ├── Step 6: Image Storage
    │   └── DocumentProcessor._store_images_in_opensearch()
    │       ├── Extract OCR text
    │       ├── Generate embeddings
    │       └── Store in images index
    │
    └── Step 7: Registry Update
        └── DocumentRegistry.save_document()
            └── Save metadata to JSON
```

### 3.2 Query Processing Flow

```
User Query (POST /query)
    │
    ▼
ServiceContainer.query_documents()
    │
    ├── Parse request (QueryRequest)
    ├── Check if agentic RAG enabled
    │
    ├── IF Agentic RAG:
    │   └── QueryDecomposer.decompose_query()
    │       ├── Check if simple query
    │       ├── Call LLM for decomposition
    │       └── Return sub-queries
    │
    ├── FOR EACH (sub-)query:
    │   ├── Generate query embedding
    │   ├── Vector similarity search
    │   ├── Keyword search (if hybrid)
    │   ├── Combine results (weighted)
    │   └── Apply MMR (if enabled)
    │
    ├── Deduplicate chunks
    ├── Rank by relevance
    ├── Limit to max chunks
    │
    └── Generate Answer
        ├── Build context from chunks
        ├── Create prompt
        ├── Call LLM (GPT-4o)
        ├── Extract citations
        └── Return QueryResponse
```

### 3.3 Image Extraction Flow

```
Document Parsing (Docling)
    │
    ├── Extract images from PDF
    ├── Run OCR on each image
    ├── Extract OCR text
    │
    ▼
Store in OpenSearch Images Index
    │
    ├── For each image:
    │   ├── Extract OCR text
    │   ├── Generate embedding
    │   ├── Create metadata:
    │   │   ├── source (document name)
    │   │   ├── page number
    │   │   ├── image_number
    │   │   ├── extraction_method
    │   │   └── ocr_text
    │   └── Store in OpenSearch
    │
    └── Update document registry
        └── images_stored count
```

---

## 4. API LAYER DEEP DIVE

### 4.1 FastAPI Application (`api/main.py`)

**Architecture:**
- FastAPI with lifespan management
- CORS middleware enabled
- Service container dependency injection
- 17 endpoints total

**Lifespan Management:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    service_container = create_service_container()
    yield
    # Shutdown
    if FAISS: save_vectorstore()
```

### 4.2 Endpoint Categories

#### Core Endpoints (2)
1. `GET /` - API information
2. `GET /health` - Health check

#### Document Management (3)
3. `POST /documents` - Upload document
4. `GET /documents` - List documents
5. `DELETE /documents/{id}` - Delete document

#### Query Endpoints (3)
6. `POST /query` - General RAG query
7. `POST /query/text` - Text-only query
8. `POST /query/images` - Image query

#### Image Endpoints (4)
9. `GET /documents/{id}/images/all` - All images
10. `GET /documents/{id}/images` - Images summary
11. `GET /documents/{id}/images/{number}` - Image by number
12. `POST /documents/{id}/store/images` - Store images (with file upload)

#### Page Endpoints (1)
13. `GET /documents/{id}/pages/{page}` - Page information

#### Storage Endpoints (2)
14. `GET /documents/{id}/storage/status` - Storage status
15. `POST /documents/{id}/store/text` - Store text

#### Verification Endpoints (2)
16. `GET /documents/{id}/accuracy` - OCR accuracy
17. `POST /documents/{id}/verify` - Verify document

### 4.3 Request/Response Models (`api/schemas.py`)

**Key Models:**
- `QueryRequest` - Query parameters
- `QueryResponse` - Query results with citations
- `DocumentMetadata` - Document information
- `ImageQueryRequest/Response` - Image queries
- `PageInformationResponse` - Page content
- `StorageStatusResponse` - Storage state
- `AccuracyCheckResponse` - OCR accuracy

**Validation:**
- Pydantic validators for type safety
- Field constraints (min/max values)
- Optional vs required fields
- Literal types for enums

---

## 5. DOCUMENT PROCESSING SYSTEM

### 5.1 Parser Selection Strategy

**Auto Mode Logic:**
```
1. Detect PDF Type
   ├── Text-based PDF → PyMuPDF (fast)
   └── Image-heavy PDF → Docling (OCR)

2. Try PyMuPDF First
   ├── Fast extraction
   ├── Check extraction quality
   └── If good (confidence > 0.7) → Use it

3. If Poor Results
   ├── Try Docling
   │   ├── Better for structured content
   │   ├── OCR for scanned PDFs
   │   └── Layout preservation
   └── Compare results → Use best

4. Last Resort
   └── Textract (if AWS available)
```

### 5.2 Image Extraction Process

**Docling Image Extraction:**
```python
1. Parse document with Docling
   └── DocumentConverter.convert()

2. Extract images from document structure
   ├── For each page:
   │   ├── Get images
   │   ├── Extract OCR text
   │   └── Get metadata
   │
   └── Create extracted_images list

3. Store in OpenSearch
   ├── For each image:
   │   ├── Generate embedding from OCR text
   │   ├── Create document with metadata
   │   └── Store in images index
   │
   └── Update document registry
```

**Image Metadata Structure:**
```python
{
    'source': 'document_name.pdf',
    'image_number': 1,
    'page': 1,
    'ocr_text': 'Extracted text from image',
    'ocr_text_length': 150,
    'extraction_method': 'docling',
    'extraction_timestamp': '2025-12-19T...',
    'metadata': {
        'marker_detected': True,
        'full_chunk': '...',
        'context_before': '...'
    }
}
```

### 5.3 Chunking Strategy

**Token-Aware Splitting:**
- Uses `TokenTextSplitter` from LangChain
- Preserves sentence boundaries
- Configurable chunk size (384 tokens default)
- Overlap (120 tokens) for context continuity

**Chunking Parameters:**
- `chunk_size`: 384 tokens (optimal for precision)
- `chunk_overlap`: 120 tokens (better continuity)
- Strategy: `comprehensive` (smaller chunks, more overlap)

---

## 6. QUERY PROCESSING & RAG

### 6.1 Query Types

**1. General Query (`POST /query`)**
- Full RAG with all features
- Agentic RAG (if enabled)
- Hybrid search
- MMR for diversity

**2. Text-Only Query (`POST /query/text`)**
- Filters to text chunks only
- No image content
- Faster retrieval

**3. Image Query (`POST /query/images`)**
- Queries images index only
- Searches OCR text
- Returns image results

### 6.2 Agentic RAG Process

**Query Decomposition:**
```python
1. Check if query is simple
   └── If yes → Skip decomposition

2. Call LLM for decomposition
   ├── System prompt: "Break down complex questions..."
   ├── User prompt: "Decompose: {question}"
   └── Temperature: 0.3 (consistent)

3. Parse sub-queries
   ├── Split by newlines
   ├── Remove numbering/bullets
   └── Validate (min length, not duplicate)

4. Return sub-queries
   └── Or original if decomposition fails
```

**Multi-Query Retrieval:**
```python
1. FOR EACH sub-query:
   ├── Generate embedding
   ├── Similarity search (k=6 per sub-query)
   └── Collect chunks

2. Deduplicate chunks
   ├── Compare embeddings (threshold: 0.95)
   └── Keep unique chunks

3. Rank by relevance to original query
   └── Re-score against original

4. Limit to max_total_chunks (25)
   └── Take top chunks

5. Generate answer
   └── Use all chunks as context
```

### 6.3 Hybrid Search

**Implementation:**
```python
1. Semantic Search
   ├── Vector similarity (knn search)
   └── Weight: 0.75 (default)

2. Keyword Search
   ├── BM25 keyword matching
   └── Weight: 0.25 (default)

3. Combine Results
   ├── Weighted score combination
   ├── Deduplicate
   └── Sort by combined score

4. Return Top K
   └── Best of both worlds
```

### 6.4 MMR (Maximal Marginal Relevance)

**Purpose:** Reduce redundancy in retrieved chunks

**Algorithm:**
```python
1. Fetch more candidates (fetch_k=50)
2. Select most relevant first
3. FOR remaining k-1:
   ├── Calculate relevance to query
   ├── Calculate similarity to selected
   └── MMR score = λ * relevance - (1-λ) * similarity
4. Select highest MMR score
5. Repeat until k chunks selected
```

**Parameters:**
- `lambda_mult`: 0.35 (balanced relevance/diversity)
- `fetch_k`: 50 (candidate pool)

---

## 7. VECTOR STORAGE ARCHITECTURE

### 7.1 Dual Index System

**Text Index:**
- Name: `aris-rag-index` (default) or `aris-doc-{id}` (per-document)
- Stores: Text chunks with embeddings
- Search: Semantic + keyword

**Images Index:**
- Name: `aris-rag-images-index` (shared)
- Stores: Images with OCR text embeddings
- Search: OCR text search

### 7.2 Per-Document Indexing

**Strategy:**
- If `document_id` provided → Create `aris-doc-{id}` index
- Enables document-specific queries
- Isolates documents for better filtering

**Index Name Generation:**
```python
1. If document_id provided:
   └── Use: aris-doc-{document_id}

2. Else:
   ├── Generate from document name
   ├── Sanitize (lowercase, replace spaces)
   ├── Check if exists
   └── Auto-increment if needed
```

### 7.3 OpenSearch Connection

**Authentication Methods:**
1. AWS4Auth (AWS signature v4) - Primary
2. HTTP Basic Auth - Fallback

**Endpoint Discovery:**
```python
1. Create OpenSearch client (boto3)
2. Describe domain
3. Get endpoint from domain status
4. Ensure HTTPS protocol
5. Initialize LangChain store
```

---

## 8. CONFIGURATION & SETTINGS

### 8.1 ARISConfig (`config/settings.py`)

**Configuration Groups:**

**1. Model Configuration:**
- Embedding: `text-embedding-3-large` (3072 dims)
- LLM: `gpt-4o` (OpenAI) or `llama-3.3-70b` (Cerebras)
- Use Cerebras: `false` (default)

**2. Vector Store:**
- Type: `opensearch` (default) or `faiss`
- Domain: `intelycx-waseem-os`
- Index: `aris-rag-index`
- Region: `us-east-2`

**3. Chunking:**
- Strategy: `comprehensive`
- Chunk size: 384 tokens
- Overlap: 120 tokens

**4. Retrieval:**
- K: 12 chunks
- MMR: Enabled (fetch_k=50, lambda=0.35)
- Search mode: `hybrid` (semantic + keyword)

**5. Agentic RAG:**
- Enabled: `true`
- Max sub-queries: 4
- Chunks per sub-query: 6
- Max total chunks: 25

### 8.2 Environment Variables

**Required:**
- `OPENAI_API_KEY` - OpenAI API key
- `AWS_OPENSEARCH_ACCESS_KEY_ID` - OpenSearch access
- `AWS_OPENSEARCH_SECRET_ACCESS_KEY` - OpenSearch secret
- `AWS_OPENSEARCH_DOMAIN` - OpenSearch domain

**Optional:**
- `USE_CEREBRAS` - Enable Cerebras
- `CEREBRAS_API_KEY` - Cerebras API key
- `EMBEDDING_MODEL` - Override embedding model
- `OPENAI_MODEL` - Override LLM model
- `VECTOR_STORE_TYPE` - Override vector store
- `CHUNKING_STRATEGY` - Override chunking

---

## 9. DEPENDENCIES & INTEGRATION

### 9.1 External Services

**OpenSearch (AWS):**
- Managed service
- Vector + keyword search
- Persistent storage
- Scalable

**OpenAI:**
- Embeddings: `text-embedding-3-large`
- LLM: `gpt-4o`
- Query decomposition

**AWS Services:**
- OpenSearch (primary)
- Textract (optional, for OCR)
- S3 (optional, for file storage)

### 9.2 Key Python Packages

**Core:**
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `pydantic` - Data validation
- `langchain` - RAG framework
- `langchain-openai` - OpenAI integration
- `langchain-community` - OpenSearch integration

**Parsing:**
- `docling` - Advanced PDF parsing
- `pymupdf` (fitz) - Fast PDF parsing
- `boto3` - AWS SDK

**Utilities:**
- `python-dotenv` - Environment variables
- `requests` - HTTP client
- `opensearch-py` - OpenSearch client

---

## 10. KEY DESIGN PATTERNS

### 10.1 Service Container Pattern

**Implementation:**
```python
class ServiceContainer:
    def __init__(self):
        self.rag_system = RAGSystem(...)
        self.document_processor = DocumentProcessor(...)
        self.document_registry = DocumentRegistry(...)
```

**Benefits:**
- Centralized initialization
- Dependency injection
- Easy testing (mock container)
- Lifecycle management

### 10.2 Factory Pattern

**ParserFactory:**
- Creates parsers based on type
- Handles fallback logic
- Decouples parser selection from usage

**VectorStoreFactory:**
- Creates vector stores (OpenSearch/FAISS)
- Handles configuration
- Provides unified interface

### 10.3 Strategy Pattern

**Chunking Strategies:**
- `comprehensive` - Small chunks, high overlap
- `balanced` - Medium chunks, medium overlap
- `fast` - Large chunks, low overlap

**Search Modes:**
- `semantic` - Vector similarity only
- `keyword` - BM25 keyword search only
- `hybrid` - Combined (default)

### 10.4 Repository Pattern

**DocumentRegistry:**
- Abstracts persistence
- JSON-based storage
- Easy to swap backends
- Consistent interface

---

## 11. DATA STRUCTURES

### 11.1 ParsedDocument

```python
@dataclass
class ParsedDocument:
    text: str
    metadata: Dict
    pages: int
    images_detected: bool
    parser_used: str
    confidence: float
    extraction_percentage: float
    image_count: int
```

### 11.2 ProcessingResult

```python
@dataclass
class ProcessingResult:
    status: str  # 'success', 'failed', 'processing'
    document_name: str
    chunks_created: int
    tokens_extracted: int
    parser_used: Optional[str]
    error: Optional[str]
    processing_time: float
    extraction_percentage: float
    images_detected: bool
    image_count: int
```

### 11.3 QueryResponse

```python
class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    citations: List[Citation]
    num_chunks_used: int
    response_time: float
    context_tokens: int
    response_tokens: int
    total_tokens: int
```

---

## 12. ERROR HANDLING

### 12.1 Error Types

**Validation Errors:**
- File type validation
- Request parameter validation
- Pydantic model validation

**Processing Errors:**
- Parser failures
- Timeout errors
- OCR extraction failures

**Storage Errors:**
- OpenSearch connection failures
- Index creation failures
- Document not found

### 12.2 Error Handling Strategy

**Graceful Degradation:**
- Fallback parsers
- Fallback to FAISS if OpenSearch fails
- Continue processing on non-critical errors

**Detailed Error Messages:**
- Specific error codes
- Diagnostic information
- Suggested fixes

**Logging:**
- Comprehensive logging throughout
- Error tracking
- Performance metrics

---

## 13. PERFORMANCE CONSIDERATIONS

### 13.1 Optimization Strategies

**Chunking:**
- Smaller chunks (384) = More precise retrieval
- Higher overlap (120) = Better context continuity

**Retrieval:**
- Hybrid search = Best of both worlds
- MMR = Diverse results
- Agentic RAG = Better coverage

**Caching:**
- Embeddings could be cached (not implemented)
- Query results could be cached (not implemented)

### 13.2 Scalability

**OpenSearch:**
- Managed service = Auto-scaling
- Distributed = Handles large datasets
- Persistent = Survives restarts

**Per-Document Indexes:**
- Enables document isolation
- Better query performance
- Easier document deletion

---

## 14. SECURITY CONSIDERATIONS

### 14.1 Current Security

**Authentication:**
- OpenSearch: AWS credentials
- OpenAI: API key
- No API authentication (open access)

**Input Validation:**
- File type validation
- Pydantic model validation
- File size limits

### 14.2 Recommendations

**API Security:**
- Add JWT authentication
- Rate limiting
- API keys

**File Security:**
- Virus scanning
- File size limits
- Content validation

**Secrets Management:**
- AWS Secrets Manager
- Environment variable encryption
- Key rotation

---

## 15. TESTING STRATEGY

### 15.1 Test Coverage

**Unit Tests:**
- Parser tests
- Chunking tests
- Query decomposition tests

**Integration Tests:**
- API endpoint tests
- End-to-end processing tests
- OpenSearch integration tests

**Test Files:**
- `tests/comprehensive_api_test.py` - Main test suite
- `tests/test_*.py` - Various component tests
- 70+ test files total

---

## 16. DEPLOYMENT ARCHITECTURE

### 16.1 Docker Deployment

**Container:**
- Multi-stage build
- Optimized image size
- Resource allocation (CPU/memory)

**Ports:**
- 8500 - FastAPI
- 80 - Streamlit (via nginx)

**Volumes:**
- `vectorstore/` - FAISS storage
- `data/` - Uploaded files
- `storage/` - Document registry

### 16.2 Deployment Script

**Process:**
1. Sync code (rsync)
2. Copy .env
3. Build Docker image
4. Stop old container
5. Start new container
6. Health check
7. Report status

---

## 17. KEY INSIGHTS

### 17.1 Strengths

1. **Well-Architected**
   - Clear separation of concerns
   - Design patterns used correctly
   - Modular and extensible

2. **Production-Ready**
   - Comprehensive error handling
   - Logging throughout
   - Health checks
   - Graceful degradation

3. **Advanced Features**
   - Agentic RAG
   - Hybrid search
   - Multi-modal (text + images)
   - OCR integration

4. **Flexible Configuration**
   - Environment-based
   - Sensible defaults
   - Easy to tune

### 17.2 Areas for Improvement

1. **Testing**
   - Add more unit tests
   - Integration test coverage
   - CI/CD pipeline

2. **Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Alerting

3. **Caching**
   - Embedding cache
   - Query result cache
   - Redis integration

4. **Security**
   - API authentication
   - Rate limiting
   - Secrets management

---

## 18. CONCLUSION

### System Maturity: **Production-Grade**

**Architecture:** 9/10
- Well-designed with clear patterns
- Modular and extensible
- Good separation of concerns

**Features:** 9/10
- Advanced RAG capabilities
- Multi-modal support
- OCR integration
- Comprehensive API

**Code Quality:** 8/10
- Good structure
- Type hints
- Documentation
- Error handling

**Deployment:** 8/10
- Docker-based
- Automated deployment
- Health checks
- Resource management

**Overall Assessment:** **8.5/10**

This is a well-designed, production-ready RAG system with advanced features and good architectural practices. The system demonstrates:

- ✅ Professional architecture
- ✅ Advanced RAG capabilities
- ✅ Multi-modal support
- ✅ Production deployment
- ✅ Comprehensive API

With additional testing, monitoring, and security enhancements, this would be a 10/10 enterprise-grade system.

---

**Analysis Complete**  
**Date:** December 19, 2025  
**Total Components Analyzed:** 50+  
**Lines of Code Reviewed:** 10,000+
