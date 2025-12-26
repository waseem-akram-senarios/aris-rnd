# Deployment Instructions for API Fixes

## Fixes Applied

### ✅ Fix #1: search_mode Validation
**File:** `api/schemas.py` line 16
**Change:** Added `Literal['semantic', 'keyword', 'hybrid']` type constraint with default `'hybrid'`
**Impact:** Fixes validation errors in query endpoints

### ✅ Fix #2: Get Document Endpoint
**File:** `api/main.py` lines 586-631
**Change:** Added comprehensive error handling and safe defaults for all metadata fields
**Impact:** Prevents 500 errors when document metadata is incomplete

### ✅ Fix #3: Storage Status Endpoint
**File:** `api/main.py` lines 1254-1310
**Change:** Added document existence check, safe defaults, and better error handling
**Impact:** Fixes 422 and 500 errors

### ✅ Fix #4: Accuracy Check Endpoint
**File:** `api/main.py` lines 2256-2342
**Change:** Added try-catch error handling
**Impact:** Prevents 500 errors when OCR metrics are missing

---

## How to Deploy to Server

### Option 1: Manual File Copy (If you have SSH access)
```bash
# Copy fixed files to server
scp api/schemas.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/
scp api/main.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/

# SSH into server and restart FastAPI
ssh ubuntu@44.221.84.58
cd /home/ubuntu/aris
sudo systemctl restart aris-fastapi
# or
sudo docker-compose restart api
```

### Option 2: Git Pull on Server (If server has git access)
```bash
# SSH into server
ssh ubuntu@44.221.84.58

# Pull latest changes
cd /home/ubuntu/aris
git pull origin main

# Restart FastAPI
sudo systemctl restart aris-fastapi
# or
sudo docker-compose restart api
```

### Option 3: Use Deployment Script
```bash
# From your local machine
cd /home/senarios/Desktop/aris
./scripts/deploy-fast.sh
```

---

## Testing After Deployment

### Quick Test (Manual)
```bash
# Test search_mode fix
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "search_mode": "hybrid", "k": 5}'

# Test get document (replace with actual document_id)
curl http://44.221.84.58:8500/documents/{document_id}

# Test storage status
curl http://44.221.84.58:8500/documents/{document_id}/storage/status

# Test accuracy check
curl http://44.221.84.58:8500/documents/{document_id}/accuracy
```

### Automated Test
```bash
# Run test script
python3 test_api_fixes.py
```

---

## What's Fixed vs What Still Needs Investigation

### ✅ FIXED:
1. **search_mode validation error** - Now accepts 'semantic', 'keyword', or 'hybrid'
2. **Get document endpoint 500 errors** - Better error handling and safe defaults
3. **Storage status 422/500 errors** - Proper validation and error handling
4. **Accuracy check 500 errors** - Try-catch blocks prevent crashes

### ⚠️ STILL NEEDS INVESTIGATION:
1. **Zero chunks created** - Root cause of most query failures
   - Documents being processed but no chunks generated
   - Need to check logs: `tail -f logs/document_processor.log`
   - May be parser issue (try PyMuPDF instead of Docling)

2. **Image endpoints returning no results**
   - Images may not be extracted during processing
   - Check if Docling is extracting images properly
   - Verify images are stored in OpenSearch images index

3. **Wrong citations in text queries**
   - May be related to zero chunks issue
   - Check if page numbers are preserved in metadata

4. **Large PDF issues**
   - May need to adjust chunk size for large documents
   - Check if adaptive chunking is working

---

## Verification Checklist

After deployment, verify:

- [ ] FastAPI service is running: `curl http://44.221.84.58:8500/docs`
- [ ] Query endpoint accepts search_mode: Test with curl command above
- [ ] Get document returns proper metadata (not 500 error)
- [ ] Storage status returns data (not 422/500)
- [ ] Accuracy check doesn't crash (not 500)
- [ ] Check logs for any new errors: `tail -f logs/fastapi.log`

---

## Next Steps

1. **Deploy these fixes to server**
2. **Run test script** to verify fixes work
3. **Investigate zero chunks issue** - This is the blocker for most functionality
4. **Check document processing logs** to see why chunks aren't being created
5. **Test with simple PDF** to isolate the problem

---

## Rollback Plan (If Something Breaks)

```bash
# SSH into server
ssh ubuntu@44.221.84.58
cd /home/ubuntu/aris

# Revert to previous commit
git reset --hard HEAD~1

# Restart service
sudo systemctl restart aris-fastapi
```

---

**Created:** December 26, 2025
**Status:** Fixes committed locally, ready for deployment
**Commit:** 16400c0
