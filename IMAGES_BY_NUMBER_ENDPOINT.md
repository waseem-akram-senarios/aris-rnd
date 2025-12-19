# Images by Number Endpoints

## Overview

Two new endpoints to easily find how many images are in a document and get the OCR text content for each image by its number.

## Endpoints

### 1. Get All Images Summary

**GET** `/documents/{document_id}/images`

Returns a summary of all images with their numbers and OCR text.

#### Request

```http
GET http://44.221.84.58:8500/documents/{document_id}/images
```

#### Response

```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "total_images": 99,
  "images": [
    {
      "image_number": 0,
      "page": 1,
      "ocr_text": "Complete OCR text from image 0...",
      "ocr_text_length": 1234,
      "image_id": "uuid-here"
    },
    {
      "image_number": 1,
      "page": 2,
      "ocr_text": "Complete OCR text from image 1...",
      "ocr_text_length": 567,
      "image_id": "uuid-here"
    }
  ]
}
```

#### Response Fields

- **document_id**: Document identifier
- **document_name**: Name of the document
- **total_images**: Total number of images in the document
- **images**: List of images, sorted by image_number
  - **image_number**: Image number (0-indexed)
  - **page**: Page number where image appears
  - **ocr_text**: Complete OCR text extracted from the image
  - **ocr_text_length**: Length of OCR text in characters
  - **image_id**: Unique image identifier

---

### 2. Get Specific Image by Number

**GET** `/documents/{document_id}/images/{image_number}`

Returns the OCR text and details for a specific image by its number.

#### Request

```http
GET http://44.221.84.58:8500/documents/{document_id}/images/{image_number}
```

#### Parameters

- **document_id** (path): Document ID
- **image_number** (path): Image number (0-indexed, e.g., 0, 1, 2, ...)

#### Response

```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "image_number": 0,
  "page": 1,
  "ocr_text": "Complete OCR text from this specific image...",
  "ocr_text_length": 1234,
  "image_id": "uuid-here",
  "metadata": {
    "extraction_method": "docling_ocr",
    "drawer_references": ["1", "2"],
    "part_numbers": ["12345"],
    "tools_found": ["wrench"]
  }
}
```

#### Response Fields

- **document_id**: Document identifier
- **document_name**: Name of the document
- **image_number**: The requested image number
- **page**: Page number where image appears
- **ocr_text**: Complete OCR text extracted from the image
- **ocr_text_length**: Length of OCR text in characters
- **image_id**: Unique image identifier
- **metadata**: Additional metadata (extraction method, detected content, etc.)

#### Error Responses

- **404 Not Found**: If document or image number doesn't exist
  ```json
  {
    "detail": "Image number 5 not found in document abc-123"
  }
  ```

---

## Usage Examples

### Python

```python
import requests

API_BASE = "http://44.221.84.58:8500"
doc_id = "your-document-id"

# Get all images summary
response = requests.get(f"{API_BASE}/documents/{doc_id}/images")
data = response.json()

print(f"Total Images: {data['total_images']}")
for img in data['images']:
    print(f"Image {img['image_number']}: {img['ocr_text_length']} chars")
    print(f"OCR: {img['ocr_text'][:100]}...")

# Get specific image by number
image_number = 0
response = requests.get(f"{API_BASE}/documents/{doc_id}/images/{image_number}")
img_data = response.json()

print(f"Image {img_data['image_number']} on page {img_data['page']}")
print(f"OCR Text: {img_data['ocr_text']}")
```

### cURL

```bash
# Get all images summary
curl -X GET \
  "http://44.221.84.58:8500/documents/abc-123/images" \
  -H "Accept: application/json"

# Get specific image by number
curl -X GET \
  "http://44.221.84.58:8500/documents/abc-123/images/0" \
  -H "Accept: application/json"
```

### JavaScript

```javascript
const API_BASE = 'http://44.221.84.58:8500';
const docId = 'your-document-id';

// Get all images summary
const response = await fetch(`${API_BASE}/documents/${docId}/images`);
const data = await response.json();

console.log(`Total Images: ${data.total_images}`);
data.images.forEach(img => {
  console.log(`Image ${img.image_number}: ${img.ocr_text_length} chars`);
});

// Get specific image
const imageNumber = 0;
const imgResponse = await fetch(
  `${API_BASE}/documents/${docId}/images/${imageNumber}`
);
const imgData = await imgResponse.json();
console.log(`OCR: ${imgData.ocr_text}`);
```

---

## Postman Collection

Add these requests to your Postman collection:

### Request 1: Get All Images Summary

```
GET http://44.221.84.58:8500/documents/{{document_id}}/images
```

### Request 2: Get Image by Number

```
GET http://44.221.84.58:8500/documents/{{document_id}}/images/{{image_number}}
```

Variables:
- `document_id`: Your document ID
- `image_number`: Image number (0, 1, 2, ...)

---

## Use Cases

1. **Count Images**: Use `/images` endpoint to get total count
2. **List All OCR**: Get all OCR text from all images
3. **Get Specific Image**: Use `/images/{number}` to get OCR for a specific image
4. **Iterate by Number**: Loop through image numbers to process each image
5. **Quality Check**: Check OCR text length to identify images with content

---

## Notes

- Image numbers are **0-indexed** (start from 0)
- Images are sorted by image_number in the response
- If an image number doesn't exist, you'll get a 404 error
- OCR text is the complete extracted text from the image
- The `/images` endpoint returns up to 1000 images (use `/images/all` for more details)
