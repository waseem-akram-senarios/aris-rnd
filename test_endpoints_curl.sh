#!/bin/bash
# Quick cURL Test Script for OCR Verification Endpoints

API_BASE="http://44.221.84.58:8500"

echo "=================================================================================="
echo "OCR VERIFICATION ENDPOINTS - cURL TEST"
echo "=================================================================================="
echo

# Get document ID
echo "📋 Step 1: Getting document ID..."
DOC_ID=$(curl -s "$API_BASE/documents" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('documents'):
        print(data['documents'][0]['document_id'])
except:
    print('')
" 2>/dev/null)

if [ -z "$DOC_ID" ]; then
    echo "❌ No documents found"
    exit 1
fi

echo "✅ Document ID: $DOC_ID"
echo

# Test accuracy endpoint
echo "📊 Step 2: Testing Accuracy Endpoint..."
echo "Command: curl -s \"$API_BASE/documents/$DOC_ID/accuracy\""
echo "---"
curl -s "$API_BASE/documents/$DOC_ID/accuracy" | python3 -m json.tool 2>/dev/null || echo "⚠️  Endpoint not available (may need deployment)"
echo
echo "---"
echo

# Test verification endpoint (if PDF available)
PDF_FILE="FL10.11 SPECIFIC8 (1).pdf"
if [ -f "$PDF_FILE" ]; then
    echo "🔍 Step 3: Testing Verification Endpoint..."
    echo "Command: curl -X POST \"$API_BASE/documents/$DOC_ID/verify\" -F \"file=@$PDF_FILE\" -F \"auto_fix=false\""
    echo "⚠️  This may take several minutes..."
    echo "---"
    curl -X POST \
      "$API_BASE/documents/$DOC_ID/verify" \
      -F "file=@$PDF_FILE" \
      -F "auto_fix=false" \
      -o verification_result.json 2>&1 | tail -5
    
    if [ -f "verification_result.json" ]; then
        echo
        echo "✅ Verification complete! Summary:"
        python3 -c "
import json
try:
    with open('verification_result.json') as f:
        data = json.load(f)
    print(f\"Overall Accuracy: {data.get('overall_accuracy', 0):.2%}\")
    print(f\"Images Verified: {len(data.get('image_verifications', []))}\")
    print(f\"Issues: {len(data.get('issues_found', []))}\")
except Exception as e:
    print(f'Error: {e}')
" 2>/dev/null
    fi
else
    echo "⚠️  PDF file not found: $PDF_FILE"
    echo "   Skipping verification test"
fi

echo
echo "=================================================================================="
echo "✅ Test complete!"
echo "=================================================================================="
