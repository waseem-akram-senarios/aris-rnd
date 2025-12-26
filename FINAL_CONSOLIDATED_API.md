# Final Consolidated API Structure

## 🎯 **10 ENDPOINTS TOTAL (Down from 26)**

---

## **FOCUSED API (6 endpoints)**

### 1. `GET/POST /v1/config`
**All configuration management**
- Get all settings or specific section
- Update any settings
- Covers: API provider, model, parser, chunking, vector store, retrieval

### 2. `GET /v1/library`
**Document library**
- List all documents
- Filter by status
- Get document counts

### 3. `GET /v1/library/{id}`
**Specific document details**
- Get detailed document info

### 4. `GET /v1/metrics`
**System metrics**
- Processing stats
- Parser usage
- Storage stats

### 5. `GET /v1/status`
**System status & overview**
- Complete UI state
- How to use instructions
- Available endpoints

---

## **CORE API (4 endpoints)**

### 6. `POST /documents`
**Upload documents**
- Upload PDF, TXT, DOCX files
- Auto-processing

### 7. `DELETE /documents/{id}`
**Delete documents**
- Remove document from system

### 8. `GET /documents/{id}?info=<type>`
**Unified document info**
- `GET /documents/{id}` - Basic metadata
- `GET /documents/{id}?info=storage` - Storage status
- `GET /documents/{id}?info=images` - All images
- `GET /documents/{id}?info=accuracy` - Accuracy check

**Replaces 5 endpoints:**
- ❌ GET /documents/{id}/storage/status
- ❌ GET /documents/{id}/images/all
- ❌ GET /documents/{id}/images-summary
- ❌ GET /documents/{id}/accuracy
- ✅ GET /documents/{id}?info=<type>

### 9. `POST /query?action=<type>`
**Unified query endpoint**
- `POST /query` or `POST /query?action=text` - Text query (default)
- `POST /query?action=images` - Image query
- `POST /query?document_id=xxx` - Query specific document

**Replaces 4 endpoints:**
- ❌ POST /query
- ❌ POST /documents/{id}/query
- ❌ POST /query/text
- ❌ POST /query/images
- ✅ POST /query?action=<type>

---

## **REMOVED/CONSOLIDATED ENDPOINTS**

### **Removed (not needed):**
- ❌ GET / (root)
- ❌ GET /health (use /v1/status instead)
- ❌ GET /documents (use /v1/library instead)
- ❌ GET /documents/{id}/images/{number} (use info=images)
- ❌ GET /documents/{id}/pages/{page} (rarely used)
- ❌ POST /documents/{id}/store/text (auto-handled)
- ❌ POST /documents/{id}/store/images (auto-handled)
- ❌ POST /documents/{id}/verify (use info=accuracy)

---

## 📊 **BEFORE vs AFTER**

### **Before: 26 endpoints**
```
Focused API: 6
Default: 20
Total: 26
```

### **After: 10 endpoints**
```
Focused API: 5
Core API: 4
Health: 1 (/v1/status)
Total: 10
```

**Reduction: 62% fewer endpoints!**

---

## 🚀 **USAGE EXAMPLES**

### **Configuration**
```bash
# Get all config
GET /v1/config

# Get model config
GET /v1/config?section=model

# Update settings
POST /v1/config
Body: {"api": {"provider": "cerebras"}}
```

### **Documents**
```bash
# Upload
POST /documents (with file)

# List all
GET /v1/library

# Get specific
GET /v1/library/{id}

# Get storage status
GET /documents/{id}?info=storage

# Get images
GET /documents/{id}?info=images

# Check accuracy
GET /documents/{id}?info=accuracy

# Delete
DELETE /documents/{id}
```

### **Query**
```bash
# Text query (default)
POST /query
Body: {"question": "...", "k": 5}

# Image query
POST /query?action=images
Body: {"question": "...", "k": 5}

# Query specific document
POST /query?document_id=xxx
Body: {"question": "..."}
```

### **System**
```bash
# Get metrics
GET /v1/metrics

# Get status
GET /v1/status
```

---

## ✅ **BENEFITS**

1. **62% fewer endpoints** (10 vs 26)
2. **Cleaner API** - logical grouping
3. **Flexible** - query parameters for variations
4. **Consistent** - similar patterns across endpoints
5. **Powerful** - each endpoint does more
6. **Simple** - easier to remember and use

---

## 🎯 **FINAL STRUCTURE**

```
/v1/config          - All settings
/v1/library         - All documents
/v1/library/{id}    - Document details
/v1/metrics         - System metrics
/v1/status          - System status

/documents          - Upload
/documents/{id}     - Info/Delete
/query              - Query (text/images)
```

**Clean, minimal, powerful!**
