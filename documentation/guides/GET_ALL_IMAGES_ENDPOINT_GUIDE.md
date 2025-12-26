# Get All Images Information Endpoint

## New Endpoint

**GET `/documents/{document_id}/images/all`**

Returns **ALL** image information from a document stored in OpenSearch, including complete OCR text, metadata, and extraction details.

## Purpose

This endpoint provides comprehensive access to all image OCR data stored in OpenSearch, allowing you to:
- Get complete OCR text from all images
- Access full metadata for each image
- View extraction details (method, timestamp)
- Analyze OCR content across all images
- Export all image information

## Request

```http
GET /documents/{document_id}/images/all?limit=1000
```

### Parameters

- **document_id** (path): Document ID
- **limit** (query, optional): Maximum number of images to return (default: 1000, max: 1000)

## Response

```json
{
  "document_id": "abc-123-def",
  "document_name": "FL10.11 SPECIFIC8 (1).pdf",
  "images": [
    {
      "image_id": "9a2f3953-c8aa-4001-be53-ad1ba49dfb8f",
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "image_number": 0,
      "page": 26,
      "ocr_text": "Complete OCR text from image...",
      "ocr_text_length": 3917,
      "metadata": {
        "drawer_references": ["1", "2"],
        "part_numbers": ["65300128", "65300134"],
        "tools_found": ["wrench", "socket"],
        "has_structured_content": true
      },
      "extraction_method": "docling_ocr",
      "extraction_timestamp": "2025-12-19T11:00:00Z",
      "marker_detected": true,
      "full_chunk": "Context around image...",
      "context_before": "Text before image...",
      "score": null
    },
    ...
  ],
  "total": 99,
  "images_index": "aris-rag-images-index",
  "total_ocr_text_length": 250650,
  "average_ocr_length": 2532.0,
  "images_with_ocr": 99
}
```

## Response Fields

### Summary Fields
- **document_id**: Document ID
- **document_name**: Document name
- **total**: Total number of images
- **images_index**: OpenSearch index name
- **total_ocr_text_length**: Total OCR characters across all images
- **average_ocr_length**: Average OCR characters per image
- **images_with_ocr**: Number of images that have OCR text

### Image Fields (per image)
- **image_id**: Unique image ID
- **source**: Document source name
- **image_number**: Image number within document
- **page**: Page number where image appears
- **ocr_text**: Complete OCR text extracted from image
- **ocr_text_length**: Length of OCR text in characters
- **metadata**: Full metadata dictionary including:
  - `drawer_references`: List of drawer numbers found
  - `part_numbers`: List of part numbers found
  - `tools_found`: List of tools mentioned
  - `has_structured_content`: Boolean indicating structured content
- **extraction_method**: Method used to extract OCR (e.g., "docling_ocr")
- **extraction_timestamp**: When OCR was extracted
- **marker_detected**: Whether image marker was detected in document
- **full_chunk**: Full chunk text containing the image
- **context_before**: Text context before the image
- **score**: Relevance score (null for this endpoint)

## Usage Examples

### Get All Images (Python)

```python
import requests

doc_id = "your-document-id"
response = requests.get(
    f"http://44.221.84.58:8500/documents/{doc_id}/images/all?limit=1000",
    timeout=60
)

if response.status_code == 200:
    data = response.json()
    print(f"Total Images: {data['total']}")
    print(f"Total OCR Text: {data['total_ocr_text_length']:,} characters")
    
    for img in data['images']:
        print(f"Image {img['image_number']}: {img['ocr_text_length']:,} OCR chars")
        print(f"OCR: {img['ocr_text'][:200]}...")
```

### Get All Images (cURL)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/images/all?limit=100" \
  -H "Accept: application/json"
```

### Get All Images (JavaScript)

```javascript
const docId = 'your-document-id';
const response = await fetch(
  `http://44.221.84.58:8500/documents/${docId}/images/all?limit=1000`
);
const data = await response.json();

console.log(`Total Images: ${data.total}`);
console.log(`Total OCR: ${data.total_ocr_text_length} characters`);

data.images.forEach(img => {
  console.log(`Image ${img.image_number}: ${img.ocr_text_length} chars`);
  console.log(`OCR: ${img.ocr_text.substring(0, 200)}...`);
});
```

## Use Cases

1. **Export All OCR Data**: Get all OCR text for analysis or export
2. **Bulk Analysis**: Analyze OCR content across all images
3. **Data Extraction**: Extract specific information from all images
4. **Quality Check**: Verify OCR quality across all images
5. **Metadata Analysis**: Analyze metadata patterns across images

## Comparison with Other Endpoints

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /documents/{id}/images/all` | Get ALL image information | Complete details for all images |
| `POST /query/images` | Search images semantically | Top K matching images |
| `GET /documents/{id}/storage/status` | Check storage status | Summary statistics only |

## Test Results

✅ **Endpoint Working**: Successfully retrieves all image information
✅ **OCR Content**: Complete OCR text included
✅ **Metadata**: Full metadata available
✅ **Performance**: Fast retrieval from OpenSearch

### Example Output

```
Total Images: 99
Total OCR Text: 250,650 characters
Average OCR Length: 2,532 characters
Images with OCR: 99/99

✅ All images have complete OCR text and metadata!
```

## Notes

- Images are sorted by `image_number`
- OCR text is the complete extracted text (no truncation)
- Metadata includes extracted information (drawers, parts, tools)
- All fields are optional and may be null if not available
- Maximum limit is 1000 images per request
