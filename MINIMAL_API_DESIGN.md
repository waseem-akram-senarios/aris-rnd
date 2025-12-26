# Minimal API Design - Sync with UI

## 🎯 **GOAL**
Reduce from 26+ endpoints to **5-7 CORE ENDPOINTS** using multipart forms and query parameters.

---

## 📊 **CURRENT PROBLEM**
- 26+ endpoints in Swagger UI
- Too many similar endpoints (POST /query, POST /query/text, POST /query/images)
- Not synced with UI needs
- Confusing for users

---

## ✅ **PROPOSED MINIMAL API (7 ENDPOINTS)**

### **1. Health & Info (2 endpoints)**
```
GET  /health                    # Health check
GET  /info                      # System info (replaces /v1/status, /v1/metrics)
```

### **2. Configuration (2 endpoints)**
```
GET  /config                    # Get all settings (replaces /v1/config)
  ?section=model|parser|chunking|vectorstore|retrieval
  
POST /config                    # Update settings
```

### **3. Documents (1 endpoint - MULTIPART)**
```
POST /documents                 # Upload ANY type (text/image/pdf)
  - Multipart form with file
  - Auto-detect type
  - Returns document_id
  
GET  /documents                 # List all documents
  ?document_id=xxx             # Get specific document info
  
DELETE /documents/{id}          # Delete document
```

### **4. Query (1 endpoint - UNIFIED)**
```
POST /query                     # Query ANYTHING
  ?type=text|image|document    # What to query
  ?document_id=xxx             # Optional: filter to specific doc
  
  Body:
  {
    "question": "...",
    "k": 12,
    "search_mode": "hybrid"
  }
```

---

## 🔥 **CONSOLIDATED DESIGN**

### **BEFORE (26 endpoints):**
```
POST /documents                 # Upload
POST /query                     # Query all
POST /query/text                # Query text
POST /query/images              # Query images
POST /documents/{id}/query      # Query specific doc
GET  /documents/{id}            # Get doc info
GET  /documents/{id}/storage/status
GET  /documents/{id}/images/all
GET  /documents/{id}/images-summary
GET  /documents/{id}/images/{number}
GET  /documents/{id}/pages/{page}
POST /documents/{id}/store/text
POST /documents/{id}/store/images
GET  /documents/{id}/accuracy
POST /documents/{id}/verify
... and 11 more
```

### **AFTER (7 endpoints):**
```
GET  /health
GET  /info                      # System status + metrics
GET  /config?section=...        # All settings
POST /config                    # Update settings
POST /documents                 # Upload (multipart)
GET  /documents?id=...          # List or get specific
DELETE /documents/{id}
POST /query?type=...&doc_id=... # Unified query
```

---

## 📋 **DETAILED ENDPOINT SPECS**

### **1. GET /info**
Combines: `/v1/status`, `/v1/metrics`, `/v1/library`

**Response:**
```json
{
  "status": "operational",
  "api_provider": "cerebras",
  "vector_store": "opensearch",
  "documents": {
    "total": 5,
    "with_images": 3,
    "total_chunks": 247
  },
  "metrics": {
    "total_queries": 150,
    "avg_response_time": 2.3
  }
}
```

### **2. GET /config?section=model**
Replaces: `/v1/config?section=...`

**Response:**
```json
{
  "model": {
    "openai_model": "gpt-4o",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0
  }
}
```

### **3. POST /documents (Multipart)**
Replaces: All upload and store endpoints

**Request:**
```
Content-Type: multipart/form-data

file: [binary]
parser: "docling" (optional)
```

**Response:**
```json
{
  "document_id": "abc123",
  "document_name": "file.pdf",
  "status": "processing",
  "type": "pdf"
}
```

### **4. GET /documents?id=abc123**
Replaces: `/documents/{id}`, `/documents/{id}/storage/status`, `/documents/{id}/images/all`, etc.

**Without ID (list all):**
```json
{
  "documents": [
    {
      "document_id": "abc123",
      "document_name": "file.pdf",
      "chunks": 47,
      "images": 13
    }
  ],
  "total": 5
}
```

**With ID (get specific):**
```json
{
  "document_id": "abc123",
  "document_name": "file.pdf",
  "status": "success",
  "chunks_created": 47,
  "images_detected": true,
  "image_count": 13,
  "storage": {
    "text_chunks": 47,
    "images": 13
  }
}
```

### **5. POST /query?type=text&document_id=abc123**
Replaces: `/query`, `/query/text`, `/query/images`, `/documents/{id}/query`

**Query Types:**
- `type=text` (default) - Query text chunks
- `type=image` - Query images with OCR
- `type=document` - Query specific document

**Request:**
```json
{
  "question": "What are the specifications?",
  "k": 12,
  "search_mode": "hybrid"
}
```

**Response:**
```json
{
  "answer": "The specifications are...",
  "sources": ["file.pdf"],
  "citations": [...],
  "type": "text",
  "num_chunks_used": 12
}
```

---

## 🎯 **UI MAPPING**

### **UI Screen → API Endpoint**

**Settings Page:**
```
GET  /config?section=model
GET  /config?section=parser
POST /config  (when user changes settings)
```

**Upload Page:**
```
POST /documents  (multipart form)
```

**Documents Library:**
```
GET  /documents  (list all)
GET  /documents?id=xxx  (get details)
```

**Query Page:**
```
POST /query?type=text  (text query)
POST /query?type=image  (image query)
POST /query?type=text&document_id=xxx  (query specific doc)
```

**System Status:**
```
GET  /info  (all system info)
```

---

## ✅ **BENEFITS**

1. **Simpler** - 7 endpoints instead of 26 (73% reduction)
2. **Cleaner Swagger UI** - Easy to understand
3. **UI Synced** - Matches exactly what UI needs
4. **Flexible** - Parameters handle variations
5. **RESTful** - Proper resource-based design
6. **Easier to Use** - Less confusion
7. **Maintainable** - Less code to maintain

---

## 🚀 **IMPLEMENTATION PLAN**

1. Create new minimal endpoints in `api/main.py`
2. Keep old endpoints as deprecated (for backward compatibility)
3. Update Swagger tags to show "Minimal API" vs "Legacy"
4. Test all functionality
5. Deploy
6. Update UI to use new endpoints
7. Eventually remove legacy endpoints

---

## 📝 **EXAMPLE USAGE**

### **Upload Document:**
```bash
curl -X POST http://44.221.84.58:8500/documents \
  -F "file=@document.pdf" \
  -F "parser=docling"
```

### **Query Text:**
```bash
curl -X POST "http://44.221.84.58:8500/query?type=text" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is this about?","k":12}'
```

### **Query Images:**
```bash
curl -X POST "http://44.221.84.58:8500/query?type=image" \
  -H "Content-Type: application/json" \
  -d '{"question":"Find charts","k":5}'
```

### **Query Specific Document:**
```bash
curl -X POST "http://44.221.84.58:8500/query?document_id=abc123" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the specs?"}'
```

### **Get System Info:**
```bash
curl http://44.221.84.58:8500/info
```

### **Get Config:**
```bash
curl "http://44.221.84.58:8500/config?section=model"
```

---

**This design gives you a clean, minimal API that perfectly syncs with your UI!**
