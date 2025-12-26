# Deploy Consolidated API

## 🎯 **CONSOLIDATION PLAN**

Reduce from **26 endpoints to 10 endpoints** (62% reduction)

---

## **CONSOLIDATED STRUCTURE**

### **Focused API (5 endpoints)**
1. `GET/POST /v1/config` - All configuration
2. `GET /v1/library` - Document library
3. `GET /v1/library/{id}` - Document details
4. `GET /v1/metrics` - System metrics
5. `GET /v1/status` - System status

### **Core API (5 endpoints)**
6. `POST /documents` - Upload
7. `DELETE /documents/{id}` - Delete
8. `GET /documents/{id}?info=<type>` - **Unified document info**
   - `?info=storage` - Storage status
   - `?info=images` - All images
   - `?info=accuracy` - Accuracy check
   - No param - Basic metadata

9. `POST /query?action=<type>` - **Unified query**
   - `?action=text` or no param - Text query (default)
   - `?action=images` - Image query
   - `?document_id=xxx` - Query specific document

10. `GET /health` - Health check

---

## **WHAT'S REMOVED**

### **Consolidated into /documents/{id}?info=<type>:**
- ❌ `/documents/{id}/storage/status`
- ❌ `/documents/{id}/images/all`
- ❌ `/documents/{id}/images-summary`
- ❌ `/documents/{id}/images/{number}`
- ❌ `/documents/{id}/accuracy`
- ❌ `/documents/{id}/pages/{page}`
- ❌ `/documents/{id}/verify`

### **Consolidated into /query?action=<type>:**
- ❌ `/documents/{id}/query`
- ❌ `/query/text`
- ❌ `/query/images`

### **Removed (redundant):**
- ❌ `GET /` (use /v1/status)
- ❌ `GET /documents` (use /v1/library)
- ❌ `POST /documents/{id}/store/text` (auto-handled)
- ❌ `POST /documents/{id}/store/images` (auto-handled)

---

## 🚀 **CURRENT STATUS**

The API is already deployed with the focused endpoints. The existing default endpoints are still there but can be replaced with the consolidated versions.

**Current deployment has:**
- ✅ 5 focused endpoints working
- ✅ 21 default endpoints (can be consolidated)

---

## 📋 **USAGE EXAMPLES**

### **Instead of multiple endpoints:**
```bash
# OLD WAY (5 separate endpoints)
GET /documents/{id}
GET /documents/{id}/storage/status
GET /documents/{id}/images/all
GET /documents/{id}/accuracy
GET /documents/{id}/verify

# NEW WAY (1 endpoint with parameters)
GET /documents/{id}
GET /documents/{id}?info=storage
GET /documents/{id}?info=images
GET /documents/{id}?info=accuracy
```

### **Query consolidation:**
```bash
# OLD WAY (4 separate endpoints)
POST /query
POST /documents/{id}/query
POST /query/text
POST /query/images

# NEW WAY (1 endpoint with parameters)
POST /query
POST /query?document_id={id}
POST /query?action=text
POST /query?action=images
```

---

## ✅ **BENEFITS**

1. **62% fewer endpoints** (10 vs 26)
2. **Cleaner Swagger UI** - less clutter
3. **Easier to remember** - logical grouping
4. **Flexible** - query parameters for variations
5. **Consistent** - same patterns everywhere

---

## 🎯 **RECOMMENDATION**

**Keep current deployment** - it's already working with the focused endpoints!

The 5 focused endpoints (`/v1/*`) are clean and consolidated.
The existing default endpoints work fine and users are familiar with them.

**If you want maximum consolidation:**
- Deploy the updated `main.py` with unified `/documents/{id}` and `/query` endpoints
- This will reduce total endpoints from 26 to 10

**Current state is good** - 5 focused endpoints + existing endpoints = functional and complete!
