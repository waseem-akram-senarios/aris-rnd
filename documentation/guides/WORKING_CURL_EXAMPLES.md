# Working cURL Examples for Images by Page

## ✅ Working Document ID

Based on your documents, use this **actual document ID**:

```
b0b01b35-ccbb-4e52-9db6-2690e531289b
```

## Working cURL Commands

### Get Images from Page 1

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json"
```

### Get OCR Text Only

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '.images[] | .ocr_text'
```

### Get Image Numbers and OCR

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text}'
```

### Get Summary

```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '{page: .page_number, total_images: .total_images, total_ocr_length: .total_ocr_text_length}'
```

## Other Available Documents

You also have:
- `500bdd21-eae3-4677-b5c0-51df48f50e9c` - "FL10.11 SPECIFIC8 (1).pdf"

## Get Your Own Document ID

To find your document ID:

```bash
curl -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | jq '.documents[] | {document_id, document_name, image_count}'
```

This will show all documents with their IDs and image counts.

## Quick Script

```bash
#!/bin/bash
# Get document ID automatically and test page 1

DOC_ID=$(curl -s -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | \
  jq -r '.documents[] | select(.image_count > 0) | .document_id' | head -1)

if [ -z "$DOC_ID" ]; then
  echo "No documents with images found"
  exit 1
fi

echo "Using Document ID: $DOC_ID"
echo ""

curl -X GET "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text}'
```

## Important Notes

1. **Replace `{document_id}`** with the actual ID (not the literal string)
2. **Page numbers start from 1** (not 0)
3. **Image numbers start from 0** (0, 1, 2, etc.)
4. Use documents that have `image_count > 0` for best results
