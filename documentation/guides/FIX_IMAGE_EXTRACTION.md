# Fix: Image OCR Extraction Issue

## Problem

Images were detected (13 images) but OCR text was 0 because:
1. Images weren't stored in OpenSearch (`images_stored: 0`)
2. The `/store/images` endpoint couldn't access `extracted_images` from `ProcessingResult`
3. `ProcessingResult` doesn't include `parsed_document` attribute

## Root Cause

The endpoint was trying to access:
```python
result.parsed_document.metadata.get('extracted_images')
```

But `ProcessingResult` doesn't have a `parsed_document` attribute, so `extracted_images` was always empty.

## Fix Applied

Changed the endpoint to use `DoclingParser` directly instead of going through `DocumentProcessor.process_document()`:

**Before:**
```python
result = processor.process_document(...)
extracted_images = result.parsed_document.metadata.get('extracted_images', [])  # ❌ Doesn't work
```

**After:**
```python
docling_parser = DoclingParser()
parsed_doc = docling_parser.parse(temp_file_path, file_content=file_content)
extracted_images = parsed_doc.metadata.get('extracted_images', [])  # ✅ Works
```

## What This Fixes

1. ✅ **Direct Access**: Now directly parses with Docling and gets `extracted_images`
2. ✅ **Proper Extraction**: Will extract images with OCR text from PDF
3. ✅ **Better Error Messages**: Provides specific error if images detected but OCR fails
4. ✅ **Storage**: Images will be properly stored in OpenSearch

## Next Steps

1. **Deploy the fix**:
   ```bash
   ./scripts/deploy-api-updates.sh
   ```

2. **Test with file upload**:
   ```bash
   curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
     -F "file=@FL10.11 SPECIFIC8 (2).pdf" \
     -H "Accept: application/json"
   ```

3. **Verify images stored**:
   ```bash
   curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=10" \
     -H "Accept: application/json" | jq '.total'
   ```

4. **Get OCR by page**:
   ```bash
   curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/4" \
     -H "Accept: application/json" | jq '.images[] | {image_number, ocr_text}'
   ```

## Expected Results After Fix

- Images will be extracted with OCR text
- Images will be stored in OpenSearch
- `/pages/{page_number}` endpoint will return images with OCR
- OCR text will be accessible per page
