# cURL Commands: Get Image OCR Content by Page Number

## Main Endpoint

**GET** `/documents/{document_id}/pages/{page_number}`

Returns all images from a specific page with their OCR text content.

---

## Basic cURL Command

### Get Images from Page 1

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json"
```

### Get Images from Page 2

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/2" \
  -H "Accept: application/json"
```

### Get Images from Any Page

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/{page_number}" \
  -H "Accept: application/json"
```

---

## Complete Examples

### Example 1: Get All Images from Page 1

```bash
# Replace {document_id} with your actual document ID
curl -X GET \
  "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text_length, ocr_text}'
```

**Response includes:**
- All images from page 1
- OCR text for each image
- Image numbers
- Metadata

### Example 2: Pretty Print Only OCR Text

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq '.images[] | "Image \(.image_number) (Page \(.page)): \(.ocr_text)"'
```

### Example 3: Get Summary (Count and OCR Lengths)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq '{
    page_number: .page_number,
    total_images: .total_images,
    total_ocr_length: .total_ocr_text_length,
    images: [.images[] | {image_number, page, ocr_text_length}]
  }'
```

### Example 4: Get OCR Text Only (No Metadata)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq '.images[] | .ocr_text'
```

### Example 5: Save OCR to File

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq -r '.images[] | "=== Image \(.image_number) (Page \(.page)) ===\n\(.ocr_text)\n"' > page_1_ocr.txt
```

---

## Response Structure

The endpoint returns:

```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "page_number": 1,
  "images": [
    {
      "image_id": "uuid-here",
      "image_number": 0,
      "page": 1,
      "ocr_text": "Complete OCR text from image 0...",
      "ocr_text_length": 1234,
      "metadata": {...},
      "extraction_method": "docling_ocr"
    },
    {
      "image_id": "uuid-here",
      "image_number": 1,
      "page": 1,
      "ocr_text": "Complete OCR text from image 1...",
      "ocr_text_length": 567,
      "metadata": {...}
    }
  ],
  "total_images": 2,
  "total_ocr_text_length": 1801
}
```

---

## Advanced Usage

### Get Images from Multiple Pages

```bash
# Page 1
curl -X GET "http://44.221.84.58:8500/documents/{document_id}/pages/1" -H "Accept: application/json" > page_1.json

# Page 2
curl -X GET "http://44.221.84.58:8500/documents/{document_id}/pages/2" -H "Accept: application/json" > page_2.json

# Page 3
curl -X GET "http://44.221.84.58:8500/documents/{document_id}/pages/3" -H "Accept: application/json" > page_3.json
```

### Loop Through Pages (Bash Script)

```bash
#!/bin/bash
DOC_ID="your-document-id"
MAX_PAGE=10

for page in $(seq 1 $MAX_PAGE); do
  echo "Getting images from page $page..."
  curl -X GET \
    "http://44.221.84.58:8500/documents/$DOC_ID/pages/$page" \
    -H "Accept: application/json" | jq "{
      page: .page_number,
      images_count: .total_images,
      ocr_texts: [.images[] | {image_number, ocr_text}]
    }" > "page_${page}_images.json"
done
```

### Filter by Image Number

```bash
# Get only image number 0 from page 1
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq '.images[] | select(.image_number == 0)'
```

### Get OCR Text with Image Numbers

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json" | jq -r '.images[] | "Image \(.image_number):\n\(.ocr_text)\n---"'
```

---

## Quick Reference

### Get Document ID First

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | jq '.documents[0].document_id'
```

### Get All Pages Summary

```bash
# Get total pages (you need to know this or try pages 1-100)
for page in {1..10}; do
  echo "Page $page:"
  curl -s -X GET \
    "http://44.221.84.58:8500/documents/{document_id}/pages/$page" \
    -H "Accept: application/json" | jq '{page: .page_number, images: .total_images, ocr_length: .total_ocr_text_length}'
done
```

---

## Using jq for Better Output

### Install jq (if not installed)

```bash
# Ubuntu/Debian
sudo apt-get install jq

# macOS
brew install jq
```

### Useful jq Filters

```bash
# Count images per page
curl ... | jq '.total_images'

# Get all OCR text concatenated
curl ... | jq -r '.images[].ocr_text' | tr '\n' ' '

# Get image numbers and OCR lengths
curl ... | jq '.images[] | {image_number, ocr_text_length}'

# Get full image details
curl ... | jq '.images[]'
```

---

## Error Handling

### Check if Page Exists

```bash
response=$(curl -s -w "%{http_code}" -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/pages/1" \
  -H "Accept: application/json")

http_code="${response: -3}"
body="${response%???}"

if [ "$http_code" = "200" ]; then
  echo "$body" | jq '.images[] | .ocr_text'
else
  echo "Error: HTTP $http_code"
  echo "$body"
fi
```

---

## Complete Working Example

```bash
#!/bin/bash

# Step 1: Get document ID
echo "Getting document ID..."
DOC_ID=$(curl -s -X GET \
  "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | jq -r '.documents[0].document_id')

echo "Document ID: $DOC_ID"

# Step 2: Get images from page 1
echo "Getting images from page 1..."
curl -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json" | jq '{
    page: .page_number,
    total_images: .total_images,
    images: [.images[] | {
      image_number: .image_number,
      page: .page,
      ocr_text: .ocr_text,
      ocr_text_length: .ocr_text_length
    }]
  }'
```

---

## Notes

- **Page numbers are 1-indexed** (start from 1, not 0)
- **Image numbers are 0-indexed** (start from 0)
- Response includes both text chunks and images from the page
- Use `jq` for better JSON parsing and filtering
- Large responses may take a few seconds

---

## Alternative: Get All Images (Not by Page)

If you want all images regardless of page:

```bash
# Get all images summary
curl -X GET \
  "http://44.221.84.58:8500/documents/{document_id}/images" \
  -H "Accept: application/json" | jq '.images[] | select(.page == 1) | .ocr_text'
```

This gets all images and filters by page number using jq.
