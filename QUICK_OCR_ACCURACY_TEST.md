# Quick OCR Accuracy Test - Ready to Use Commands

## Quick Start

### 1. Get Document ID

```bash
# Get first document ID
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('documents'):
    print(data['documents'][0]['document_id'])
")

echo "Document ID: $DOC_ID"
```

### 2. Quick Accuracy Check (No PDF needed)

```bash
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

**Output shows:**
- Overall accuracy percentage
- Status (accurate/needs_review/inaccurate)
- Whether verification is needed

### 3. Full Verification with Side-by-Side Comparison (Requires PDF)

```bash
# Set your PDF file path
PDF_FILE="FL10.11 SPECIFIC8 (1).pdf"

# Run verification
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@$PDF_FILE" \
  -F "auto_fix=false" \
  -o verification_report.json

# View results
python3 -m json.tool verification_report.json | head -200
```

### 4. View Accuracy Summary

```bash
python3 -c "
import json
with open('verification_report.json') as f:
    data = json.load(f)
    
print('='*80)
print('OCR ACCURACY SUMMARY')
print('='*80)
print(f\"Overall Accuracy: {data.get('overall_accuracy', 0):.2%}\")
print(f\"Total Images: {len(data.get('image_verifications', []))}\")

# Count status
images = data.get('image_verifications', [])
accurate = sum(1 for img in images if img.get('status') == 'accurate')
needs_review = sum(1 for img in images if img.get('status') == 'needs_review')
inaccurate = sum(1 for img in images if img.get('status') == 'inaccurate')

print(f\"\\nImage Status:\")
print(f\"  ✅ Accurate: {accurate}\")
print(f\"  ⚠️  Needs Review: {needs_review}\")
print(f\"  ❌ Inaccurate: {inaccurate}\")

print(f\"\\nIssues Found: {len(data.get('issues_found', []))}\")
print(f\"Recommendations: {len(data.get('recommendations', []))}\")
"
```

### 5. View Side-by-Side Comparison for Specific Image

```bash
python3 -c "
import json
with open('verification_report.json') as f:
    data = json.load(f)

# Get first image verification
img = data.get('image_verifications', [{}])[0]

print('='*80)
print('SIDE-BY-SIDE COMPARISON - Image 1')
print('='*80)
print(f\"Page: {img.get('page_number')}, Index: {img.get('image_index')}\")
print(f\"Accuracy: {img.get('ocr_accuracy', 0):.2%}\")
print(f\"Status: {img.get('status')}\")
print(f\"\\nStored OCR Length: {img.get('stored_ocr_length', 0):,} chars\")
print(f\"Verified OCR Length: {img.get('verified_ocr_length', 0):,} chars\")

missing = img.get('missing_content', [])
if missing:
    print(f\"\\n⚠️  Missing Content ({len(missing)} items):\")
    for item in missing[:5]:
        print(f\"  - {item[:100]}\")

extra = img.get('extra_content', [])
if extra:
    print(f\"\\n➕ Extra Content ({len(extra)} items):\")
    for item in extra[:5]:
        print(f\"  - {item[:100]}\")
"
```

## Complete Test Workflow

```bash
#!/bin/bash

# Step 1: Get document ID
echo "Getting document ID..."
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('documents'):
    print(data['documents'][0]['document_id'])
else:
    print('')
")

if [ -z "$DOC_ID" ]; then
    echo "❌ No documents found"
    exit 1
fi

echo "✅ Document ID: $DOC_ID"

# Step 2: Quick accuracy check
echo -e "\n📊 Quick Accuracy Check:"
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool

# Step 3: Full verification (if PDF available)
PDF_FILE="FL10.11 SPECIFIC8 (1).pdf"
if [ -f "$PDF_FILE" ]; then
    echo -e "\n🔍 Running Full Verification..."
    curl -X POST \
      "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
      -F "file=@$PDF_FILE" \
      -F "auto_fix=false" \
      -o verification_report.json
    
    echo -e "\n✅ Verification complete! Report saved to verification_report.json"
    
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
```

## Understanding Results

### Accuracy Scores
- **≥ 90%**: ✅ Excellent - OCR is very accurate
- **85-90%**: ⚠️ Good - Acceptable but could improve
- **< 85%**: ❌ Needs Attention - Should be reviewed/fixed

### What the Comparison Shows
1. **Stored OCR**: What your API has in OpenSearch
2. **Verified OCR**: What's extracted directly from PDF (ground truth)
3. **Accuracy**: How well they match
4. **Missing Content**: Words in PDF but not in stored OCR
5. **Extra Content**: Words in stored OCR but not in PDF

## Tips

- Run quick accuracy check first (fast, no PDF needed)
- Use full verification for detailed analysis (requires PDF)
- Check `issues_found` for specific problems
- Review `recommendations` for improvement suggestions
- Use `auto_fix=true` to automatically fix low accuracy issues
