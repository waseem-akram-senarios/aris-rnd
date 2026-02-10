# ARIS RAG System - Complete API Reference

**Base URLs:**
- Gateway: `http://44.221.84.58:8500` (Orchestrator - minimal endpoints)
- Ingestion: `http://44.221.84.58:8501` (Document processing + admin)
- Retrieval: `http://44.221.84.58:8502` (Search/query + admin)

---

## 📋 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GATEWAY (:8500)                          │
│           Minimal orchestrator for common operations            │
│   Documents, Queries, Stats, Sync (14 endpoints)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────────┐     ┌─────────────────────────────┐
│   INGESTION (:8501) │     │      RETRIEVAL (:8502)      │
│   Document ingest   │     │   Search, Query, Vectors    │
│   Registry admin    │     │   Index admin, Chunk admin  │
│   (15+ endpoints)   │     │   (25+ endpoints)           │
└─────────────────────┘     └─────────────────────────────┘
```

---

## 🌐 Gateway Service APIs (Minimal)

**Base URL:** `http://44.221.84.58:8500`  
**Role:** Orchestrator - routes to appropriate microservice

### Endpoints (14 total)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root - connectivity check |
| `GET` | `/health` | Health check with registry status |
| `GET` | `/documents` | List all documents |
| `POST` | `/documents` | Upload document (routes to Ingestion) |
| `GET` | `/documents/{id}` | Get document by ID |
| `PUT` | `/documents/{id}` | Update document metadata |
| `DELETE` | `/documents/{id}` | Delete document |
| `GET` | `/documents/{id}/images` | Get document images |
| `POST` | `/query` | RAG query (routes to Retrieval) |
| `POST` | `/query/images` | Image query |
| `GET` | `/stats` | System statistics |
| `GET` | `/stats/chunks` | Chunk statistics |
| `GET` | `/sync/status` | Sync status across all services |
| `POST` | `/sync/force` | Force sync all services |
| `POST` | `/sync/check` | Check and sync if needed |

### Example: Query
```bash
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the leave policy?", "k": 5}'
```

---

## 📥 Ingestion Service APIs

**Base URL:** `http://44.221.84.58:8501`  
**Role:** Document processing, registry management

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/ingest` | Ingest document (async) |
| `POST` | `/process` | Process document (sync) |
| `GET` | `/status/{document_id}` | Processing status |
| `GET` | `/metrics` | Processing metrics |

### Index Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/indexes/{name}/exists` | Check if index exists |
| `GET` | `/indexes/{base}/next-available` | Get next available index name |

### Sync Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sync/status` | Sync status |
| `POST` | `/sync/force` | Force sync |
| `POST` | `/sync/check` | Check and sync |

### Admin - Document Registry

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/admin/documents` | Create document entry |
| `PUT` | `/admin/documents/{id}` | Update document metadata |
| `DELETE` | `/admin/documents/{id}` | Delete document |
| `POST` | `/admin/documents/bulk-delete` | Bulk delete documents |
| `GET` | `/admin/documents/registry-stats` | Registry statistics |

### Example: Ingest Document
```bash
curl -X POST http://44.221.84.58:8501/ingest \
  -F "file=@document.pdf" \
  -F "parser_preference=ocrmypdf"
```

---

## 🔍 Retrieval Service APIs

**Base URL:** `http://44.221.84.58:8502`  
**Role:** Search, querying, vector database management

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/query` | RAG query |
| `POST` | `/query/images` | Image search |
| `GET` | `/documents/{id}/images` | Get document images |
| `DELETE` | `/documents/{id}` | Delete document vectors |
| `GET` | `/metrics` | Query metrics |

### Sync Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/sync/status` | Sync status |
| `POST` | `/sync/force` | Force sync |
| `POST` | `/sync/check` | Check and sync |

### Admin - Vector Indexes

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/indexes` | List all indexes |
| `GET` | `/admin/indexes/{name}` | Get index info |
| `DELETE` | `/admin/indexes/{name}` | Delete index |
| `POST` | `/admin/indexes/bulk-delete` | Bulk delete indexes |

### Admin - Chunks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/indexes/{name}/chunks` | List chunks |
| `POST` | `/admin/indexes/{name}/chunks` | Create chunk |
| `GET` | `/admin/indexes/{name}/chunks/{id}` | Get chunk |
| `PUT` | `/admin/indexes/{name}/chunks/{id}` | Update chunk |
| `DELETE` | `/admin/indexes/{name}/chunks/{id}` | Delete chunk |

### Admin - Index Map

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin/index-map` | Get document-to-index mapping |
| `POST` | `/admin/index-map` | Update mapping |
| `DELETE` | `/admin/index-map/{doc_name}` | Delete mapping entry |

### Admin - Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/admin/search` | Direct vector search |

### Example: Direct Vector Search
```bash
curl -X POST http://44.221.84.58:8502/admin/search \
  -H "Content-Type: application/json" \
  -d '{"query": "leave policy", "k": 10}'
```

---

## 📊 Summary

| Service | Endpoints | Purpose |
|---------|-----------|---------|
| **Gateway** | 14 | Orchestration, routing |
| **Ingestion** | 15+ | Document processing, registry |
| **Retrieval** | 25+ | Search, vectors, admin |
| **Total** | 54+ | |

---

## 🔗 Quick Reference by Use Case

### Common Operations (via Gateway)
```bash
# List documents
curl http://44.221.84.58:8500/documents

# Upload document
curl -X POST http://44.221.84.58:8500/documents -F "file=@doc.pdf"

# Query
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "your question"}'
```

### Admin Operations (direct to services)
```bash
# Registry stats (Ingestion)
curl http://44.221.84.58:8501/admin/documents/registry-stats

# List vector indexes (Retrieval)
curl http://44.221.84.58:8502/admin/indexes

# Get index map (Retrieval)
curl http://44.221.84.58:8502/admin/index-map

# Delete index (Retrieval)
curl -X DELETE "http://44.221.84.58:8502/admin/indexes/my-index?confirm=true"
```

---

## 🔐 Notes

1. **No authentication** - currently all endpoints are public
2. **Admin operations** - go directly to Ingestion/Retrieval services
3. **Gateway** - only handles common user-facing operations
4. **Timeouts** - 30-60s for queries, 10s for simple operations

---

**Last Updated:** January 16, 2026  
**Version:** 2.0.0 (Minimal Gateway)
