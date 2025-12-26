# Postman Collection for Verification Endpoints

## ⚠️ IMPORTANT: Endpoints Need Deployment

The verification endpoints return "Not Found" because they need to be deployed to the server first.

## Deployment Required

Before using these endpoints in Postman, deploy the code:

```bash
./scripts/deploy-api-updates.sh
```

Wait 10-15 seconds after deployment, then test.

## Postman Requests

### 1. Quick Accuracy Check

**Method:** `GET`  
**URL:** `http://44.221.84.58:8500/documents/{document_id}/accuracy`

**Path Variables:**
- `document_id`: Your document ID (e.g., `2bac8df5-931a-4d5a-9074-c8eaa7d6247e`)

**Headers:**
- `Accept: application/json`

**Example:**
```
GET http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/accuracy
```

**Expected Response (after deployment):**
```json
{
  "document_id": "2bac8df5-931a-4d5a-9074-c8eaa7d6247e",
  "document_name": "document.pdf",
  "overall_accuracy": 0.95,
  "ocr_accuracy": 0.94,
  "text_accuracy": null,
  "status": "accurate",
  "verification_needed": false,
  "last_verification": "2024-12-19T18:00:00Z"
}
```

**Current Response (before deployment):**
```json
{
  "detail": "Not Found"
}
```

### 2. Full Verification

**Method:** `POST`  
**URL:** `http://44.221.84.58:8500/documents/{document_id}/verify`

**Path Variables:**
- `document_id`: Your document ID

**Body Type:** `form-data`

**Form Data:**
- `file`: (File) - Select your PDF file
- `auto_fix`: (Text) - `false` or `true`

**Example:**
```
POST http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/verify

Body (form-data):
  file: [Select PDF file]
  auto_fix: false
```

**Expected Response (after deployment):**
```json
{
  "document_id": "2bac8df5-931a-4d5a-9074-c8eaa7d6247e",
  "document_name": "document.pdf",
  "verification_timestamp": "2024-12-19T18:00:00Z",
  "overall_accuracy": 0.945,
  "page_verifications": [...],
  "image_verifications": [...],
  "issues_found": [],
  "recommendations": [],
  "auto_fix_applied": false
}
```

## Postman Setup Steps

### Step 1: Get Document ID

**Request 1: List Documents**
- Method: `GET`
- URL: `http://44.221.84.58:8500/documents`
- Headers: `Accept: application/json`

Copy the `document_id` from the response.

### Step 2: Test Accuracy Endpoint

**Request 2: Accuracy Check**
- Method: `GET`
- URL: `http://44.221.84.58:8500/documents/{{document_id}}/accuracy`
- Headers: `Accept: application/json`

**Note:** Replace `{{document_id}}` with actual ID or use Postman variables.

### Step 3: Test Verification Endpoint

**Request 3: Full Verification**
- Method: `POST`
- URL: `http://44.221.84.58:8500/documents/{{document_id}}/verify`
- Body: `form-data`
  - Key: `file`, Type: `File`, Value: [Select PDF]
  - Key: `auto_fix`, Type: `Text`, Value: `false`

## Postman Environment Variables

Create a Postman environment with:

```json
{
  "base_url": "http://44.221.84.58:8500",
  "document_id": "2bac8df5-931a-4d5a-9074-c8eaa7d6247e"
}
```

Then use:
- `{{base_url}}/documents/{{document_id}}/accuracy`
- `{{base_url}}/documents/{{document_id}}/verify`

## Troubleshooting

### "Not Found" Error

**Cause:** Endpoints not deployed yet

**Solution:**
1. Deploy: `./scripts/deploy-api-updates.sh`
2. Wait 10-15 seconds
3. Retry request

### 404 Error

**Cause:** Document ID doesn't exist

**Solution:**
1. Check document ID: `GET /documents`
2. Use correct document ID
3. Ensure document is uploaded

### Timeout Error

**Cause:** Verification takes time (5-10 minutes for large PDFs)

**Solution:**
1. Increase Postman timeout settings
2. Use smaller PDF for testing
3. Check server logs if persistent

## Currently Working Endpoints (No Deployment Needed)

These work right now in Postman:

### Get All Images
- Method: `GET`
- URL: `http://44.221.84.58:8500/documents/{{document_id}}/images/all`

### Get Page Information
- Method: `GET`
- URL: `http://44.221.84.58:8500/documents/{{document_id}}/pages/1`

### Query Text
- Method: `POST`
- URL: `http://44.221.84.58:8500/query/text`
- Body (JSON):
```json
{
  "question": "What is in this document?",
  "k": 5
}
```

### Query Images
- Method: `POST`
- URL: `http://44.221.84.58:8500/query/images`
- Body (JSON):
```json
{
  "question": "tools and equipment",
  "k": 5
}
```

## Quick Test After Deployment

```bash
# Test in terminal first
curl -s "http://44.221.84.58:8500/documents/YOUR_DOC_ID/accuracy" | python3 -m json.tool

# If it works, then use in Postman
```
