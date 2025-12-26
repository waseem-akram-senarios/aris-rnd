# Deploy Verification Endpoints Now

## Quick Deployment Command

```bash
./scripts/deploy-api-updates.sh
```

This will:
1. Copy all updated API files
2. Copy new utility files (verification, OCR verifier, etc.)
3. Copy config files
4. Copy updated storage files
5. Copy files into Docker container
6. Restart the container

## After Deployment

Wait 10-15 seconds, then test:

```bash
# Get document ID
DOC_ID=$(curl -s http://44.221.84.58:8500/documents | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['documents'][0]['document_id'] if d.get('documents') else '')")

# Test accuracy endpoint
curl -s "http://44.221.84.58:8500/documents/$DOC_ID/accuracy" | python3 -m json.tool
```

If it works, you'll see JSON response. If you still get "Not Found", check:
1. Container logs: `ssh user@server "sudo docker logs aris-rag-app"`
2. Container status: `ssh user@server "sudo docker ps | grep aris-rag-app"`

## Files Being Deployed

- ✅ api/main.py (with new endpoints)
- ✅ api/schemas.py (with new schemas)
- ✅ utils/pdf_metadata_extractor.py
- ✅ utils/pdf_content_extractor.py
- ✅ utils/ocr_verifier.py
- ✅ utils/ocr_auto_fix.py
- ✅ config/accuracy_config.py
- ✅ storage/document_registry.py (with version tracking)
- ✅ vectorstores/opensearch_images_store.py (with OCR quality metrics)

## Test After Deployment

```bash
# Quick test script
./test_endpoints_curl.sh
```
