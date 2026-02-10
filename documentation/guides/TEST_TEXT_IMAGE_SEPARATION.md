# Text and Image OCR Separation - End-to-End Test Guide

## Overview

This test verifies that text and image OCR content are stored and queried separately using the new FastAPI endpoints.

## Test Script

**File**: `test_text_image_separation_e2e.py`

## Prerequisites

1. **F1 Document**: Ensure `FL10.11 SPECIFIC8 (1).pdf` is available in:
   - Current directory, OR
   - `./test_documents/` directory, OR
   - `./documents/` directory

2. **FastAPI Server**: Running at `http://44.221.84.58:8500` (or set `FASTAPI_URL` environment variable)

3. **OpenSearch**: Configured and accessible (required for image storage)

## Running the Test

```bash
# Basic run
python test_text_image_separation_e2e.py

# With custom server URL
FASTAPI_URL=http://localhost:8000 python test_text_image_separation_e2e.py
```

## Test Steps

The test performs the following steps:

1. **Health Check** - Verifies API is accessible
2. **Find F1 Document** - Locates the test document
3. **Upload Document** - Uploads with Docling parser (includes OCR processing)
4. **Check Storage Status** - Verifies text and images are stored separately
5. **Store Text Separately** - Tests `POST /documents/{id}/store/text`
6. **Store Images Separately** - Tests `POST /documents/{id}/store/images`
7. **Query Text Only** - Tests `POST /query/text` (excludes images)
8. **Query Images Only** - Tests `POST /query/images` (excludes text)
9. **Verify Separation** - Confirms text and images are truly separated
10. **Summary** - Displays test results and metrics

## Expected Results

### Successful Test Output

```
✅ Document uploaded successfully
   - Text Chunks: X
   - Images Stored: Y
   - Text Index: aris-rag-index
   - Images Index: aris-rag-images-index

✅ Storage status retrieved
   - Text Chunks: X
   - Images Count: Y
   - OCR Enabled: True

✅ Text storage verified
✅ Image OCR storage verified
✅ Text query completed (content_type: "text")
✅ Image query completed (content_type: "image_ocr")
✅ Text query correctly excludes image content
✅ Image query correctly excludes regular text
```

## Endpoints Tested

### Storage Endpoints

1. **POST /documents** - Upload document
   - Returns separate text/image storage statistics
   - Fields: `text_chunks_stored`, `images_stored`, `text_index`, `images_index`

2. **GET /documents/{id}/storage/status** - Get storage status
   - Returns detailed separation information
   - Shows counts, status, and OCR statistics

3. **POST /documents/{id}/store/text** - Store text separately
   - Verifies text is stored in text index
   - Returns text storage statistics

4. **POST /documents/{id}/store/images** - Store images separately
   - Verifies images are stored in images index
   - Returns image OCR statistics

### Query Endpoints

1. **POST /query/text** - Query text only
   - Queries only `aris-rag-index`
   - Returns `content_type: "text"`
   - Excludes image OCR content

2. **POST /query/images** - Query images only
   - Queries only `aris-rag-images-index`
   - Returns `content_type: "image_ocr"`
   - Excludes regular text content

## Verification

The test verifies:

- ✅ Text and images are stored in separate OpenSearch indexes
- ✅ Text query returns only text content (no images)
- ✅ Image query returns only OCR content (no regular text)
- ✅ Storage status shows correct separation
- ✅ All endpoints return correct `content_type` metadata

## Troubleshooting

### Document Not Found

```
❌ F1 document not found!
```

**Solution**: Place `FL10.11 SPECIFIC8 (1).pdf` in the current directory or `./test_documents/`

### Upload Timeout

```
❌ Upload error: Timeout
```

**Solution**: Docling OCR processing can take 5-10 minutes. The test has a 10-minute timeout. For very large documents, increase `TEST_TIMEOUT` in the script.

### OpenSearch Not Configured

```
❌ Image storage requires OpenSearch
```

**Solution**: Ensure `OPENSEARCH_DOMAIN` or `AWS_OPENSEARCH_DOMAIN` is set in environment variables.

### No Images Detected

```
⚠️  No images detected in document
```

**Solution**: Ensure document contains images and Docling parser is used (it's the default in the test).

## Test Output Example

```
======================================================================
ARIS RAG API - TEXT/IMAGE SEPARATION END-TO-END TEST
======================================================================
Server: http://44.221.84.58:8500

STEP 1: Health Check
✅ Response received (Status: 200)

STEP 2: Find F1 Document
✅ Found document: ./FL10.11 SPECIFIC8 (1).pdf
   File size: 1.55 MB

STEP 3: Upload Document with Docling Parser
✅ Document uploaded successfully
   Document ID: abc-123-def-456
   Text Chunks: 45
   Images Stored: 13
   Text Index: aris-rag-index
   Images Index: aris-rag-images-index

STEP 4: Check Storage Status
✅ Storage status retrieved
   Text Chunks: 45
   Images Count: 13
   OCR Enabled: True

STEP 5: Store Text Separately
✅ Text storage verified
   Text Chunks Stored: 45

STEP 6: Store Images Separately
✅ Image OCR storage verified
   Images Stored: 13
   Total OCR Text Length: 105,895 characters

STEP 7: Query Text Content Only
✅ Text query completed
   Content Type: text
   Chunks Used: 5
   Total Text Chunks: 45

STEP 8: Query Image OCR Content Only
✅ Image query completed
   Content Type: image_ocr
   Total Images: 13

STEP 9: Verify Text and Image Separation
✅ Text query correctly excludes image content
✅ Image query correctly excludes regular text

STEP 10: Test Summary
Test Results:
  Total Tests: 9
  Passed: 9
  Failed: 0
  Success Rate: 100.0%

✅ All tests passed!
```

## Next Steps

After successful test:

1. Verify separation in OpenSearch directly
2. Test with multiple documents
3. Test query performance
4. Test with different document types
