# Quick Reference: Images by Number Endpoints

## Endpoints

### 1. Get All Images (Summary)
```
GET /documents/{document_id}/images
```

**Returns:**
- Total count of images
- List of all images with their numbers and OCR text

**Example:**
```bash
curl http://44.221.84.58:8500/documents/abc-123/images
```

**Response:**
```json
{
  "document_id": "abc-123",
  "document_name": "file.pdf",
  "total_images": 99,
  "images": [
    {
      "image_number": 0,
      "page": 1,
      "ocr_text": "Text from image 0...",
      "ocr_text_length": 1234
    }
  ]
}
```

---

### 2. Get Specific Image by Number
```
GET /documents/{document_id}/images/{image_number}
```

**Returns:**
- OCR text for the specific image
- Page number
- Metadata

**Example:**
```bash
curl http://44.221.84.58:8500/documents/abc-123/images/0
```

**Response:**
```json
{
  "document_id": "abc-123",
  "document_name": "file.pdf",
  "image_number": 0,
  "page": 1,
  "ocr_text": "Complete OCR text...",
  "ocr_text_length": 1234,
  "image_id": "uuid",
  "metadata": {...}
}
```

---

## Postman

1. **Get All Images:**
   ```
   GET http://44.221.84.58:8500/documents/{{document_id}}/images
   ```

2. **Get Image by Number:**
   ```
   GET http://44.221.84.58:8500/documents/{{document_id}}/images/{{image_number}}
   ```

---

## Notes

- Image numbers start from **0** (0-indexed)
- Use `/images` to get total count
- Use `/images/{number}` to get specific image OCR text
- Images are sorted by number in responses
