# CURL Commands - Quick Reference

## Server Information
- **Base URL:** `http://44.221.84.58:8500`
- **Working Document ID:** `a1064075-218c-4e7b-8cde-d54337b9c491` (47 chunks, 13 images)

---

## 1. API Health Check

```bash
curl -X GET "http://44.221.84.58:8500/docs"
```

**Expected:** 200 OK, Swagger UI HTML

---

## 2. List All Documents

```bash
curl -X GET "http://44.221.84.58:8500/documents" | jq '.'
```

**Expected:** JSON array of all documents with metadata

---

## 3. Get Single Document Metadata

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491" | jq '.'
```

**Expected:** Full document metadata including chunks, images, status

---

## 4. Query with search_mode (FIX #1)

```bash
curl -X POST "http://44.221.84.58:8500/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is this document about?",
    "search_mode": "hybrid",
    "k": 3
  }' | jq '.'
```

**Expected:** Answer with citations and sources

**Valid search_mode values:** `hybrid`, `semantic`, `keyword`

---

## 5. Text Query

```bash
curl -X POST "http://44.221.84.58:8500/query/text" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Summarize the main points",
    "k": 5
  }' | jq '.'
```

**Expected:** Text-only answer with text chunks

---

## 6. Image Query (FIX #5)

```bash
curl -X POST "http://44.221.84.58:8500/query/images" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show me images with diagrams",
    "k": 3
  }' | jq '.'
```

**Expected:** Array of images with OCR text and metadata

---

## 7. Get Storage Status (FIX #3)

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/storage/status" | jq '.'
```

**Expected:**
```json
{
  "document_id": "...",
  "text_chunks_count": 47,
  "text_storage_status": "completed",
  "images_count": 13,
  "images_storage_status": "completed"
}
```

---

## 8. Get Document Accuracy (FIX #4)

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/accuracy" | jq '.'
```

**Expected:** OCR accuracy metrics and quality report

---

## 9. Get All Images

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/images" | jq '.'
```

**Expected:** Array of all images with OCR text

---

## 10. Get Images Summary (FIX #8)

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/images-summary" | jq '.'
```

**Expected:**
```json
{
  "total_images": 13,
  "images_with_ocr": 13,
  "total_ocr_length": 12345
}
```

---

## 11. Get Image by Number

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/images/1" | jq '.'
```

**Expected:** Single image details with OCR text

---

## 12. Get Page Content (FIX #6)

```bash
curl -X GET "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/pages/1" | jq '.'
```

**Expected:** Text chunks and images for specific page

---

## 13. Verify Endpoint (FIX #7)

```bash
curl -X POST "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "page_number": 1
  }' | jq '.'
```

**Expected:** Verification report for page OCR accuracy

---

## 14. Re-store Text Content (FIX #9)

```bash
curl -X POST "http://44.221.84.58:8500/documents/a1064075-218c-4e7b-8cde-d54337b9c491/re-store/text" | jq '.'
```

**Expected:** Success message or helpful error if 0 chunks

---

## Quick Test All Endpoints

Run the automated script:

```bash
chmod +x CURL_TEST_ALL_APIS.sh
./CURL_TEST_ALL_APIS.sh
```

---

## Common Options

### Pretty Print JSON
```bash
curl ... | jq '.'
```

### Show Only HTTP Status
```bash
curl ... -s -o /dev/null -w "Status: %{http_code}\n"
```

### Save Response to File
```bash
curl ... -o response.json
```

### Verbose Output
```bash
curl -v ...
```

---

## Testing Different Documents

Replace `DOC_ID` with your document ID:

```bash
DOC_ID="your-document-id-here"
curl -X GET "http://44.221.84.58:8500/documents/$DOC_ID"
```

---

## Expected Test Results (After Deployment)

- ✅ **13/14 endpoints** should return 200 OK
- ✅ **Storage Status** - No more 500 errors
- ✅ **Accuracy Check** - No more 500 errors
- ✅ **Images Summary** - No more 422 errors
- ✅ **search_mode** - Validates properly
- ⚠️ **Re-store Text** - May fail if document has 0 chunks (not a bug)

---

## Troubleshooting

### 422 Unprocessable Entity
- Check request body format
- Verify required fields are present
- Check search_mode is valid: `hybrid`, `semantic`, or `keyword`

### 500 Internal Server Error
- Check server logs: `sudo journalctl -u aris-fastapi -n 50`
- Verify document exists
- Check OpenSearch connection

### 404 Not Found
- Verify document ID exists
- Check endpoint URL is correct

---

**All commands ready to use! Just copy and paste.**
