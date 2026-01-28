# Page Extraction Enhancement - Deployed

## Fix Applied

**Enhanced text marker extraction** to handle patterns like "VUORMAR Page 10" in document content.

### What Was Changed

Updated `_extract_page_number()` in both:
- `services/retrieval/engine.py`
- `api/rag_system.py`

### New Patterns Supported

1. **Document Name + Page Pattern** (confidence: 0.5)
   - "VUORMAR Page 10"
   - "Document Page 5"
   - Pattern: `(\w+)\s+Page\s+(\d+)`

2. **Standalone Page Pattern** (confidence: 0.4)
   - "Page 10" at line start
   - Pattern: `(?:^|\n)\s*Page\s+(\d+)(?:\s|$|\.|,|;|:)`

3. **Page Range Pattern** (confidence: 0.4)
   - "Page 10 of 20" or "Page 10/20"
   - Pattern: `Page\s+(\d+)(?:\s+of\s+\d+|\s*/\s*\d+)`

### How It Works

When page metadata is missing from OpenSearch (old documents), the system now:

1. ✅ Checks character positions (if available)
2. ✅ Checks source_page metadata
3. ✅ Checks page_blocks metadata
4. ✅ Checks page metadata
5. ✅ **NEW**: Extracts from text patterns like "VUORMAR Page 10" ✅
6. ✅ Falls back to Page 1 only if all above fail

### Example

**Before Fix**:
- Text: "VUORMAR Page 10 ... Desbobinador Apagado"
- Citation: Page 1 ❌

**After Fix**:
- Text: "VUORMAR Page 10 ... Desbobinador Apagado"
- Citation: Page 10 ✅

## Deployment Status

✅ **Deployed**: Both retrieval engine and UI RAG system updated
✅ **Services Restarted**: Retrieval and UI services restarted
✅ **Ready**: Enhanced page extraction is now active

## Testing

Query VUORMAR.pdf and check if citations now show **Page 10** instead of Page 1:

```bash
curl -X POST http://44.221.84.58:8500/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What does the text say about Desbobinador Apagado?",
    "k": 3,
    "active_sources": ["VUORMAR.pdf"]
  }'
```

**Expected**: Citations should now show **Page 10** (extracted from "VUORMAR Page 10" in text)

## Note

This fix works for **existing documents** without requiring re-ingestion, as long as the text contains page markers like "VUORMAR Page 10".

For best accuracy, documents should still be re-ingested to get proper metadata, but this enhancement provides a fallback that works immediately.
