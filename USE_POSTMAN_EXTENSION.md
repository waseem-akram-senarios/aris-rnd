# How to Use Postman Extension in Cursor

## 🚀 Quick Start

### Step 1: Open Postman Extension

1. **In Cursor**, look for the **Postman extension** icon in the sidebar
2. **Or** use the command palette: `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
3. **Type**: "Postman" and select "Postman: Open Postman"

### Step 2: Import Collection

1. **Click "Import"** button in Postman extension
2. **Click "Upload Files"** or drag and drop
3. **Select**: `postman_collection.json` from your project
4. **Collection imported**: "ARIS RAG - Complete API Collection"

### Step 3: Set Variables

**Important**: Set these variables before testing:

1. **Click on collection name**: "ARIS RAG - Complete API Collection"
2. **Go to "Variables" tab** (at the bottom)
3. **Set these variables:**
   - `document_id`: Leave empty (will get from first request)
   - `page_number`: `1`
   - `image_number`: `0`
   - `document_name`: Leave empty

### Step 4: Test Endpoints

#### ✅ Test 1: Health Check
- **Request**: "Health Check"
- **Click**: "Send"
- **Expected**: `{"status": "healthy"}`
- **Status**: ✅ Works immediately

#### ✅ Test 2: Get Document ID
- **Request**: "Get All Documents"
- **Click**: "Send"
- **Expected**: JSON with documents array
- **Action**:
  1. Find `document_id` in response (first document)
  2. Copy it
  3. Go to collection → Variables tab
  4. Paste into `document_id` variable
  5. Click "Save" or it auto-saves

#### ✅ Test 3: Get Images Summary (NEW!)
- **Request**: "Get Images Summary (By Number)"
- **Click**: "Send"
- **Expected**: 
  ```json
  {
    "total_images": 99,
    "images": [
      {
        "image_number": 0,
        "ocr_text": "...",
        "page": 1
      }
    ]
  }
  ```
- **Status**: ⚠️ Needs deployment (returns 404 until deployed)

#### ✅ Test 4: Get Image by Number (NEW!)
- **Request**: "Get Image by Number"
- **Setup**: 
  1. Go to collection Variables
  2. Set `image_number` to `0` (or any number)
  3. Save
- **Click**: "Send"
- **Expected**: OCR text for that specific image
- **Status**: ⚠️ Needs deployment (returns 404 until deployed)

---

## 📋 All Available Requests

### Working Now (No Deployment Needed)

1. ✅ **Health Check** - API status
2. ✅ **Get All Documents** - List all documents
3. ✅ **Get All Images (Detailed)** - All images with full metadata
4. ✅ **Get Page Information** - Text and images from a page
5. ✅ **Query Text Only** - Search text content
6. ✅ **Query Images Only** - Search image OCR content

### New Endpoints (Need Deployment)

7. ⚠️ **Get Images Summary (By Number)** - Total count and OCR by number
8. ⚠️ **Get Image by Number** - Specific image OCR by number
9. ⚠️ **Quick Accuracy Check** - Fast accuracy status
10. ⚠️ **Full Verification** - Complete OCR verification

---

## 🔧 Deploy New Endpoints

The new endpoints return "Not Found" until deployed:

```bash
./scripts/deploy-api-updates.sh
```

**Wait 10-15 seconds**, then retry the requests in Postman.

---

## 💡 Tips for Using Postman Extension

### 1. Variables
- **Set once, use everywhere**: Set `document_id` in collection variables
- **Use syntax**: `{{document_id}}` in URLs
- **Auto-save**: Variables save automatically

### 2. Testing Workflow
1. **Health Check** → Verify API is up
2. **Get All Documents** → Get document_id
3. **Set Variables** → Update `document_id` and `image_number`
4. **Test Endpoints** → Run requests in any order

### 3. Response Viewing
- **Pretty**: Auto-formats JSON
- **Raw**: See exact response
- **Preview**: See formatted view
- **Save**: Right-click response → "Save Response"

### 4. Error Handling
- **404 Not Found**: Endpoint not deployed or document/image doesn't exist
- **500 Server Error**: Check server logs
- **Timeout**: Increase timeout in settings

---

## 📝 Example: Get Image by Number

### Setup:
1. **Run "Get All Documents"** → Get document_id
2. **Set variable**: `document_id = "abc-123"`
3. **Set variable**: `image_number = 0`
4. **Run "Get Image by Number"**

### Expected Response:
```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "image_number": 0,
  "page": 1,
  "ocr_text": "Complete OCR text from image 0...",
  "ocr_text_length": 1234
}
```

---

## 🎯 Quick Test Checklist

- [ ] Import `postman_collection.json`
- [ ] Set `document_id` variable (from "Get All Documents")
- [ ] Test "Health Check" → Should work ✅
- [ ] Test "Get Images Summary" → Will work after deployment ⚠️
- [ ] Test "Get Image by Number" → Will work after deployment ⚠️
- [ ] Deploy endpoints: `./scripts/deploy-api-updates.sh`
- [ ] Retest new endpoints → Should work ✅

---

## 🆘 Troubleshooting

### "Collection not importing"
- **Fix**: Make sure file is `postman_collection.json` (not .txt)
- **Fix**: Try re-downloading the file

### "Variables not working"
- **Fix**: Set variables in **collection** (not request)
- **Fix**: Use `{{variable_name}}` syntax
- **Fix**: Save collection after setting variables

### "404 Not Found"
- **Fix**: Deploy endpoints first: `./scripts/deploy-api-updates.sh`
- **Fix**: Wait 10-15 seconds after deployment
- **Fix**: Check document_id is correct

### "Can't find Postman extension"
- **Fix**: Install from Cursor extensions marketplace
- **Fix**: Search for "Postman" in extensions
- **Fix**: Reload Cursor after installation

---

## 📁 Files

- **postman_collection.json** - Import this into Postman
- **USE_POSTMAN_EXTENSION.md** - This guide
- **POSTMAN_QUICK_START.md** - Quick reference
- **HOW_TO_USE_POSTMAN_IN_CURSOR.md** - Detailed guide

---

## ✅ After Deployment

Once you deploy, these will work:

1. **Get Images Summary** → See total count and all images
2. **Get Image by Number** → Get OCR for specific image
3. **Quick Accuracy Check** → Fast accuracy status
4. **Full Verification** → Complete verification report

All endpoints will return proper JSON responses instead of "Not Found"!
