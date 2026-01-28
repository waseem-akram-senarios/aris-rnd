# Re-Ingest All Documents for Correct Page Numbers

## Root Cause

**All existing documents were ingested BEFORE the page metadata fixes were deployed.**

The fixes we implemented will only work for **newly ingested documents**. Existing documents in OpenSearch have `pages: null` and no page metadata stored in their chunks.

## Evidence

- **VUORMAR.pdf**: Citation shows "Page 1" but content says "VUORMAR Page 10" ❌
- **X90 PDF**: Citation shows "Page 1" for all content ❌
- **All other documents**: Likely have the same issue ❌

## What Was Fixed (Now Deployed)

1. ✅ OpenSearch metadata extraction - reads `page`, `source_page`, `start_char`, `end_char` from search results
2. ✅ Similarity percentage calculation - shows "N/A" instead of misleading 100%
3. ✅ Filename resolution - always uses latest document_id
4. ✅ Page extraction logic - uses character positions and page_blocks for accuracy

## Solution: Re-Ingest All Documents

### Option 1: Re-upload via UI
1. Go to http://44.221.84.58
2. Upload each document again (use same filename)
3. The system will create a new document_id with proper page metadata

### Option 2: Re-upload via API (Bulk Script)

```bash
#!/bin/bash
# Save as: reingest_all_documents.sh

# Define documents to re-ingest
DOCUMENTS=(
    "VUORMAR.pdf"
    "1762860333_1762273725_model_x90_polymer_enclosure_specs.pdf"
    "Large_Marine_Ecosystem_Approach_22062017.pdf"
    # Add all other documents here
)

GATEWAY_URL="http://44.221.84.58:8500"

for doc in "${DOCUMENTS[@]}"; do
    echo "Re-ingesting: $doc"
    
    # Check if file exists locally
    if [ -f "$doc" ]; then
        curl -X POST "$GATEWAY_URL/documents" \
          -F "file=@$doc" \
          -F "parser_preference=ocrmypdf"
        echo ""
        echo "✅ Submitted: $doc"
        sleep 5  # Wait between uploads
    else
        echo "❌ File not found: $doc"
    fi
    echo "---"
done

echo "✅ All documents submitted for re-ingestion"
```

### Option 3: Get Document List and Re-upload

```bash
# Get list of all documents currently in the system
curl -X GET http://44.221.84.58:8500/documents | \
  python3 -c "import sys, json; docs = json.load(sys.stdin).get('documents', []); [print(d.get('document_name')) for d in docs]"
```

## How to Verify Fix Worked

After re-ingesting a document, query it and check:

```bash
# Query VUORMAR.pdf
curl -X POST http://44.221.84.58:8500/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "What does the text say about Desbobinador Apagado?",
    "k": 3,
    "active_sources": ["VUORMAR.pdf"]
  }' | python3 -m json.tool
```

**Expected result**:
- Citation should show **Page 10** (not Page 1) ✅
- Content matches the page number ✅
- `page_confidence` and `page_extraction_method` fields present ✅

## Why Re-Ingestion Is Required

When documents are processed, the system:

1. **Parsing**: OCRmyPDF extracts text and creates `page_blocks` with start_char, end_char, and page numbers
2. **Chunking**: Tokenizer splits text and assigns page metadata to each chunk using page_blocks
3. **Storage**: OpenSearch stores chunks with metadata (page, source_page, start_char, end_char)
4. **Retrieval**: Search results extract page numbers from chunk metadata

**Old documents** (ingested before fixes):
- ❌ Missing page metadata in OpenSearch chunks
- ❌ Retrieval engine falls back to Page 1

**New documents** (ingested after fixes):
- ✅ Complete page metadata stored
- ✅ Accurate page extraction during retrieval

## Alternative: Keep Old Documents

If you don't want to re-ingest:
- Old documents will continue showing "Page 1" for all citations
- New documents uploaded from now on will have correct page numbers
- The system will work, but page accuracy will be incomplete

## Recommendation

**Re-ingest all critical documents** that need accurate page citations, especially:
1. VUORMAR.pdf
2. X90 Polymer Enclosure Specs
3. Any multi-page technical documents
4. Documents where page references are important

Single-page documents can stay as-is (Page 1 is always correct).
