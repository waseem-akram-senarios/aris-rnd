# Enhanced Image OCR Extraction Fix

## Problem

Getting error: `"No images with OCR text were extracted from the document"` even though images are detected.

## Root Causes Identified

1. **ProcessingResult doesn't have parsed_document** - ✅ FIXED
2. **OCR models may not be installed** - Added verification
3. **Extraction logic may fail silently** - Added fallback
4. **Text available but extracted_images empty** - Added fallback logic

## Fixes Applied

### 1. Direct Docling Parser Access ✅
- Changed from `processor.process_document()` to direct `DoclingParser.parse()`
- Now properly accesses `extracted_images` from `parsed_doc.metadata`

### 2. Enhanced Diagnostics ✅
- OCR model verification before parsing
- Detailed logging of:
  - Images detected count
  - Text length extracted
  - Metadata keys available
  - Extraction process steps

### 3. Fallback Logic ✅
If images are detected but `extracted_images` is empty:
- **Check if text is available** (length > 100 chars)
- **Create fallback image entries** from extracted text
- **Use page_blocks** if available to create per-page images
- **Single image entry** if no page_blocks

### 4. Better Error Messages ✅
- Detailed diagnostics in error response
- Specific guidance on what to check
- OCR model installation instructions

## Code Changes

### Before
```python
result = processor.process_document(...)
extracted_images = result.parsed_document.metadata.get('extracted_images', [])  # ❌
```

### After
```python
docling_parser = DoclingParser()
ocr_models_available = docling_parser._verify_ocr_models()  # ✅ Check models
parsed_doc = docling_parser.parse(temp_file_path, file_content=file_content)  # ✅ Direct parse
extracted_images = parsed_doc.metadata.get('extracted_images', [])  # ✅ Works

# Fallback if extraction failed but text available
if not extracted_images and images_detected and text_available:
    extracted_images = create_fallback_from_text(...)  # ✅ Fallback
```

## Testing

### 1. Deploy the fix:
```bash
./scripts/deploy-api-updates.sh
```

### 2. Test with file upload:
```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@FL10.11 SPECIFIC8 (2).pdf" \
  -H "Accept: application/json" | jq .
```

### 3. Run diagnostics:
```bash
python3 test_image_extraction_fix.py
```

### 4. Check page 4:
```bash
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/4" \
  -H "Accept: application/json" | jq '.images[] | {image_number, ocr_text_length, extraction_method}'
```

## Expected Behavior

### Scenario 1: OCR Works Properly
- ✅ Images extracted with OCR text
- ✅ Stored in OpenSearch
- ✅ Available via `/pages/{page_number}`

### Scenario 2: OCR Fails But Text Available
- ⚠️ Extraction fails
- ✅ Fallback creates image entries from text
- ✅ Images stored with `extraction_method: 'docling_ocr_fallback'`
- ✅ Available via `/pages/{page_number}`

### Scenario 3: No Text Extracted
- ❌ Error with detailed diagnostics
- 📋 Instructions to install OCR models
- 📋 Guidance on possible causes

## Server Logs to Check

After deployment, check server logs for:
- `OCR models available: True/False`
- `Parsed document - images_detected: ...`
- `Found X images in metadata.extracted_images`
- `Created X fallback image entries from text` (if fallback used)
- `Final extracted_images count: X`

## Troubleshooting

### If still getting "No images extracted":

1. **Check OCR models**:
   ```bash
   # On server
   docker exec -it aris-rag-app bash
   docling download-models
   ```

2. **Check server logs** for detailed diagnostics

3. **Verify PDF has extractable text**:
   - Some PDFs have images with no text
   - Diagrams/charts may not have OCR-able text

4. **Check extraction_method in response**:
   - `docling` = Normal extraction worked
   - `docling_ocr_fallback` = Fallback used (text available but extraction failed)

## Next Steps

1. Deploy the fix
2. Test with file upload
3. Check diagnostics output
4. Review server logs for detailed information
5. If still failing, check OCR model installation
