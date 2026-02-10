# Deploy and Test Image Extraction Fix

## Current Status

- ✅ **Fix Applied**: Code updated to use DoclingParser directly with fallback logic
- ❌ **Not Deployed**: Fix needs to be deployed to server
- ⚠️  **File Path**: PDF file path in curl command needs verification

## Step 1: Deploy the Fix

```bash
cd /home/senarios/Desktop/aris
./scripts/deploy-api-updates.sh
```

This will:
- Copy updated `api/main.py` (with fix)
- Copy parser files (`parsers/docling_parser.py`, `parsers/base_parser.py`)
- Restart Docker container
- Apply all changes

## Step 2: Find Your PDF File

The curl command needs the correct file path. Find your PDF:

```bash
# Search for the PDF file
find ~ -name "FL10.11 SPECIFIC8 (2).pdf" 2>/dev/null

# Or check common locations
ls -la ~/Downloads/*.pdf
ls -la ~/Desktop/*.pdf
ls -la ./*.pdf
```

## Step 3: Test with Correct File Path

Once you find the file, use the full path:

```bash
# Example if file is in Downloads
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@/home/senarios/Downloads/FL10.11 SPECIFIC8 (2).pdf" \
  -H "Accept: application/json" | jq .
```

Or if file is in current directory:

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@./FL10.11\ SPECIFIC8\ (2).pdf" \
  -H "Accept: application/json" | jq .
```

## Step 4: Verify Results

After upload, check if images were stored:

```bash
# Check total images stored
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=5" \
  -H "Accept: application/json" | jq '.total'

# Check page 4
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/4" \
  -H "Accept: application/json" | jq '.images[] | {image_number, ocr_text_length, extraction_method}'
```

## Expected Behavior After Fix

### If OCR Works:
```json
{
  "document_id": "...",
  "images_stored": 13,
  "total_ocr_text_length": 5000,
  "status": "completed",
  "reprocessed": true,
  "extraction_method": "docling"
}
```

### If OCR Fails But Text Available (Fallback):
```json
{
  "document_id": "...",
  "images_stored": 13,
  "total_ocr_text_length": 5000,
  "status": "completed",
  "reprocessed": true,
  "extraction_method": "docling_ocr_fallback"
}
```

### If Everything Fails:
```json
{
  "detail": "Document: FL10.11 SPECIFIC8 (2).pdf\nImages detected: True\nImage count: 13\nText extracted: 0 chars\nOCR models available: False\n\nImages were detected but OCR text extraction failed.\nPossible causes:\n1. Docling OCR models not installed - Run: docling download-models\n..."
}
```

## Troubleshooting

### If still getting "No images extracted":

1. **Check server logs**:
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58
   sudo docker logs aris-rag-app --tail 100 | grep -i "extracted_images\|OCR\|fallback"
   ```

2. **Install OCR models** (if needed):
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58
   sudo docker exec -it aris-rag-app bash
   docling download-models
   ```

3. **Verify file was uploaded**:
   - Check response for `reprocessed: true`
   - Check `extraction_method` field
   - Check server logs for "Processing document with Docling parser"

## Quick Test Script

Run this after deployment:

```bash
python3 test_image_extraction_fix.py
```

This will show:
- Document status
- Images stored count
- Page 4 retrieval test
- Diagnostics
