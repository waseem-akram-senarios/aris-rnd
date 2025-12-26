# Store Images First - Then Query by Page

## Problem

You're getting empty results because images are detected but **not stored** in OpenSearch yet:

```json
{
  "image_count": 13,
  "images_stored": 0,
  "images_storage_status": "pending"
}
```

## Solution: Store Images First

### Option 1: Re-process with File Upload (Recommended)

If images were detected but OCR wasn't extracted, you can re-process the document by uploading the PDF file:

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@/path/to/your/document.pdf" \
  -H "Accept: application/json"
```

**Expected Response:**
```json
{
  "status": "completed",
  "images_stored": 13,
  "total_ocr_text_length": 25000,
  "reprocessed": true,
  "extraction_method": "docling",
  "message": "Successfully re-processed and stored 13 images with OCR in index 'aris-rag-images-index'"
}
```

### Option 2: Check if Already Stored (No File Upload)

If images might already be stored, check without uploading:

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -H "Accept: application/json"
```

**If images are already stored:**
```json
{
  "status": "completed",
  "images_stored": 13,
  "total_ocr_text_length": 25000,
  "reprocessed": false,
  "message": "Image OCR content verified: 13 images in index 'aris-rag-images-index'"
}
```

**If images are not stored:**
```json
{
  "detail": "Images were detected but not stored. Provide the PDF file in the request to re-process with Docling parser and extract image OCR."
}
```

### Step 2: Wait a Few Seconds

Wait 5-10 seconds for images to be indexed in OpenSearch.

### Step 3: Query by Page

Now you can get images by page:

```bash
# Get images from page 1
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text}'
```

## Complete Workflow

### With File Upload (Re-process Document)

```bash
#!/bin/bash
DOC_ID="b0b01b35-ccbb-4e52-9db6-2690e531289b"
PDF_FILE="/path/to/document.pdf"

echo "=== Step 1: Re-process and Store Images ==="
curl -X POST "http://44.221.84.58:8500/documents/$DOC_ID/store/images" \
  -F "file=@$PDF_FILE" \
  -H "Accept: application/json" | jq '.'

echo ""
echo "Waiting 5 seconds for indexing..."
sleep 5

echo ""
echo "=== Step 2: Check Which Pages Have Images ==="
curl -s -X GET "http://44.221.84.58:8500/documents/$DOC_ID/images/all?limit=1000" \
  -H "Accept: application/json" | \
  jq '[.images[] | .page] | unique | sort'

echo ""
echo "=== Step 3: Get Images from Page 1 ==="
curl -X GET "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json" | \
  jq '.images[] | {image_number, page, ocr_text}'
```

## Quick Commands

### Re-process and Store Images (With File Upload)
```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@document.pdf" \
  -H "Accept: application/json"
```

### Check if Images Already Stored (No File Upload)
```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -H "Accept: application/json"
```

### Find Which Pages Have Images
```bash
curl -s -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=1000" \
  -H "Accept: application/json" | jq '[.images[] | .page] | unique | sort'
```

### Get Images from Specific Page
```bash
# Replace PAGE_NUMBER with actual page (e.g., 1, 2, 3, etc.)
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/PAGE_NUMBER" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text}'
```

## Check Storage Status

```bash
curl -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | \
  jq '.documents[] | select(.document_id == "b0b01b35-ccbb-4e52-9db6-2690e531289b") | {images_stored, images_storage_status}'
```

Look for:
- `images_storage_status`: Should be "success" or "completed" (not "pending")
- `images_stored`: Should match `image_count`

## Notes

- **File upload is optional** - if provided, document will be re-processed with Docling parser
- **If no file provided** - endpoint checks if images are already stored
- **Always store images first** if `images_storage_status` is "pending"
- **Wait 5-10 seconds** after storing before querying
- **Use `/images/all`** to see all images and find which pages have them
- **Use `/pages/{page_number}`** to get images from a specific page
- **Re-processing extracts OCR** from images using Docling parser
