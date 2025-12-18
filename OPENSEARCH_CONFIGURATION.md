# OpenSearch Configuration for FastAPI

## ✅ Configuration Complete

The FastAPI application is now configured to use **OpenSearch** as the vector database by default.

### Configuration Details

1. **Default Vector Store**: OpenSearch (configured in `config/settings.py`)
   - Default: `VECTOR_STORE_TYPE=opensearch`

2. **OpenSearch Settings**:
   - Domain: `intelycx-waseem-os` (default)
   - Index: `aris-rag-index` (default)
   - Region: `us-east-2` (default)

3. **Query Endpoint Enhancement**:
   - Now properly handles OpenSearch even when vectorstore is None
   - Automatically initializes OpenSearch connection on query
   - Works with documents stored in OpenSearch cloud

### Environment Variables Required

Make sure these are set in your `.env` file:

```env
VECTOR_STORE_TYPE=opensearch
AWS_OPENSEARCH_DOMAIN=intelycx-waseem-os
AWS_OPENSEARCH_INDEX=aris-rag-index
AWS_OPENSEARCH_ACCESS_KEY_ID=your_access_key
AWS_OPENSEARCH_SECRET_ACCESS_KEY=your_secret_key
AWS_OPENSEARCH_REGION=us-east-2
OPENAI_API_KEY=your_openai_key
```

### How It Works

1. **On Startup**: FastAPI initializes OpenSearch connection
2. **On Document Upload**: Documents are stored in OpenSearch indexes
3. **On Query**: 
   - If vectorstore is None, it attempts to initialize
   - Queries OpenSearch indexes directly
   - Works even if vectorstore object is None (OpenSearch is cloud-based)

### Testing

The query endpoint now:
- ✅ Checks for OpenSearch domain configuration
- ✅ Initializes OpenSearch connection if needed
- ✅ Allows queries even if vectorstore object is None (for OpenSearch)
- ✅ Returns appropriate errors if no documents exist

### Status

✅ **OpenSearch is now the default and working vector database for FastAPI**

