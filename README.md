# Intelycx ARIS Agent

AI-powered manufacturing assistant with document processing, tool calling, and microservices architecture. ARIS provides real-time conversational AI over WebSocket with support for manufacturing documents, production data access, and email notifications.

## Features

- **🔒 Secure WebSocket Communication**: JWT-based authentication with Cognito integration
- **📄 Document Processing**: Support for 10 file types (PDF, Office docs, text files) with S3 integration
- **🛠️ Tool Calling**: MCP (Model Context Protocol) integration for manufacturing data and email services
- **🏭 Manufacturing Focus**: Specialized for equipment, maintenance, OEE, and production workflows
- **🚀 Microservices Architecture**: Separate containers for different tool categories
- **⚡ Real-time Streaming**: Progressive response streaming with heartbeat support
- **🛡️ Optional Guardrails**: Configurable topic filtering to maintain manufacturing focus

## Quick Start

1. **Setup Environment**:
   ```bash
   cp config/.env.example config/.env
   # Edit config/.env with your AWS credentials and settings
   ```

2. **Run with Docker Compose** (Recommended):
   ```bash
   cd docker
   docker compose up -d
   ```

3. **Access the Service**:
   - Health check: `GET https://localhost:4444/health`
   - WebSocket: `wss://localhost:4444/ws` with `Authorization: Bearer <token>` header

## Architecture

### Services
- **`services/agent/`**: Main aiohttp WebSocket server with agent orchestration
- **`services/mcp-servers/`**: MCP tool servers in separate containers
  - `intelycx-core/`: Manufacturing data API (machines, groups, production)
  - `intelycx-email/`: Email notification service
- **`services/lambdas/`**: Lambda functions (podcast placeholder)
- **`infra/`**: AWS CDK application and stacks
- **`config/`**: Configuration files and environment templates

### Key Components
- **File Processing**: Modular handlers for document extraction and S3 integration
- **MCP Integration**: HTTP-based tool calling with authentication and routing
- **Guardrails**: Bedrock-powered relevance filtering with heuristic fallback
- **Streaming**: Token-by-token response delivery with final message consolidation

## Development

### Local Development
```bash
# Start all services
cd docker && docker compose up -d

# View logs
docker compose logs -f aris-agent
docker compose logs -f aris-mcp-intelycx-core

# Rebuild after changes
docker compose build --no-cache aris-agent
docker compose up -d
```

### Virtual Environment (Agent Development)
```bash
cd services/agent
python3 -m venv .venv --upgrade-deps
source .venv/bin/activate
pip install -e .
```

### Message Format
```json
{
  "action": "agent",
  "question": "Tell me about machine M001",
  "doc_bucket": "my-bucket",
  "doc_key": "documents/manual.pdf",
  "model_id": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
  "rag_params": {
    "guardrails": false,
    "model_params": {
      "temperature": 0.25
    }
  }
}
```

## Supported File Types

| Type | Extensions | Handler |
|------|------------|---------|
| Text | `.txt`, `.csv`, `.rtf` | TextHandler |
| PDF | `.pdf` | PDFHandler (PyMuPDF) |
| Excel | `.xls`, `.xlsx` | ExcelHandler (pandas, openpyxl) |
| Word | `.doc`, `.docx` | WordHandler (python-docx) |
| PowerPoint | `.ppt`, `.pptx` | PowerPointHandler (python-pptx) |

**Limits**: 4MB maximum file size

## Available Tools

### Manufacturing Data (intelycx-core)
- `get_machine(machine_id)`: Detailed machine information
- `get_machine_group(group_id)`: Machine group details and metrics
- `get_production_summary(params)`: Production data and analytics

### Email Services (intelycx-email)
- `send_email(to, subject, body, attachments)`: Send notifications
- `send_simple_email(to, subject, body)`: Quick email sending

## Configuration

Key environment variables in `config/.env`:

```bash
# AWS Configuration
REGION=us-east-2
BEDROCK_REGION=us-east-2
USER_POOL_ID=your-cognito-pool-id
USER_POOL_CLIENT_ID=your-client-id

# MCP Configuration
MCP_API_KEY=mcp-dev-key-12345
INTELYCX_CORE_MCP_URL=http://aris-mcp-intelycx-core:8080/mcp
INTELYCX_EMAIL_MCP_URL=http://aris-mcp-intelycx-email:8081/mcp

# Manufacturing API
INTEELYCX_CORE_BASE_URL=https://api.intelycx.com
INTEELYCX_CORE_API_KEY=your-api-key

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@company.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
```

## Container Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   aris-agent    │───▶│aris-mcp-intelycx│───▶│aris-mcp-intelycx│
│   (port 4444)  │    │   -core (8080)   │    │  -email (8081)  │
│                 │    │                  │    │                  │
│ • WebSocket     │    │ • Machine data   │    │ • Email service  │
│ • File proc.    │    │ • Production API │    │ • SMTP client    │
│ • MCP client    │    │ • FastAPI server │    │ • FastAPI server │
└─────────────────┘    └──────────────────┘    └──────────────────┘
```

## Production Deployment

The project includes AWS CDK infrastructure stubs in `infra/` for production deployment:

```bash
cd infra
npm install
cdk deploy --context env=prod
```

## Next Steps

- **Production Infrastructure**: Complete CDK resources (ECS, ALB, networking, secrets)
- **Real API Integration**: Replace dummy MCP server data with actual manufacturing APIs
- **Testing**: Add comprehensive unit and integration tests
- **Monitoring**: Implement observability for MCP servers and agent performance
- **Authentication**: Upgrade to JWT/mTLS for production MCP server security

## Contributing

1. Follow the established patterns in `memory-bank/` for architecture decisions
2. Use `docker compose` (not `docker-compose`) for container operations
3. Update memory bank files when making significant changes
4. Test with multiple file types and MCP tool scenarios

## License

Proprietary - Intelycx Corporation
