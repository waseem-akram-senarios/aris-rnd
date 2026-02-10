# FastAPI Access Guide

## ✅ FastAPI is Running and Accessible

**Server**: 35.175.133.235  
**Port**: 8500 (confirmed open)  
**Status**: ✅ Running and healthy

---

## Correct Access URLs

### ⚠️ Important: Use Colon (`:`) Not Slash (`/`)

**❌ WRONG:**
- `http://35.175.133.235/8500/docs` (incorrect format)

**✅ CORRECT:**
- `http://35.175.133.235:8500/docs` (use colon)

---

## FastAPI Endpoints

### Documentation
- **Swagger UI**: http://35.175.133.235:8500/docs
- **ReDoc**: http://35.175.133.235:8500/redoc
- **OpenAPI JSON**: http://35.175.133.235:8500/openapi.json

### API Endpoints
- **Root**: http://35.175.133.235:8500/
- **Health Check**: http://35.175.133.235:8500/health
- **List Documents**: http://35.175.133.235:8500/documents
- **Upload Document**: `POST http://35.175.133.235:8500/documents`
- **Query Documents**: `POST http://35.175.133.235:8500/query`
- **Get Stats**: http://35.175.133.235:8500/stats

### Sync Endpoints
- **Sync Status**: http://35.175.133.235:8500/sync/status
- **Reload Vectorstore**: `POST http://35.175.133.235:8500/sync/reload-vectorstore`
- **Save Vectorstore**: `POST http://35.175.133.235:8500/sync/save-vectorstore`
- **Reload Registry**: `POST http://35.175.133.235:8500/sync/reload-registry`

---

## Verification

### Test from Command Line
```bash
# Health check
curl http://35.175.133.235:8500/health

# Root endpoint
curl http://35.175.133.235:8500/

# OpenAPI spec
curl http://35.175.133.235:8500/openapi.json
```

### Expected Responses
- **Health**: `{"status":"healthy"}`
- **Root**: `{"message":"ARIS RAG API","version":"1.0.0","docs":"/docs"}`
- **OpenAPI**: Full OpenAPI 3.1.0 specification JSON

---

## Troubleshooting

### If Swagger UI appears blank:

1. **Check browser console** (F12) for JavaScript errors
2. **Verify OpenAPI JSON loads**: http://35.175.133.235:8500/openapi.json
3. **Try ReDoc instead**: http://35.175.133.235:8500/redoc
4. **Check if CDN is blocked**: Swagger UI loads from CDN (cdn.jsdelivr.net)

### If port 8500 is not accessible:

1. **Verify port is open** in AWS Security Group
2. **Check container is running**: `docker ps | grep aris-rag`
3. **Check port mapping**: Should show `0.0.0.0:8500->8000/tcp`
4. **Check FastAPI logs**: `docker logs aris-rag-app | grep FastAPI`

---

## Current Status

✅ **Port 8500**: Open and accessible  
✅ **FastAPI**: Running on port 8000 (mapped to 8500)  
✅ **Health Check**: Responding with 200 OK  
✅ **OpenAPI JSON**: Accessible and valid  
✅ **Swagger UI**: HTML page loads (HTTP 200)

---

## Quick Test

```bash
# Test all endpoints
curl http://35.175.133.235:8500/health
curl http://35.175.133.235:8500/
curl http://35.175.133.235:8500/openapi.json | head -20
```

All should return valid responses.

---

**Last Verified**: December 4, 2025  
**Status**: ✅ Fully Operational

