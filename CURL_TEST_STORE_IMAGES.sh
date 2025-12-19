#!/bin/bash
# Curl commands to test /store/images endpoint

API_BASE="http://44.221.84.58:8500"

# Get document ID first
echo "=== Getting Document ID ==="
DOC_ID=$(curl -s -X GET "$API_BASE/documents" -H "Accept: application/json" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); docs=d.get('documents',[]); \
  doc=next((d for d in docs if d.get('images_detected') or d.get('image_count',0)>0), docs[0] if docs else None); \
  print(doc.get('document_id') or doc.get('document_name','') if doc else '')")

if [ -z "$DOC_ID" ]; then
  echo "❌ No document ID found"
  exit 1
fi

echo "✅ Document ID: $DOC_ID"
echo ""

# Test 1: Without file
echo "=== TEST 1: Store Images (NO FILE) ==="
echo "Command:"
echo "curl -X POST \"$API_BASE/documents/$DOC_ID/store/images\" \\"
echo "  -H \"Accept: application/json\""
echo ""
echo "Response:"
curl -X POST "$API_BASE/documents/$DOC_ID/store/images" \
  -H "Accept: application/json" | python3 -m json.tool 2>/dev/null || curl -X POST "$API_BASE/documents/$DOC_ID/store/images" -H "Accept: application/json"

echo ""
echo ""

# Test 2: With file (if PDF exists)
echo "=== TEST 2: Store Images (WITH FILE) ==="
PDF_FILE=""
for file in *.pdf; do
  if [ -f "$file" ]; then
    PDF_FILE="$file"
    break
  fi
done

if [ -n "$PDF_FILE" ] && [ -f "$PDF_FILE" ]; then
  echo "Using PDF: $PDF_FILE"
  echo "Command:"
  echo "curl -X POST \"$API_BASE/documents/$DOC_ID/store/images\" \\"
  echo "  -F \"file=@$PDF_FILE\" \\"
  echo "  -H \"Accept: application/json\""
  echo ""
  echo "Response (processing may take 1-2 minutes):"
  curl -X POST "$API_BASE/documents/$DOC_ID/store/images" \
    -F "file=@$PDF_FILE" \
    -H "Accept: application/json" | python3 -m json.tool 2>/dev/null || curl -X POST "$API_BASE/documents/$DOC_ID/store/images" -F "file=@$PDF_FILE" -H "Accept: application/json"
else
  echo "⚠️  No PDF file found in current directory"
  echo ""
  echo "To test with file, use:"
  echo "curl -X POST \"$API_BASE/documents/$DOC_ID/store/images\" \\"
  echo "  -F \"file=@/path/to/your/document.pdf\" \\"
  echo "  -H \"Accept: application/json\""
fi

echo ""
echo ""

# Test 3: Verify images stored
echo "=== TEST 3: Verify Images Stored ==="
echo "Command:"
echo "curl -X GET \"$API_BASE/documents/$DOC_ID/images/all?limit=5\" \\"
echo "  -H \"Accept: application/json\""
echo ""
echo "Response:"
curl -s -X GET "$API_BASE/documents/$DOC_ID/images/all?limit=5" \
  -H "Accept: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"Total Images: {d.get('total',0)}\"); print(f\"Images with OCR: {d.get('images_with_ocr',0)}\")" 2>/dev/null || echo "Check manually"
