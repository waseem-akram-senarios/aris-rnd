# Images by Number Endpoints - Summary

## ✅ Endpoints Created

I've created **2 new endpoints** to find images and their OCR text by image number:

### 1. Get All Images Summary
**Endpoint:** `GET /documents/{document_id}/images`

**What it does:**
- Returns total count of images in the document
- Lists all images with their numbers and OCR text
- Sorted by image number

**Example Response:**
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
      "image_id": "uuid"
    },
    {
      "image_number": 1,
      "page": 2,
      "ocr_text": "Complete OCR text from image 1...",
      "ocr_text_length": 567,
      "image_id": "uuid"
    }
  ]
}
```

---

### 2. Get Specific Image by Number
**Endpoint:** `GET /documents/{document_id}/images/{image_number}`

**What it does:**
- Returns OCR text for a specific image number
- Includes page number and metadata
- Use this to get text from image 0, 1, 2, etc.

**Example Request:**
```
GET /documents/abc-123/images/0
```

**Example Response:**
```json
{
  "document_id": "abc-123",
  "document_name": "document.pdf",
  "image_number": 0,
  "page": 1,
  "ocr_text": "Complete OCR text from this specific image...",
  "ocr_text_length": 1234,
  "image_id": "uuid",
  "metadata": {
    "extraction_method": "docling_ocr",
    "drawer_references": ["1", "2"]
  }
}
```

---

## 📋 Quick Usage

### Find Total Images
```bash
curl http://44.221.84.58:8500/documents/{doc_id}/images
```
Look for `"total_images"` in the response.

### Get OCR Text for Image Number 0
```bash
curl http://44.221.84.58:8500/documents/{doc_id}/images/0
```
Look for `"ocr_text"` in the response.

### Get OCR Text for Image Number 5
```bash
curl http://44.221.84.58:8500/documents/{doc_id}/images/5
```

---

## 🚀 Deployment Required

The endpoints are created but need to be deployed to the server:

```bash
./scripts/deploy-api-updates.sh
```

After deployment, wait 10-15 seconds, then test the endpoints.

---

## 📝 Postman Collection

Add these requests to your Postman collection:

1. **Get All Images:**
   ```
   GET http://44.221.84.58:8500/documents/{{document_id}}/images
   ```

2. **Get Image by Number:**
   ```
   GET http://44.221.84.58:8500/documents/{{document_id}}/images/{{image_number}}
   ```

Set variables:
- `document_id`: Your document ID
- `image_number`: 0, 1, 2, etc.

---

## 📚 Files Created

1. **API Endpoints:** `api/main.py` (2 new endpoints added)
2. **Schemas:** `api/schemas.py` (3 new response models)
3. **Documentation:** 
   - `IMAGES_BY_NUMBER_ENDPOINT.md` (full guide)
   - `QUICK_REFERENCE_IMAGES_BY_NUMBER.md` (quick reference)
4. **Test Script:** `test_images_by_number.py`

---

## ✅ What You Can Do

1. **Count Images:** Use `/images` to see total count
2. **List All OCR:** Get all OCR text from all images
3. **Get Specific Image:** Use `/images/{number}` for image 0, 1, 2, etc.
4. **Iterate:** Loop through image numbers to process each one
5. **Quality Check:** Check OCR text length to see which images have content

---

## Notes

- Image numbers are **0-indexed** (start from 0, not 1)
- Images are automatically sorted by number
- If image number doesn't exist, you'll get 404 error
- OCR text is the complete extracted text from the image
