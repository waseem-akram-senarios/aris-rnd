# Postman Extension - Step by Step Guide

## 🎯 Goal
Test your API endpoints using the Postman extension in Cursor.

---

## Step 1: Open Postman Extension

**Option A: From Sidebar**
1. Look for **Postman icon** in Cursor's left sidebar
2. Click it to open Postman panel

**Option B: From Command Palette**
1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
2. Type: `Postman`
3. Select: **"Postman: Open Postman"**

---

## Step 2: Import Collection

1. **In Postman panel**, click **"Import"** button (top right)
2. **Click "Upload Files"** or drag and drop
3. **Navigate to**: `/home/senarios/Desktop/aris/`
4. **Select**: `postman_collection.json`
5. **Click "Import"**
6. ✅ Collection appears: **"ARIS RAG - Complete API Collection"**

---

## Step 3: Set Variables

**Why?** Variables let you reuse values across requests.

1. **Click on collection name**: "ARIS RAG - Complete API Collection"
2. **Click "Variables" tab** (at the bottom of the panel)
3. **Set these values:**

   | Variable | Value | Description |
   |----------|-------|-------------|
   | `document_id` | (leave empty) | Will get from first request |
   | `page_number` | `1` | Page number to query |
   | `image_number` | `0` | Image number (0, 1, 2, etc.) |
   | `document_name` | (leave empty) | Optional document name |

4. **Variables auto-save** (no need to click save)

---

## Step 4: Test Endpoints

### ✅ Test 1: Health Check

1. **Click request**: "Health Check"
2. **Click "Send"** button
3. **Expected Response:**
   ```json
   {
     "status": "healthy"
   }
   ```
4. ✅ **Status Code**: 200 OK

---

### ✅ Test 2: Get Document ID

1. **Click request**: "Get All Documents"
2. **Click "Send"**
3. **Look at response**: Find `document_id` in the JSON
4. **Copy the document_id** (e.g., `"b0b01b35-ccbb-4e52-9db6-2690e531289b"`)
5. **Go to Variables tab**
6. **Paste into `document_id` variable**
7. ✅ **Now all requests will use this document_id**

---

### ✅ Test 3: Get Images Summary (NEW!)

1. **Click request**: "Get Images Summary (By Number)"
2. **Click "Send"**
3. **Expected Response:**
   ```json
   {
     "document_id": "...",
     "document_name": "...",
     "total_images": 99,
     "images": [
       {
         "image_number": 0,
         "page": 1,
         "ocr_text": "...",
         "ocr_text_length": 1234
       }
     ]
   }
   ```
4. ⚠️ **Note**: Returns 404 until endpoints are deployed

---

### ✅ Test 4: Get Image by Number (NEW!)

1. **Set variable**: Go to Variables tab, set `image_number = 0`
2. **Click request**: "Get Image by Number"
3. **Click "Send"**
4. **Expected Response:**
   ```json
   {
     "document_id": "...",
     "image_number": 0,
     "page": 1,
     "ocr_text": "Complete OCR text from image 0...",
     "ocr_text_length": 1234
   }
   ```
5. ⚠️ **Note**: Returns 404 until endpoints are deployed

---

## 🚀 Deploy New Endpoints

The new endpoints need deployment:

```bash
./scripts/deploy-api-updates.sh
```

**Wait 10-15 seconds**, then retry the requests.

---

## 📋 All Available Requests

Your collection now has **11 requests**:

### Working Now ✅
1. Health Check
2. Get All Documents
3. Get All Images (Detailed)
4. Get Page Information
5. Query Text Only
6. Query Images Only

### New Endpoints (Need Deployment) ⚠️
7. Get Images Summary (By Number) - **NEW!**
8. Get Image by Number - **NEW!**
9. Quick Accuracy Check
10. Full Verification
11. Verification with Auto-Fix

---

## 💡 Pro Tips

### 1. Use Variables
- Set `document_id` once, use everywhere
- Change `image_number` to test different images
- Variables update all requests automatically

### 2. Save Responses
- **Right-click** on response → "Save Response"
- Useful for comparing results

### 3. Test Different Images
- Set `image_number = 0` → Test image 0
- Set `image_number = 1` → Test image 1
- Set `image_number = 5` → Test image 5

### 4. Check Status Codes
- **200** = Success ✅
- **404** = Not Found (needs deployment or wrong ID) ⚠️
- **500** = Server Error ❌

---

## 🎯 Quick Workflow

1. ✅ **Import** `postman_collection.json`
2. ✅ **Set** `document_id` variable (from "Get All Documents")
3. ✅ **Test** "Get Images Summary" → See total count
4. ✅ **Set** `image_number = 0`
5. ✅ **Test** "Get Image by Number" → Get OCR for image 0
6. ✅ **Change** `image_number = 1`
7. ✅ **Test** again → Get OCR for image 1

---

## 🆘 Troubleshooting

### "Can't find Postman extension"
- Install from Cursor extensions marketplace
- Search for "Postman"
- Reload Cursor after installation

### "404 Not Found"
- Deploy endpoints: `./scripts/deploy-api-updates.sh`
- Wait 10-15 seconds
- Check `document_id` is correct

### "Variables not working"
- Set in **collection** variables (not request)
- Use `{{variable_name}}` syntax
- Save collection

### "Collection won't import"
- Check file is `postman_collection.json`
- Try re-downloading
- Check file is valid JSON

---

## ✅ Success Checklist

- [ ] Postman extension opened
- [ ] Collection imported
- [ ] Variables set (`document_id`, `image_number`)
- [ ] Health Check works (200 OK)
- [ ] Get All Documents works (200 OK)
- [ ] Get Images Summary tested (will work after deployment)
- [ ] Get Image by Number tested (will work after deployment)
- [ ] Endpoints deployed: `./scripts/deploy-api-updates.sh`
- [ ] All endpoints working after deployment

---

## 📁 Files Reference

- **postman_collection.json** - Import this file
- **USE_POSTMAN_EXTENSION.md** - Detailed guide
- **POSTMAN_STEP_BY_STEP.md** - This file
- **POSTMAN_QUICK_START.md** - Quick reference

---

## 🎉 You're Ready!

Your Postman collection is updated with:
- ✅ 11 total requests
- ✅ 4 variables (document_id, page_number, image_number, document_name)
- ✅ New endpoints for images by number
- ✅ All endpoints ready to test

**Next**: Import the collection and start testing!
