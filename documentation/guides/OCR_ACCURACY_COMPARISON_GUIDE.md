# OCR Accuracy Comparison Guide

## Overview

This guide explains how to use the OCR accuracy comparison tool to verify the accuracy of OCR stored in your API by comparing it side-by-side with OCR extracted directly from PDF images.

## What It Does

The comparison tool:
1. **Extracts OCR directly from PDF images** - Gets the "ground truth" OCR from the actual document
2. **Retrieves stored OCR from API** - Gets what your API has stored in OpenSearch
3. **Compares side-by-side** - Shows both OCR texts and calculates accuracy metrics
4. **Generates detailed report** - Provides accuracy scores, differences, and recommendations

## Usage

### Basic Usage

```bash
python3 test_ocr_accuracy_comparison.py
```

The script will:
- Automatically find the first document in your API
- Locate the corresponding PDF file
- Extract OCR from PDF images
- Get stored OCR from API
- Compare and show results

### Requirements

1. **PDF file** - The original PDF must be in the current directory
2. **API access** - API must be running and accessible
3. **Document uploaded** - Document must already be uploaded to the API

## Output

### Console Output

The script provides:
- **Summary statistics**: Total images, matched images, overall accuracy
- **Side-by-side comparison**: For each image:
  - Direct OCR (from PDF)
  - Stored OCR (from API)
  - Accuracy metrics (similarity, character accuracy)
  - Differences (missing/extra words)

### JSON Report

A detailed JSON report is saved to `ocr_comparison_report.json` containing:
- All comparison data
- Full OCR texts
- Accuracy metrics
- Timestamps

## Understanding the Results

### Accuracy Metrics

- **Similarity**: Overall text similarity (0-100%)
- **Character Accuracy**: Character-level matching (0-100%)

### Status Indicators

- ✅ **EXCELLENT MATCH** (≥90%): OCR is very accurate
- ⚠️ **GOOD MATCH** (85-90%): OCR is acceptable but could improve
- ❌ **POOR MATCH** (<85%): OCR needs attention

### What to Look For

1. **Missing Content**: Words in direct OCR but not in stored OCR
2. **Extra Content**: Words in stored OCR but not in direct OCR
3. **Length Differences**: Significant differences in text length
4. **Low Accuracy**: Images with accuracy below 85%

## Example Output

```
================================================================================
OCR ACCURACY COMPARISON REPORT
================================================================================

📊 Summary:
  Direct PDF Images: 22
  Stored API Images: 22
  Matched Images: 22
  Overall Accuracy: 94.5%
  Average Accuracy: 94.5%

================================================================================
DETAILED SIDE-BY-SIDE COMPARISON
================================================================================

────────────────────────────────────────────────────────────────────────────────
IMAGE 1 - Page 1
────────────────────────────────────────────────────────────────────────────────

📏 Length Comparison:
  Direct OCR: 2,586 characters
  Stored OCR: 2,584 characters
  Difference: 2 characters

📊 Accuracy Metrics:
  Similarity: 99.2%
  Character Accuracy: 99.1%
  ✅ Status: EXCELLENT MATCH

📄 Direct OCR (from PDF):
  ────────────────────────────────────────────────────────────────────────────
  | Line 11 Batch Change Standard Work                      | RPF 1 and 2 Handler                                                             | p. 14                                                  |
  ...

💾 Stored OCR (from API):
  ────────────────────────────────────────────────────────────────────────────
  | Line 11 Batch Change Standard Work                      | RPF 1 and 2 Handler                                                             | p. 14                                                  |
  ...
```

## Troubleshooting

### No Images Extracted from PDF
- **Cause**: PDF may not have extractable images or Docling not configured
- **Solution**: Ensure Docling is installed and PDF has images

### No Stored Images Found
- **Cause**: Document not processed or images not stored
- **Solution**: Upload and process document first

### Low Accuracy Scores
- **Cause**: OCR quality issues, preprocessing problems, or extraction method differences
- **Solution**: 
  - Review specific differences
  - Consider re-processing with enhanced OCR settings
  - Check image quality in original PDF

## Integration with Verification Endpoint

You can also use the verification endpoint for automated accuracy checking:

```bash
# Get document ID first
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | jq -r '.documents[0].document_id')

# Run verification (requires PDF file upload)
curl -X POST \
  "http://44.221.84.58:8500/documents/$DOC_ID/verify" \
  -F "file=@your_document.pdf" \
  -F "auto_fix=false" | jq .
```

## Best Practices

1. **Regular Testing**: Run comparison tests after document uploads
2. **Monitor Accuracy**: Track accuracy trends over time
3. **Review Low Accuracy**: Investigate images with accuracy < 85%
4. **Use Auto-Fix**: Enable auto-fix for documents with low accuracy
5. **Document Issues**: Keep records of accuracy issues for improvement

## Next Steps

After running the comparison:
1. Review the accuracy report
2. Identify problematic images
3. Use verification endpoint for detailed analysis
4. Apply auto-fix if needed
5. Re-process documents with low accuracy
