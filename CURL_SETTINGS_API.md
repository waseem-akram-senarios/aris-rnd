# Settings API - CURL Commands

All your UI settings are now available via API!

**Base URL:** `http://44.221.84.58:8500`

---

## 📋 GET ALL SETTINGS

Get complete system configuration (all UI settings in one call):

```bash
curl -X GET "http://44.221.84.58:8500/settings/" | jq '.'
```

**Response includes:**
- Model settings (API provider, models, temperature, max_tokens)
- Parser settings (parser choice, timeout)
- Chunking settings (strategy, chunk size, overlap)
- Vector store settings (type, OpenSearch config)
- Retrieval settings (k, MMR, search mode, weights)
- Agentic RAG settings (sub-queries, chunks, deduplication)

---

## ⚙️ MODEL SETTINGS

### Get Model Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/model" | jq '.'
```

**Response:**
```json
{
  "api_provider": "openai",
  "openai_model": "gpt-4o",
  "cerebras_model": "llama-3.3-70b",
  "embedding_model": "text-embedding-3-large",
  "temperature": 0.0,
  "max_tokens": 1200
}
```

### Update Model Settings
```bash
curl -X POST "http://44.221.84.58:8500/settings/model" \
  -H "Content-Type: application/json" \
  -d '{
    "api_provider": "openai",
    "openai_model": "gpt-4o",
    "cerebras_model": "llama-3.3-70b",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0,
    "max_tokens": 1200
  }' | jq '.'
```

---

## 🔧 PARSER SETTINGS

### Get Parser Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/parser" | jq '.'
```

**Response:**
```json
{
  "parser": "docling",
  "docling_timeout": 1800
}
```

---

## ✂️ CHUNKING SETTINGS

### Get Chunking Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/chunking" | jq '.'
```

**Response:**
```json
{
  "strategy": "comprehensive",
  "chunk_size": 384,
  "chunk_overlap": 120
}
```

### Update Chunking Settings
```bash
curl -X POST "http://44.221.84.58:8500/settings/chunking" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "comprehensive",
    "chunk_size": 384,
    "chunk_overlap": 120
  }' | jq '.'
```

**Valid strategies:** `comprehensive`, `balanced`, `fast`

---

## 💾 VECTOR STORE SETTINGS

### Get Vector Store Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/vector-store" | jq '.'
```

**Response:**
```json
{
  "vector_store_type": "opensearch",
  "opensearch_domain": "intelycx-waseem-os",
  "opensearch_index": "aris-rag-index",
  "opensearch_region": "us-east-2"
}
```

---

## 🔍 RETRIEVAL SETTINGS

### Get Retrieval Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/retrieval" | jq '.'
```

**Response:**
```json
{
  "default_k": 12,
  "use_mmr": true,
  "mmr_fetch_k": 50,
  "mmr_lambda": 0.35,
  "search_mode": "hybrid",
  "semantic_weight": 0.75,
  "keyword_weight": 0.25
}
```

### Update Retrieval Settings
```bash
curl -X POST "http://44.221.84.58:8500/settings/retrieval" \
  -H "Content-Type: application/json" \
  -d '{
    "default_k": 12,
    "use_mmr": true,
    "mmr_fetch_k": 50,
    "mmr_lambda": 0.35,
    "search_mode": "hybrid",
    "semantic_weight": 0.75,
    "keyword_weight": 0.25
  }' | jq '.'
```

**Valid search_mode:** `semantic`, `keyword`, `hybrid`

---

## 🤖 AGENTIC RAG SETTINGS

### Get Agentic RAG Settings
```bash
curl -X GET "http://44.221.84.58:8500/settings/agentic-rag" | jq '.'
```

**Response:**
```json
{
  "use_agentic_rag": true,
  "max_sub_queries": 4,
  "chunks_per_subquery": 6,
  "max_total_chunks": 25,
  "deduplication_threshold": 0.95
}
```

---

## 📚 DOCUMENT LIBRARY

### Get Document Library Info
```bash
curl -X GET "http://44.221.84.58:8500/settings/library" | jq '.'
```

**Response:**
```json
{
  "total_documents": 8,
  "documents": [
    {
      "document_id": "...",
      "document_name": "...",
      "status": "success",
      "chunks_created": 47,
      "images_detected": true,
      "image_count": 13,
      ...
    }
  ],
  "storage_persists": true
}
```

---

## 📊 R&D METRICS & ANALYTICS

### Get Metrics
```bash
curl -X GET "http://44.221.84.58:8500/settings/metrics" | jq '.'
```

**Response:**
```json
{
  "total_documents_processed": 8,
  "total_chunks_created": 150,
  "total_images_extracted": 25,
  "average_processing_time": 450.5,
  "total_queries": 0,
  "average_query_time": 0.0,
  "parsers_used": {
    "docling": 5,
    "pymupdf": 3
  },
  "storage_stats": {
    "successful_documents": 6,
    "failed_documents": 2,
    "total_text_chunks_stored": 150,
    "total_images_stored": 25
  }
}
```

---

## 🎯 COMPLETE UI SETTINGS MAPPING

| UI Section | API Endpoint | Method |
|------------|-------------|--------|
| ⚙️ Model Settings | `/settings/model` | GET/POST |
| 🔧 Parser Settings | `/settings/parser` | GET |
| ✂️ Chunking Strategy | `/settings/chunking` | GET/POST |
| 💾 Vector Store | `/settings/vector-store` | GET |
| 🔍 Retrieval Settings | `/settings/retrieval` | GET/POST |
| 🤖 Agentic RAG | `/settings/agentic-rag` | GET |
| 📚 Document Library | `/settings/library` | GET |
| 📊 Metrics & Analytics | `/settings/metrics` | GET |
| 🌐 All Settings | `/settings/` | GET |

---

## 💡 USAGE EXAMPLES

### Get All Settings at Once
```bash
curl -X GET "http://44.221.84.58:8500/settings/" | jq '.'
```

### Change Model to Cerebras
```bash
curl -X POST "http://44.221.84.58:8500/settings/model" \
  -H "Content-Type: application/json" \
  -d '{
    "api_provider": "cerebras",
    "openai_model": "gpt-4o",
    "cerebras_model": "llama-3.3-70b",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0,
    "max_tokens": 1200
  }' | jq '.'
```

### Change Chunking Strategy
```bash
curl -X POST "http://44.221.84.58:8500/settings/chunking" \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "balanced",
    "chunk_size": 512,
    "chunk_overlap": 100
  }' | jq '.'
```

### Check Document Library
```bash
curl -X GET "http://44.221.84.58:8500/settings/library" | jq '.total_documents, .documents[].document_name'
```

### View Metrics
```bash
curl -X GET "http://44.221.84.58:8500/settings/metrics" | jq '.total_documents_processed, .total_chunks_created, .parsers_used'
```

---

## 📝 NOTES

1. **Runtime vs Persistent Changes:**
   - POST endpoints update runtime configuration
   - To persist changes across restarts, update `.env` file

2. **Validation:**
   - All settings have validation (min/max values, allowed options)
   - Invalid values will return 422 Unprocessable Entity

3. **Authentication:**
   - Currently no authentication required
   - Add authentication for production use

---

**All your UI settings are now accessible via API!**
