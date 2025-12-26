# Deploy Verification Endpoints - Quick Guide

## Issue: "Not Found" Error

If you're getting `{"detail": "Not Found"}`, it means the new verification endpoints need to be deployed to the server.

## Quick Deployment

### Option 1: Use Existing Deployment Script

```bash
# Deploy updated API files
./scripts/deploy-api-updates.sh
```

### Option 2: Manual Deployment

```bash
# 1. Copy updated files to server
scp api/main.py api/schemas.py user@44.221.84.58:/opt/aris-rag/api/
scp -r utils/ user@44.221.84.58:/opt/aris-rag/
scp -r config/ user@44.221.84.58:/opt/aris-rag/

# 2. Copy into Docker container
ssh user@44.221.84.58 "sudo docker cp /opt/aris-rag/api/main.py aris-rag-app:/app/api/"
ssh user@44.221.84.58 "sudo docker cp /opt/aris-rag/api/schemas.py aris-rag-app:/app/api/"
ssh user@44.221.84.58 "sudo docker cp /opt/aris-rag/utils aris-rag-app:/app/"
ssh user@44.221.84.58 "sudo docker cp /opt/aris-rag/config aris-rag-app:/app/"

# 3. Restart container
ssh user@44.221.84.58 "sudo docker restart aris-rag-app"
```

## Verify Deployment

After deployment, test the endpoints:

```bash
# 1. Get document ID
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')")

# 2. Test accuracy endpoint
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool

# Should return JSON, not "Not Found"
```

## Files That Need Deployment

1. `api/main.py` - Contains new endpoints
2. `api/schemas.py` - Contains new schemas
3. `utils/pdf_metadata_extractor.py` - New utility
4. `utils/pdf_content_extractor.py` - New utility
5. `utils/ocr_verifier.py` - New utility
6. `utils/ocr_auto_fix.py` - New utility
7. `config/accuracy_config.py` - New config
8. `storage/document_registry.py` - Updated with version tracking

## Alternative: Test Existing Endpoints

While waiting for deployment, you can test existing endpoints:

```bash
# List documents
curl -s http://44.221.84.58:8500/documents | python3 -m json.tool

# Get all images for a document
DOC_ID="your-document-id"
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/images/all" | python3 -m json.tool

# Get page information
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/pages/1" | python3 -m json.tool
```
