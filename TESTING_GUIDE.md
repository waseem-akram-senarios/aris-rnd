# Testing Guide - Server Testing

## ✅ Server Status
- **URL**: http://35.175.133.235/
- **Status**: Ready for testing
- **All fixes**: Deployed and active

## 🧪 How to Test

### Step 1: Access the Application
1. Open your browser
2. Go to: **http://35.175.133.235/**
3. You should see the ARIS RAG Document Q&A System interface

### Step 2: Test Document Processing

#### Test with Scanned PDF (Image-based):
1. **Select Parser**: Choose **"Docling"** from the parser dropdown
2. **Upload Document**: Upload your scanned PDF
   - File: `1763080529_1740003655_x1000_sl_industrial_air_compressor (4).pdf`
3. **Click "Process Documents"**
4. **What to Expect**:
   - UI shows: "🔍 Docling parsing (5-10 min, processing all pages)..."
   - **Note**: UI may not update during processing (this is normal)
   - Processing takes 5-20 minutes for scanned PDFs

### Step 3: Monitor Processing

**Open a terminal and run:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
sudo docker logs -f aris-rag-app | grep -i docling
```

**You'll see:**
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
Docling: Markdown export completed (X characters)
```

### Step 4: Verify Completion

**In the browser:**
- Wait for processing to complete (5-20 minutes)
- You should see a success message when done
- Document will be available for querying

**In logs:**
- Look for "Docling: Document conversion successful"
- Look for "Chunking and embedding completed"
- Look for success message in Streamlit

## 🔍 Quick Status Check

**Run this command to check current status:**
```bash
bash scripts/monitor_docling_processing.sh
```

## ⚠️ Important Notes

1. **UI May Not Update**: Streamlit UI may not show progress updates during long processing. This is normal.

2. **Processing Takes Time**: 
   - Scanned PDFs: 5-20 minutes
   - Text PDFs: 1-3 minutes
   - This is normal for OCR processing

3. **Monitor Logs**: The best way to see progress is through logs, not the UI

4. **No Fallback**: When Docling is selected, it will NOT fall back to PyMuPDF. It will complete with Docling or show an error.

## 🐛 Troubleshooting

### If Processing Appears Stuck:

1. **Check Logs**:
   ```bash
   sudo docker logs --tail=50 aris-rag-app | grep -i docling
   ```

2. **Look for Progress Messages**:
   - Should see "Docling: Still processing... (Xm Ys elapsed)" every minute
   - If you see this, processing is ongoing (normal)

3. **Check Resource Usage**:
   ```bash
   sudo docker stats aris-rag-app
   ```
   - CPU > 0% means processing is active
   - Memory usage should be stable

4. **Wait Full Timeout**:
   - Maximum wait time: 20 minutes
   - If no completion after 20 minutes, check for errors

### If You See Errors:

1. **Check Error Message**: It will tell you what went wrong
2. **Check Logs**: `sudo docker logs aris-rag-app | tail -50`
3. **Restart if Needed**: `sudo docker restart aris-rag-app`

## ✅ Success Indicators

You'll know processing completed successfully when you see:

1. **In UI**:
   - Success message: "✅ Processed 1 document(s) into X chunks"
   - Document appears in the query interface

2. **In Logs**:
   - "Docling: Document conversion successful"
   - "Chunking and embedding completed"
   - "Processing completed in X seconds"

## 🎯 Ready to Test!

**Application URL**: http://35.175.133.235/

**Start Testing Now:**
1. Open the URL in your browser
2. Select "Docling" parser
3. Upload your scanned PDF
4. Monitor logs in a separate terminal
5. Wait 5-20 minutes for completion

Good luck! 🚀



