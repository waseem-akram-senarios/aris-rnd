#!/bin/bash
# Quick OCR Accuracy Test Script

API_BASE="http://44.221.84.58:8500"

echo "=" | head -c 80 && echo
echo "OCR ACCURACY TEST"
echo "=" | head -c 80 && echo

# Get document ID
echo "Getting document ID..."
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

# Quick accuracy check
echo -e "\n📊 Quick Accuracy Check:"
curl -s "$API_BASE/documents/$DOC_ID/accuracy" | python3 -m json.tool 2>/dev/null || echo "Endpoint not available yet"

echo -e "\n✅ Test complete!"
