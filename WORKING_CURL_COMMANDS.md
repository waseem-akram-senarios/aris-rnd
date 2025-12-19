# Working cURL Commands (Currently Available Endpoints)

## ✅ Currently Working Endpoints

### 1. Health Check
```bash
curl -s http://44.221.84.58:8500/health | python3 -m json.tool
```

### 2. List Documents
```bash
curl -s http://44.221.84.58:8500/documents | python3 -m json.tool
```

### 3. Get All Images for Document
```bash
# Get document ID first
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')")

# Get all images
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/images/all" | python3 -m json.tool
```

### 4. Get Page Information
```bash
# Get page 1 information (text + images)
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" | python3 -m json.tool
```

### 5. Query Text Only
```bash
curl -X POST \
  "http://44.221.84.58:8500/query/text" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is in this document?", "k": 5}' \
  | python3 -m json.tool
```

### 6. Query Images Only
```bash
curl -X POST \
  "http://44.221.84.58:8500/query/images" \
  -H "Content-Type: application/json" \
  -d '{"question": "tools and equipment", "k": 5}' \
  | python3 -m json.tool
```

## ⚠️ Endpoints Needing Deployment

These endpoints are implemented but need to be deployed:

### 1. Accuracy Check (Not Deployed Yet)
```bash
# This will return "Not Found" until deployed
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

### 2. Verification (Not Deployed Yet)
```bash
# This will return "Not Found" until deployed
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_file.pdf" \
  -F "auto_fix=false" \
  | python3 -m json.tool
```

## Quick Test of Available Endpoints

```bash
#!/bin/bash
API_BASE="http://44.221.84.58:8500"

echo "Testing Available Endpoints..."
echo

# 1. Health
echo "1. Health Check:"
curl -s "$API_BASE/health" | python3 -m json.tool
echo

# 2. Documents
echo "2. Documents List:"
DOC_ID=$(curl -s "$API_BASE/documents" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')")
echo "Document ID: $DOC_ID"
echo

# 3. Images
if [ ! -z "$DOC_ID" ]; then
    echo "3. All Images:"
    curl -s "$API_BASE/documents/$DOC_ID/images/all" | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"Total images: {d.get('total', 0)}\")"
    echo
    
    echo "4. Page 1 Information:"
    curl -s "$API_BASE/documents/$DOC_ID/pages/1" | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"Text chunks: {d.get('total_text_chunks', 0)}, Images: {d.get('total_images', 0)}\")"
fi
```

## After Deployment

Once you deploy the new endpoints, these will work:

```bash
# Accuracy check
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool

# Verification
curl -X POST "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_file.pdf" -F "auto_fix=false" | python3 -m json.tool
```
