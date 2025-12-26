# Consolidated API Guide

## 🎯 **3 POWERFUL ENDPOINTS INSTEAD OF 20+**

All your UI settings and system information are now available through just **3 consolidated endpoints**!

---

## 📋 **THE 3 CONSOLIDATED ENDPOINTS**

### **1. GET `/api/config` - Unified Configuration**
Get or query any configuration section

### **2. POST `/api/config` - Update Configuration**
Update any settings in one call

### **3. GET `/api/system` - Complete System Info**
Get library, metrics, and config together

---

## 🚀 **USAGE EXAMPLES**

### **1. GET ALL CONFIGURATION**

```bash
curl -X GET "http://44.221.84.58:8500/api/config"
```

**Response:**
```json
{
  "model": {
    "api_provider": "openai",
    "openai_model": "gpt-4o",
    "cerebras_model": "llama-3.3-70b",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0,
    "max_tokens": 1200
  },
  "parser": {
    "parser": "docling",
    "docling_timeout": 1800
  },
  "chunking": {
    "strategy": "comprehensive",
    "chunk_size": 384,
    "chunk_overlap": 120
  },
  "vector_store": {
    "vector_store_type": "opensearch",
    "opensearch_domain": "intelycx-waseem-os",
    "opensearch_index": "aris-rag-index",
    "opensearch_region": "us-east-2"
  },
  "retrieval": {
    "default_k": 12,
    "use_mmr": true,
    "search_mode": "hybrid",
    "semantic_weight": 0.75,
    "keyword_weight": 0.25
  },
  "agentic_rag": {
    "use_agentic_rag": true,
    "max_sub_queries": 4,
    "chunks_per_subquery": 6,
    "max_total_chunks": 25
  }
}
```

---

### **2. GET SPECIFIC CONFIGURATION SECTION**

```bash
# Get only model settings
curl -X GET "http://44.221.84.58:8500/api/config?section=model"

# Get only chunking settings
curl -X GET "http://44.221.84.58:8500/api/config?section=chunking"

# Get only retrieval settings
curl -X GET "http://44.221.84.58:8500/api/config?section=retrieval"
```

**Valid sections:**
- `model` - Model configuration
- `parser` - Parser settings
- `chunking` - Chunking strategy
- `vector_store` - Vector store config
- `retrieval` - Retrieval settings
- `agentic_rag` - Agentic RAG config
- `all` - Everything (default)

---

### **3. UPDATE CONFIGURATION (Multiple Sections at Once)**

```bash
curl -X POST "http://44.221.84.58:8500/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "model": {
      "api_provider": "cerebras",
      "temperature": 0.5
    },
    "chunking": {
      "strategy": "balanced",
      "chunk_size": 512
    },
    "retrieval": {
      "default_k": 15,
      "search_mode": "semantic"
    }
  }'
```

**Response:**
```json
{
  "status": "success",
  "message": "Updated 3 configuration section(s)",
  "updated_sections": ["model", "chunking", "retrieval"],
  "note": "Changes are runtime only. Update .env file to persist across restarts."
}
```

**You can update:**
- One section at a time
- Multiple sections together
- Only specific fields (others remain unchanged)

---

### **4. GET COMPLETE SYSTEM INFORMATION**

```bash
curl -X GET "http://44.221.84.58:8500/api/system"
```

**Response:**
```json
{
  "library": {
    "total_documents": 8,
    "documents": [...],
    "storage_persists": true
  },
  "metrics": {
    "total_documents_processed": 8,
    "total_chunks_created": 150,
    "total_images_extracted": 25,
    "average_processing_time": 450.5,
    "parsers_used": {
      "docling": 5,
      "pymupdf": 3
    },
    "storage_stats": {
      "successful_documents": 6,
      "failed_documents": 2
    }
  },
  "config": {
    "model": {...},
    "chunking": {...},
    "vector_store": {...},
    "retrieval": {...}
  }
}
```

---

### **5. GET SPECIFIC SYSTEM INFORMATION**

```bash
# Get only document library
curl -X GET "http://44.221.84.58:8500/api/system?include=library"

# Get only metrics
curl -X GET "http://44.221.84.58:8500/api/system?include=metrics"

# Get only configuration
curl -X GET "http://44.221.84.58:8500/api/system?include=config"

# Get everything (default)
curl -X GET "http://44.221.84.58:8500/api/system?include=all"
```

---

## 📊 **COMPARISON: BEFORE vs AFTER**

### **BEFORE (12 separate endpoints):**
```bash
GET /settings/
GET /settings/model
GET /settings/parser
GET /settings/chunking
GET /settings/vector-store
GET /settings/retrieval
GET /settings/agentic-rag
GET /settings/library
GET /settings/metrics
POST /settings/model
POST /settings/chunking
POST /settings/retrieval
```

### **AFTER (3 consolidated endpoints):**
```bash
GET  /api/config        # Get any/all config
POST /api/config        # Update any config
GET  /api/system        # Get library + metrics + config
```

**Result:** 12 endpoints → 3 endpoints (75% reduction!)

---

## 🎯 **COMMON USE CASES**

### **Use Case 1: Check Current Settings**
```bash
curl -X GET "http://44.221.84.58:8500/api/config"
```

### **Use Case 2: Switch to Cerebras**
```bash
curl -X POST "http://44.221.84.58:8500/api/config" \
  -H "Content-Type: application/json" \
  -d '{"model": {"api_provider": "cerebras"}}'
```

### **Use Case 3: Change Chunking Strategy**
```bash
curl -X POST "http://44.221.84.58:8500/api/config" \
  -H "Content-Type: application/json" \
  -d '{"chunking": {"strategy": "balanced", "chunk_size": 512}}'
```

### **Use Case 4: Get Document Library Stats**
```bash
curl -X GET "http://44.221.84.58:8500/api/system?include=library"
```

### **Use Case 5: Get Processing Metrics**
```bash
curl -X GET "http://44.221.84.58:8500/api/system?include=metrics"
```

### **Use Case 6: Get Everything at Once**
```bash
curl -X GET "http://44.221.84.58:8500/api/system"
```

---

## 📋 **COMPLETE API MAPPING**

| Old Endpoints | New Endpoint | Query Parameter |
|--------------|--------------|-----------------|
| `GET /settings/` | `GET /api/config` | - |
| `GET /settings/model` | `GET /api/config` | `?section=model` |
| `GET /settings/chunking` | `GET /api/config` | `?section=chunking` |
| `GET /settings/retrieval` | `GET /api/config` | `?section=retrieval` |
| `POST /settings/model` | `POST /api/config` | Body: `{"model": {...}}` |
| `POST /settings/chunking` | `POST /api/config` | Body: `{"chunking": {...}}` |
| `GET /settings/library` | `GET /api/system` | `?include=library` |
| `GET /settings/metrics` | `GET /api/system` | `?include=metrics` |

---

## ✅ **BENEFITS**

1. **Fewer Endpoints** - 3 instead of 12
2. **More Flexible** - Query exactly what you need
3. **Batch Updates** - Update multiple settings in one call
4. **Consistent API** - Same pattern for all operations
5. **Less Code** - Easier to maintain
6. **Better Performance** - Fewer HTTP requests

---

## 🚀 **DEPLOYMENT**

Deploy the new consolidated endpoint:

```bash
# Copy to server
scp api/consolidated_endpoints.py ubuntu@44.221.84.58:/tmp/

# SSH and deploy
ssh ubuntu@44.221.84.58
sudo cp /tmp/consolidated_endpoints.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
```

---

**3 powerful endpoints. All your options. Much simpler!**
