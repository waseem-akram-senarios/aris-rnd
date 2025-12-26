# Postman Response Guide - Understanding Null Values

## Important: Null Values Are Expected for Some Fields

When querying the API in Postman, you may see `null` values for some fields. **This is normal and expected behavior.**

## Query Response Structure

### Main Response Fields (Never Null)

These fields **always** have values:

```json
{
  "answer": "string - The answer to your question",
  "sources": ["list", "of", "source", "files"],
  "citations": [/* array of citation objects */],
  "num_chunks_used": 12,
  "response_time": 16.34,
  "context_tokens": 18702,
  "response_tokens": 432,
  "total_tokens": 19134
}
```

### Citation Fields

#### Always Present (Never Null)
- `id`: Integer citation ID
- `source`: String - document name
- `snippet`: String - preview text
- `full_text`: String - complete text
- `source_location`: String - location description
- `content_type`: String - "text" or "image"

#### Optional (Can Be Null)
- `page`: Integer or null - page number (null if not available)
- `image_ref`: Object or null - **null for text citations, object for image citations**
- `image_info`: String or null - **null for text citations, string for image citations**
- `source_confidence`: Float or null - confidence score
- `page_confidence`: Float or null - page confidence score
- `section`: String or null - section heading
- `start_char`: Integer or null - character start position
- `end_char`: Integer or null - character end position
- `chunk_index`: Integer or null - chunk index
- `extraction_method`: String or null - extraction method used
- `similarity_score`: Float or null - similarity score

## Example Responses

### Text Citation (image_ref and image_info are null - this is correct!)

```json
{
  "id": 1,
  "source": "document.pdf",
  "page": 3,
  "snippet": "Text preview...",
  "full_text": "Complete text...",
  "source_location": "Page 3",
  "content_type": "text",
  "image_ref": null,  // ✅ NULL is correct for text citations
  "image_info": null  // ✅ NULL is correct for text citations
}
```

### Image Citation (image_ref and image_info have values)

```json
{
  "id": 6,
  "source": "FL10.11 SPECIFIC8 (1).pdf",
  "page": 39,
  "snippet": "Tool reorder sheet...",
  "full_text": "Complete OCR text...",
  "source_location": "Page 39 | Image 1",
  "content_type": "image",
  "image_ref": {  // ✅ Has value for image citations
    "page": 39,
    "image_index": 1,
    "source": "FL10.11 SPECIFIC8 (1).pdf"
  },
  "image_info": "Image 1 on Page 39"  // ✅ Has value for image citations
}
```

## Why Some Fields Are Null

1. **image_ref and image_info**: These are only populated for citations that come from images. For regular text citations, they are `null` (this is correct!).

2. **page**: May be `null` if page number couldn't be determined from the document.

3. **Other optional fields**: May be `null` if not available or not applicable.

## How to Verify Your Response is Working

### ✅ Good Response (Working Correctly)
```json
{
  "answer": "The document contains...",  // ✅ Has value
  "sources": ["doc1.pdf", "doc2.pdf"],  // ✅ Has values
  "citations": [/* array with items */],  // ✅ Has items
  "num_chunks_used": 5,  // ✅ Has value
  "response_time": 12.5  // ✅ Has value
}
```

### ❌ Bad Response (Not Working)
```json
{
  "answer": null,  // ❌ Should never be null
  "sources": null,  // ❌ Should never be null
  "citations": null,  // ❌ Should never be null
  "num_chunks_used": null  // ❌ Should never be null
}
```

## Testing in Postman

1. **Check the main fields first**:
   - `answer` should have text
   - `sources` should be an array
   - `citations` should be an array

2. **Check citations**:
   - Each citation should have `id`, `source`, `snippet`, `full_text`
   - `image_ref` and `image_info` will be `null` for text citations (this is OK!)
   - `image_ref` and `image_info` will have values for image citations

3. **If you see null in required fields**:
   - Check if documents are uploaded
   - Check if the query is formatted correctly
   - Check the response status code (should be 200)

## Common Issues

### Issue: "All fields are null"
**Solution**: 
- Verify documents are uploaded: `GET /documents`
- Check request format matches the schema
- Verify `Content-Type: application/json` header

### Issue: "image_ref is always null"
**Solution**: 
- This is normal for text citations
- Query with image-related questions to get image citations
- Use `POST /query/images` to get images directly

### Issue: "No answer returned"
**Solution**:
- Check if documents exist: `GET /documents`
- Verify the question is clear and specific
- Check response status code (should be 200, not 400 or 500)

## Quick Test

Try this in Postman:

```json
POST /query
{
  "question": "What is this document about?",
  "k": 5
}
```

**Expected Response**:
- ✅ `answer`: String with text
- ✅ `sources`: Array with document names
- ✅ `citations`: Array with citation objects
- ✅ `num_chunks_used`: Number
- ✅ `response_time`: Number
- ⚠️ `image_ref` and `image_info` in citations: May be `null` (this is OK for text citations!)

## Summary

- **Main response fields** (answer, sources, citations, etc.) should **never** be null
- **image_ref and image_info** in citations are **expected to be null** for text citations
- **image_ref and image_info** will have values for image citations
- If you see null in required fields, check your request format and document upload status



