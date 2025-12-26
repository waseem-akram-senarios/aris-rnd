# How to Query Images from the API

## Image Query Endpoint

**Endpoint**: `POST /query/images`

## Request Format

```json
{
  "question": "your search query",
  "source": "optional document name",
  "k": 5
}
```

## Parameters

- **question** (required): Search query text
  - For semantic search: Use descriptive text (e.g., "drawer tools", "part numbers")
  - To get all images: Use empty string `""`
  
- **source** (optional): Document name to filter by
  - Example: `"FL10.11 SPECIFIC8 (1).pdf"`
  - If not provided, searches all documents

- **k** (optional): Number of images to return (default: 5, max: 50)

## Query Types

### 1. Get All Images from a Document

To retrieve all images from a specific document, use an empty question and specify the source:

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "",
    "source": "FL10.11 SPECIFIC8 (1).pdf",
    "k": 20
  }'
```

**Response**:
```json
{
  "images": [
    {
      "image_id": "fde7e9f4-0182-4310-bb40-a5c14685ea07",
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "image_number": 0,
      "page": 1,
      "ocr_text": "Week: ____________\n|       | Monday   | Tuesday   | Wednesday   | Thursday   | Friday   | Saturday   | Sunday   |...",
      "metadata": {},
      "score": null
    },
    // ... more images
  ],
  "total": 13
}
```

### 2. Semantic Search in Images

To search for images by content (using OCR text):

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "drawer tools part numbers",
    "k": 10
  }'
```

**Response**: Returns images whose OCR text matches the query semantically.

### 3. Search Specific Document's Images

Combine semantic search with source filter:

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "tool reorder sheet",
    "source": "FL10.11 SPECIFIC8 (1).pdf",
    "k": 5
  }'
```

## Python Examples

### Example 1: Get All Images from a Document

```python
import requests

API_BASE_URL = "http://44.221.84.58:8500"

response = requests.post(
    f"{API_BASE_URL}/query/images",
    json={
        "question": "",
        "source": "FL10.11 SPECIFIC8 (1).pdf",
        "k": 20
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total']} images")
    
    for img in data['images']:
        print(f"\nImage {img['image_number']}:")
        print(f"  ID: {img['image_id']}")
        print(f"  Page: {img['page']}")
        print(f"  OCR Text (first 200 chars): {img['ocr_text'][:200]}...")
```

### Example 2: Semantic Search

```python
import requests

API_BASE_URL = "http://44.221.84.58:8500"

response = requests.post(
    f"{API_BASE_URL}/query/images",
    json={
        "question": "drawer 1 tools",
        "k": 10
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total']} matching images")
    
    for img in data['images']:
        print(f"\nImage from {img['source']}:")
        print(f"  Page: {img['page']}")
        print(f"  OCR: {img['ocr_text'][:300]}...")
```

### Example 3: Search for Specific Tools or Part Numbers

```python
import requests

API_BASE_URL = "http://44.221.84.58:8500"

# Search for specific tool
response = requests.post(
    f"{API_BASE_URL}/query/images",
    json={
        "question": "wire stripper socket wrench",
        "k": 5
    }
)

if response.status_code == 200:
    data = response.json()
    for img in data['images']:
        # Check if OCR text contains the tool
        if 'wire stripper' in img['ocr_text'].lower():
            print(f"Found in {img['source']}, page {img['page']}")
            print(f"OCR: {img['ocr_text'][:500]}")
```

## Response Fields

Each image in the response contains:

- **image_id**: Unique identifier for the image
- **source**: Document name where image appears
- **image_number**: Sequential image number
- **page**: Page number where image appears
- **ocr_text**: Full OCR text extracted from the image
- **metadata**: Additional metadata (drawer refs, part numbers, etc.)
- **score**: Similarity score (for semantic search)

## Common Use Cases

### 1. Find Tools in Drawers

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "drawer 1 tools",
    "k": 10
  }'
```

### 2. Find Part Numbers

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "part number 65300077",
    "k": 5
  }'
```

### 3. Find Tool Reorder Sheets

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "tool reorder sheet",
    "k": 5
  }'
```

### 4. Get All Images from a Document

```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "",
    "source": "FL10.11 SPECIFIC8 (1).pdf",
    "k": 50
  }'
```

## Integration with Regular Query

You can also query images through the regular query endpoint (`POST /query`). The query endpoint will:
1. Search document chunks (including image OCR text)
2. Return citations with `image_ref` and `image_info` when from images
3. Include image content in the answer

Example:
```bash
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What tools are in drawer 1?",
    "k": 10
  }'
```

This will return:
- Answer using image content
- Citations with `image_ref` and `image_info` fields
- OCR text from images in citation `full_text` field

## Tips

1. **Empty question + source**: Gets all images from a document
2. **Semantic search**: Finds images by meaning, not just exact text match
3. **Source filter**: Limits search to specific document
4. **Higher k value**: Returns more results (up to 50)

## Status

✅ **Image query endpoint is fully functional!**

- Get all images from documents
- Semantic search in image OCR text
- Filter by document source
- Access full OCR text and metadata



