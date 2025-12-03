# PyMuPDF Progress Tracking & Hanging Fix

## Problem
1. **PyMuPDF was hanging** - Users reported that PyMuPDF parser would get stuck in "processing" state with no feedback
2. **No progress updates** - Users had no idea what was happening during processing
3. **Unknown status** - UI showed "processing" but no details about progress

## Solution

### 1. Added Progress Callback Support
- PyMuPDF parser now accepts an optional `progress_callback` parameter
- Provides step-by-step progress updates throughout processing
- Updates shown in real-time in the Streamlit UI

### 2. Step-by-Step Progress Updates

The parser now reports progress at each stage:

1. **Opening PDF** (0%): "🔍 Opening PDF document..."
2. **Opening file** (5%): "📄 Opening PDF file..."
3. **Page count** (10%): "📖 Found X pages. Starting extraction..."
4. **Processing pages** (10-95%): "📄 Processing page X/Y..."
   - Updates every 5 pages or every 2 seconds
   - Shows current page and total pages
5. **Combining text** (95%): "📝 Combining extracted text..."
6. **Complete** (100%): "✅ Completed! Extracted X/Y pages"

### 3. Improved Timeout Handling

- **Reduced timeout**: 5 minutes (from 10 minutes)
- **Better monitoring**: Checks progress every 0.5 seconds
- **Warning at 9m 40s**: Alerts if processing is taking too long
- **Clear error messages**: Explains timeout and suggests alternatives

### 4. Real-Time UI Updates

- **Main status**: Shows overall progress (parsing, chunking, embedding)
- **Detailed status**: Shows specific parser progress (e.g., "Processing page 5/49...")
- **Progress bar**: Visual progress indicator
- **Time elapsed**: Shows elapsed time during processing

## Code Changes

### `parsers/pymupdf_parser.py`
- Added `progress_callback` parameter to `parse()` method
- Progress updates at each stage of processing
- Periodic updates every 2 seconds or every 5 pages
- Better timeout monitoring with warnings

### `parsers/parser_factory.py`
- Updated `parse_with_fallback()` to accept `progress_callback`
- Passes callback to parsers that support it
- Uses `inspect` to check if parser supports progress callbacks

### `ingestion/document_processor.py`
- Creates wrapper callback to map parser progress to overall progress
- Forwards detailed messages from parser to UI
- Maps parser progress (0-100%) to parsing phase (25-45% of total)

### `app.py`
- Updated progress callback to accept `detailed_message` parameter
- Shows detailed status in separate info box
- Better status messages for PyMuPDF parser

## User Experience

### Before
- ❌ UI shows "Processing..." with no details
- ❌ No idea if it's working or stuck
- ❌ No progress indication
- ❌ Timeout after 10 minutes with no warning

### After
- ✅ Real-time progress updates: "Processing page 5/49..."
- ✅ Clear status messages at each stage
- ✅ Visual progress bar showing completion percentage
- ✅ Time elapsed shown during processing
- ✅ Warning if processing is taking too long
- ✅ Clear error messages with suggestions

## Example Progress Flow

```
🔍 Opening PDF document... (0%)
📄 Opening PDF file... (5%)
📖 Found 49 pages. Starting extraction... (10%)
📄 Processing page 5/49... (15%)
📄 Processing page 10/49... (20%)
📄 Processing page 15/49... (25%)
...
📝 Combining extracted text... (95%)
✅ Completed! Extracted 49/49 pages (100%)
```

## Testing

Test with the benchmark document:
```bash
# On server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
sudo docker exec -it aris-rag-app python -c "
from parsers.pymupdf_parser import PyMuPDFParser
parser = PyMuPDFParser()

def progress_cb(msg, p):
    print(f'{p*100:.0f}%: {msg}')

result = parser.parse('samples/FL10.11 SPECIFIC8 (1).pdf', progress_callback=progress_cb)
print(f'Success: {result.pages} pages, {len(result.text)} chars')
"
```

## Deployment

✅ **Deployed**: Latest code with progress tracking is now live on server
- URL: http://35.175.133.235/
- Status: Running and healthy
- Timeout: 5 minutes (reduced from 10)
- Progress updates: Every 2 seconds or every 5 pages

## Next Steps

1. **Test in UI**: Upload a PDF and verify progress updates appear
2. **Monitor logs**: Check server logs for detailed progress information
3. **User feedback**: Collect feedback on progress visibility

## Notes

- Progress callback is optional - parsers without it still work
- Timeout reduced to 5 minutes for faster failure detection
- Progress updates don't slow down processing (non-blocking)
- Detailed messages help users understand what's happening




