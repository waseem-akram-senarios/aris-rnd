# Test Store Images Endpoint

## Test 1: Without File Upload (Check Existing Images)

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -H "Accept: application/json" | jq '.'
```

**Expected Results:**
- If images already stored: Returns count and status "completed"
- If images not stored: Returns error with instructions to provide file

## Test 2: With File Upload (Re-process Document)

```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@/path/to/FL10.11 SPECIFIC8 (2).pdf" \
  -H "Accept: application/json" | jq '.'
```

**Expected Results:**
- Status: "completed"
- images_stored: > 0
- reprocessed: true
- extraction_method: "docling"
- total_ocr_text_length: > 0

## Test 3: Verify Images Are Stored

After re-processing, verify images are accessible:

```bash
# Get all images
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/images/all?limit=10" \
  -H "Accept: application/json" | jq '{total: .total, images_with_ocr: .images_with_ocr}'

# Get images from page 1
curl -X GET "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/pages/1" \
  -H "Accept: application/json" | jq '.total_images'
```

## Test 4: Error Cases

### Invalid File Type
```bash
curl -X POST "http://44.221.84.58:8500/documents/b0b01b35-ccbb-4e52-9db6-2690e531289b/store/images" \
  -F "file=@test.txt" \
  -H "Accept: application/json"
```

**Expected**: 400 Bad Request - "Invalid file type"

### Document Not Found
```bash
curl -X POST "http://44.221.84.58:8500/documents/invalid-id/store/images" \
  -H "Accept: application/json"
```

**Expected**: 404 Not Found

## Python Test Script

```python
import requests

API_BASE = "http://44.221.84.58:8500"
DOC_ID = "b0b01b35-ccbb-4e52-9db6-2690e531289b"

# Test 1: Without file
print("Test 1: Check existing images (no file upload)")
response = requests.post(f"{API_BASE}/documents/{DOC_ID}/store/images")
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# Test 2: With file
print("\nTest 2: Re-process with file upload")
with open("FL10.11 SPECIFIC8 (2).pdf", "rb") as f:
    files = {"file": ("document.pdf", f, "application/pdf")}
    response = requests.post(
        f"{API_BASE}/documents/{DOC_ID}/store/images",
        files=files
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

# Test 3: Verify storage
print("\nTest 3: Verify images are stored")
response = requests.get(f"{API_BASE}/documents/{DOC_ID}/images/all?limit=10")
data = response.json()
print(f"Total images: {data.get('total')}")
print(f"Images with OCR: {data.get('images_with_ocr')}")
```

## Success Criteria

1. ✅ Endpoint accepts optional file parameter
2. ✅ Without file: Checks existing images or returns helpful error
3. ✅ With file: Re-processes document and extracts OCR
4. ✅ Images are stored in OpenSearch
5. ✅ Response includes reprocessed and extraction_method fields
6. ✅ Images are queryable by page after storage
