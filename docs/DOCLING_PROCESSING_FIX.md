# Docling Processing Fix - Progress Tracking

## Issue
When processing documents with Docling, the UI shows "🔍 Docling parsing (5-10 min, processing all pages)..." but appears to hang with no updates.

## Root Cause
1. Docling processing takes 5-20 minutes for scanned PDFs with OCR
2. No periodic progress updates during processing
3. Streamlit UI doesn't show that processing is ongoing
4. Timeout was 15 minutes, which may not be enough for OCR processing

## Fixes Applied

### 1. Increased Timeout
- **Before**: 15 minutes (900 seconds)
- **After**: 20 minutes (1200 seconds)
- **Location**: `parsers/docling_parser.py`
- **Reason**: OCR processing on scanned PDFs takes longer

### 2. Periodic Progress Logging
- Added progress logging every 60 seconds
- Shows elapsed time: "Docling: Still processing... (Xm Ys elapsed, max 20m)"
- **Location**: `parsers/docling_parser.py`
- **Benefit**: Can monitor progress in logs even if UI doesn't update

### 3. Enhanced Logging
- More detailed logging at each step
- Logs when conversion starts, progresses, and completes
- **Location**: `parsers/docling_parser.py`
- **Benefit**: Better visibility into processing status

### 4. Streamlit Configuration
- Updated for long-running operations
- **Location**: `.streamlit/config.toml`
- **Benefit**: Better handling of long operations

## How to Monitor Processing

### Option 1: Watch Logs in Real-Time
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
sudo docker logs -f aris-rag-app | grep -i docling
```

You'll see:
```
Docling: Starting conversion of <file> (2.02 MB)
Docling: Initializing DocumentConverter...
Docling: Processing in background thread (timeout: 1200s)...
Docling: This may take 5-20 minutes for scanned PDFs with OCR...
Docling: Still processing... (1m 0s elapsed, max 20m)
Docling: Still processing... (2m 0s elapsed, max 20m)
...
Docling: Document conversion successful
Docling: Exporting document to markdown...
```

### Option 2: Use Monitoring Script
```bash
bash scripts/monitor_docling_processing.sh
```

### Option 3: Check Container Status
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
sudo docker ps --filter "name=aris-rag-app"
sudo docker stats aris-rag-app
```

## Expected Behavior

### For Scanned PDFs (Image-based):
1. **Upload**: Document is uploaded
2. **UI Shows**: "🔍 Docling parsing (5-10 min, processing all pages)..."
3. **Processing**: 
   - Docling initializes OCR models (1-2 minutes)
   - Processes each page with OCR (5-15 minutes total)
   - Logs show progress every minute
4. **Completion**: 
   - "Docling: Document conversion successful"
   - Text extraction and chunking
   - Success message in UI

### Processing Times:
- **Text PDFs**: 1-3 minutes
- **Scanned PDFs (3 pages)**: 5-15 minutes
- **Large scanned PDFs**: 15-20 minutes

## Troubleshooting

### If Processing Appears Stuck:

1. **Check Logs**:
   ```bash
   sudo docker logs --tail=50 aris-rag-app | grep -i docling
   ```

2. **Look for Progress Messages**:
   - Should see "Docling: Still processing... (Xm Ys elapsed)" every minute
   - If you see this, processing is ongoing (normal)

3. **Check if Completed**:
   - Look for "Docling: Document conversion successful"
   - If not found, processing may still be running

4. **Check Resource Usage**:
   ```bash
   sudo docker stats aris-rag-app
   ```
   - CPU usage should be > 0% if processing
   - Memory usage should be stable

5. **If Truly Stuck**:
   - Wait up to 20 minutes (timeout limit)
   - Check logs for errors
   - Restart container if needed: `sudo docker restart aris-rag-app`

## Current Status

✅ **Fixes Deployed**:
- Timeout: 20 minutes
- Progress logging: Every 60 seconds
- Enhanced error handling
- Streamlit config updated

✅ **Application**: http://35.175.133.235/

## Next Steps

1. **Try processing your document again**
2. **Monitor logs** while processing: `sudo docker logs -f aris-rag-app | grep docling`
3. **Wait 5-20 minutes** for completion (normal for scanned PDFs)
4. **Check for completion** in logs: "Docling: Document conversion successful"

## Notes

- **UI may not update** during processing - this is a Streamlit limitation for very long operations
- **Logs are the best way** to monitor progress
- **Processing is happening** even if UI doesn't update
- **Be patient** - OCR on scanned PDFs takes time



