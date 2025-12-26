# cURL Commands for Page Query Endpoint

## Endpoint

**GET `/documents/{document_id}/pages/{page_number}`**

## Prerequisites

1. **Get a Document ID**: First, list documents to get a document ID
2. **Know the Page Number**: Page numbers are 1-indexed (page 1, page 2, etc.)

## Step 1: Get Document ID

```bash
# List all documents to get a document ID
curl -X GET \
  "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | jq '.documents[0].document_id'
```

**Example Response:**
```json
{
  "documents": [
    {
      "document_id": "2bac8df5-931a-4d5a-9074-c8eaa7d6247e",
      "document_name": "FL10.11 SPECIFIC8 (1).pdf",
      ...
    }
  ]
}
```

## Step 2: Query Page Information

### Basic Query (Page 1)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json"
```

### Pretty Print with jq

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq .
```

### Get Summary Only

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '{
    page_number: .page_number,
    total_text_chunks: .total_text_chunks,
    total_images: .total_images,
    total_text_length: .total_text_length,
    total_ocr_text_length: .total_ocr_text_length
  }'
```

### Get Text Chunks Only

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.text_chunks[] | {
    chunk_index: .chunk_index,
    page: .page,
    text_length: (.text | length),
    text_preview: (.text[:200])
  }'
```

### Get Images Only

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {
    image_number: .image_number,
    page: .page,
    ocr_text_length: .ocr_text_length,
    ocr_preview: (.ocr_text[:200])
  }'
```

### Get OCR Text from All Images

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {
    image_number: .image_number,
    ocr_text: .ocr_text
  }'
```

### Get Complete Page Content (Text + OCR)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '{
    page_number: .page_number,
    document_name: .document_name,
    text_content: [.text_chunks[] | .text],
    image_ocr: [.images[] | .ocr_text],
    summary: {
      text_chunks: .total_text_chunks,
      images: .total_images,
      total_text: .total_text_length,
      total_ocr: .total_ocr_text_length
    }
  }'
```

## Test Different Pages

### Page 1
```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.page_number, .total_text_chunks, .total_images'
```

### Page 5
```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/5" \
  -H "Accept: application/json" | jq '.page_number, .total_text_chunks, .total_images'
```

### Page 26
```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/26" \
  -H "Accept: application/json" | jq '.page_number, .total_text_chunks, .total_images'
```

## Save Response to File

```bash
# Save complete response
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" > page_1_info.json

# Save only text content
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.text_chunks[].text' > page_1_text.txt

# Save only OCR text
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json" | jq '.images[].ocr_text' > page_1_ocr.txt
```

## Quick Test Script

```bash
#!/bin/bash

# Set document ID
DOC_ID="2bac8df5-931a-4d5a-9074-c8eaa7d6247e"
PAGE_NUM=1

echo "Testing Page Query Endpoint..."
echo "Document ID: $DOC_ID"
echo "Page Number: $PAGE_NUM"
echo ""

# Test the endpoint
curl -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/pages/$PAGE_NUM" \
  -H "Accept: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" | jq '{
    status: "success",
    page_number: .page_number,
    document_name: .document_name,
    text_chunks: .total_text_chunks,
    images: .total_images,
    total_text: .total_text_length,
    total_ocr: .total_ocr_text_length,
    total_content: (.total_text_length + .total_ocr_text_length)
  }'
```

## Expected Response Format

```json
{
  "document_id": "2bac8df5-931a-4d5a-9074-c8eaa7d6247e",
  "document_name": "FL10.11 SPECIFIC8 (1).pdf",
  "page_number": 1,
  "text_chunks": [
    {
      "chunk_index": 0,
      "text": "--- Page 1 ---\n<!-- image -->\n| FILLING HANDLER...",
      "page": 1,
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "token_count": 150,
      "start_char": 0,
      "end_char": 4273
    }
  ],
  "images": [
    {
      "image_id": "9a2f3953-c8aa-4001-be53-ad1ba49dfb8f",
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "image_number": 0,
      "page": 1,
      "ocr_text": "Complete OCR text...",
      "ocr_text_length": 3917,
      "metadata": {...}
    }
  ],
  "total_text_chunks": 10,
  "total_images": 65,
  "total_text_length": 39910,
  "total_ocr_text_length": 154345,
  "text_index": "aris-rag-index",
  "images_index": "aris-rag-images-index"
}
```

## Error Handling

### Document Not Found (404)
```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/invalid-id/pages/1" \
  -H "Accept: application/json"
```

### Invalid Page Number (400)
```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/0" \
  -H "Accept: application/json"
```

## Complete Test Workflow

```bash
# 1. Check health
curl http://44.221.84.58:8500/health

# 2. Get document ID
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | jq -r '.documents[0].document_id')
echo "Document ID: $DOC_ID"

# 3. Query page 1
curl -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json" | jq '{
    page: .page_number,
    text_chunks: .total_text_chunks,
    images: .total_images,
    total_content: (.total_text_length + .total_ocr_text_length)
  }'
```
