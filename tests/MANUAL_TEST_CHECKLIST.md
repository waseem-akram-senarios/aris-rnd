# Manual Testing Checklist

This document provides a step-by-step guide for manually testing the ARIS RAG system synchronization between FastAPI and Streamlit.

## Prerequisites

1. Ensure `.env` file is configured with `OPENAI_API_KEY`
2. Have a test PDF file ready (small file recommended for quick testing, 1-2 pages)
3. Both FastAPI and Streamlit should be able to run simultaneously

## Test 1: FastAPI Server Testing

### Step 1: Start FastAPI Server
```bash
cd /home/senarios/Desktop/aris
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected**: Server starts without errors, shows "Application startup complete"

### Step 2: Test Root Endpoint
```bash
curl http://localhost:8000/
```

**Expected**: Returns `{"message": "ARIS RAG API"}`

### Step 3: Test Health Endpoint
```bash
curl http://localhost:8000/health
```

**Expected**: Returns `{"status": "healthy"}`

### Step 4: Test Sync Status Endpoint
```bash
curl http://localhost:8000/sync/status
```

**Expected**: Returns JSON with:
- `document_registry` (total_documents, last_update, etc.)
- `vectorstore` (type, exists, path, etc.)
- `rag_stats` (system statistics)
- `conflicts` (null or conflict info)

### Step 5: Upload Document via API
```bash
curl -X POST "http://localhost:8000/documents" \
  -F "file=@/path/to/test.pdf" \
  -F "parser=auto"
```

**Expected**: 
- Status 201
- Document metadata returned with `document_id`
- Document saved to shared registry

### Step 6: Verify Document in Registry
```bash
curl http://localhost:8000/documents
```

**Expected**: List contains the uploaded document

### Step 7: Test Sync Endpoints
```bash
# Save vectorstore
curl -X POST http://localhost:8000/sync/save-vectorstore

# Reload vectorstore
curl -X POST http://localhost:8000/sync/reload-vectorstore

# Reload registry
curl -X POST http://localhost:8000/sync/reload-registry
```

**Expected**: All return success messages

## Test 2: Streamlit Integration

### Step 1: Start Streamlit (in new terminal)
```bash
cd /home/senarios/Desktop/aris
streamlit run app.py
```

**Expected**: Streamlit starts, opens browser at http://localhost:8501

### Step 2: Check Synchronization Status
1. Navigate to "📊 R&D Metrics & Analytics" section
2. Scroll to "🔄 Synchronization Status"
3. **Expected**: Should show document count from FastAPI (1 document if you uploaded one)

### Step 3: Query Document Processed in FastAPI
1. Go to "💬 Chat with Documents" section
2. Enter a query about the document you uploaded via FastAPI
3. **Expected**: Should get answer using the document processed in FastAPI

### Step 4: Upload Another Document in Streamlit
1. Upload a new document via Streamlit UI
2. Process it
3. **Expected**: 
   - Document processed successfully
   - Vectorstore saved automatically
   - Document count increases to 2
   - Success message shows "💾 Vectorstore saved to shared storage"

### Step 5: Verify in FastAPI
```bash
curl http://localhost:8000/documents
```

**Expected**: Should show 2 documents (one from FastAPI, one from Streamlit)

### Step 6: Test Manual Sync Buttons
1. In Streamlit, go to sync status section
2. Click "💾 Save Vectorstore" button
3. **Expected**: Success message "✅ Vectorstore saved to shared storage"
4. Click "🔄 Reload Vectorstore" button
5. **Expected**: Success message, registry reloaded

## Test 3: Cross-System Document Access

### Step 1: Process Document in FastAPI
```bash
curl -X POST "http://localhost:8000/documents" \
  -F "file=@/path/to/another-test.pdf" \
  -F "parser=pymupdf"
```

### Step 2: Query in Streamlit
1. In Streamlit, go to chat section
2. Query about the document processed in FastAPI
3. **Expected**: Answer generated using document from FastAPI

### Step 3: Process Document in Streamlit
1. Upload and process a document in Streamlit
2. **Expected**: Document processed and saved

### Step 4: Query in FastAPI
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?", "k": 5}'
```

**Expected**: Answer generated using document processed in Streamlit

## Test 4: Conflict Detection

### Step 1: Modify Registry Externally
```bash
# Edit the registry file directly (simulate external modification)
# This will trigger conflict detection
python3 -c "
import json
with open('storage/document_registry.json', 'r') as f:
    data = json.load(f)
data['_external_modification'] = 'test'
with open('storage/document_registry.json', 'w') as f:
    json.dump(data, f)
"
```

### Step 2: Check Conflict in Streamlit
1. Refresh Streamlit page
2. Check sync status section
3. **Expected**: Warning about conflict detected (if timing allows)

### Step 3: Resolve Conflict
1. Click "🔄 Reload Registry" button in Streamlit
2. **Expected**: Conflict resolved, registry reloaded

### Step 4: Verify in FastAPI
```bash
curl http://localhost:8000/sync/status
```

**Expected**: `conflicts` field shows conflict info or null

## Test 5: Configuration Synchronization

### Step 1: Check Config in FastAPI
```bash
curl http://localhost:8000/stats
```

Note the configuration values (embedding model, vector store type, etc.)

### Step 2: Check Config in Streamlit
1. Open Streamlit sidebar
2. Check default values for:
   - API selection (should match USE_CEREBRAS env var)
   - Models (should match OPENAI_MODEL, CEREBRAS_MODEL)
   - Embedding model (should match EMBEDDING_MODEL)
   - Chunking strategy (should match CHUNKING_STRATEGY)
   - Vector store (should match VECTOR_STORE_TYPE)

**Expected**: All defaults match environment variables/ARISConfig

## Test 6: Vectorstore Persistence

### Step 1: Process Document in Streamlit
1. Upload and process a document
2. **Expected**: Vectorstore saved automatically

### Step 2: Restart FastAPI
1. Stop FastAPI (Ctrl+C)
2. Restart FastAPI
3. **Expected**: FastAPI loads existing vectorstore on startup

### Step 3: Verify Documents Available
```bash
curl http://localhost:8000/documents
```

**Expected**: Documents from before restart are still available

### Step 4: Query Documents
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What documents are available?"}'
```

**Expected**: Can query documents processed before restart

## Success Criteria

✅ Documents uploaded in FastAPI appear in Streamlit  
✅ Documents uploaded in Streamlit appear in FastAPI  
✅ Queries work across both systems  
✅ Vectorstore is shared between systems  
✅ Configuration is consistent  
✅ Conflict detection works  
✅ Manual sync buttons work  
✅ All sync endpoints respond correctly  
✅ Data persists across restarts  
✅ Cross-system document access works

## Troubleshooting

### Issue: Documents not appearing in other system
- Check sync status endpoint: `curl http://localhost:8000/sync/status`
- Verify registry file exists: `ls -la storage/document_registry.json`
- Try manual reload: Click reload button or use `/sync/reload-registry` endpoint

### Issue: Vectorstore not loading
- Check vectorstore path: `ls -la vectorstore/`
- Verify path in config: Check `VECTORSTORE_PATH` env var
- Try manual reload: Use `/sync/reload-vectorstore` endpoint

### Issue: Conflicts not detected
- Conflicts are detected based on version timestamps
- May require external modification with time delay
- Check version file: `ls -la storage/document_registry.json.version`

### Issue: Configuration mismatch
- Verify `.env` file has correct values
- Check that both systems are reading from same config source
- Restart both systems after changing `.env`

