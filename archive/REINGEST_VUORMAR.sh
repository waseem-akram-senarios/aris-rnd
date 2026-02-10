#!/bin/bash
# Quick script to re-ingest VUORMAR.pdf

echo "Re-ingesting VUORMAR.pdf with latest page metadata fixes..."

# Check if file exists
if [ ! -f "VUORMAR.pdf" ]; then
    echo "❌ Error: VUORMAR.pdf not found in current directory"
    echo "Please run this script from the directory containing VUORMAR.pdf"
    exit 1
fi

# Re-upload to Gateway
echo "Uploading to Gateway..."
RESPONSE=$(curl -sS -X POST http://44.221.84.58:8500/documents \
  -F "file=@VUORMAR.pdf" \
  -F "parser_preference=ocrmypdf")

echo "$RESPONSE" | python3 -m json.tool

# Extract document_id
DOC_ID=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('document_id', 'unknown'))")

echo ""
echo "✅ Upload submitted. Document ID: $DOC_ID"
echo ""
echo "Waiting for processing to complete (30 seconds)..."
sleep 30

# Check status
echo "Checking processing status..."
STATUS=$(curl -sS -X GET "http://44.221.84.58:8501/status/$DOC_ID")
echo "$STATUS" | python3 -m json.tool

echo ""
echo "Testing query with new document..."
sleep 5

# Test query
curl -sS -X POST http://44.221.84.58:8500/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What does the text say about Desbobinador Apagado?",
    "k": 3,
    "active_sources": ["VUORMAR.pdf"]
  }' | python3 -c "
import sys, json
data = json.load(sys.stdin)
citations = data.get('citations', [])
print('\n📎 Citations with page numbers:')
for c in citations:
    page = c.get('page', 'N/A')
    source = c.get('source', 'Unknown')
    snippet = c.get('snippet', '')[:80]
    print(f'  [{c.get(\"id\")}] {source} - Page {page}')
    print(f'      Snippet: {snippet}...')
    print()
"

echo ""
echo "✅ Done! Check if page numbers are now correct (should show Page 10, not Page 1)"
