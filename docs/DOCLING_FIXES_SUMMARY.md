# Docling Processing Fixes - Summary

## Issues Fixed

### 1. ✅ No Fallback When Docling is Explicitly Selected
**Problem:** When Docling was explicitly selected, the system would fall back to PyMuPDF if Docling failed or timed out.

**Fix:** Modified `parsers/parser_factory.py` to:
- When Docling is explicitly selected, it will NOT fall back to PyMuPDF
- If Docling fails or times out, it will raise an error instead of falling back
- User gets clear error message about what went wrong

**Code Change:**
```python
# If specific parser requested, use it WITHOUT fallback
if preferred_parser and preferred_parser.lower() != 'auto':
    parser = cls.get_parser(file_path, preferred_parser)
    if parser:
        try:
            return parser.parse(file_path, file_content)
        except Exception as e:
            # Raise error instead of falling back
            raise ValueError(f"{preferred_parser.capitalize()} parser failed: {error_msg}")
```

### 2. ✅ Enhanced Logging for Docling Processing
**Problem:** Limited visibility into Docling processing progress.

**Fix:** Added detailed logging in `parsers/docling_parser.py`:
- Logs when conversion starts
- Logs file being processed
- Logs when conversion completes
- Logs document access and page count
- Better error logging

### 3. ✅ Increased Timeouts for Document Processing
**Problem:** Nginx was timing out after 60 seconds, but Docling can take 5-15 minutes.

**Fix:** Updated Nginx configuration:
- `proxy_read_timeout`: 60s → 1200s (20 minutes)
- `proxy_send_timeout`: 60s → 1200s (20 minutes)
- `keepalive_timeout`: 65s → 1200s (20 minutes)

### 4. ✅ Streamlit Configuration for Long Operations
**Fix:** Updated `.streamlit/config.toml`:
- Disabled fast reruns during long operations
- Configured for long-running document processing

## Testing

### Automated Test Created
Created `tests/test_document_processing_e2e.py` to verify:
- Docling doesn't fall back when explicitly selected
- Docling completes successfully
- Proper error handling

### How to Test on Server
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
sudo docker exec -it aris-rag-app python3 tests/test_document_processing_e2e.py
```

## Current Status

✅ **Fixes Deployed:**
- Parser factory updated (no fallback for explicit Docling)
- Enhanced Docling logging
- Nginx timeouts increased to 20 minutes
- Streamlit configured for long operations
- Container restarted with new code

✅ **Application URL:**
- http://35.175.133.235/

## Expected Behavior

### When Docling is Explicitly Selected:
1. ✅ System uses ONLY Docling (no fallback to PyMuPDF)
2. ✅ If Docling succeeds → Returns Docling result
3. ✅ If Docling fails/times out → Raises error (does NOT fall back)
4. ✅ User sees clear error message

### When "Auto" is Selected:
1. ✅ System tries PyMuPDF first
2. ✅ If results are poor, tries Docling
3. ✅ Falls back to PyMuPDF if Docling fails

## Monitoring

### Check Logs:
```bash
# Streamlit logs
sudo docker logs -f aris-rag-app

# Look for:
# - "Docling: Starting conversion"
# - "Docling: Conversion completed"
# - "Docling: Document conversion successful"
```

### Check Processing Status:
```bash
# Container status
sudo docker ps --filter "name=aris-rag"

# Resource usage
sudo docker stats aris-rag-app
```

## Notes

- Docling processing can take 5-15 minutes for large documents (this is normal)
- Nginx will now wait up to 20 minutes for responses
- If Docling times out after 15 minutes, user will see an error (no automatic fallback)
- Enhanced logging helps diagnose any processing issues



