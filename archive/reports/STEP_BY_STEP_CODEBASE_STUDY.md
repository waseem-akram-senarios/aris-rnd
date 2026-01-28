# ARIS RAG System - Step-by-Step Deep Codebase Study
## Complete Systematic Analysis

**Date:** December 30, 2025  
**Total Code:** 131 Python files, 45,550+ lines  
**Analysis Type:** Comprehensive step-by-step architectural and implementation review

---

## 📋 TABLE OF CONTENTS

1. [System Overview & Entry Points](#1-system-overview--entry-points)
2. [Application Initialization Flow](#2-application-initialization-flow)
3. [API Layer Architecture](#3-api-layer-architecture)
4. [Service Container Pattern](#4-service-container-pattern)
5. [Document Processing Pipeline](#5-document-processing-pipeline)
6. [Parser System Deep Dive](#6-parser-system-deep-dive)
7. [RAG System Core](#7-rag-system-core)
8. [Query Processing & Agentic RAG](#8-query-processing--agentic-rag)
9. [Vector Storage Architecture](#9-vector-storage-architecture)
10. [Image & OCR System](#10-image--ocr-system)
11. [Configuration Management](#11-configuration-management)
12. [Data Flow Diagrams](#12-data-flow-diagrams)
13. [Error Handling & Resilience](#13-error-handling--resilience)
14. [Design Patterns Used](#14-design-patterns-used)
15. [Key Algorithms](#15-key-algorithms)

---

## 1. SYSTEM OVERVIEW & ENTRY POINTS

### 1.1 Dual Application Architecture

The system has **two entry points**:

**A. Streamlit Web UI** (`app.py` → `api/app.py`)
```python
# Root app.py is a thin wrapper
import runpy
runpy.run_path("api/app.py", run_name="__main__")
```

**B. FastAPI REST API** (`api/main.py`)
```python
app = FastAPI(
    title="ARIS RAG API - Minimal",
    description="Minimal API with 10 endpoints",
    version="2.0.0",
    lifespan=lifespan  # Startup/shutdown management
)
```

### 1.2 Entry Point Analysis

#### Streamlit Entry (`api/app.py`)
- **Purpose:** Interactive web UI for document processing and querying
- **Features:**
  - File upload with progress tracking
  - Real-time processing status
  - Interactive query interface
  - Metrics dashboard
  - Document library browser
- **Session State:** Manages RAG system, documents, chat history
- **Initialization:** Lazy loading of RAG system on first use

#### FastAPI Entry (`api/main.py`)
- **Purpose:** RESTful API for programmatic access
- **Features:**
  - 17 endpoints (Core, Query, Image, Page, Storage, Verification)
  - OpenAPI/Swagger documentation
  - Background task processing
  - CORS enabled
- **Initialization:** Service container created at startup via `lifespan`

### 1.3 RAG System Entry Point

**File:** `rag_system.py` (root level)
```python
from api.rag_system import RAGSystem
__all__ = ["RAGSystem"]
```

This is a **re-export** that points to the actual implementation in `api/rag_system.py`, maintaining backward compatibility.

---

## 2. APPLICATION INITIALIZATION FLOW

### 2.1 FastAPI Initialization Sequence

```
Application Start
    │
    ▼
lifespan(app) - Startup
    │
    ├── [STEP 1] Log startup banner
    ├── [STEP 2] create_service_container()
    │   │
    │   ├── Load ARISConfig defaults
    │   ├── Check OpenSearch credentials
    │   ├── Fallback to FAISS if no OpenSearch
    │   └── Get chunking parameters
    │
    ├── [STEP 3] ServiceContainer.__init__()
    │   │
    │   ├── [STEP 3.1] Initialize MetricsCollector
    │   │   └── Tracks: processing, queries, tokens
    │   │
    │   ├── [STEP 3.2] Initialize RAGSystem
    │   │   ├── Load embedding model (text-embedding-3-large)
    │   │   ├── Initialize TokenTextSplitter
    │   │   ├── Load document_index_map (if exists)
    │   │   └── Initialize vector store (lazy)
    │   │
    │   ├── [STEP 3.3] Initialize DocumentProcessor
    │   │   └── Wraps RAGSystem for processing
    │   │
    │   └── [STEP 3.4] Initialize DocumentRegistry
    │       └── Load JSON registry from disk
    │
    └── [STEP 4] Application ready
        └── Service container available via dependency injection
```

### 2.2 Service Container Creation

**Function:** `create_service_container()` in `api/service.py`

**Process:**
```python
1. Read configuration from ARISConfig
   ├── Model settings (embedding, LLM)
   ├── Vector store type
   ├── Chunking strategy
   └── OpenSearch config

2. Validate OpenSearch availability
   ├── Check credentials exist
   ├── Check domain configured
   └── Fallback to FAISS if missing

3. Get chunking parameters
   └── From strategy (comprehensive/balanced/fast)

4. Create ServiceContainer instance
   └── Pass all configuration
```

**Key Configuration Sources:**
- Environment variables (`.env`)
- `ARISConfig` class defaults
- Function parameters (override)

---

## 3. API LAYER ARCHITECTURE

### 3.1 FastAPI Application Structure

**File:** `api/main.py` (2,100+ lines)

**Architecture:**
- FastAPI app with lifespan management
- CORS middleware (all origins)
- Dependency injection for ServiceContainer
- 17 endpoints organized by tags

### 3.2 Endpoint Categories

#### Core Endpoints (5)
1. **GET /** - API information
2. **GET /health** - Health check
3. **GET /documents** - List all documents
4. **POST /documents** - Upload and process document
5. **DELETE /documents/{id}** - Delete document

#### Query Endpoints (1 unified)
6. **POST /query** - Unified query endpoint
   - Supports `type=text|image`
   - Supports `focus=all|important|summary|specific`
   - Supports `document_id` filtering
   - Query parameter overrides

#### Image Endpoints (4)
7. **GET /documents/{id}/images/all** - All images with OCR
8. **GET /documents/{id}/images** - Images summary by number
9. **GET /documents/{id}/images/{number}** - Specific image by number
10. **POST /documents/{id}/store/images** - Store images (with file upload)

#### Page Endpoints (1)
11. **GET /documents/{id}/pages/{page}** - Page information

#### Storage Endpoints (2)
12. **GET /documents/{id}/storage/status** - Storage status
13. **POST /documents/{id}/store/text** - Store text

#### Verification Endpoints (2)
14. **GET /documents/{id}/accuracy** - OCR accuracy check
15. **POST /documents/{id}/verify** - Verify document

#### Settings Endpoints (2 via router)
16. **GET /v1/config** - Get configuration
17. **POST /v1/config** - Update configuration

### 3.3 Request/Response Models

**File:** `api/schemas.py` (425 lines)

**Key Models:**
- `QueryRequest` - Query parameters with validation
- `QueryResponse` - Query results with citations
- `DocumentMetadata` - Complete document information
- `ImageQueryRequest/Response` - Image queries
- `PageInformationResponse` - Page content
- `StorageStatusResponse` - Storage state
- `SystemSettings` - Complete configuration

**Validation:**
- Pydantic validators for type safety
- Field constraints (min/max, ranges)
- Literal types for enums
- Optional vs required fields

---

## 4. SERVICE CONTAINER PATTERN

### 4.1 ServiceContainer Class

**File:** `api/service.py` (369 lines)

**Purpose:** Central dependency injection container

**Components Managed:**
1. `MetricsCollector` - Performance and usage metrics
2. `RAGSystem` - Core RAG implementation
3. `DocumentProcessor` - Document processing pipeline
4. `DocumentRegistry` - Persistent metadata storage

### 4.2 Initialization Sequence

```python
ServiceContainer.__init__()
  │
  ├── [STEP 1] MetricsCollector()
  │   └── Initialize metrics tracking
  │
  ├── [STEP 2] RAGSystem(config)
  │   ├── Load embedding model
  │   ├── Initialize text splitter
  │   ├── Load document index map
  │   └── Prepare vector store (lazy init)
  │
  ├── [STEP 3] DocumentProcessor(rag_system)
  │   └── Wraps RAGSystem for processing
  │
  └── [STEP 4] DocumentRegistry(path)
      └── Load JSON registry from disk
```

### 4.3 Key Methods

**Document Management:**
- `get_document(id)` - Retrieve metadata
- `list_documents()` - List all documents
- `add_document(id, result)` - Save metadata
- `remove_document(id)` - Delete document

**Query Methods:**
- `query_text_only(...)` - Text-only queries
- `query_images_only(...)` - Image OCR queries
- `get_storage_status(id)` - Check storage state

**Design Pattern:** Service Locator / Dependency Injection

---

## 5. DOCUMENT PROCESSING PIPELINE

### 5.1 DocumentProcessor Class

**File:** `ingestion/document_processor.py` (760 lines)

**Purpose:** Orchestrates document parsing and processing

### 5.2 Processing Steps (Detailed)

```
Step 1: Validation & Preparation (0-10% progress)
  ├── Validate file type (.pdf, .txt, .docx, .doc)
  ├── Get file size
  ├── Check file exists
  └── Initialize processing state

Step 2: Parser Selection & Parsing (10-45% progress)
  ├── Determine parser preference
  ├── ParserFactory.parse_with_fallback()
  │   ├── Detect PDF type (text vs image-heavy)
  │   ├── Try PyMuPDF (fast)
  │   ├── Try Docling (OCR, structured)
  │   └── Try Textract (AWS OCR, fallback)
  │
  ├── Extract text content
  ├── Extract images (if any)
  ├── Extract metadata
  └── Get page-level information

Step 3: Chunking (45-60% progress)
  ├── TokenTextSplitter.split_text()
  │   ├── Count tokens per chunk
  │   ├── Split at token boundaries
  │   ├── Preserve sentence boundaries
  │   └── Apply overlap
  │
  └── Adaptive chunking for large documents
      └── Upscale chunk size if >200 chunks estimated

Step 4: Embedding & Storage (60-90% progress)
  ├── RAGSystem.add_documents_incremental()
  │   ├── Generate embeddings (OpenAI)
  │   ├── Create Document objects
  │   ├── Store in vector store
  │   │   ├── OpenSearch: Per-document index
  │   │   └── FAISS: Shared index
  │   └── Track metrics
  │
  └── Batch processing for large documents

Step 5: Image Storage (90-95% progress)
  ├── Extract images from parsed document
  ├── For each image:
  │   ├── Extract OCR text
  │   ├── Generate embedding from OCR text
  │   ├── Create metadata
  │   └── Store in OpenSearch images index
  │
  └── Update document registry

Step 6: Registry Update (95-100% progress)
  └── DocumentRegistry.save_document()
      ├── Save metadata to JSON
      ├── Track version history
      └── Update processing state
```

### 5.3 ProcessingResult Dataclass

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

**Note:** This dataclass does NOT have a `parsed_document` attribute. The parsed document is used during processing but not stored in the result.

---

## 6. PARSER SYSTEM DEEP DIVE

### 6.1 Parser Architecture

**Base Interface:** `parsers/base_parser.py`

```python
class BaseParser(ABC):
    @abstractmethod
    def parse(file_path, file_content) -> ParsedDocument:
        pass
    
    @abstractmethod
    def can_parse(file_path) -> bool:
        pass
```

**ParsedDocument Dataclass:**
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

### 6.2 ParserFactory

**File:** `parsers/parser_factory.py` (395 lines)

**Parser Selection Logic:**

```
IF preferred_parser specified:
  └── Use that parser (NO fallback)

ELSE (auto mode):
  1. Detect PDF type
     ├── Text-based PDF
     └── Image-heavy PDF
  
  2. IF image-heavy:
     └── Try Docling first (OCR capabilities)
  
  3. Try PyMuPDF (fastest)
     ├── Check quality (confidence > 0.7)
     └── IF good → Use it
  
  4. IF poor results:
     ├── Try Docling (structured content, OCR)
     └── Compare results → Use best
  
  5. Last resort:
     └── Textract (if AWS available)
```

### 6.3 DoclingParser

**File:** `parsers/docling_parser.py` (1,684 lines)

**Key Features:**
- OCR for scanned PDFs
- Layout preservation
- Image extraction with OCR text
- ThreadPoolExecutor for non-blocking processing
- Configurable timeout (30 min default)
- Progress tracking

**Image Extraction Process:**
```python
1. DocumentConverter.convert(file_path)
   └── Returns: DocumentResult

2. Extract images from document structure
   ├── For each page:
   │   ├── Get images
   │   ├── Extract OCR text
   │   └── Get metadata (bbox, page)
   │
   └── Create extracted_images list

3. Store in metadata
   └── parsed_doc.metadata['extracted_images'] = [...]
```

**Image Marker Insertion:**
- Inserts `<!-- image -->` markers in text
- Helps identify image locations in text
- Used for context extraction

### 6.4 PyMuPDFParser

**File:** `parsers/pymupdf_parser.py`

**Key Features:**
- Fast text extraction (10x faster than Docling)
- High quality for text-based PDFs
- No OCR capability
- Lightweight dependencies

---

## 7. RAG SYSTEM CORE

### 7.1 RAGSystem Class

**File:** `api/rag_system.py` (5,600 lines)

**Purpose:** Core RAG implementation with advanced features

### 7.2 Initialization

```python
RAGSystem.__init__()
  ├── Load model configuration
  ├── Initialize embeddings (OpenAI or LocalHash)
  ├── Initialize TokenTextSplitter
  ├── Load document_index_map
  ├── Initialize metrics collector
  └── Prepare LLM (OpenAI or Cerebras)
```

### 7.3 Key Methods

#### `process_documents()`
- Chunks documents using TokenTextSplitter
- Creates Document objects
- Handles PyMuPDF NoSessionContext errors
- Adaptive chunking for large documents

#### `add_documents_incremental()`
- Adds documents to vector store incrementally
- Progress tracking
- Batch processing
- Returns processing statistics

#### `query_with_rag()`
- Main query method
- Supports agentic RAG
- Hybrid search
- MMR retrieval
- Document filtering

#### `query_images()`
- Queries images index
- Searches OCR text
- Returns image results with metadata

### 7.4 Document Index Mapping

**Purpose:** Track which OpenSearch index contains which document

**Storage:** `vectorstore/document_index_map.json`

**Structure:**
```json
{
  "document_name.pdf": "aris-doc-uuid-123",
  "another_doc.pdf": "aris-doc-uuid-456"
}
```

**Usage:**
- Enables per-document indexing
- Supports document-specific queries
- Easier document deletion

---

## 8. QUERY PROCESSING & AGENTIC RAG

### 8.1 Query Flow

```
User Query
    │
    ▼
POST /query endpoint
    │
    ├── Parse QueryRequest
    ├── Apply focus adjustments
    │   ├── important → 2x k, hybrid search
    │   ├── summary → k=20, MMR, summary prompt
    │   └── specific → k=6, semantic only
    │
    ▼
ServiceContainer.query_text_only()
    │
    ├── Set document filter (if document_id)
    ├── Set active_sources
    └── Set document_index_map
    │
    ▼
RAGSystem.query_with_rag()
    │
    ├── Check if agentic RAG enabled
    │
    ├── IF Agentic RAG:
    │   └── QueryDecomposer.decompose_query()
    │       ├── Check if simple query
    │       ├── Call LLM (GPT-4o) for decomposition
    │       └── Return sub-queries (2-4)
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

### 8.2 Agentic RAG Implementation

**File:** `rag/query_decomposer.py` (248 lines)

**QueryDecomposer Class:**

```python
class QueryDecomposer:
    def decompose_query(question, max_subqueries=4) -> List[str]:
        1. Check if simple query
           ├── Very short (< 30 chars)
           ├── Single question mark
           ├── No conjunctions
           └── Single question word
           
           IF simple → Return [question]
        
        2. Call LLM for decomposition
           ├── System prompt: "Break down complex questions..."
           ├── User prompt: "Decompose: {question}"
           ├── Temperature: 0.3 (consistent)
           └── Max tokens: 200
        
        3. Parse sub-queries
           ├── Split by newlines
           ├── Remove numbering/bullets
           └── Validate (min length, not duplicate)
        
        4. Return sub-queries
           └── Or [question] if decomposition fails
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

### 8.3 Hybrid Search

**Implementation in OpenSearch:**

```python
1. Semantic Search
   ├── Vector similarity (knn search)
   ├── Weight: 0.75 (default)
   └── Fetch: k * 2 candidates

2. Keyword Search
   ├── BM25 keyword matching
   ├── Weight: 0.25 (default)
   └── Fetch: k * 2 candidates

3. Combine Results
   ├── Weighted score combination
   ├── Deduplicate
   └── Sort by combined score

4. Return Top K
   └── Best of both worlds
```

### 8.4 MMR (Maximal Marginal Relevance)

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

## 9. VECTOR STORAGE ARCHITECTURE

### 9.1 Dual Index System

**Text Index:**
- Name: `aris-rag-index` (default) or `aris-doc-{id}` (per-document)
- Stores: Text chunks with embeddings
- Search: Semantic + keyword (hybrid)

**Images Index:**
- Name: `aris-rag-images-index` (shared)
- Stores: Images with OCR text embeddings
- Search: OCR text search

### 9.2 OpenSearchVectorStore

**File:** `vectorstores/opensearch_store.py` (986 lines)

**Key Features:**
- AWS OpenSearch Service integration
- Per-document index support
- Hybrid search (semantic + keyword)
- MMR retrieval
- Incremental document addition
- **Dimension mismatch auto-fix** (NEW)

**Index Structure:**
```json
{
  "mappings": {
    "properties": {
      "text": {"type": "text"},
      "embedding": {
        "type": "knn_vector",
        "dimension": 3072  // text-embedding-3-large
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

**Connection Management:**
```python
1. Get AWS credentials from .env
2. Create OpenSearch client (boto3)
3. Describe domain to get endpoint
4. Initialize LangChain OpenSearchVectorSearch
5. Try AWS4Auth (primary)
6. Fallback to HTTP Basic Auth
```

**Dimension Mismatch Auto-Fix:**
```python
# In add_documents() and from_documents()
IF dimension mismatch error detected:
  1. Log warning
  2. Get current embedding dimension
  3. Delete old index
  4. Recreate vectorstore (creates new index)
  5. Retry adding documents
  6. Success!
```

### 9.3 OpenSearchImagesStore

**File:** `vectorstores/opensearch_images_store.py` (693 lines)

**Purpose:** Separate index for image OCR data

**Key Methods:**
- `store_image()` - Store single image with OCR
- `get_images_by_source()` - Get all images for document
- `query_images()` - Search images by OCR text
- `delete_by_source()` - Delete all images for document
- `count_images_by_source()` - Count images for document

**Image Metadata Structure:**
```python
{
    'source': 'document_name.pdf',
    'image_number': 1,
    'page': 1,
    'ocr_text': 'Extracted text from image',
    'ocr_text_length': 150,
    'extraction_method': 'docling',
    'metadata': {
        'marker_detected': True,
        'full_chunk': '...',
        'context_before': '...'
    }
}
```

### 9.4 VectorStoreFactory

**File:** `vectorstores/vector_store_factory.py` (328 lines)

**Purpose:** Factory pattern for vector store creation

**Supported Types:**
- `faiss` - Local FAISS vector store
- `opensearch` - AWS OpenSearch Service

**Methods:**
- `create_vector_store()` - Create new store
- `load_vector_store()` - Load existing store

---

## 10. IMAGE & OCR SYSTEM

### 10.1 Image Extraction Flow

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
    │   ├── Generate embedding (from OCR text)
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

### 10.2 Image Storage Endpoint

**Endpoint:** `POST /documents/{id}/store/images`

**Process:**
```python
1. Check if file provided
   ├── IF file provided:
   │   ├── Save to temp file
   │   ├── Parse with DoclingParser directly
   │   ├── Extract images from parsed_doc.metadata
   │   └── Store in OpenSearch
   │
   └── IF no file:
       └── Check existing images in registry

2. Store images
   ├── For each extracted image:
   │   ├── Get OCR text
   │   ├── Generate embedding
   │   ├── Create Document with metadata
   │   └── Store in images index
   │
   └── Update document registry

3. Return ImageStorageResponse
   └── images_stored count, status, message
```

**Fallback Logic:**
- If `extracted_images` is empty but images detected:
  - Create synthetic image entries from text
  - Split by page blocks if available
  - Mark as `extraction_method='docling_ocr_fallback'`

### 10.3 Image Query Endpoints

**GET /documents/{id}/images**
- Returns summary with image numbers and OCR text lengths

**GET /documents/{id}/images/{number}**
- Returns specific image by number with full OCR text

**GET /documents/{id}/images/all**
- Returns all images with complete OCR text

---

## 11. CONFIGURATION MANAGEMENT

### 11.1 ARISConfig Class

**File:** `config/settings.py` (157 lines)

**Configuration Groups:**

**1. Model Configuration:**
```python
EMBEDDING_MODEL: 'text-embedding-3-large'  # 3072 dims
OPENAI_MODEL: 'gpt-4o'  # Latest GPT-4o
CEREBRAS_MODEL: 'llama-3.3-70b'  # 70B parameters
USE_CEREBRAS: False  # Default to OpenAI
```

**2. Vector Store:**
```python
VECTOR_STORE_TYPE: 'opensearch'  # or 'faiss'
AWS_OPENSEARCH_DOMAIN: 'intelycx-waseem-os'
AWS_OPENSEARCH_INDEX: 'aris-rag-index'
AWS_OPENSEARCH_REGION: 'us-east-2'
```

**3. Chunking:**
```python
CHUNKING_STRATEGY: 'comprehensive'
DEFAULT_CHUNK_SIZE: 384  # tokens
DEFAULT_CHUNK_OVERLAP: 120  # tokens
```

**4. Retrieval:**
```python
DEFAULT_RETRIEVAL_K: 12  # chunks
DEFAULT_USE_MMR: True
DEFAULT_MMR_FETCH_K: 50
DEFAULT_MMR_LAMBDA: 0.35
DEFAULT_SEARCH_MODE: 'hybrid'
```

**5. Agentic RAG:**
```python
DEFAULT_USE_AGENTIC_RAG: True
DEFAULT_MAX_SUB_QUERIES: 4
DEFAULT_CHUNKS_PER_SUBQUERY: 6
DEFAULT_MAX_TOTAL_CHUNKS: 25
DEFAULT_DEDUPLICATION_THRESHOLD: 0.95
```

### 11.2 Configuration Methods

**Class Methods:**
- `get_model_config()` - Model settings
- `get_chunking_config()` - Chunking parameters
- `get_opensearch_config()` - OpenSearch settings
- `get_hybrid_search_config()` - Search weights
- `get_agentic_rag_config()` - Agentic RAG settings

---

## 12. DATA FLOW DIAGRAMS

### 12.1 Complete Document Upload Flow

```
User Uploads PDF
    │
    ▼
POST /documents (FastAPI)
    │
    ├── Validate file type
    ├── Generate document_id (UUID)
    ├── Save file to disk
    ├── Calculate file hash (SHA256)
    ├── Check for duplicates
    │
    ▼
Background Task: DocumentProcessor.process_document()
    │
    ├── [Step 1] Validation (0-10%)
    │   └── File type, size, existence
    │
    ├── [Step 2] Parsing (10-45%)
    │   └── ParserFactory.parse_with_fallback()
    │       ├── Detect PDF type
    │       ├── Try parsers in order
    │       └── Return ParsedDocument
    │
    ├── [Step 3] Chunking (45-60%)
    │   └── TokenTextSplitter.split_text()
    │       ├── Split into chunks (384 tokens)
    │       ├── Overlap (120 tokens)
    │       └── Preserve sentences
    │
    ├── [Step 4] Embedding & Storage (60-90%)
    │   └── RAGSystem.add_documents_incremental()
    │       ├── Generate embeddings (OpenAI)
    │       ├── Store in OpenSearch (per-doc index)
    │       └── Track metrics
    │
    ├── [Step 5] Image Storage (90-95%)
    │   └── _store_images_in_opensearch()
    │       ├── Extract OCR text
    │       ├── Generate embeddings
    │       └── Store in images index
    │
    └── [Step 6] Registry Update (95-100%)
        └── DocumentRegistry.save_document()
            └── Save metadata to JSON
```

### 12.2 Complete Query Flow

```
User Query (POST /query)
    │
    ▼
Parse QueryRequest
    │
    ├── Apply focus adjustments
    │   ├── important → 2x k, hybrid
    │   ├── summary → k=20, MMR, summary prompt
    │   └── specific → k=6, semantic
    │
    ▼
ServiceContainer.query_text_only()
    │
    ├── Set document filter (if document_id)
    ├── Set active_sources
    └── Set document_index_map
    │
    ▼
RAGSystem.query_with_rag()
    │
    ├── Check agentic RAG
    │
    ├── IF Agentic RAG:
    │   └── QueryDecomposer.decompose_query()
    │       ├── Check if simple
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

---

## 13. ERROR HANDLING & RESILIENCE

### 13.1 Error Handling Strategy

**Graceful Degradation:**
- Fallback parsers (PyMuPDF → Docling → Textract)
- Fallback to FAISS if OpenSearch fails
- Continue processing on non-critical errors

**Dimension Mismatch Handling:**
- **FAISS:** Auto-recreate on mismatch
- **OpenSearch:** Auto-delete and recreate index
- Both: Clear error messages with solutions

**Parser Errors:**
- Timeout handling (Docling: 30 min)
- Progress tracking during long operations
- Error recovery with fallback parsers

### 13.2 Error Types

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

### 13.3 Logging

**Comprehensive logging throughout:**
- Structured logging with levels
- Progress tracking
- Error details with stack traces
- Performance metrics

**Log Files:**
- `logs/fastapi.log` - API logs
- `logs/document_processor.log` - Processing logs
- Console output for real-time monitoring

---

## 14. DESIGN PATTERNS USED

### 14.1 Service Container Pattern
- Centralized initialization
- Dependency injection
- Lifecycle management

### 14.2 Factory Pattern
- `ParserFactory` - Parser selection
- `VectorStoreFactory` - Vector store creation

### 14.3 Strategy Pattern
- Chunking strategies (precise, balanced, comprehensive)
- Search modes (semantic, keyword, hybrid)

### 14.4 Repository Pattern
- `DocumentRegistry` - Abstracted persistence
- Easy to swap backends

### 14.5 Template Method Pattern
- `BaseParser` - Common parsing interface
- Parser-specific implementations

---

## 15. KEY ALGORITHMS

### 15.1 Adaptive Chunking

**Purpose:** Optimize chunk size for large documents

**Algorithm:**
```python
1. Estimate total tokens
2. Calculate estimated chunks
3. IF estimated_chunks > 200 AND chunk_size <= 512:
   ├── Calculate target chunk size
   ├── Limit to 512-1536 range
   ├── Calculate proportional overlap
   └── Use adaptive splitter
4. ELSE:
   └── Use configured splitter
```

### 15.2 Query Decomposition

**Purpose:** Break complex queries into sub-queries

**Algorithm:**
```python
1. Check if simple query
   └── IF simple → Return [question]

2. Call LLM for decomposition
   ├── System prompt with examples
   ├── User prompt: "Decompose: {question}"
   └── Temperature: 0.3

3. Parse response
   ├── Split by newlines
   ├── Remove numbering/bullets
   └── Validate (min length, not duplicate)

4. Return sub-queries
   └── Or [question] if fails
```

### 15.3 MMR Algorithm

**Purpose:** Diverse result retrieval

**Algorithm:**
```python
1. Fetch candidates (fetch_k=50)
2. Select most relevant first
3. FOR remaining k-1:
   ├── relevance = similarity(query, doc)
   ├── max_similarity = max(similarity(doc, selected))
   └── score = λ * relevance - (1-λ) * max_similarity
4. Select highest score
5. Repeat until k selected
```

---

## 16. FILE ORGANIZATION

### 16.1 Current Structure

```
aris/
├── api/                    # FastAPI application
│   ├── main.py            # Main API (17 endpoints)
│   ├── app.py             # Streamlit UI
│   ├── service.py         # Service container
│   ├── schemas.py         # Pydantic models
│   └── rag_system.py      # Core RAG (5,600 lines)
│
├── parsers/               # Document parsers
│   ├── base_parser.py     # Base interface
│   ├── docling_parser.py  # Advanced OCR (1,684 lines)
│   ├── pymupdf_parser.py # Fast parser
│   └── parser_factory.py  # Parser selection
│
├── vectorstores/          # Vector storage
│   ├── opensearch_store.py      # Text storage (986 lines)
│   ├── opensearch_images_store.py  # Image storage (693 lines)
│   └── vector_store_factory.py  # Factory
│
├── ingestion/             # Document processing
│   └── document_processor.py  # Processing pipeline (760 lines)
│
├── rag/                   # RAG components
│   └── query_decomposer.py  # Agentic RAG (248 lines)
│
├── storage/               # Persistence
│   └── document_registry.py  # JSON registry (309 lines)
│
├── config/                # Configuration
│   └── settings.py       # ARISConfig (157 lines)
│
├── utils/                 # Utilities
│   ├── tokenizer.py      # Token-aware splitting
│   ├── chunking_strategies.py  # Chunking presets
│   └── ocr_verifier.py   # OCR verification
│
├── scripts/               # Scripts
│   ├── all_scripts/      # All .sh files (45 files)
│   └── utilities/        # Python utilities
│
├── tests/                 # Test suite (78 files)
├── documentation/         # Documentation
└── reports/              # Test reports
```

### 16.2 Root Directory (Clean)

**Essential Files Only:**
- `app.py` - Streamlit entry point
- `rag_system.py` - RAG re-export
- `README.md` - Project documentation
- `Dockerfile`, `docker-compose.yml` - Docker config
- `pytest.ini` - Test config
- `.env` - Environment variables

**All other files organized in folders**

---

## 17. KEY INSIGHTS & FINDINGS

### 17.1 Architecture Strengths

1. **Clear Separation of Concerns**
   - API layer separate from business logic
   - Service container for dependency management
   - Parser abstraction for flexibility

2. **Production-Ready Features**
   - Comprehensive error handling
   - Logging throughout
   - Health checks
   - Graceful degradation

3. **Advanced RAG Capabilities**
   - Agentic RAG with query decomposition
   - Hybrid search (semantic + keyword)
   - MMR for diversity
   - Multi-modal (text + images)

4. **Flexible Configuration**
   - Environment-based
   - Sensible defaults
   - Easy to tune

### 17.2 Recent Improvements

1. **Dimension Mismatch Auto-Fix**
   - Automatically handles embedding dimension changes
   - Deletes and recreates indexes
   - No manual intervention needed

2. **Per-Document Indexing**
   - Document isolation
   - Better query performance
   - Easier deletion

3. **Image OCR Storage**
   - Separate index for images
   - Query by image number
   - Full OCR text retrieval

### 17.3 Code Quality

**Strengths:**
- Type hints throughout
- Comprehensive docstrings
- Error handling
- Logging

**Areas for Improvement:**
- More unit tests
- Integration test coverage
- CI/CD pipeline
- Monitoring (Prometheus/Grafana)

---

## 18. SYSTEM METRICS

### 18.1 Code Statistics
- **Total Python Files:** 131
- **Total Python Lines:** 45,550+
- **API Endpoints:** 17
- **Parsers:** 5
- **Vector Stores:** 2 (OpenSearch, FAISS)
- **Test Files:** 78

### 18.2 Component Sizes
- `api/rag_system.py`: ~5,600 lines (core RAG)
- `parsers/docling_parser.py`: ~1,684 lines (advanced parser)
- `vectorstores/opensearch_store.py`: ~986 lines
- `api/main.py`: ~2,100 lines (API endpoints)
- `api/schemas.py`: ~425 lines (data models)
- `ingestion/document_processor.py`: ~760 lines

---

## 19. DEPENDENCIES & INTEGRATIONS

### 19.1 External Services
- **OpenSearch (AWS)** - Vector + keyword search
- **OpenAI** - Embeddings & LLM
- **AWS Services** - OpenSearch, Textract (optional), S3 (optional)

### 19.2 Key Python Packages
- `fastapi` - REST API framework
- `streamlit` - Web UI framework
- `langchain` - RAG framework
- `langchain-openai` - OpenAI integration
- `langchain-community` - OpenSearch integration
- `docling` - Advanced PDF parsing
- `pymupdf` - Fast PDF parsing
- `boto3` - AWS SDK
- `pydantic` - Data validation
- `tiktoken` - Token counting

---

## 20. CONCLUSION

### System Maturity: **Production-Grade (8.5/10)**

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
- ✅ Comprehensive API (17 endpoints)
- ✅ Robust error handling
- ✅ Flexible configuration
- ✅ Recent improvements (dimension mismatch fix, per-document indexing)

With additional testing, monitoring, and security enhancements, this would be a 10/10 enterprise-grade system.

---

**Analysis Complete**  
**Date:** December 30, 2025  
**Total Components Analyzed:** 50+  
**Lines of Code Reviewed:** 45,550+  
**Documentation Created:** Complete step-by-step analysis
