# Intelycx RAG Knowledge Base MCP Server

FastMCP server for document ingestion and semantic search using AWS Bedrock, OpenSearch, and PostgreSQL.

## Features

- **Document Ingestion**: Process documents from S3 with semantic chunking
- **Vector Search**: Semantic similarity search using Titan embeddings
- **Hybrid Search**: Combined vector and keyword search
- **Knowledge Management**: Track documents and chunks in PostgreSQL
- **Manufacturing Focus**: Optimized for manufacturing domain knowledge

## Tools

### `ingest_document`
Ingest a document from S3 into the knowledge base with semantic chunking and vector indexing.

### `search_knowledge_base`
Search the knowledge base using semantic similarity and hybrid search techniques.

## Configuration

Environment variables:
- `OPENSEARCH_ENDPOINT`: OpenSearch cluster endpoint
- `S3_DOCUMENT_BUCKET`: S3 bucket for documents
- `EMBEDDING_MODEL`: Bedrock embedding model (default: amazon.titan-embed-text-v2:0)
- `DATABASE_URL`: PostgreSQL connection string

## Development

```bash
pip install -e .
intelycx-rag-mcp-server
```
