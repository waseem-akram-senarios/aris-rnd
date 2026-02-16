# Intelycx Email MCP Server

FastMCP-based email server for the Intelycx ARIS agent system.

## Features

- **Single `send_email` tool** with flexible recipient support
- **Multiple recipient formats**: strings, lists, or objects with name/email
- **CC/BCC support** with same flexible formats
- **HTML/Plain text** email support
- **Built with FastMCP** for minimal boilerplate and maximum performance

## Tool: `send_email`

Send emails with flexible recipient formats.

### Parameters

- `to` (required): Recipients - string, list of strings, or list of dicts with email/name
- `subject` (required): Email subject line
- `body` (required): Email body content
- `cc` (optional): CC recipients - same formats as 'to'
- `bcc` (optional): BCC recipients - same formats as 'to'  
- `is_html` (optional): Whether body is HTML format (default: False)

### Examples

```json
// Simple email
{
  "to": "user@example.com",
  "subject": "Hello",
  "body": "Hello World!"
}

// Multiple recipients with names
{
  "to": [
    {"email": "user1@example.com", "name": "User One"},
    {"email": "user2@example.com", "name": "User Two"}
  ],
  "subject": "Team Update",
  "body": "<h1>Important Update</h1><p>Please review...</p>",
  "is_html": true
}

// With CC and BCC
{
  "to": "recipient@example.com",
  "subject": "Project Status", 
  "body": "Here's the latest update...",
  "cc": ["manager@example.com"],
  "bcc": ["archive@example.com"]
}
```

## Environment Variables

- `SMTP_HOST`: SMTP server host (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP server port (default: 587)
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `SMTP_USE_TLS`: Use TLS encryption (default: true)

## Health Check

The server includes a custom health check endpoint at `GET /health` that returns:

```json
{
  "status": "healthy",
  "service": "intelycx-email-mcp-server", 
  "version": "0.1.0",
  "transport": "http",
  "smtp_configured": true,
  "timestamp": "2024-08-26T00:00:00Z"
}
```

This endpoint is used by Docker health checks and monitoring systems.

## Development

```bash
# Install dependencies
pip install -e .

# Run server
python -m app.server

# Or use the entry point
intelycx-email-mcp-server

# Test health endpoint
curl http://localhost:8081/health
```

## Docker

```bash
# Build
docker build -t aris-mcp-intelycx-email:dev .

# Run
docker run -p 8081:8081 -e SMTP_USER=your@email.com aris-mcp-intelycx-email:dev
```

The server will be available at `http://localhost:8081/mcp`.
