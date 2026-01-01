# Deep Codebase Analysis & Improvement Plan
**Date:** 2025-12-31 (Updated)
**Scope:** ARIS RAG System

---

## 1. Executive Summary
The ARIS codebase has evolved into a **Unified "Hybrid-Storage" Monolith**. It now features S3-backed document storage, a modular Service Layer, and state-of-the-art Accuracy features (Reranking, Recursive Chunking).

**Current Strengths (New):**
- **Unified Architecture:** UI and API share the exact same `ServiceContainer` logic (`api/service.py`).
- **High Accuracy:** RAG pipeline now uses `FlashRank` Cross-Encoder and Context-Aware Chunking.
- **Scalable Storage:** Documents are stored in S3, decoupled from the compute instance.
- **Configurability:** `ARISConfig` drives all defaults (Chunking, Reranking, Models).

**Remaining Critical Weaknesses:**
- **Concurrency Model:** Ingestion is still synchronous (via ThreadPool). Heavy parsing can block queries.
- **State Management:** `document_registry.json` is simple but not concurrent-safe or queryable.
- **Security:** Still missing API Key authentication.

---

## 2. Current Architecture Snapshot

### 🏗️ Design Pattern: "Modular Service Monolith"
- **Frontend Layer:** 
    - **Streamlit (`api/app.py`)**: UI for uploading/querying. Connects to Service Layer.
    - **FastAPI (`api/main.py`)**: REST API. Connects to Service Layer.
- **Service Layer (`api/service.py`)**:
    - **`ServiceContainer`**: Singleton that holds `RAGSystem`, `DocumentProcessor`, and `MetricsCollector`.
    - **Responsibility**: Single Source of Truth for system initialization.
- **Core Logic Layer (`api/rag_system.py`)**:
    - Handles Retrieval, Reranking (`FlashRank`), Generation, and Vector Store Ops.
- **Storage Layer**:
    - **Vector**: OpenSearch (AWS) or FAISS (Local).
    - **Blob**: AWS S3 (Documents).
    - **Metadata**: JSON File (`document_registry.json`).

---

## 3. Improvement Plans (Roadmap)

### Step 1: Concurrency & Performance (High Priority)
*Current Bottleneck: Parsing blocks the CPU.*
1.  **Implement Process Isolation:** 
    - Wrap `ParserFactory.parse_with_fallback` in `concurrent.futures.ProcessPoolExecutor`. 
    - **Impact:** Decouples heavy layout analysis (Docling/PyMuPDF) from the API loop. Responsiveness increases 10x during upload.

### Step 2: Database & State (Medium Priority)
*Current Bottleneck: JSON is fragile.*
1.  **Migrate to SQLite:**
    - Replace `document_registry.json` with `aris.db` (SQLite).
    - Use SQLAlchemy for reliable ACID transactions.
    - **Impact:** Job status survives crashes. Multiple users can write safely.

### Step 3: Security (Medium Priority)
*Current Risk: Open API.*
1.  **Add API Key Auth:**
    - Middleware to check `X-API-Key` header.
    - **Impact:** Prevents unauthorized uploads.

### Step 4: Distributed Task Queue (Future Scale)
*Only needed if handling >1000 concurrent uploads.*
1.  **Celery + Redis:**
    - Move ingestion to separate worker nodes.

---

## 4. Immediate Recommendation

Proceed with **Step 1 (Process Isolation)**. It is a pure code change (no new infra) that solves the "Laggy UI during upload" problem.

Then proceed to **Step 2 (SQLite)** to solve the "Lost progress on restart" problem.
