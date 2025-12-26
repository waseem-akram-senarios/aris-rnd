# How to Find Which Pages Have Images

## Problem

You're getting empty results:
```json
{
  "page_number": 1,
  "total_images": 0,
  "images": []
}
```

This means either:
1. Images aren't stored in OpenSearch yet
2. Images are on different pages
3. Images need to be stored first

## Solution 1: Check All Images in Document

### Get All Images (Find Which Pages Have Images)

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=1000" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text_length}'
```

This shows all images and which page each is on.

### Find Pages with Images

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=1000" \
  -H "Accept: application/json" | jq '[.images[] | .page] | unique | sort'
```

This lists all page numbers that have images.

## Solution 2: Check Document Status

### Check if Images Are Stored

```bash
curl -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | jq '.documents[] | select(.document_id == "b0b01b35-ccbb-4e52-9db6-2690e531289b") | {document_name, image_count, images_stored, images_storage_status}'
```

Look for:
- `images_storage_status`: Should be "success" or "completed"
- `images_stored`: Should be > 0
- `image_count`: Total images detected

## Solution 3: Try Different Pages

If images aren't on page 1, try other pages:

```bash
# Try page 2
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/2" \
  -H "Accept: application/json" | jq '.total_images'

# Try page 10
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/10" \
  -H "Accept: application/json" | jq '.total_images'

# Try page 20
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/20" \
  -H "Accept: application/json" | jq '.total_images'
```

## Solution 4: Store Images First

If `images_storage_status` is "pending", you need to store images. You can re-process the document with file upload:

```bash
# Re-process with file upload (extracts OCR from images)
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@/path/to/document.pdf" \
  -H "Accept: application/json"
```

Or check if images are already stored (without file upload):

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -H "Accept: application/json"
```

**Note**: If images were detected but OCR wasn't extracted, you must provide the PDF file to re-process with Docling parser.

## Complete Script to Find Images

```bash
#!/bin/bash
DOC_ID="b0b01b35-ccbb-4e52-9db6-2690e531289b"

echo "=== Checking Document Status ==="
curl -s -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | \
  jq ".documents[] | select(.document_id == \"$DOC_ID\") | {image_count, images_stored, images_storage_status}"

echo ""
echo "=== Getting All Images ==="
curl -s -X GET "http://44.221.84.58:8500/documents/$DOC_ID/images/all?limit=1000" \
  -H "Accept: application/json" | \
  jq '{total: .total, pages_with_images: [.images[] | .page] | unique | sort}'

echo ""
echo "=== First 5 Images ==="
curl -s -X GET "http://44.221.84.58:8500/documents/$DOC_ID/images/all?limit=5" \
  -H "Accept: application/json" | \
  jq '.images[] | {image_number, page, ocr_text_length}'
```

## Quick Commands

### Find Pages with Images
```bash
curl -s -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=1000" \
  -H "Accept: application/json" | jq '[.images[] | .page] | unique | sort | .[]'
```

### Get Images from a Specific Page (After Finding Which Page)
```bash
# Replace PAGE_NUMBER with actual page number from above
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/PAGE_NUMBER" \
  -H "Accept: application/json" | jq '.images[] | {image_number, ocr_text}'
```

## Notes

- **Page numbers start from 1** (1-indexed)
- **Image numbers start from 0** (0-indexed)
- If `images_storage_status` is "pending", images need to be stored first
- Use `/images/all` to see all images regardless of page
- Use `/pages/{page_number}` to get images from a specific page
