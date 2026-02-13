# Intelycx Core MCP Server

FastMCP-based server providing access to Intelycx Core manufacturing data and authentication.

## Features

- **JWT Authentication**: Login to Intelycx Core API and manage authentication tokens
- **Manufacturing Data Access**: Retrieve fake/sample data for testing and development
- **FastMCP Integration**: Modern MCP protocol implementation with HTTP transport
- **Docker Support**: Containerized deployment with health checks
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

## Tools

### `intelycx_login`
Authenticates with Intelycx Core API and returns a JWT token for subsequent API calls.

**Parameters:**
- `username` (optional): Username for authentication (defaults to `INTELYCX_CORE_USERNAME` env var)
- `password` (optional): Password for authentication (defaults to `INTELYCX_CORE_PASSWORD` env var)

**Returns:**
- `success`: Boolean indicating if login was successful
- `jwt_token`: JWT token for API authentication (if successful)
- `expires_in`: Token expiration time in seconds
- `expires_at`: ISO timestamp when token expires
- `user`: Username that was authenticated
- `error`: Error message (if unsuccessful)

### `get_fake_data`
Retrieves fake/sample manufacturing data from Intelycx Core API.

**Parameters:**
- `jwt_token` (required): Valid JWT token from `intelycx_login`
- `data_type` (optional): Type of data to retrieve (e.g., "machines", "production", "alerts")

**Returns:**
- `success`: Boolean indicating if request was successful
- `data`: The fake data response from the API (if successful)
- `data_type`: Type of data that was requested
- `timestamp`: ISO timestamp when data was retrieved
- `error`: Error message (if unsuccessful)
- `authentication_failed`: Boolean indicating if JWT token was invalid

## Environment Variables

- `INTELYCX_CORE_BASE_URL`: Base URL for Intelycx Core API (default: `http://intelycx-api-1:8000`)
- `INTELYCX_CORE_USERNAME`: Username for API authentication
- `INTELYCX_CORE_PASSWORD`: Password for API authentication
- `MCP_API_KEY`: API key for MCP server authentication (optional)

## Usage

### Development
```bash
# Install dependencies
pip install -e .

# Run the server
python -m app.server
```

### Docker
```bash
# Build image
docker build -t intelycx-core-mcp-server .

# Run container
docker run -p 8080:8080 \
  -e INTELYCX_CORE_BASE_URL=http://intelycx-api-1:8000 \
  -e INTELYCX_CORE_USERNAME=your_username \
  -e INTELYCX_CORE_PASSWORD=your_password \
  intelycx-core-mcp-server
```

### Tool Usage Example

```python
# 1. First, login to get JWT token
login_result = await client.call_tool("intelycx_login", {})
if login_result["success"]:
    jwt_token = login_result["jwt_token"]
    
    # 2. Use token to get data
    data_result = await client.call_tool("get_fake_data", {
        "jwt_token": jwt_token,
        "data_type": "machines"
    })
    
    if data_result["success"]:
        manufacturing_data = data_result["data"]
        print(f"Retrieved data: {manufacturing_data}")
```

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /mcp` - MCP protocol endpoint
- `GET /tools` - List available tools

## Authentication Flow

1. **Login**: Call `intelycx_login` tool to authenticate and receive JWT token
2. **Token Storage**: Store the JWT token for subsequent API calls
3. **API Access**: Use the JWT token with `get_fake_data` and other tools
4. **Token Refresh**: Re-authenticate when token expires (indicated by `authentication_failed: true`)

## Error Handling

- **Authentication Errors**: Returns `authentication_failed: true` when JWT token is invalid/expired
- **Network Errors**: Handles timeouts and connection issues gracefully
- **API Errors**: Provides detailed error messages from the Intelycx Core API
- **Validation Errors**: Clear error messages for missing or invalid parameters

## Logging

The server provides comprehensive logging:
- Tool execution with input/output details
- Authentication attempts and results
- API communication status
- Error conditions and debugging information

Log levels can be controlled via standard Python logging configuration.
