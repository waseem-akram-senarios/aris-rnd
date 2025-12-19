# Query Endpoint - Image Data Verification ✅

**Date**: December 18, 2025  
**Status**: ✅ **WORKING**

## ✅ Image Data Now Included in Query Responses

The query endpoint (`POST /query`) now returns image data in citations when image content is found.

## Test Results

### Query: "What tools are in drawer 1?"

**Response**:
- ✅ **Status**: 200 OK
- ✅ **Citations with Images**: 3 out of 5 citations
- ✅ **Image References**: Included in citations
- ✅ **Image Info**: Included in citations
- ✅ **Content Type**: Marked as "image" for image citations

### Sample Image Citation

```json
{
  "id": 1,
  "source": "FL10.11 SPECIFIC8 (2).pdf",
  "page": 40,
  "image_ref": {
    "page": 40,
    "image_index": 1,
    "source": "FL10.11 SPECIFIC8 (2).pdf"
  },
  "image_info": "Image 1 on Page 40",
  "content_type": "image",
  "snippet": "...__ 78900101- 180° Snap Ring ___ 78900102- 90°   Snap Ring ___ 65300085- Small Phillips ___ 65300086- Large Phillips ___ 65300087- Small Flat-head ___ 65300088- Large Flat-head ___ 65300076- Large C...",
  "full_text": "[Full OCR text from image]"
}
```

## What's Included in Image Citations

1. **image_ref**: Dictionary with:
   - `page`: Page number where image appears
   - `image_index`: Sequential image number
   - `source`: Document source

2. **image_info**: Human-readable string like "Image 1 on Page 40"

3. **content_type**: Set to "image" for image citations

4. **snippet**: Preview of OCR text from the image

5. **full_text**: Complete OCR text extracted from the image

## How It Works

1. **Image Content Extraction**: When documents are processed, image OCR text is extracted and stored
2. **Image Content Detection**: During queries, chunks with image markers (`<!-- image -->`) are identified
3. **Citation Building**: Citations from image content chunks are marked with:
   - `image_ref`: Image reference metadata
   - `image_info`: Human-readable image description
   - `content_type`: "image" to distinguish from text citations
4. **Context Inclusion**: Image OCR text is also added to the context sent to the LLM

## Verification

✅ **Image data is now being returned in query responses!**

- Citations include `image_ref` and `image_info` when from images
- `content_type` is set to "image" for image citations
- OCR text from images is included in `snippet` and `full_text`
- Image information is accessible via the API

## Example Usage

```bash
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What tools are in drawer 1?",
    "k": 10
  }'
```

**Response includes**:
- Answer using image content
- Citations with `image_ref`, `image_info`, and `content_type: "image"`
- Full OCR text from images in citation `full_text` field

## Status

✅ **Image data is successfully included in query responses!**



