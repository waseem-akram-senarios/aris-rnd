# Complete Unified API Guide

## 🎯 **ALL UI FEATURES VIA API**

Your entire Streamlit UI is now available through **7 powerful REST API endpoints**!

---

## 📋 **THE 7 UNIFIED ENDPOINTS**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ui/dashboard` | GET | Complete UI in one call |
| `/ui/settings` | GET/POST | All settings (API, model, parser, chunking, vector store) |
| `/ui/library` | GET | Document library (8 documents stored) |
| `/ui/metrics` | GET | R&D metrics & analytics |
| `/ui/status` | GET | System status & health check |
| `/ui/library/{id}` | GET | Specific document details |
| `/ui/settings?section=X` | GET | Specific settings section |

---

## 🚀 **QUICK START**

### **Get Complete Dashboard (Everything at Once)**
```bash
curl -X GET "http://44.221.84.58:8500/ui/dashboard"
```

**Response includes:**
- All settings (API provider, models, parser, chunking, vector store)
- Document library (8 documents)
- R&D metrics
- How to use instructions
- Supported formats

---

## 📖 **DETAILED USAGE**

### **1. GET ALL SETTINGS**

```bash
curl -X GET "http://44.221.84.58:8500/ui/settings"
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
    "openai_model_description": "Latest GPT-4o model with vision capabilities",
    "embedding_model": "text-embedding-3-large",
    "embedding_model_description": "High-quality 3072-dimension embeddings",
    "temperature": 0.0,
    "max_tokens": 1200
  },
  "parser": {
    "current_parser": "docling",
    "options": ["pymupdf", "docling", "textract"],
    "descriptions": {
      "pymupdf": "Fast parser for text-based PDFs",
      "docling": "Extracts the most content, takes 5-10 minutes",
      "textract": "AWS OCR for scanned PDFs"
    }
  },
  "chunking": {
    "strategy": "comprehensive",
    "options": ["comprehensive", "balanced", "fast"],
    "current_config": {
      "chunk_size": 384,
      "chunk_overlap": 120
    }
  },
  "vector_store": {
    "type": "opensearch",
    "options": ["faiss", "opensearch"],
    "opensearch_domain": "intelycx-waseem-os",
    "opensearch_index": "aris-rag-index"
  },
  "library": {
    "total_documents": 8,
    "documents": [...]
  },
  "metrics": {
    "total_documents_processed": 8,
    "total_chunks_created": 150,
    ...
  }
}
```

---

### **2. GET SPECIFIC SETTINGS SECTION**

```bash
# Get only API settings
curl -X GET "http://44.221.84.58:8500/ui/settings?section=api"

# Get only model settings
curl -X GET "http://44.221.84.58:8500/ui/settings?section=model"

# Get only parser settings
curl -X GET "http://44.221.84.58:8500/ui/settings?section=parser"

# Get only chunking settings
curl -X GET "http://44.221.84.58:8500/ui/settings?section=chunking"

# Get only vector store settings
curl -X GET "http://44.221.84.58:8500/ui/settings?section=vector_store"

# Get only library
curl -X GET "http://44.221.84.58:8500/ui/settings?section=library"

# Get only metrics
curl -X GET "http://44.221.84.58:8500/ui/settings?section=metrics"
```

---

### **3. UPDATE SETTINGS (Like Changing UI Dropdowns)**

```bash
# Switch to Cerebras
curl -X POST "http://44.221.84.58:8500/ui/settings" \
  -H "Content-Type: application/json" \
  -d '{"api": {"provider": "cerebras"}}'

# Change model temperature
curl -X POST "http://44.221.84.58:8500/ui/settings" \
  -H "Content-Type: application/json" \
  -d '{"model": {"temperature": 0.5}}'

# Change chunking strategy
curl -X POST "http://44.221.84.58:8500/ui/settings" \
  -H "Content-Type: application/json" \
  -d '{"chunking": {"strategy": "balanced"}}'

# Update multiple settings at once
curl -X POST "http://44.221.84.58:8500/ui/settings" \
  -H "Content-Type: application/json" \
  -d '{
    "api": {"provider": "cerebras"},
    "model": {"temperature": 0.5},
    "chunking": {"strategy": "balanced"}
  }'
```

---

### **4. GET DOCUMENT LIBRARY**

```bash
# Get all documents
curl -X GET "http://44.221.84.58:8500/ui/library"

# Filter by status
curl -X GET "http://44.221.84.58:8500/ui/library?filter_status=success"
curl -X GET "http://44.221.84.58:8500/ui/library?filter_status=failed"
```

**Response:**
```json
{
  "total_documents": 8,
  "documents": [
    {
      "document_id": "...",
      "document_name": "FL10.11 SPECIFIC8 (1).pdf",
      "status": "success",
      "chunks_created": 47,
      "image_count": 13,
      "parser_used": "docling",
      "processing_time": 450.5
    },
    ...
  ],
  "storage_persists": true,
  "successful_documents": 6,
  "failed_documents": 2
}
```

---

### **5. GET SPECIFIC DOCUMENT DETAILS**

```bash
curl -X GET "http://44.221.84.58:8500/ui/library/a1064075-218c-4e7b-8cde-d54337b9c491"
```

---

### **6. GET R&D METRICS**

```bash
# Get all metrics
curl -X GET "http://44.221.84.58:8500/ui/metrics"

# Get specific metric type
curl -X GET "http://44.221.84.58:8500/ui/metrics?metric_type=processing"
curl -X GET "http://44.221.84.58:8500/ui/metrics?metric_type=storage"
curl -X GET "http://44.221.84.58:8500/ui/metrics?metric_type=parsers"
```

**Response:**
```json
{
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
    "failed_documents": 2,
    "total_text_chunks_stored": 150,
    "total_images_stored": 25
  }
}
```

---

### **7. GET SYSTEM STATUS**

```bash
curl -X GET "http://44.221.84.58:8500/ui/status"
```

**Response:**
```json
{
  "status": "operational",
  "api_provider": "openai",
  "vector_store": "opensearch",
  "total_documents": 8,
  "storage_persists": true,
  "endpoints_available": {
    "settings": "GET /ui/settings",
    "library": "GET /ui/library",
    "metrics": "GET /ui/metrics",
    "dashboard": "GET /ui/dashboard",
    "upload": "POST /documents (existing)",
    "query": "POST /query (existing)"
  }
}
```

---

## 📊 **COMPLETE UI MAPPING**

| UI Section | API Endpoint |
|------------|--------------|
| **⚙️ Settings → Choose API** | `GET /ui/settings?section=api` |
| **🤖 Model Settings** | `GET /ui/settings?section=model` |
| **🔧 Parser Settings** | `GET /ui/settings?section=parser` |
| **✂️ Chunking Strategy** | `GET /ui/settings?section=chunking` |
| **💾 Vector Store Settings** | `GET /ui/settings?section=vector_store` |
| **📚 Document Library** | `GET /ui/library` |
| **📊 R&D Metrics** | `GET /ui/metrics` |
| **📄 Upload Documents** | `POST /documents` (existing) |
| **💬 Ask Questions** | `POST /query` (existing) |
| **🔄 Load Stored Documents** | `GET /ui/library` |
| **📖 Review Documents** | `GET /ui/library/{id}` |
| **💾 Storage Information** | `GET /ui/metrics?metric_type=storage` |

---

## 🎯 **COMMON WORKFLOWS**

### **Workflow 1: Check System Status**
```bash
curl -X GET "http://44.221.84.58:8500/ui/status"
```

### **Workflow 2: View All Documents**
```bash
curl -X GET "http://44.221.84.58:8500/ui/library"
```

### **Workflow 3: Switch to Cerebras and Ask Question**
```bash
# 1. Switch to Cerebras
curl -X POST "http://44.221.84.58:8500/ui/settings" \
  -H "Content-Type: application/json" \
  -d '{"api": {"provider": "cerebras"}}'

# 2. Ask question
curl -X POST "http://44.221.84.58:8500/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this document about?", "k": 5}'
```

### **Workflow 4: Get Complete Dashboard**
```bash
curl -X GET "http://44.221.84.58:8500/ui/dashboard"
```

### **Workflow 5: Check Processing Metrics**
```bash
curl -X GET "http://44.221.84.58:8500/ui/metrics"
```

---

## 📦 **DEPLOYMENT**

```bash
# 1. Copy to server
scp api/unified_api.py ubuntu@44.221.84.58:/tmp/
scp api/main.py ubuntu@44.221.84.58:/tmp/

# 2. SSH and deploy
ssh ubuntu@44.221.84.58
sudo cp /tmp/unified_api.py /home/ubuntu/aris/api/
sudo cp /tmp/main.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
exit

# 3. Test
curl -X GET "http://44.221.84.58:8500/ui/dashboard"
```

---

## ✅ **WHAT YOU GET**

### **Complete UI Features:**
- ✅ All settings (API, model, parser, chunking, vector store)
- ✅ Document library (8 documents stored)
- ✅ R&D metrics & analytics
- ✅ Document upload (existing endpoint)
- ✅ Q&A functionality (existing endpoint)
- ✅ Storage information
- ✅ Processing statistics
- ✅ Parser options and descriptions

### **API Benefits:**
- **7 endpoints** instead of 20+
- **Complete UI** via REST API
- **Batch operations** supported
- **Flexible queries** with parameters
- **Consistent responses** across all endpoints

---

## 🔗 **INTEGRATION WITH EXISTING ENDPOINTS**

The unified API works with your existing endpoints:

```bash
# Upload document (existing)
POST /documents

# Query documents (existing)
POST /query
POST /query/text
POST /query/images

# Get document info (existing)
GET /documents
GET /documents/{id}

# NEW: Get UI settings
GET /ui/settings
GET /ui/library
GET /ui/metrics
GET /ui/dashboard
```

---

**Your entire Streamlit UI is now available via REST API!**
