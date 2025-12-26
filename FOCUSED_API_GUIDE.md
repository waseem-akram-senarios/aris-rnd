# Focused API Guide

## 🎯 **5 FOCUSED ENDPOINTS**

Clean, minimal API structure - no repetition, just what you need.

---

## 📋 **THE 5 ENDPOINTS**

| Endpoint | Methods | Purpose |
|----------|---------|---------|
| `/v1/config` | GET, POST | All configuration (API, model, parser, chunking, vector store) |
| `/v1/library` | GET | Document library with filtering |
| `/v1/library/{id}` | GET | Specific document details |
| `/v1/metrics` | GET | Processing metrics & analytics |
| `/v1/status` | GET | System health & overview |

**Plus existing optimized endpoints:**
- `POST /documents` - Upload
- `POST /query` - Query
- `GET /documents/{id}/storage/status` - Storage details
- `GET /documents/{id}/images/all` - Images
- `GET /documents/{id}/accuracy` - Accuracy

---

## 🚀 **USAGE**

### **1. GET CONFIGURATION**

```bash
# All configuration
curl -X GET "http://44.221.84.58:8500/v1/config"

# Specific section
curl -X GET "http://44.221.84.58:8500/v1/config?section=model"
curl -X GET "http://44.221.84.58:8500/v1/config?section=chunking"
curl -X GET "http://44.221.84.58:8500/v1/config?section=vector_store"
```

**Response:**
```json
{
  "api": {
    "provider": "openai",
    "options": ["openai", "cerebras"]
  },
  "model": {
    "openai_model": "gpt-4o",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0,
    "max_tokens": 1200
  },
  "parser": {
    "current": "docling",
    "options": ["pymupdf", "docling", "textract"]
  },
  "chunking": {
    "strategy": "comprehensive",
    "chunk_size": 384,
    "chunk_overlap": 120
  },
  "vector_store": {
    "type": "opensearch",
    "opensearch_domain": "intelycx-waseem-os",
    "opensearch_index": "aris-rag-index"
  },
  "retrieval": {
    "default_k": 12,
    "search_mode": "hybrid",
    "use_mmr": true
  }
}
```

---

### **2. UPDATE CONFIGURATION**

```bash
curl -X POST "http://44.221.84.58:8500/v1/config" \
  -H "Content-Type: application/json" \
  -d '{
    "api": {"provider": "cerebras"},
    "model": {"temperature": 0.5},
    "chunking": {"strategy": "balanced"}
  }'
```

**Response:**
```json
{
  "status": "success",
  "updated": ["api", "model", "chunking"],
  "message": "Updated 3 section(s)"
}
```

---

### **3. GET DOCUMENT LIBRARY**

```bash
# All documents
curl -X GET "http://44.221.84.58:8500/v1/library"

# Filter by status
curl -X GET "http://44.221.84.58:8500/v1/library?status=success"
curl -X GET "http://44.221.84.58:8500/v1/library?status=failed"
```

**Response:**
```json
{
  "total": 8,
  "documents": [
    {
      "document_id": "...",
      "document_name": "FL10.11 SPECIFIC8 (1).pdf",
      "status": "success",
      "chunks_created": 47,
      "image_count": 13,
      "parser_used": "docling",
      "processing_time": 450.5
    }
  ],
  "successful": 6,
  "failed": 2
}
```

---

### **4. GET SPECIFIC DOCUMENT**

```bash
curl -X GET "http://44.221.84.58:8500/v1/library/a1064075-218c-4e7b-8cde-d54337b9c491"
```

---

### **5. GET METRICS**

```bash
curl -X GET "http://44.221.84.58:8500/v1/metrics"
```

**Response:**
```json
{
  "total_documents": 8,
  "total_chunks": 150,
  "total_images": 25,
  "avg_processing_time": 450.5,
  "parsers": {
    "docling": 5,
    "pymupdf": 3
  },
  "storage": {
    "successful": 6,
    "failed": 2,
    "text_chunks": 150,
    "images_stored": 25
  }
}
```

---

### **6. GET SYSTEM STATUS**

```bash
curl -X GET "http://44.221.84.58:8500/v1/status"
```

**Response:**
```json
{
  "status": "operational",
  "api_provider": "openai",
  "vector_store": "opensearch",
  "total_documents": 8,
  "endpoints": {
    "config": "GET/POST /v1/config",
    "library": "GET /v1/library",
    "metrics": "GET /v1/metrics",
    "status": "GET /v1/status",
    "upload": "POST /documents",
    "query": "POST /query"
  }
}
```

---

## 📊 **COMPLETE API STRUCTURE**

### **Focused Endpoints (5):**
1. `GET/POST /v1/config` - Configuration
2. `GET /v1/library` - Document library
3. `GET /v1/library/{id}` - Document details
4. `GET /v1/metrics` - Metrics
5. `GET /v1/status` - Status

### **Existing Endpoints (unchanged):**
- `POST /documents` - Upload
- `DELETE /documents/{id}` - Delete
- `POST /query` - Query
- `POST /query/text` - Text query
- `POST /query/images` - Image query
- `GET /documents/{id}/storage/status` - Storage
- `GET /documents/{id}/images/all` - Images
- `GET /documents/{id}/accuracy` - Accuracy
- `GET /documents/{id}/pages/{page}` - Page content

**Total: ~14 endpoints (down from 20+)**

---

## 🎯 **COMMON WORKFLOWS**

### **Check System**
```bash
curl -X GET "http://44.221.84.58:8500/v1/status"
```

### **View Documents**
```bash
curl -X GET "http://44.221.84.58:8500/v1/library"
```

### **View Metrics**
```bash
curl -X GET "http://44.221.84.58:8500/v1/metrics"
```

### **Change Settings**
```bash
# Switch to Cerebras
curl -X POST "http://44.221.84.58:8500/v1/config" \
  -H "Content-Type: application/json" \
  -d '{"api": {"provider": "cerebras"}}'

# Verify
curl -X GET "http://44.221.84.58:8500/v1/config?section=api"
```

### **Upload and Query**
```bash
# Upload (existing endpoint)
curl -X POST "http://44.221.84.58:8500/documents" -F "file=@document.pdf"

# Query (existing endpoint)
curl -X POST "http://44.221.84.58:8500/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?", "k": 5}'
```

---

## 📦 **DEPLOYMENT**

```bash
# Copy to server
scp api/focused_endpoints.py ubuntu@44.221.84.58:/tmp/
scp api/main.py ubuntu@44.221.84.58:/tmp/

# SSH and deploy
ssh ubuntu@44.221.84.58
sudo cp /tmp/focused_endpoints.py /home/ubuntu/aris/api/
sudo cp /tmp/main.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
exit

# Test
curl -X GET "http://44.221.84.58:8500/v1/status"
```

---

## ✅ **BENEFITS**

- **5 focused endpoints** for settings/library/metrics
- **Clean structure** - `/v1/` prefix for versioning
- **No repetition** - each endpoint has clear purpose
- **Flexible** - query parameters for filtering
- **Simple** - easy to understand and use

---

## 📋 **UI MAPPING**

| UI Section | API Endpoint |
|------------|--------------|
| ⚙️ Settings | `GET /v1/config` |
| 🤖 Model Settings | `GET /v1/config?section=model` |
| 🔧 Parser | `GET /v1/config?section=parser` |
| ✂️ Chunking | `GET /v1/config?section=chunking` |
| 💾 Vector Store | `GET /v1/config?section=vector_store` |
| 📚 Document Library | `GET /v1/library` |
| 📊 Metrics | `GET /v1/metrics` |
| 📄 Upload | `POST /documents` |
| 💬 Query | `POST /query` |

---

**Clean, focused, minimal - exactly what you need!**
