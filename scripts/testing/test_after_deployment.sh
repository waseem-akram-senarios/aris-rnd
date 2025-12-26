#!/bin/bash
# Test endpoints after deployment

API_BASE="http://44.221.84.58:8500"

echo "=================================================================================="
echo "TESTING ENDPOINTS AFTER DEPLOYMENT"
echo "=================================================================================="
echo

# Get document ID
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
echo "📊 Testing Accuracy Endpoint..."
ACC_RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE/documents/$DOC_ID/accuracy" 2>/dev/null)
HTTP_CODE=$(echo "$ACC_RESPONSE" | tail -1)
BODY=$(echo "$ACC_RESPONSE" | head -n -1)

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Accuracy endpoint is working!"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
elif [ "$HTTP_CODE" = "404" ]; then
    echo "❌ Accuracy endpoint not found (404) - needs deployment"
else
    echo "⚠️  Status code: $HTTP_CODE"
    echo "$BODY"
fi

echo
echo "=================================================================================="
