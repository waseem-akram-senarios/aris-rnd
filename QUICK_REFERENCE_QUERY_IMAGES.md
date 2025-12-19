# Quick Reference: How to Query Images

## Endpoint
```
POST http://44.221.84.58:8500/query/images
```

## Quick Examples

### 1. Get All Images from a Document
```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "",
    "source": "FL10.11 SPECIFIC8 (1).pdf",
    "k": 20
  }'
```

### 2. Search Images by Content
```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "drawer tools",
    "k": 10
  }'
```

### 3. Search Specific Document's Images
```bash
curl -X POST http://44.221.84.58:8500/query/images \
  -H "Content-Type: application/json" \
  -d '{
    "question": "tool reorder",
    "source": "FL10.11 SPECIFIC8 (1).pdf",
    "k": 5
  }'
```

## Python Quick Example

```python
import requests

# Get all images
response = requests.post(
    "http://44.221.84.58:8500/query/images",
    json={
        "question": "",
        "source": "FL10.11 SPECIFIC8 (1).pdf",
        "k": 20
    }
)

data = response.json()
for img in data['images']:
    print(f"Image {img['image_number']}: {img['ocr_text'][:200]}")
```

## Response Format

```json
{
  "images": [
    {
      "image_id": "...",
      "source": "document.pdf",
      "image_number": 0,
      "page": 1,
      "ocr_text": "Full OCR text from image...",
      "metadata": {},
      "score": null
    }
  ],
  "total": 13
}
```

## Key Points

- **Empty question (`""`) + source**: Get all images from document
- **Question + source**: Search specific document's images
- **Question only**: Search all documents' images
- **k parameter**: Number of results (max 50)

## Also Available via Regular Query

You can also query images through the regular query endpoint:

```bash
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What tools are in drawer 1?",
    "k": 10
  }'
```

This returns citations with `image_ref` and `image_info` when from images.



