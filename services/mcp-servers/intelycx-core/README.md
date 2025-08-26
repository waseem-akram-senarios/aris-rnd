# Intelycx Core MCP Server

HTTP-based MCP (Model Context Protocol) server for Intelycx Core manufacturing data API.

## Features

- **Machine Information**: Get detailed machine status, specifications, and maintenance data
- **Machine Groups**: Access production line and machine group information
- **Production Summary**: Retrieve production metrics and performance data
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
    "name": "get_machine",
    "arguments": {
      "machine_id": "M001"
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

1. **get_machine**: Get machine information by ID
2. **get_machine_group**: Get machine group details by ID  
3. **get_production_summary**: Get production metrics and summaries

## Environment Variables

- `INTEELYCX_CORE_BASE_URL`: Base URL for Intelycx Core API (default: https://api.intelycx.com)
- `INTEELYCX_CORE_API_KEY`: API key for Intelycx Core API
- `MCP_API_KEY`: API key for MCP server authentication (default: mcp-dev-key-12345)

## Development

```bash
# Install dependencies
pip install -e .

# Run server
intelycx-core-mcp-server

# Or run directly
python -m app.main
```

## Docker

```bash
# Build image
docker build -t intelycx-core-mcp-server .

# Run container
docker run -p 8080:8080 \
  -e INTEELYCX_CORE_API_KEY=your-api-key \
  -e MCP_API_KEY=your-mcp-key \
  intelycx-core-mcp-server
```
