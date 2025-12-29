#!/bin/bash
# Test OCR API endpoints with curl
# Demonstrates all OCR integration features

API_URL="${API_URL:-http://44.221.84.58:8500}"
TEST_FILE="${1:-sample.pdf}"

echo "=========================================="
echo "Testing OCR API Endpoints"
echo "=========================================="
echo ""
echo "API URL: $API_URL"
echo "Test File: $TEST_FILE"
echo ""

# Check if test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo "⚠️  Test file not found: $TEST_FILE"
    echo "Usage: $0 <pdf_file>"
    exit 1
fi

# Test 1: Upload with OCRmyPDF parser
echo "Test 1: Upload document with OCRmyPDF parser"
echo "-------------------------------------------"
echo "Command:"
echo "curl -X POST \"$API_URL/documents\" \\"
echo "  -F \"file=@$TEST_FILE\" \\"
echo "  -F \"parser_preference=ocrmypdf\""
echo ""

response=$(curl -s -X POST "$API_URL/documents" \
  -F "file=@$TEST_FILE" \
  -F "parser_preference=ocrmypdf")

echo "Response:"
echo "$response" | jq '.' 2>/dev/null || echo "$response"
echo ""

# Extract document ID
doc_id=$(echo "$response" | jq -r '.document_id' 2>/dev/null)
echo "Document ID: $doc_id"
echo ""

# Test 2: OCR preprocessing endpoint
echo "Test 2: OCR Preprocessing (standalone)"
echo "-------------------------------------------"
echo "Command:"
echo "curl -X POST \"$API_URL/documents/ocr-preprocess\" \\"
echo "  -F \"file=@$TEST_FILE\" \\"
echo "  -F \"languages=eng\" \\"
echo "  -F \"force_ocr=false\" \\"
echo "  --output ocr_output.pdf"
echo ""

curl -s -X POST "$API_URL/documents/ocr-preprocess" \
  -F "file=@$TEST_FILE" \
  -F "languages=eng" \
  -F "force_ocr=false" \
  --output ocr_output.pdf

if [ -f "ocr_output.pdf" ]; then
    size=$(ls -lh ocr_output.pdf | awk '{print $5}')
    echo "✅ OCR output saved: ocr_output.pdf ($size)"
    rm ocr_output.pdf
else
    echo "❌ OCR preprocessing failed"
fi
echo ""

# Test 3: Upload with OCR preprocessing + PyMuPDF
echo "Test 3: Hybrid approach (OCR preprocessing + PyMuPDF)"
echo "-------------------------------------------"
echo "Command:"
echo "curl -X POST \"$API_URL/documents\" \\"
echo "  -F \"file=@$TEST_FILE\" \\"
echo "  -F \"parser_preference=pymupdf\" \\"
echo "  -F \"use_ocr_preprocessing=true\""
echo ""

response=$(curl -s -X POST "$API_URL/documents" \
  -F "file=@$TEST_FILE" \
  -F "parser_preference=pymupdf" \
  -F "use_ocr_preprocessing=true")

echo "Response:"
echo "$response" | jq '.' 2>/dev/null || echo "$response"
echo ""

# Test 4: Multi-language OCR preprocessing
echo "Test 4: Multi-language OCR preprocessing"
echo "-------------------------------------------"
echo "Command:"
echo "curl -X POST \"$API_URL/documents/ocr-preprocess\" \\"
echo "  -F \"file=@$TEST_FILE\" \\"
echo "  -F \"languages=eng+spa\" \\"
echo "  --output ocr_multilang.pdf"
echo ""

curl -s -X POST "$API_URL/documents/ocr-preprocess" \
  -F "file=@$TEST_FILE" \
  -F "languages=eng+spa" \
  --output ocr_multilang.pdf 2>&1

if [ -f "ocr_multilang.pdf" ]; then
    size=$(ls -lh ocr_multilang.pdf | awk '{print $5}')
    echo "✅ Multi-language OCR output saved: ocr_multilang.pdf ($size)"
    rm ocr_multilang.pdf
else
    echo "⚠️  Multi-language OCR may require Spanish language pack"
    echo "   Install with: sudo apt-get install tesseract-ocr-spa"
fi
echo ""

# Test 5: Query document (if we have a doc_id)
if [ ! -z "$doc_id" ] && [ "$doc_id" != "null" ]; then
    echo "Test 5: Query OCR-processed document"
    echo "-------------------------------------------"
    echo "Command:"
    echo "curl -X POST \"$API_URL/query?document_id=$doc_id\" \\"
    echo "  -H \"Content-Type: application/json\" \\"
    echo "  -d '{\"question\": \"Summarize this document\", \"k\": 5}'"
    echo ""
    
    # Wait a bit for processing
    echo "Waiting 5 seconds for document processing..."
    sleep 5
    
    response=$(curl -s -X POST "$API_URL/query?document_id=$doc_id" \
      -H "Content-Type: application/json" \
      -d '{"question": "Summarize this document", "k": 5}')
    
    echo "Response:"
    echo "$response" | jq '.' 2>/dev/null || echo "$response"
    echo ""
fi

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "✅ All OCR API endpoints tested"
echo ""
echo "Available OCR features:"
echo "  1. Direct OCRmyPDF parsing"
echo "  2. Standalone OCR preprocessing"
echo "  3. Hybrid OCR + fast parsing"
echo "  4. Multi-language support"
echo "  5. RAG queries on OCR'd documents"
echo ""
echo "Documentation:"
echo "  - OCR_INTEGRATION_GUIDE.md"
echo "  - OCR_QUICK_START.md"
echo ""
