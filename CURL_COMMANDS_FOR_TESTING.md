# cURL Commands for Testing OCR Verification Endpoints

## Quick Start

### Step 1: Get Document ID

```bash
# Get first document ID
curl -s http://44.221.84.58:8500/documents | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('documents'):
    print(data['documents'][0]['document_id'])
"
```

**Or save to variable:**
```bash
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('documents'):
    print(data['documents'][0]['document_id'])
")

echo "Document ID: $DOC_ID"
```

### Step 2: Test Accuracy Endpoint

```bash
# Quick accuracy check (no PDF needed)
curl -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" \
  -H "Accept: application/json"
```

**Pretty print:**
```bash
curl -s -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" \
  -H "Accept: application/json" | python3 -m json.tool
```

### Step 3: Test Verification Endpoint

```bash
# Full verification (requires PDF file)
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_document.pdf" \
  -F "auto_fix=false" \
  -H "Accept: application/json"
```

**Save to file:**
```bash
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_document.pdf" \
  -F "auto_fix=false" \
  -o verification_report.json
```

## Complete Test Workflow

### One-Line Commands

```bash
# 1. Get document ID and test accuracy
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')") && \
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

```bash
# 2. Full verification with PDF
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')") && \
curl -X POST "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@FL10.11 SPECIFIC8 (1).pdf" \
  -F "auto_fix=false" | python3 -m json.tool
```

## Detailed Commands

### Test 1: Health Check

```bash
curl -X GET \
  "http://44.221.84.58:8500/health" \
  -H "Accept: application/json"
```

### Test 2: List Documents

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | python3 -m json.tool
```

### Test 3: Get Document Details

```bash
# Replace DOC_ID with actual document ID
DOC_ID="your-document-id-here"

curl -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID" \
  -H "Accept: application/json" | python3 -m json.tool
```

### Test 4: Quick Accuracy Check

```bash
DOC_ID="your-document-id-here"

curl -s -X GET \
  "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" \
  -H "Accept: application/json" | python3 -m json.tool
```

**Expected Response:**
```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "overall_accuracy": 0.95,
  "ocr_accuracy": 0.94,
  "status": "accurate",
  "verification_needed": false,
  "last_verification": "2024-12-19T17:00:00Z"
}
```

### Test 5: Full Verification (Side-by-Side Comparison)

```bash
DOC_ID="your-document-id-here"
PDF_FILE="FL10.11 SPECIFIC8 (1).pdf"

curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@$PDF_FILE" \
  -F "auto_fix=false" \
  -H "Accept: application/json" \
  -o verification_report.json

# View results
python3 -m json.tool verification_report.json | head -100
```

**With Auto-Fix Enabled:**
```bash
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@$PDF_FILE" \
  -F "auto_fix=true" \
  -H "Accept: application/json" | python3 -m json.tool
```

## View Verification Results

### Get Summary

```bash
python3 -c "
import json
with open('verification_report.json') as f:
    data = json.load(f)
print('Overall Accuracy:', f\"{data.get('overall_accuracy', 0):.2%}\")
print('Images Verified:', len(data.get('image_verifications', [])))
print('Issues Found:', len(data.get('issues_found', [])))
"
```

### Get Image-by-Image Accuracy

```bash
python3 -c "
import json
with open('verification_report.json') as f:
    data = json.load(f)
for img in data.get('image_verifications', [])[:10]:
    print(f\"Image {img.get('image_index')} (Page {img.get('page_number')}): {img.get('ocr_accuracy', 0):.2%} - {img.get('status')}\")
"
```

## Complete Test Script

```bash
#!/bin/bash

API_BASE="http://44.221.84.58:8500"

echo "=" | head -c 80 && echo
echo "OCR VERIFICATION ENDPOINT TEST"
echo "=" | head -c 80 && echo

# Step 1: Health check
echo -e "\n1. Testing Health..."
curl -s "$API_BASE/health" | python3 -m json.tool

# Step 2: Get document ID
echo -e "\n2. Getting Document ID..."
DOC_ID=$(curl -s "$API_BASE/documents" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('documents'):
        print(data['documents'][0]['document_id'])
except:
    print('')
")

if [ -z "$DOC_ID" ]; then
    echo "❌ No documents found"
    exit 1
fi

echo "✅ Document ID: $DOC_ID"

# Step 3: Quick accuracy check
echo -e "\n3. Quick Accuracy Check..."
curl -s "$API_BASE/documents/$DOC_ID/accuracy" | python3 -m json.tool

# Step 4: Full verification (if PDF available)
PDF_FILE="FL10.11 SPECIFIC8 (1).pdf"
if [ -f "$PDF_FILE" ]; then
    echo -e "\n4. Full Verification (this may take a few minutes)..."
    curl -X POST \
      "$API_BASE/documents/$DOC_ID/verify" \
      -F "file=@$PDF_FILE" \
      -F "auto_fix=false" \
      -o verification_report.json
    
    echo -e "\n✅ Verification complete! Results saved to verification_report.json"
    
    # Show summary
    python3 -c "
import json
with open('verification_report.json') as f:
    data = json.load(f)
print(f\"\\n📊 Overall Accuracy: {data.get('overall_accuracy', 0):.2%}\")
print(f\"🖼️  Images Verified: {len(data.get('image_verifications', []))}\")
print(f\"⚠️  Issues: {len(data.get('issues_found', []))}\")
"
else
    echo -e "\n⚠️  PDF file not found: $PDF_FILE"
    echo "   Skipping full verification"
fi

echo -e "\n✅ Test complete!"
```

## Quick Reference

### Most Common Commands

```bash
# Get document ID
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;print(json.load(sys.stdin)['documents'][0]['document_id'] if json.load(sys.stdin).get('documents') else '')")

# Quick accuracy check
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool

# Full verification
curl -X POST "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_file.pdf" -F "auto_fix=false" | python3 -m json.tool
```

## Error Handling

### Check if Endpoint Exists

```bash
# Test if endpoint is available
curl -s -o /dev/null -w "%{http_code}" \
  "http://44.221.84.58:8500/documents/$DOC_ID/accuracy"

# 200 = Available
# 404 = Not found (needs deployment)
# 500 = Server error
```

### Handle Timeouts

```bash
# Increase timeout for verification (can take 5-10 minutes)
curl --max-time 600 -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_file.pdf" \
  -F "auto_fix=false"
```

## Examples with Real Data

### Example 1: Check Accuracy of Existing Document

```bash
# Get document
DOC_ID="2bac8df5-931a-4d5a-9074-c8eaa7d6247e"

# Check accuracy
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

### Example 2: Verify Document with PDF

```bash
DOC_ID="2bac8df5-931a-4d5a-9074-c8eaa7d6247e"
PDF="FL10.11 SPECIFIC8 (1).pdf"

curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@$PDF" \
  -F "auto_fix=false" \
  -o report.json && \
python3 -m json.tool report.json | head -50
```

## Tips

1. **Use `-s` flag** to silence progress output
2. **Use `python3 -m json.tool`** to pretty-print JSON
3. **Save to file** with `-o filename.json` for large responses
4. **Increase timeout** with `--max-time 600` for verification
5. **Check status code** with `-w "%{http_code}"` to verify endpoint availability
