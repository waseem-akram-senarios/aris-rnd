# Manual Deployment Steps

## Current Status
- ✅ Server is running at http://44.221.84.58:8500
- ⚠️ Server is running OLD code (before fixes)
- ✅ Test results: 5/7 endpoints working (2 timeout due to old code)

## Files That Need to Be Deployed

1. **api/schemas.py** - Fixed search_mode validation
2. **api/main.py** - Fixed 7 endpoints with error handling

## Deployment Options

### Option 1: Using Server Terminal/SSH (RECOMMENDED)

If you have access to the server terminal:

```bash
# 1. SSH into server
ssh ubuntu@44.221.84.58

# 2. Navigate to project directory
cd /home/ubuntu/aris

# 3. Pull latest changes (if git is configured)
git pull origin main

# 4. Restart FastAPI service
sudo systemctl restart aris-fastapi

# 5. Verify it's running
curl http://localhost:8500/docs
```

### Option 2: Using File Upload

If you have file upload access to the server:

```bash
# 1. From your local machine, create deployment package
cd /home/senarios/Desktop/aris
tar -czf aris_fixes.tar.gz api/schemas.py api/main.py

# 2. Upload aris_fixes.tar.gz to server (use your file manager/FTP/SCP)

# 3. On server, extract and move files
cd /home/ubuntu/aris
tar -xzf ~/aris_fixes.tar.gz -C api/

# 4. Restart service
sudo systemctl restart aris-fastapi
```

### Option 3: Using Docker (if running in Docker)

```bash
# SSH into server
ssh ubuntu@44.221.84.58

# Navigate to project
cd /home/ubuntu/aris

# Pull latest code
git pull origin main

# Rebuild and restart containers
sudo docker-compose down
sudo docker-compose up -d --build

# Check logs
sudo docker-compose logs -f api
```

### Option 4: Manual File Copy

If you can access the server files directly:

1. Copy `api/schemas.py` from local to server at `/home/ubuntu/aris/api/schemas.py`
2. Copy `api/main.py` from local to server at `/home/ubuntu/aris/api/main.py`
3. Restart service: `sudo systemctl restart aris-fastapi`

## Verification After Deployment

Run these commands to verify deployment:

```bash
# 1. Check if API is running
curl http://44.221.84.58:8500/docs

# 2. Test search_mode fix (should not timeout)
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "search_mode": "hybrid", "k": 3}' \
  --max-time 30

# 3. Run full test suite
cd /home/senarios/Desktop/aris
python3 test_api_fixes.py
```

## Expected Results After Deployment

- ✅ All 7 tests should pass
- ✅ Query endpoints should respond (not timeout)
- ✅ search_mode validation should work
- ✅ Better error messages in all endpoints

## Current Test Results (Before Deployment)

```
✅ list_documents - PASSED
✅ get_document - PASSED (404 is expected with document_id=None)
❌ query_search_mode - TIMEOUT (old code doesn't have fix)
✅ storage_status - PASSED (404 is expected)
✅ accuracy_check - PASSED (404 is expected)
❌ query_text - TIMEOUT (old code issue)
✅ query_images - PASSED
```

## What to Do Next

1. **Choose a deployment method** from above
2. **Deploy the fixed files** to server
3. **Restart the FastAPI service**
4. **Run test suite again**: `python3 test_api_fixes.py`
5. **Verify all tests pass**

## Need Help?

If you can provide:
- SSH key location, OR
- Server access method (FTP/file manager), OR
- Confirmation that git works on server

I can provide more specific deployment commands.
