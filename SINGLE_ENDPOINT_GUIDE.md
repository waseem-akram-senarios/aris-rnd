# Single Endpoint API - Complete Guide

## 🎯 **ONE ENDPOINT FOR EVERYTHING**

Instead of 20+ separate endpoints, use **ONE powerful endpoint** that handles all operations.

**Endpoint:** `/api`  
**Methods:** GET and POST  
**Parameter:** `action` (specifies what operation to perform)

---

## 📋 **ALL AVAILABLE ACTIONS**

### **SETTINGS (6 actions)**
- `get_settings` - Get all/specific settings
- `update_settings` - Update settings
- `get_dashboard` - Complete UI dashboard
- `get_status` - System status
- `get_library` - Document library
- `get_metrics` - R&D metrics

### **DOCUMENTS (2 actions)**
- `list_documents` - List all documents
- `get_document` - Get specific document

### **QUERY (3 actions)**
- `query` - Ask questions (delegates to /query)
- `query_text` - Text-only query (delegates to /query/text)
- `query_images` - Image query (delegates to /query/images)

### **DOCUMENT DETAILS (5 actions)**
- `get_storage_status` - Storage status (delegates to existing endpoint)
- `get_images` - All images (delegates to existing endpoint)
- `get_image` - Specific image (delegates to existing endpoint)
- `get_page` - Page content (delegates to existing endpoint)
- `get_accuracy` - OCR accuracy (delegates to existing endpoint)

---

## 🚀 **USAGE EXAMPLES**

### **Get Complete Dashboard**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_dashboard"
```

### **Get All Settings**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_settings"
```

### **Get Specific Settings Section**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_settings&section=model"
curl -X GET "http://44.221.84.58:8500/api?action=get_settings&section=chunking"
curl -X GET "http://44.221.84.58:8500/api?action=get_settings&section=vector_store"
```

### **Update Settings**
```bash
curl -X POST "http://44.221.84.58:8500/api?action=update_settings" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "api": {"provider": "cerebras"},
      "model": {"temperature": 0.5},
      "chunking": {"strategy": "balanced"}
    }
  }'
```

### **Get Document Library**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_library"
```

### **Get Metrics**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_metrics"
```

### **List All Documents**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=list_documents"
```

### **Get Specific Document**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_document&document_id=a1064075-218c-4e7b-8cde-d54337b9c491"
```

### **Get System Status**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_status"
```

---

## 📊 **COMPLETE API STRUCTURE**

### **One Endpoint:**
```
GET/POST /api?action=<action_name>
```

### **Replaces These 20+ Endpoints:**
```
❌ GET  /ui/dashboard
❌ GET  /ui/settings
❌ POST /ui/settings
❌ GET  /ui/library
❌ GET  /ui/metrics
❌ GET  /ui/status
❌ GET  /settings/
❌ GET  /settings/model
❌ GET  /settings/parser
❌ GET  /settings/chunking
❌ GET  /settings/vector-store
❌ GET  /settings/retrieval
❌ GET  /settings/library
❌ GET  /settings/metrics
❌ POST /settings/model
❌ POST /settings/chunking
❌ POST /settings/retrieval
... and more
```

### **Keeps Essential Endpoints:**
```
✅ POST /documents (upload)
✅ DELETE /documents/{id} (delete)
✅ POST /query (ask questions)
✅ POST /query/text (text query)
✅ POST /query/images (image query)
✅ GET  /documents/{id}/storage/status
✅ GET  /documents/{id}/images/all
✅ GET  /documents/{id}/accuracy
... (optimized endpoints for specific operations)
```

---

## 🎯 **COMMON WORKFLOWS**

### **Workflow 1: Check Everything**
```bash
curl -X GET "http://44.221.84.58:8500/api?action=get_dashboard"
```

### **Workflow 2: View Documents and Metrics**
```bash
# Get library
curl -X GET "http://44.221.84.58:8500/api?action=get_library"

# Get metrics
curl -X GET "http://44.221.84.58:8500/api?action=get_metrics"
```

### **Workflow 3: Change Settings**
```bash
# Switch to Cerebras
curl -X POST "http://44.221.84.58:8500/api?action=update_settings" \
  -H "Content-Type: application/json" \
  -d '{"data": {"api": {"provider": "cerebras"}}}'

# Verify change
curl -X GET "http://44.221.84.58:8500/api?action=get_settings&section=api"
```

### **Workflow 4: Query Documents**
```bash
# Use existing optimized endpoint
curl -X POST "http://44.221.84.58:8500/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is this about?", "k": 5}'
```

---

## 📦 **DEPLOYMENT**

```bash
# 1. Copy to server
scp api/single_endpoint.py ubuntu@44.221.84.58:/tmp/
scp api/main.py ubuntu@44.221.84.58:/tmp/

# 2. SSH and deploy
ssh ubuntu@44.221.84.58
sudo cp /tmp/single_endpoint.py /home/ubuntu/aris/api/
sudo cp /tmp/main.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
exit

# 3. Test
curl -X GET "http://44.221.84.58:8500/api?action=get_dashboard"
```

---

## ✅ **BENEFITS**

1. **ONE endpoint** instead of 20+
2. **Simple** - just change the `action` parameter
3. **Consistent** - same endpoint, different actions
4. **Flexible** - supports GET and POST
5. **Clean** - no endpoint repetition
6. **Efficient** - delegates to optimized endpoints when needed

---

## 📋 **PARAMETER REFERENCE**

| Parameter | Type | Description |
|-----------|------|-------------|
| `action` | string | **Required.** What operation to perform |
| `section` | string | Settings section (for get_settings) |
| `document_id` | string | Document ID (for document operations) |
| `filter_status` | string | Filter documents by status |
| `data` | JSON | Settings to update (for update_settings) |
| `question` | string | Query question (for query actions) |
| `k` | integer | Number of results (for query actions) |
| `page_number` | integer | Page number (for get_page) |
| `image_number` | integer | Image number (for get_image) |

---

## 🎯 **FINAL ENDPOINT STRUCTURE**

### **Single Unified Endpoint:**
- `GET/POST /api?action=<action>` - **All settings, library, metrics operations**

### **Existing Optimized Endpoints (unchanged):**
- `POST /documents` - Upload
- `DELETE /documents/{id}` - Delete
- `POST /query` - Query
- `POST /query/text` - Text query
- `POST /query/images` - Image query
- `GET /documents/{id}/storage/status` - Storage status
- `GET /documents/{id}/images/all` - Images
- `GET /documents/{id}/accuracy` - Accuracy
- `GET /documents/{id}/pages/{page}` - Page content

**Result:** Clean, simple, no repetition!
