# Swagger UI Testing Guide

## 🎯 **ACCESS SWAGGER UI**

FastAPI automatically generates interactive API documentation (Swagger UI).

**URL:** `http://44.221.84.58:8500/docs`

---

## 📖 **HOW TO USE SWAGGER UI**

### **Step 1: Open Swagger UI**

Open your browser and go to:
```
http://44.221.84.58:8500/docs
```

You'll see all your API endpoints listed with expandable sections.

---

### **Step 2: Test Endpoints**

#### **Test GET /v1/status**

1. Find the **"Focused API"** section
2. Click on `GET /v1/status`
3. Click **"Try it out"** button
4. Click **"Execute"** button
5. See the response below

**Expected Response:**
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

#### **Test GET /v1/config**

1. Click on `GET /v1/config`
2. Click **"Try it out"**
3. (Optional) Enter a section name in the `section` field:
   - `model`
   - `chunking`
   - `vector_store`
   - Leave empty for all config
4. Click **"Execute"**
5. See the response

**Example - Get all config:**
- Leave `section` empty
- Click Execute

**Example - Get model config only:**
- Enter `model` in the `section` field
- Click Execute

---

#### **Test POST /v1/config (Update Settings)**

1. Click on `POST /v1/config`
2. Click **"Try it out"**
3. Edit the JSON in the **Request body** field:

```json
{
  "api": {
    "provider": "cerebras"
  },
  "model": {
    "temperature": 0.5
  }
}
```

4. Click **"Execute"**
5. See the response:

```json
{
  "status": "success",
  "updated": ["api", "model"],
  "message": "Updated 2 section(s)"
}
```

---

#### **Test GET /v1/library**

1. Click on `GET /v1/library`
2. Click **"Try it out"**
3. (Optional) Enter status filter:
   - `success`
   - `failed`
   - Leave empty for all documents
4. Click **"Execute"**
5. See all documents with metadata

---

#### **Test GET /v1/library/{document_id}**

1. Click on `GET /v1/library/{document_id}`
2. Click **"Try it out"**
3. Enter a document ID in the `document_id` field:
   - Example: `a1064075-218c-4e7b-8cde-d54337b9c491`
4. Click **"Execute"**
5. See detailed document information

---

#### **Test GET /v1/metrics**

1. Click on `GET /v1/metrics`
2. Click **"Try it out"**
3. Click **"Execute"**
4. See processing metrics:
   - Total documents
   - Total chunks
   - Total images
   - Average processing time
   - Parser usage
   - Storage stats

---

#### **Test POST /query (Existing Endpoint)**

1. Scroll down to find `POST /query`
2. Click **"Try it out"**
3. Edit the request body:

```json
{
  "question": "What is this document about?",
  "k": 5,
  "search_mode": "hybrid"
}
```

4. Click **"Execute"**
5. See the answer with citations

---

#### **Test POST /documents (Upload)**

1. Find `POST /documents`
2. Click **"Try it out"**
3. Click **"Choose File"** and select a PDF
4. Click **"Execute"**
5. See upload confirmation and document ID

---

## 🎨 **SWAGGER UI FEATURES**

### **Interactive Testing**
- ✅ No need for curl or Postman
- ✅ Fill in parameters in forms
- ✅ Edit JSON request bodies
- ✅ See responses immediately
- ✅ Copy curl commands

### **Documentation**
- ✅ See all available endpoints
- ✅ View request/response schemas
- ✅ See parameter descriptions
- ✅ View example values

### **Response Details**
- ✅ HTTP status code
- ✅ Response body (formatted JSON)
- ✅ Response headers
- ✅ Response time

---

## 📋 **TESTING WORKFLOW**

### **1. Check System Status**
```
GET /v1/status
```

### **2. View Current Configuration**
```
GET /v1/config
```

### **3. View Documents**
```
GET /v1/library
```

### **4. View Metrics**
```
GET /v1/metrics
```

### **5. Update Settings**
```
POST /v1/config
Body: {"api": {"provider": "cerebras"}}
```

### **6. Verify Update**
```
GET /v1/config?section=api
```

### **7. Upload Document**
```
POST /documents
File: your_document.pdf
```

### **8. Query Documents**
```
POST /query
Body: {"question": "What is this about?", "k": 5}
```

---

## 🔍 **ALTERNATIVE: ReDoc**

FastAPI also provides ReDoc documentation:

**URL:** `http://44.221.84.58:8500/redoc`

ReDoc is better for:
- Reading documentation
- Viewing schemas
- Printing/exporting docs

Swagger is better for:
- Interactive testing
- Trying out endpoints
- Quick experiments

---

## 💡 **TIPS**

1. **Use Swagger for quick testing** - No need to write curl commands
2. **Copy curl commands** - Swagger shows the curl equivalent
3. **Test in order** - Start with GET /v1/status to verify system is running
4. **Check responses** - Green = success (200), Red = error (400/500)
5. **Use filters** - Try different query parameters
6. **Test updates** - Change settings and verify with GET requests

---

## 🎯 **QUICK ACCESS LINKS**

- **Swagger UI:** http://44.221.84.58:8500/docs
- **ReDoc:** http://44.221.84.58:8500/redoc
- **OpenAPI JSON:** http://44.221.84.58:8500/openapi.json

---

## ✅ **WHAT YOU'LL SEE IN SWAGGER**

### **Focused API Section:**
- GET /v1/config
- POST /v1/config
- GET /v1/library
- GET /v1/library/{document_id}
- GET /v1/metrics
- GET /v1/status

### **Default Section (Existing Endpoints):**
- GET /
- GET /health
- GET /documents
- POST /documents
- DELETE /documents/{document_id}
- POST /query
- POST /query/text
- POST /query/images
- GET /documents/{document_id}/storage/status
- GET /documents/{document_id}/images/all
- GET /documents/{document_id}/accuracy
- ... and more

---

**Open http://44.221.84.58:8500/docs in your browser to start testing!**
