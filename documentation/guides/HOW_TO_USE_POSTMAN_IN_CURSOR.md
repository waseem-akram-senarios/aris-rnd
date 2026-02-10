# How to Use Postman Extension in Cursor

## Step 1: Import Collection

1. **Open Postman Extension** in Cursor
2. **Click "Import"** button
3. **Select file**: `postman_collection.json`
4. Collection will be imported with all requests

## Step 2: Set Variables

Before testing, set the collection variables:

1. **Click on collection name**: "ARIS RAG - OCR Verification Endpoints"
2. **Go to "Variables" tab**
3. **Set these variables:**
   - `document_id`: Get this from "Get All Documents" request
   - `page_number`: Set to `1` (or any page number)
   - `document_name`: Optional - document name for filtering

## Step 3: Test Requests in Order

### 1. Health Check
- **Purpose**: Verify API is running
- **Expected**: `{"status": "healthy"}`
- **Action**: Click "Send"

### 2. Get All Documents
- **Purpose**: Get list of documents and find document_id
- **Expected**: JSON with documents array
- **Action**: 
  1. Click "Send"
  2. Copy `document_id` from response
  3. Paste into collection variable `document_id`

### 3. Quick Accuracy Check
- **Purpose**: Get accuracy status (fast, no PDF needed)
- **Expected**: JSON with accuracy scores
- **Note**: Will return "Not Found" until endpoints are deployed
- **Action**: Click "Send"

### 4. Full Verification
- **Purpose**: Complete OCR verification with PDF upload
- **Setup**:
  1. In Body → form-data
  2. Click "Select Files" next to `file` field
  3. Choose your PDF file
  4. Set `auto_fix` to `false` (or `true` to enable auto-fix)
- **Expected**: Detailed verification report
- **Note**: Takes 5-10 minutes for large PDFs
- **Action**: Click "Send"

## Quick Test Workflow

1. **Run "Get All Documents"** → Copy document_id
2. **Update variable** → Set `document_id` in collection variables
3. **Run "Quick Accuracy Check"** → See accuracy status
4. **Run "Full Verification"** → Upload PDF and get detailed report

## Troubleshooting

### "Not Found" Error

**Cause**: Endpoints not deployed

**Solution**:
```bash
./scripts/deploy-api-updates.sh
```

Wait 10-15 seconds, then retry.

### Variable Not Working

**Fix**: 
1. Make sure variable is set in collection (not request)
2. Use `{{document_id}}` syntax in URL
3. Save collection after setting variables

### File Upload Not Working

**Fix**:
1. Use `form-data` body type (not `raw` or `binary`)
2. Set `file` field type to "File"
3. Click "Select Files" to choose PDF

## Collection Structure

The collection includes:

1. ✅ **Health Check** - API status
2. ✅ **Get All Documents** - List documents
3. ⚠️ **Quick Accuracy Check** - Needs deployment
4. ⚠️ **Full Verification** - Needs deployment
5. ✅ **Get All Images** - Already working
6. ✅ **Get Page Information** - Already working
7. ✅ **Query Text Only** - Already working
8. ✅ **Query Images Only** - Already working

## Tips

- **Save responses**: Right-click response → "Save Response"
- **Use variables**: Set once, use everywhere
- **Test in order**: Some requests depend on others
- **Check status codes**: 200 = success, 404 = not found, 500 = server error

## After Deployment

Once you deploy the endpoints:

1. **Refresh collection** (re-import if needed)
2. **Test "Quick Accuracy Check"** - Should return JSON
3. **Test "Full Verification"** - Upload PDF and get report

## Example Response (After Deployment)

**Quick Accuracy Check:**
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

**Full Verification:**
```json
{
  "document_id": "abc-123",
  "overall_accuracy": 0.945,
  "image_verifications": [
    {
      "image_id": "page_1_img_0",
      "ocr_accuracy": 0.98,
      "status": "accurate"
    }
  ],
  "issues_found": [],
  "recommendations": []
}
```
