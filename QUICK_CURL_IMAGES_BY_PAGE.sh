#!/bin/bash
# Quick cURL commands for getting image OCR by page number

API_BASE="http://44.221.84.58:8500"

# Get document ID first
echo "=== Getting Document ID ==="
DOC_ID=$(curl -s -X GET "$API_BASE/documents" -H "Accept: application/json" | jq -r '.documents[0].document_id // empty')

if [ -z "$DOC_ID" ]; then
    echo "❌ No document ID found. Upload a document first."
    exit 1
fi

echo "✅ Document ID: $DOC_ID"
echo ""

# Get page number from argument or default to 1
PAGE_NUMBER=${1:-1}

echo "=== Getting Images from Page $PAGE_NUMBER ==="
echo ""

# Get images from page
curl -X GET \
  "$API_BASE/documents/$DOC_ID/pages/$PAGE_NUMBER" \
  -H "Accept: application/json" | jq '{
    page_number: .page_number,
    total_images: .total_images,
    total_ocr_length: .total_ocr_text_length,
    images: [.images[] | {
      image_number: .image_number,
      page: .page,
      ocr_text_length: .ocr_text_length,
      ocr_text: .ocr_text
    }]
  }'

echo ""
echo "=== To get OCR text only, use: ==="
echo "curl -X GET \"$API_BASE/documents/$DOC_ID/pages/$PAGE_NUMBER\" -H \"Accept: application/json\" | jq -r '.images[] | \"Image \(.image_number):\\n\(.ocr_text)\\n\"'"
