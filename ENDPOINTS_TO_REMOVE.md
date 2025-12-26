# Endpoints to Remove/Keep

## ✅ KEEP (10 endpoints)

### Core (5)
1. `GET /` - Root
2. `GET /health` - Health check
3. `GET /documents` - List documents
4. `POST /documents` - Upload document
5. `DELETE /documents/{id}` - Delete document

### Focused API (5)
6. `GET /v1/config` - Get config
7. `POST /v1/config` - Update config
8. `GET /v1/library` - Document library
9. `GET /v1/metrics` - Metrics
10. `GET /v1/status` - Status

## ❌ REMOVE (16 endpoints)

These will be replaced by query parameters:

1. `GET /documents/{id}` - Use `GET /v1/library?id={id}` instead
2. `POST /query` - Keep but enhance with parameters
3. `POST /documents/{id}/query` - Use `POST /query?document_id={id}`
4. `POST /query/text` - Use `POST /query?type=text`
5. `POST /query/images` - Use `POST /query?type=image`
6. `GET /documents/{id}/storage/status` - Use `GET /v1/library?id={id}`
7. `GET /documents/{id}/images/all` - Use `GET /v1/library?id={id}&details=images`
8. `GET /documents/{id}/images-summary` - Use `GET /v1/library?id={id}&details=images`
9. `GET /documents/{id}/images/{number}` - Use `GET /v1/library?id={id}&image={number}`
10. `GET /documents/{id}/pages/{page}` - Use `GET /v1/library?id={id}&page={page}`
11. `POST /documents/{id}/store/text` - Auto-handled by upload
12. `POST /documents/{id}/store/images` - Auto-handled by upload
13. `GET /documents/{id}/accuracy` - Use `GET /v1/library?id={id}&details=accuracy`
14. `POST /documents/{id}/verify` - Not needed for UI
15. `GET /v1/library/{id}` - Use `GET /v1/library?id={id}` instead

## 🎯 FINAL API (10 endpoints)

```
GET  /
GET  /health
GET  /documents
POST /documents
DELETE /documents/{id}
POST /query?type=text|image&document_id=xxx
GET  /v1/config?section=xxx
POST /v1/config
GET  /v1/library?id=xxx&details=xxx
GET  /v1/metrics
GET  /v1/status
```
