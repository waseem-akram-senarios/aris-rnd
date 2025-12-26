# Manual Deployment - Consolidated API

## 📦 Deployment Package Ready

**File:** `consolidated_api_deployment.tar.gz`

**Contains:**
- `api/consolidated_endpoints.py` - 3 new consolidated endpoints
- `api/main.py` - Updated with consolidated router
- `api/schemas.py` - All schema models
- `api/service.py` - Service layer with fixes

---

## 🚀 DEPLOYMENT COMMANDS

### **Option 1: One-Line Deployment**

```bash
scp consolidated_api_deployment.tar.gz ubuntu@44.221.84.58:/tmp/ && ssh ubuntu@44.221.84.58 'cd /tmp && tar -xzf consolidated_api_deployment.tar.gz && sudo cp api/consolidated_endpoints.py api/main.py api/schemas.py api/service.py /home/ubuntu/aris/api/ && sudo systemctl restart aris-fastapi && echo "✅ Deployed!"'
```

---

### **Option 2: Step-by-Step**

```bash
# 1. Copy package to server
scp consolidated_api_deployment.tar.gz ubuntu@44.221.84.58:/tmp/

# 2. SSH into server
ssh ubuntu@44.221.84.58

# 3. Extract and deploy
cd /tmp
tar -xzf consolidated_api_deployment.tar.gz
sudo cp api/consolidated_endpoints.py /home/ubuntu/aris/api/
sudo cp api/main.py /home/ubuntu/aris/api/
sudo cp api/schemas.py /home/ubuntu/aris/api/
sudo cp api/service.py /home/ubuntu/aris/api/

# 4. Restart service
sudo systemctl restart aris-fastapi

# 5. Check status
sudo systemctl status aris-fastapi

# 6. Exit
exit
```

---

## ✅ TESTING AFTER DEPLOYMENT

### **Test 1: Get All Configuration**
```bash
curl -X GET "http://44.221.84.58:8500/api/config" | python3 -m json.tool
```

**Expected:** All configuration sections (model, parser, chunking, vector_store, retrieval, agentic_rag)

---

### **Test 2: Get Specific Section**
```bash
curl -X GET "http://44.221.84.58:8500/api/config?section=model" | python3 -m json.tool
```

**Expected:**
```json
{
  "model": {
    "api_provider": "openai",
    "openai_model": "gpt-4o",
    "cerebras_model": "llama-3.3-70b",
    "embedding_model": "text-embedding-3-large",
    "temperature": 0.0,
    "max_tokens": 1200
  }
}
```

---

### **Test 3: Get System Info**
```bash
curl -X GET "http://44.221.84.58:8500/api/system" | python3 -m json.tool
```

**Expected:** Library, metrics, and config sections

---

### **Test 4: Get Library Only**
```bash
curl -X GET "http://44.221.84.58:8500/api/system?include=library" | python3 -m json.tool
```

**Expected:**
```json
{
  "library": {
    "total_documents": 8,
    "documents": [...],
    "storage_persists": true
  }
}
```

---

### **Test 5: Get Metrics Only**
```bash
curl -X GET "http://44.221.84.58:8500/api/system?include=metrics" | python3 -m json.tool
```

**Expected:**
```json
{
  "metrics": {
    "total_documents_processed": 8,
    "total_chunks_created": 150,
    "total_images_extracted": 25,
    "average_processing_time": 450.5,
    "parsers_used": {...},
    "storage_stats": {...}
  }
}
```

---

### **Test 6: Update Configuration**
```bash
curl -X POST "http://44.221.84.58:8500/api/config" \
  -H "Content-Type: application/json" \
  -d '{
    "model": {
      "temperature": 0.5
    },
    "chunking": {
      "strategy": "balanced"
    }
  }' | python3 -m json.tool
```

**Expected:**
```json
{
  "status": "success",
  "message": "Updated 2 configuration section(s)",
  "updated_sections": ["model", "chunking"],
  "note": "Changes are runtime only. Update .env file to persist across restarts."
}
```

---

### **Test 7: Verify Update**
```bash
curl -X GET "http://44.221.84.58:8500/api/config?section=model" | python3 -m json.tool
```

**Expected:** Temperature should be 0.5 now

---

## 🔍 VERIFY ALL ENDPOINTS

```bash
# Check API documentation
curl -X GET "http://44.221.84.58:8500/docs"

# Should see new endpoints:
# - GET  /api/config
# - POST /api/config
# - GET  /api/system
```

---

## 📊 WHAT'S DEPLOYED

### **New Endpoints (3):**
1. `GET /api/config` - Get configuration (all or specific sections)
2. `POST /api/config` - Update configuration (batch updates)
3. `GET /api/system` - Get system info (library, metrics, config)

### **Fixed Endpoints (2):**
1. `GET /documents/{id}/storage/status` - Storage status (was 500, now 200)
2. `GET /documents/{id}/accuracy` - Document accuracy (was 500, now 200)

### **Total Active Endpoints:**
- 14 core document/query endpoints
- 3 consolidated system endpoints
- **17 total endpoints** (down from 26+)

---

## 🎯 EXPECTED RESULTS

After deployment:
- ✅ All 3 consolidated endpoints working
- ✅ Storage status endpoint fixed
- ✅ Accuracy endpoint fixed
- ✅ All query endpoints working
- ✅ All image endpoints working
- ✅ **100% API functionality**

---

## 🐛 TROUBLESHOOTING

### **If endpoints return 404:**
```bash
# Check if service is running
ssh ubuntu@44.221.84.58 'sudo systemctl status aris-fastapi'

# Check logs
ssh ubuntu@44.221.84.58 'sudo journalctl -u aris-fastapi -n 50'

# Restart service
ssh ubuntu@44.221.84.58 'sudo systemctl restart aris-fastapi'
```

### **If service fails to start:**
```bash
# Check for Python errors
ssh ubuntu@44.221.84.58 'sudo journalctl -u aris-fastapi -n 100'

# Verify files are in place
ssh ubuntu@44.221.84.58 'ls -la /home/ubuntu/aris/api/'
```

---

## 📝 AUTOMATED TESTING SCRIPT

Run the automated deployment and testing script:

```bash
chmod +x DEPLOY_CONSOLIDATED_API.sh
./DEPLOY_CONSOLIDATED_API.sh
```

This will:
1. Deploy all files
2. Restart service
3. Run 7 comprehensive tests
4. Show results

---

**Ready to deploy! Run the commands above to activate the consolidated API.**
