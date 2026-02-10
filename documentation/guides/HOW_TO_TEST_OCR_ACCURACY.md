# How to Test OCR Accuracy - Side-by-Side Comparison

## Overview

This guide shows you how to test OCR accuracy by comparing:
- **Direct OCR from PDF images** (ground truth)
- **Stored OCR from your API** (what's in OpenSearch)

## Method 1: Using Verification Endpoint (Recommended)

The easiest way is to use the built-in verification endpoint:

### Step 1: Get Document ID

```bash
curl -s http://44.221.84.58:8500/documents | python3 -m json.tool | grep -A 2 "document_id"
```

### Step 2: Run Verification

```bash
# Set your document ID
DOC_ID="your-document-id-here"

# Run verification (requires PDF file)
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_document.pdf" \
  -F "auto_fix=false" \
  -o verification_report.json

# View results
python3 -m json.tool verification_report.json | head -100
```

### Step 3: Check Accuracy

The verification report includes:
- **Overall accuracy** percentage
- **Per-image accuracy** scores
- **Side-by-side comparison** data
- **Missing/extra content** lists
- **Recommendations** for improvement

## Method 2: Quick Accuracy Check

For a quick check without full verification:

```bash
DOC_ID="your-document-id-here"

curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

This returns:
- Overall accuracy (if available)
- Status (accurate/needs_review/inaccurate)
- Whether full verification is needed

## Method 3: Using Python Script

### Simple Test Script

```python
import requests

API_BASE = "http://44.221.84.58:8500"
DOC_ID = "your-document-id"

# Quick accuracy check
response = requests.get(f"{API_BASE}/documents/{DOC_ID}/accuracy")
data = response.json()
print(f"Accuracy: {data.get('overall_accuracy')}")
print(f"Status: {data.get('status')}")

# Full verification (requires PDF file)
with open('your_document.pdf', 'rb') as f:
    files = {'file': f}
    data = {'auto_fix': 'false'}
    response = requests.post(
        f"{API_BASE}/documents/{DOC_ID}/verify",
        files=files,
        data=data,
        timeout=600
    )
    
result = response.json()
print(f"Overall Accuracy: {result['overall_accuracy']:.2%}")
print(f"Issues: {len(result['issues_found'])}")
```

## Understanding the Results

### Accuracy Metrics

- **Overall Accuracy**: Average accuracy across all images (0-100%)
- **Per-Image Accuracy**: Individual image accuracy scores
- **Character Accuracy**: Character-level matching
- **Word Accuracy**: Word-level matching

### Status Indicators

- ✅ **accurate** (≥90%): OCR is very accurate
- ⚠️ **needs_review** (85-90%): OCR is acceptable but could improve
- ❌ **inaccurate** (<85%): OCR needs attention

### What to Look For

1. **Missing Content**: Words in PDF but not in stored OCR
2. **Extra Content**: Words in stored OCR but not in PDF
3. **Length Differences**: Significant text length differences
4. **Low Accuracy Images**: Images with accuracy < 85%

## Example Output

```json
{
  "document_id": "abc-123",
  "overall_accuracy": 0.945,
  "image_verifications": [
    {
      "image_id": "page_1_img_0",
      "page_number": 1,
      "image_index": 0,
      "ocr_accuracy": 0.98,
      "character_accuracy": 0.99,
      "status": "accurate",
      "stored_ocr_length": 2586,
      "verified_ocr_length": 2584
    }
  ],
  "issues_found": [],
  "recommendations": []
}
```

## Troubleshooting

### No Accuracy Data
- **Cause**: Document hasn't been verified yet
- **Solution**: Run verification endpoint with PDF file

### Low Accuracy
- **Cause**: OCR quality issues, image quality, or preprocessing problems
- **Solution**: 
  - Review specific differences
  - Use auto-fix option
  - Re-process with enhanced OCR settings

### Verification Timeout
- **Cause**: Large PDF or slow processing
- **Solution**: Increase timeout or process in batches

## Best Practices

1. **Regular Testing**: Verify accuracy after document uploads
2. **Monitor Trends**: Track accuracy over time
3. **Review Low Scores**: Investigate images with < 85% accuracy
4. **Use Auto-Fix**: Enable auto-fix for low accuracy documents
5. **Document Issues**: Keep records for continuous improvement

## Next Steps

After testing accuracy:
1. Review the verification report
2. Identify problematic images
3. Apply auto-fix if needed
4. Re-process documents with low accuracy
5. Update OCR settings if necessary
