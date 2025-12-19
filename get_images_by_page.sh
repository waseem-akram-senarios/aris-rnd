#!/bin/bash
# Script to get image OCR content by page number

API_BASE="http://44.221.84.58:8500"

echo "=== Getting Document ID ==="
DOC_RESPONSE=$(curl -s -X GET "$API_BASE/documents" -H "Accept: application/json")

# Try to extract document_id using Python (more reliable)
DOC_ID=$(echo "$DOC_RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    docs = data.get('documents', [])
    if docs:
        doc = docs[0]
        doc_id = doc.get('document_id') or doc.get('id') or doc.get('_id')
        if doc_id:
            print(doc_id)
        else:
            # Try document name
            doc_name = doc.get('document_name', '')
            if doc_name:
                print(doc_name)
except:
    pass
")

if [ -z "$DOC_ID" ]; then
    echo "❌ Error: Could not get document ID"
    echo ""
    echo "Available documents:"
    echo "$DOC_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DOC_RESPONSE"
    exit 1
fi

echo "✅ Document ID: $DOC_ID"
echo ""

# Get page number from argument or default to 1
PAGE_NUMBER=${1:-1}
echo "=== Getting Images from Page $PAGE_NUMBER ==="
echo ""

# Get images from page
RESPONSE=$(curl -s -X GET "$API_BASE/documents/$DOC_ID/pages/$PAGE_NUMBER" -H "Accept: application/json")

# Check for errors
if echo "$RESPONSE" | grep -q '"detail"'; then
    echo "❌ Error:"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    exit 1
fi

# Check if jq is available
if command -v jq &> /dev/null; then
    echo "$RESPONSE" | jq '{
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
else
    echo "$RESPONSE" | python3 -m json.tool
    echo ""
    echo "💡 Tip: Install 'jq' for better JSON formatting:"
    echo "   sudo apt-get install jq  # Ubuntu/Debian"
    echo "   brew install jq          # macOS"
fi

echo ""
echo "=== To get OCR text only, run: ==="
echo "curl -X GET \"$API_BASE/documents/$DOC_ID/pages/$PAGE_NUMBER\" -H \"Accept: application/json\" | jq -r '.images[] | \"Image \(.image_number) (Page \(.page)):\\n\(.ocr_text)\\n\"'"
