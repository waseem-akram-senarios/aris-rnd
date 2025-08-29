# Intelycx Email MCP Server

HTTP-based MCP (Model Context Protocol) server for Intelycx Email communication service.

## Features

- **Email Sending**: Send emails with full control over recipients, content, and formatting
- **Simple Email**: Quick email sending with minimal parameters
- **HTML Support**: Send both plain text and HTML formatted emails
- **Multiple Recipients**: Support for TO, CC, and BCC recipients
- **Logging Mode**: Currently logs email details instead of actually sending (for development)
- **HTTP API**: RESTful interface with MCP protocol support
- **Authentication**: API key-based security
- **Health Monitoring**: Built-in health check endpoint

## API Endpoints

### Health Check
```
GET /health
```

### MCP Protocol
```
POST /mcp
Authorization: Bearer <api-key>
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "send_simple_email",
    "arguments": {
      "to_email": "user@example.com",
      "subject": "Test Email",
      "body": "This is a test email from the MCP server."
    }
  },
  "id": "1"
}
```

### List Tools
```
GET /tools
Authorization: Bearer <api-key>
```

## Available Tools

1. **send_email**: Send an email with full control over recipients, subject, body, and formatting
   - Supports multiple TO, CC, BCC recipients
   - HTML and plain text content
   - Comprehensive recipient management

2. **send_simple_email**: Send a simple email to a single recipient
   - Quick and easy for notifications
   - Minimal parameters required
   - Ideal for alerts and simple messages

## Tool Examples

### Send Simple Email
```json
{
  "name": "send_simple_email",
  "arguments": {
    "to_email": "user@example.com",
    "subject": "Production Alert",
    "body": "Machine M001 requires maintenance attention.",
    "to_name": "John Smith"
  }
}
```

### Send Complex Email
```json
{
  "name": "send_email",
  "arguments": {
    "to": [
      {"email": "manager@example.com", "name": "Production Manager"},
      {"email": "operator@example.com", "name": "Machine Operator"}
    ],
    "cc": [
      {"email": "supervisor@example.com", "name": "Supervisor"}
    ],
    "subject": "Daily Production Report",
    "body": "<h1>Production Summary</h1><p>Today's production metrics...</p>",
    "is_html": true
  }
}
```

## Environment Variables

- `SMTP_HOST`: SMTP server hostname (default: smtp.gmail.com)
- `SMTP_PORT`: SMTP server port (default: 587)
- `SMTP_USER`: SMTP username for authentication
- `SMTP_PASSWORD`: SMTP password for authentication
- `SMTP_USE_TLS`: Use TLS encryption (default: true)
- `MCP_API_KEY`: API key for MCP server authentication (default: mcp-dev-key-12345)

## Development Mode

Currently, the server operates in **logging mode** - it logs all email details instead of actually sending emails. This is perfect for development and testing without sending real emails.

## Development

```bash
# Install dependencies
pip install -e .

# Run server
intelycx-email-mcp-server

# Or run directly
python -m app.main
```

## Docker

```bash
# Build image
docker build -t intelycx-email-mcp-server .

# Run container
docker run -p 8081:8081 \
  -e SMTP_USER=your-smtp-user \
  -e SMTP_PASSWORD=your-smtp-password \
  -e MCP_API_KEY=your-mcp-key \
  intelycx-email-mcp-server
```

## Production Setup

To enable actual email sending in production:

1. Set proper SMTP credentials in environment variables
2. Modify the `EmailClient.send_email()` method to use actual SMTP sending
3. Add proper error handling and retry logic
4. Consider using email service providers like SendGrid, AWS SES, etc.
