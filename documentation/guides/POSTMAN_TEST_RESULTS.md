# Postman Endpoint Test Results

## Test Date
December 19, 2025

## Test Summary

### ✅ Working Endpoints (No Deployment Needed)

1. **Health Check** ✅
   - URL: `GET http://44.221.84.58:8500/health`
   - Status: 200 OK
   - Response: `{"status": "healthy"}`

2. **Get All Documents** ✅
   - URL: `GET http://44.221.84.58:8500/documents`
   - Status: 200 OK
   - Response: List of 7 documents
   - Note: Documents found but some may not have document_id field

3. **Query Text Only** ✅
   - URL: `POST http://44.221.84.58:8500/query/text`
   - Status: 200 OK
   - Body: `{"question": "test", "k": 3}`

4. **Query Images Only** ✅
   - URL: `POST http://44.221.84.58:8500/query/images`
   - Status: 200 OK
   - Body: `{"question": "", "k": 3}`

### ⚠️ Endpoints Needing Deployment

5. **Quick Accuracy Check** ⚠️
   - URL: `GET http://44.221.84.58:8500/documents/{id}/accuracy`
   - Status: 404 Not Found
   - **Action Required**: Deploy endpoints

6. **Full Verification** ⚠️
   - URL: `POST http://44.221.84.58:8500/documents/{id}/verify`
   - Status: 404 Not Found
   - **Action Required**: Deploy endpoints

### 📋 Endpoints That Need Document ID

These endpoints work but need a valid document_id:

- `GET /documents/{id}/images/all`
- `GET /documents/{id}/pages/{page_number}`
- `GET /documents/{id}/accuracy` (after deployment)
- `POST /documents/{id}/verify` (after deployment)

## How to Get Document ID

### Method 1: From Documents List Response

```json
{
  "documents": [
    {
      "document_id": "abc-123",  // Use this
      "document_name": "file.pdf"
    }
  ]
}
```

### Method 2: From Storage Status

If document_id is not in the list response, try:
- Check the document registry file
- Use document_name to query images endpoint
- Upload a new document (will have document_id)

## Postman Collection Usage

### Import Collection

1. Open Postman extension in Cursor
2. Click "Import"
3. Select: `postman_collection.json`

### Set Variables

1. Run "Get All Documents"
2. Find document_id in response
3. Set collection variable: `document_id = <your_id>`

### Test Requests

**Working Now:**
- ✅ Health Check
- ✅ Get All Documents
- ✅ Query Text Only
- ✅ Query Images Only

**After Deployment:**
- ⚠️ Quick Accuracy Check
- ⚠️ Full Verification

## Deployment Required

To enable accuracy and verification endpoints:

```bash
./scripts/deploy-api-updates.sh
```

Wait 10-15 seconds, then retry the requests.

## Expected Responses

### After Deployment - Accuracy Check

```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "overall_accuracy": 0.95,
  "ocr_accuracy": 0.94,
  "status": "accurate",
  "verification_needed": false
}
```

### After Deployment - Verification

```json
{
  "document_id": "abc-123",
  "overall_accuracy": 0.945,
  "image_verifications": [...],
  "issues_found": [],
  "recommendations": []
}
```

## Recommendations

1. **Deploy endpoints** to enable accuracy and verification
2. **Upload a new document** to get document_id with enhanced metadata
3. **Test with Postman collection** after deployment
4. **Use variables** in Postman to easily switch between documents
