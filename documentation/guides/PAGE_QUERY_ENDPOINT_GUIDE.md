# Query Page Information Endpoint

## New Endpoint

**GET `/documents/{document_id}/pages/{page_number}`**

Returns **ALL** information from a specific page of a document, including:
- All text chunks from that page
- All images from that page with complete OCR text
- Full metadata for both text and images

## Purpose

Query by page number to get complete information about that page:
- All text content from the page
- All images with OCR text from the page
- Complete metadata
- Full page content analysis

## Request

```http
GET /documents/{document_id}/pages/{page_number}
```

### Parameters

- **document_id** (path): Document ID
- **page_number** (path): Page number (1-indexed, must be >= 1)

## Response

```json
{
  "document_id": "abc-123-def",
  "document_name": "FL10.11 SPECIFIC8 (1).pdf",
  "page_number": 1,
  "text_chunks": [
    {
      "chunk_index": 0,
      "text": "Complete text from page...",
      "page": 1,
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "token_count": 150,
      "start_char": 0,
      "end_char": 4273
    },
    ...
  ],
  "images": [
    {
      "image_id": "9a2f3953-c8aa-4001-be53-ad1ba49dfb8f",
      "source": "FL10.11 SPECIFIC8 (1).pdf",
      "image_number": 0,
      "page": 1,
      "ocr_text": "Complete OCR text from image...",
      "ocr_text_length": 3917,
      "metadata": {...},
      "extraction_method": "docling_ocr",
      ...
    },
    ...
  ],
  "total_text_chunks": 10,
  "total_images": 65,
  "total_text_length": 39910,
  "total_ocr_text_length": 154345,
  "text_index": "aris-rag-index",
  "images_index": "aris-rag-images-index"
}
```

## Response Fields

### Summary
- **document_id**: Document ID
- **document_name**: Document name
- **page_number**: Page number queried
- **total_text_chunks**: Number of text chunks from page
- **total_images**: Number of images from page
- **total_text_length**: Total text characters from page
- **total_ocr_text_length**: Total OCR characters from images on page
- **text_index**: OpenSearch index for text
- **images_index**: OpenSearch index for images

### Text Chunks (per chunk)
- **chunk_index**: Chunk index number
- **text**: Complete text content
- **page**: Page number
- **source**: Document source
- **token_count**: Number of tokens
- **start_char**: Character start position
- **end_char**: Character end position

### Images (per image)
- **image_id**: Unique image ID
- **image_number**: Image number
- **page**: Page number
- **ocr_text**: Complete OCR text
- **ocr_text_length**: OCR text length
- **metadata**: Full metadata
- **extraction_method**: OCR extraction method
- **extraction_timestamp**: When OCR was extracted
- And more...

## Usage Examples

### Get Page 1 Information (Python)

```python
import requests

doc_id = "your-document-id"
page_num = 1

response = requests.get(
    f"http://44.221.84.58:8500/documents/{doc_id}/pages/{page_num}",
    timeout=60
)

if response.status_code == 200:
    data = response.json()
    print(f"Page {data['page_number']} Information:")
    print(f"  Text Chunks: {data['total_text_chunks']}")
    print(f"  Images: {data['total_images']}")
    print(f"  Total Text: {data['total_text_length']:,} chars")
    print(f"  Total OCR: {data['total_ocr_text_length']:,} chars")
    
    # Access text chunks
    for chunk in data['text_chunks']:
        print(f"Chunk {chunk['chunk_index']}: {chunk['text'][:100]}...")
    
    # Access images
    for img in data['images']:
        print(f"Image {img['image_number']}: {img['ocr_text'][:100]}...")
```

### Get Page 1 Information (cURL)

```bash
curl -X GET \
  "http://44.221.84.58:8500/documents/2bac8df5-931a-4d5a-9074-c8eaa7d6247e/pages/1" \
  -H "Accept: application/json"
```

### Get Page 1 Information (JavaScript)

```javascript
const docId = 'your-document-id';
const pageNum = 1;

const response = await fetch(
  `http://44.221.84.58:8500/documents/${docId}/pages/${pageNum}`
);
const data = await response.json();

console.log(`Page ${data.page_number} Information:`);
console.log(`Text Chunks: ${data.total_text_chunks}`);
console.log(`Images: ${data.total_images}`);
console.log(`Total Content: ${data.total_text_length + data.total_ocr_text_length} chars`);

// Access all text
data.text_chunks.forEach(chunk => {
  console.log(`Chunk ${chunk.chunk_index}: ${chunk.text.substring(0, 100)}...`);
});

// Access all images
data.images.forEach(img => {
  console.log(`Image ${img.image_number}: ${img.ocr_text.substring(0, 100)}...`);
});
```

## Test Results

### Page 1 Test Results

```
✅ SUCCESS! Retrieved all information from page 1

Document: FL10.11 SPECIFIC8 (1).pdf
Page: 1

📄 TEXT CONTENT:
  Text Chunks: 10
  Total Text: 39,910 characters

🖼️  IMAGE CONTENT:
  Images: 65
  Total OCR: 154,345 characters

📊 TOTAL PAGE CONTENT:
  Text: 39,910 chars
  Image OCR: 154,345 chars
  Total: 194,255 characters
```

## Use Cases

1. **Page Analysis**: Get complete information about a specific page
2. **Content Extraction**: Extract all text and images from a page
3. **Page Export**: Export complete page content
4. **Quality Check**: Verify content on a specific page
5. **Document Review**: Review all content from a page

## Comparison with Other Endpoints

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /documents/{id}/pages/{page}` | Get all info from a page | Text chunks + Images from that page |
| `GET /documents/{id}/images/all` | Get all images | All images from document |
| `POST /query/text` | Search text | Text chunks matching query |
| `POST /query/images` | Search images | Images matching query |

## Notes

- Page numbers are 1-indexed (page 1, page 2, etc.)
- Returns all text chunks from the specified page
- Returns all images from the specified page
- Text and images are returned separately for clarity
- Complete OCR text is included for all images
- Full metadata is available for analysis

## Example: Query Page 1

When you query page 1, you get:
- ✅ All 10 text chunks from page 1
- ✅ All 65 images from page 1
- ✅ Complete OCR text from all images
- ✅ Full metadata for text and images
- ✅ Total content: 194,255 characters

This gives you **complete information** about page 1!
