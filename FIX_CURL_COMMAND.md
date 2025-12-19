# Fix: "Document {document_id} not found" Error

## Problem

You used the literal string `{document_id}` instead of replacing it with an actual document ID.

**Wrong:**
```bash
curl -X GET "http://44.221.84.58:8500/documents/{document_id}/pages/1"
```

## Solution

### Step 1: Get Your Document ID

```bash
curl -X GET "http://44.221.84.58:8500/documents" -H "Accept: application/json"
```

This will return a list of documents. Find the `document_id` field.

### Step 2: Use the Real Document ID

Replace `{document_id}` with your actual document ID:

```bash
curl -X GET "http://44.221.84.58:8500/documents/YOUR_ACTUAL_DOC_ID/pages/1" \
  -H "Accept: application/json"
```

## Quick Script

Run this to automatically get a document ID and test:

```bash
# Get document ID and test
DOC_ID=$(curl -s -X GET "http://44.221.84.58:8500/documents" -H "Accept: application/json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['documents'][0].get('document_id') or d['documents'][0].get('document_name', ''))")

echo "Using Document ID: $DOC_ID"

# Get images from page 1
curl -X GET "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json" | jq '.images[] | {image_number, page, ocr_text}'
```

## Example Response Structure

When you get documents, you'll see:

```json
{
  "documents": [
    {
      "document_id": "b0b01b35-ccbb-4e52-9db6-2690e531289b",
      "document_name": "your-file.pdf"
    }
  ]
}
```

Use the `document_id` value (e.g., `b0b01b35-ccbb-4e52-9db6-2690e531289b`) in your curl command.

## Complete Working Example

```bash
# Step 1: Get document ID
DOC_ID=$(curl -s -X GET "http://44.221.84.58:8500/documents" \
  -H "Accept: application/json" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['documents'][0].get('document_id') or d['documents'][0].get('document_name', ''))")

# Step 2: Get images from page 1
curl -X GET "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" \
  -H "Accept: application/json"
```

## Alternative: Use the Script

I've created a script that does this automatically:

```bash
./get_images_by_page.sh 1
```

This will:
1. Automatically get the document ID
2. Get images from page 1
3. Display the OCR content
