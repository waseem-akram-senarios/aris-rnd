# How to Import Postman Collection

## Updated Collection File

**File**: `postman_collection_updated.json`

This collection includes all **17 API endpoints** organized into 7 folders.

## Import into Postman

### Method 1: Postman Desktop App

1. Open Postman
2. Click **Import** button (top left)
3. Select **File** tab
4. Choose `postman_collection_updated.json`
5. Click **Import**

### Method 2: Postman Extension in Cursor/VS Code

1. Open Postman extension in Cursor/VS Code
2. Click **Import** button
3. Select `postman_collection_updated.json`
4. Collection will appear in sidebar

### Method 3: Drag and Drop

1. Open Postman
2. Drag `postman_collection_updated.json` into Postman window
3. Collection will be imported automatically

## Collection Structure

### 1. Core Endpoints (2)
- `GET /` - API information
- `GET /health` - Health check

### 2. Document Management (3)
- `POST /documents` - Upload document
- `GET /documents` - List all documents
- `DELETE /documents/{document_id}` - Delete document

### 3. Query Endpoints (3)
- `POST /query` - Query documents
- `POST /query/text` - Query text only
- `POST /query/images` - Query images

### 4. Image Endpoints (4)
- `GET /documents/{document_id}/images/all` - Get all images
- `GET /documents/{document_id}/images` - Get images summary
- `GET /documents/{document_id}/images/{image_number}` - Get image by number
- `POST /documents/{document_id}/store/images` - Store images (with file upload)

### 5. Page Endpoints (1)
- `GET /documents/{document_id}/pages/{page_number}` - Get page information

### 6. Storage Endpoints (2)
- `GET /documents/{document_id}/storage/status` - Get storage status
- `POST /documents/{document_id}/store/text` - Store text content

### 7. Verification Endpoints (2)
- `GET /documents/{document_id}/accuracy` - Check OCR accuracy
- `POST /documents/{document_id}/verify` - Verify document

## Variables

The collection includes these variables (update as needed):

- `base_url`: `http://44.221.84.58:8500`
- `document_id`: Example document ID (replace with actual)
- `image_number`: `1` (0-indexed)
- `page_number`: `1` (1-indexed)
- `parser`: `docling` (docling, pymupdf, textract, auto)

## Quick Start

1. **Import the collection**
2. **Update variables**:
   - Get a real `document_id` from `GET /documents`
   - Update `base_url` if different
3. **Start testing**:
   - Begin with `GET /health` to verify connection
   - Then `GET /documents` to see available documents
   - Use the `document_id` in other requests

## Testing Workflow

### 1. Upload a Document
```
POST /documents
- Add PDF file in form-data
- Set parser to "docling"
- Copy the document_id from response
```

### 2. Store Images
```
POST /documents/{document_id}/store/images
- Upload PDF file to extract images with OCR
- Wait for processing
```

### 3. Query Images
```
GET /documents/{document_id}/images/all
- See all images with OCR text
```

### 4. Get Page Information
```
GET /documents/{document_id}/pages/1
- Get all text and images from page 1
```

### 5. Check Accuracy
```
GET /documents/{document_id}/accuracy
- Verify OCR accuracy
```

## Tips

- **Save responses**: Right-click response → Save Response
- **Set variables from response**: Use Postman's "Set variable" feature
- **Use environment variables**: Create separate environments for dev/prod
- **Test in order**: Some endpoints depend on others (upload → store → query)

## Troubleshooting

- **404 Not Found**: Check `document_id` is correct
- **Connection Error**: Verify `base_url` is correct
- **Empty Results**: Make sure document is processed and images are stored
- **File Upload Issues**: Ensure file is selected in form-data

## Collection Features

✅ All 17 endpoints included
✅ Organized into logical folders
✅ Variables pre-configured
✅ Example requests with sample data
✅ Descriptions for each endpoint
✅ Ready to use immediately

