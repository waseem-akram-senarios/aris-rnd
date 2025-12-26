# API Consolidation Plan - Reduce Endpoints with Parameters

## 🎯 **OBJECTIVE**
Consolidate existing API endpoints from 26 to ~12 using query parameters instead of separate endpoints.

---

## 📊 **CURRENT STATE (26 Endpoints)**

### **Core Operations (5)**
1. `GET /` - Root
2. `GET /health` - Health check
3. `GET /documents` - List documents
4. `POST /documents` - Upload document
5. `DELETE /documents/{id}` - Delete document

### **Query Operations (4)**
6. `POST /query` - General query
7. `POST /documents/{id}/query` - Query specific document
8. `POST /query/text` - Text-only query
9. `POST /query/images` - Image query

### **Document Details (10)**
10. `GET /documents/{id}` - Get metadata
11. `GET /documents/{id}/storage/status` - Storage status
12. `GET /documents/{id}/images/all` - All images
13. `GET /documents/{id}/images-summary` - Images summary
14. `GET /documents/{id}/images/{number}` - Specific image
15. `GET /documents/{id}/pages/{page}` - Page content
16. `POST /documents/{id}/store/text` - Store text
17. `POST /documents/{id}/store/images` - Store images
18. `GET /documents/{id}/accuracy` - OCR accuracy
19. `POST /documents/{id}/verify` - Verify OCR

### **Focused API (5)**
20. `GET /v1/config` - Get configuration
21. `POST /v1/config` - Update configuration
22. `GET /v1/library` - Document library
23. `GET /v1/library/{id}` - Document details
24. `GET /v1/metrics` - System metrics
25. `GET /v1/status` - System status

### **Removed (1)**
26. `GET /documents/{id}` - Duplicate, use basic metadata

---

## ✅ **TARGET STATE (12 Endpoints)**

### **Core Operations (5)** - Keep as-is
1. `GET /health` - Health check
2. `GET /documents` - List documents (or use `/v1/library`)
3. `POST /documents` - Upload document
4. `DELETE /documents/{id}` - Delete document
5. `POST /query` - **Unified query endpoint**

### **Unified Document Info (1)** - NEW
6. `GET /documents/{id}/info?type=<type>` - **All document information**
   - `?type=storage` - Storage status
   - `?type=images` - All images
   - `?type=images-summary` - Images summary
   - `?type=image&image_number=N` - Specific image
   - `?type=page&page_number=N` - Page content
   - `?type=accuracy` - Accuracy check
   - No param - Basic metadata

### **Focused API (5)** - Keep as-is
7. `GET /v1/config` - Get configuration
8. `POST /v1/config` - Update configuration
9. `GET /v1/library` - Document library
10. `GET /v1/metrics` - System metrics
11. `GET /v1/status` - System status

### **Optional (1)** - Can be removed
12. `POST /documents/{id}/verify` - Verify OCR (keep for now)

---

## 🔄 **CONSOLIDATION STRATEGY**

### **1. Unified Query Endpoint**
**Before (4 endpoints):**
```
POST /query
POST /documents/{id}/query
POST /query/text
POST /query/images
```

**After (1 endpoint):**
```
POST /query?mode=<mode>&document_id=<id>
- mode=text (default)
- mode=images
- document_id=xxx (optional filter)
```

**Implementation:**
```python
@app.post("/query")
async def query_documents(
    request: QueryRequest,
    mode: str = "text",
    document_id: Optional[str] = None
):
    if mode == "images":
        return query_images_handler(request, document_id)
    else:
        return query_text_handler(request, document_id)
```

### **2. Unified Document Info Endpoint** ✅ IMPLEMENTED
**Before (7 endpoints):**
```
GET /documents/{id}
GET /documents/{id}/storage/status
GET /documents/{id}/images/all
GET /documents/{id}/images-summary
GET /documents/{id}/images/{number}
GET /documents/{id}/pages/{page}
GET /documents/{id}/accuracy
```

**After (1 endpoint):**
```
GET /documents/{id}/info?type=<type>&page_number=N&image_number=N
```

**Implementation:** ✅ Already done in main.py

---

## 📋 **IMPLEMENTATION STEPS**

### **Step 1: Update Query Endpoint** ⏳ TODO
- [x] Read current query endpoints
- [ ] Consolidate into single endpoint with mode parameter
- [ ] Update schemas if needed
- [ ] Test all query modes

### **Step 2: Update Document Info Endpoint** ✅ DONE
- [x] Create unified `/documents/{id}/info` endpoint
- [x] Add type parameter routing
- [x] Create helper functions for each type
- [x] Keep old endpoints as deprecated (for backward compatibility)

### **Step 3: Remove Redundant Endpoints** ⏳ TODO
- [ ] Mark old endpoints as deprecated in docs
- [ ] Or remove them entirely (breaking change)
- [ ] Update Swagger documentation

### **Step 4: Update UI to Use New Endpoints** ⏳ TODO
- [ ] Check Streamlit UI calls
- [ ] Update to use new consolidated endpoints
- [ ] Ensure UI and API are in sync

### **Step 5: Deploy and Test** ⏳ TODO
- [ ] Deploy to server
- [ ] Test all consolidated endpoints
- [ ] Verify Swagger UI shows clean structure
- [ ] Test UI functionality

---

## 🎯 **BENEFITS**

1. **Cleaner API** - 12 endpoints instead of 26 (54% reduction)
2. **Easier to Use** - Logical grouping with parameters
3. **Better Swagger UI** - Less clutter, clearer organization
4. **Flexible** - Easy to add new info types without new endpoints
5. **Consistent** - Same pattern across all endpoints
6. **UI Sync** - API matches UI structure

---

## 📝 **NEXT ACTIONS**

1. **Consolidate Query Endpoints**
   - Update `POST /query` to accept mode parameter
   - Remove separate `/query/text` and `/query/images`
   - Update `/documents/{id}/query` to use main query endpoint

2. **Test Consolidated API**
   - Test all type parameters
   - Verify backward compatibility
   - Check error handling

3. **Deploy to Server**
   - Use `./scripts/deploy-fast.sh`
   - Verify deployment
   - Test via Swagger UI

4. **Update UI**
   - Sync Streamlit with new endpoints
   - Test all UI features
   - Ensure everything works

---

## ✅ **CURRENT PROGRESS**

- ✅ Document info endpoint consolidated (`/documents/{id}/info`)
- ⏳ Query endpoints need consolidation
- ⏳ Deployment pending
- ⏳ UI sync pending

---

**Ready to consolidate query endpoints and deploy!**
