# Postman in Cursor - Quick Start Guide

## 🚀 Quick Setup

### 1. Import Collection

1. **Open Postman extension** in Cursor (use the link you shared or open from extensions)
2. **Click "Import"** button
3. **Select file**: `postman_collection.json`
4. Collection will appear: **"ARIS RAG - OCR Verification Endpoints"**

### 2. Set Variables

**Important**: Set these variables before testing:

1. Click on collection name: **"ARIS RAG - OCR Verification Endpoints"**
2. Go to **"Variables"** tab
3. Set:
   - `document_id`: Leave empty for now (will get from first request)
   - `page_number`: `1`
   - `document_name`: Leave empty

### 3. Test in Order

#### ✅ Step 1: Health Check
- **Request**: "Health Check"
- **Click**: "Send"
- **Expected**: `{"status": "healthy"}`
- **Status**: Should work immediately ✅

#### ✅ Step 2: Get Document ID
- **Request**: "Get All Documents"
- **Click**: "Send"
- **Expected**: JSON with documents array
- **Action**: 
  1. Find `document_id` in response (first document)
  2. Copy it
  3. Go to collection → Variables
  4. Paste into `document_id` variable
  5. Save
- **Status**: Should work immediately ✅

#### ⚠️ Step 3: Quick Accuracy Check
- **Request**: "Quick Accuracy Check"
- **Click**: "Send"
- **Expected**: JSON with accuracy data
- **Current**: Will return `{"detail": "Not Found"}` until deployed
- **After Deployment**: Will return accuracy scores
- **Status**: Needs deployment ⚠️

#### ⚠️ Step 4: Full Verification
- **Request**: "Full Verification"
- **Setup**:
  1. Go to "Body" tab
  2. Select "form-data"
  3. Click "Select Files" next to `file` field
  4. Choose your PDF file (e.g., `FL10.11 SPECIFIC8 (1).pdf`)
  5. Set `auto_fix` to `false`
- **Click**: "Send"
- **Expected**: Detailed verification report
- **Note**: Takes 5-10 minutes for large PDFs
- **Status**: Needs deployment ⚠️

## 🔧 Fix "Not Found" Error

The accuracy and verification endpoints return "Not Found" because they need deployment.

### Deploy Now:

```bash
./scripts/deploy-api-updates.sh
```

**Wait 10-15 seconds**, then retry the requests.

## ✅ Working Endpoints (No Deployment Needed)

These work right now:

1. **Health Check** ✅
2. **Get All Documents** ✅
3. **Get All Images** ✅
4. **Get Page Information** ✅
5. **Query Text Only** ✅
6. **Query Images Only** ✅

## 📋 Request Details

### Quick Accuracy Check
```
GET http://44.221.84.58:8500/documents/{{document_id}}/accuracy
```

**Response (after deployment):**
```json
{
  "document_id": "...",
  "document_name": "...",
  "overall_accuracy": 0.95,
  "ocr_accuracy": 0.94,
  "status": "accurate",
  "verification_needed": false
}
```

### Full Verification
```
POST http://44.221.84.58:8500/documents/{{document_id}}/verify
Body: form-data
  - file: [Select PDF]
  - auto_fix: false
```

**Response (after deployment):**
```json
{
  "document_id": "...",
  "overall_accuracy": 0.945,
  "image_verifications": [...],
  "issues_found": [],
  "recommendations": []
}
```

## 💡 Tips

1. **Save responses**: Right-click response → "Save Response"
2. **Use variables**: Set `document_id` once, use everywhere
3. **Test in order**: Some requests need document_id first
4. **Check status codes**: 
   - 200 = Success ✅
   - 404 = Not Found (needs deployment) ⚠️
   - 500 = Server Error ❌

## 🎯 Quick Test Workflow

1. ✅ Run "Get All Documents" → Copy document_id
2. ✅ Set variable `document_id` in collection
3. ⚠️ Run "Quick Accuracy Check" → Will work after deployment
4. ⚠️ Run "Full Verification" → Upload PDF, will work after deployment

## 📁 Files

- **postman_collection.json** - Import this into Postman
- **HOW_TO_USE_POSTMAN_IN_CURSOR.md** - Detailed guide
- **POSTMAN_QUICK_START.md** - This file
