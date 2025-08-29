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

#### Manufacturing Data Access
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

### Authentication
Authentication is handled automatically by the system using environment variables. No manual authentication tools are exposed to users.

### Manufacturing Data
1. **get_machine**: Get machine information by ID
2. **get_machine_group**: Get machine group details by ID  
3. **get_production_summary**: Get production metrics and summaries

**Note**: Authentication is handled automatically by the system using environment credentials.

## Authentication Flow

1. **Automatic Authentication**: The AI Agent automatically authenticates using stored environment credentials
2. **JWT Token Management**: JWT tokens are obtained and managed automatically by the system
3. **Transparent Access**: Manufacturing data tools work seamlessly without manual authentication
4. **Token Refresh**: Expired tokens are automatically renewed without user intervention
5. **System Attribution**: All API calls are made on behalf of the configured system user

### Benefits
- **Seamless Experience**: No manual authentication required from users
- **Automatic Token Management**: JWT tokens are handled transparently
- **System-Level Security**: Credentials are stored securely as environment variables
- **Reliable Access**: Automatic token refresh ensures continuous data availability

## Environment Variables

- `INTEELYCX_CORE_BASE_URL`: Base URL for Intelycx Core API (default: https://api.intelycx.com)
- `INTEELYCX_CORE_API_KEY`: API key for Intelycx Core API (legacy, may not be needed)
- `INTELYCX_CORE_USERNAME`: Username for Intelycx Core API authentication (required)
- `INTELYCX_CORE_PASSWORD`: Password for Intelycx Core API authentication (required)
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
