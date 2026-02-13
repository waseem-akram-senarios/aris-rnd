# Intelycx File Generator MCP Server

A FastMCP-based service for creating PDF files with S3 storage backend.

## Features

- **PDF Generation**: Create PDFs with title and content using ReportLab
- **S3 Storage**: Files stored in S3 with organized folder structure
- **File Organization**: Files stored in `/chats/{chat_id}/{filename}` structure
- **FastMCP Integration**: Full MCP protocol support with context notifications
- **Security**: Non-root container, encrypted S3 storage

## Tools Available

### `create_pdf`
Create a PDF document with title and content.

**Parameters:**
- `title`: Document title
- `content`: Main text content  
- `chat_id`: Chat ID for file organization
- `filename`: Optional custom filename
- `author`: Optional document author
- `subject`: Optional document subject

## Environment Variables

```bash
# Storage Configuration
STORAGE_DRIVER=s3                              # Storage backend (default: s3)
S3_BUCKET_NAME=iris-batch-001-data-975049910508  # S3 bucket name

# AWS Configuration  
AWS_REGION=us-east-2                           # AWS region
AWS_ACCESS_KEY_ID=your_access_key              # AWS credentials
AWS_SECRET_ACCESS_KEY=your_secret_key          # AWS credentials

# Server Configuration
HOST=0.0.0.0                                  # Server host
PORT=8080                                     # Server port
```

## Usage Examples

```python
# Create a PDF
result = await agent.execute_tool("create_pdf", {
    "title": "Production Report",
    "content": "Daily production summary...",
    "chat_id": "user-123",
    "author": "ARIS Agent"
})
```

## File Storage Structure

Files are organized in S3 as:
```
s3://bucket-name/
└── chats/
    ├── user-123/
    │   ├── production_report.pdf
    │   └── dashboard.pdf
    └── user-456/
        └── analysis.pdf
```

## Development

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```

2. Update environment variables in `.env`

3. Run with Docker:
   ```bash
   docker-compose up aris-mcp-intelycx-file-generator
   ```

4. Test health endpoint:
   ```bash
   curl http://localhost:8082/health
   ```
