# Postman Troubleshooting - Null Values Issue

## Quick Check

If you're seeing null values in Postman, follow these steps:

### Step 1: Verify Documents Exist

**Request**:
```
GET http://44.221.84.58:8500/documents
```

**Expected Response**:
```json
{
  "documents": [
    {
      "document_id": "...",
      "document_name": "...",
      "status": "success",
      "chunks_created": 47,
      "image_count": 13
    }
  ],
  "total": 1
}
```

**If you see empty array or no documents**: Upload a document first!

### Step 2: Test Basic Query

**Request**:
```
POST http://44.221.84.58:8500/query
Content-Type: application/json

{
  "question": "What is this document about?",
  "k": 5
}
```

**Expected Response Structure**:
```json
{
  "answer": "string with answer",  // ✅ Should NOT be null
  "sources": ["doc1.pdf", "doc2.pdf"],  // ✅ Should NOT be null
  "citations": [/* array */],  // ✅ Should NOT be null
  "num_chunks_used": 5,  // ✅ Should NOT be null
  "response_time": 12.5,  // ✅ Should NOT be null
  "context_tokens": 1000,  // ✅ Should NOT be null
  "response_tokens": 200,  // ✅ Should NOT be null
  "total_tokens": 1200  // ✅ Should NOT be null
}
```

### Step 3: Check Citation Fields

In each citation, these fields should **NOT be null**:
- `id`: Integer
- `source`: String
- `snippet`: String
- `full_text`: String
- `source_location`: String
- `content_type`: String ("text" or "image")

These fields **CAN be null** (this is normal):
- `page`: May be null
- `image_ref`: **null for text citations** (this is correct!)
- `image_info`: **null for text citations** (this is correct!)

## Common Issues and Solutions

### Issue 1: "answer is null"

**Possible Causes**:
- No documents uploaded
- Request format incorrect
- Server error

**Solution**:
1. Check documents: `GET /documents`
2. Verify request JSON is valid
3. Check response status code (should be 200)

### Issue 2: "All citation fields are null"

**Possible Causes**:
- Citation model validation failing
- Response not being parsed correctly

**Solution**:
1. Check response status code
2. Look at raw response body
3. Verify Content-Type header is `application/json`

### Issue 3: "image_ref is always null"

**This is NORMAL!** 
- `image_ref` is only populated for image citations
- Text citations will have `image_ref: null`
- To get image citations, query with image-related questions

## Test Request Examples

### Example 1: Basic Query (Should Work)

```json
POST http://44.221.84.58:8500/query
Content-Type: application/json

{
  "question": "What is this document about?",
  "k": 5
}
```

**Check**:
- Status: 200
- `answer`: Has text (not null)
- `sources`: Array with items (not null)
- `citations`: Array with items (not null)

### Example 2: Query with document_id

```json
POST http://44.221.84.58:8500/query
Content-Type: application/json

{
  "question": "test",
  "k": 3,
  "document_id": "YOUR_DOCUMENT_ID_HERE"
}
```

**Check**:
- Status: 200
- `answer`: Has text
- `citations`: Has items

### Example 3: Image Query

```json
POST http://44.221.84.58:8500/query/images
Content-Type: application/json

{
  "question": "",
  "source": "FL10.11 SPECIFIC8 (1).pdf",
  "k": 10
}
```

**Check**:
- Status: 200
- `images`: Array with items
- `total`: Number > 0

## What to Check in Postman

1. **Request Tab**:
   - Method: POST
   - URL: Correct endpoint
   - Headers: `Content-Type: application/json`
   - Body: Raw JSON (not form-data)

2. **Response Tab**:
   - Status: 200 OK
   - Body: JSON format
   - Check if response is actually null or just has null in optional fields

3. **Console/Network**:
   - Check for errors
   - Verify request was sent correctly

## Expected vs Actual

### ✅ Expected (Working)
```json
{
  "answer": "The document contains...",
  "sources": ["doc.pdf"],
  "citations": [
    {
      "id": 1,
      "source": "doc.pdf",
      "snippet": "text...",
      "image_ref": null,  // ✅ OK - this is a text citation
      "image_info": null  // ✅ OK - this is a text citation
    }
  ]
}
```

### ❌ Problem (Not Working)
```json
{
  "answer": null,  // ❌ Should have text
  "sources": null,  // ❌ Should be array
  "citations": null  // ❌ Should be array
}
```

## Still Having Issues?

1. **Check server logs**: Look for errors
2. **Test with curl**: Verify API works outside Postman
3. **Check Postman version**: Update if outdated
4. **Verify JSON format**: Use a JSON validator
5. **Check network**: Ensure you can reach the server

## Quick Verification Script

Run this to verify API is working:

```bash
curl -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "k": 3}' \
  | python3 -m json.tool
```

If this works but Postman doesn't, the issue is with Postman configuration.



