# Tech Context

## Languages & Runtimes
- Python 3.11 across services and CDK
- Node.js (for NPX-based MCP servers, if needed)

## Dependencies (agent)
- **Core**: aiohttp, python-dotenv, python-jose, requests, boto3
- **File processing**: pymupdf, python-docx, pandas, openpyxl, xlrd, python-pptx, striprtf
- **MCP integration**: aiohttp (for HTTP client communication)

## Dependencies (MCP servers)
- **FastAPI stack**: fastapi, uvicorn, aiohttp, python-dotenv
- **Authentication**: HTTPBearer for API key validation

## Infra dependencies
- aws-cdk-lib v2, constructs v10

## Services & SDKs
- **AWS Cognito**: JWT validation via JWKS
- **AWS Bedrock Runtime**: LLM interactions, tool calling, guardrails
- **AWS S3**: Document storage and retrieval
- **Docker**: Multi-container orchestration with internal networking

## Configuration
- `config/.env.example` defines required variables:
  - `AGENT_TYPE`, `HOST`, `PORT`, `LOG_LEVEL`
  - `USER_POOL_ID`, `USER_POOL_CLIENT_ID`, `REGION`, `BEDROCK_REGION`
  - `INTEELYCX_CORE_BASE_URL`, `INTEELYCX_CORE_API_KEY`
  - `MCP_API_KEY`, `INTELYCX_CORE_MCP_URL`, `INTELYCX_EMAIL_MCP_URL`
  - SMTP settings: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_USE_TLS`
- `Settings` loads `.env` automatically when running locally
- MCP servers configured in `services/agent/mcp_servers.json`

## Build & Run
- **Local development**: `docker compose up -d` in `docker/` directory
- **Agent container**: Built from `services/agent/Dockerfile` with editable install
- **MCP containers**: Separate builds for `intelycx-core` and `intelycx-email`
- **Entrypoint script**: `aris-agent` (from `pyproject.toml` console script)
- **Container naming**: `aris-mcp-[server-name]` convention

## Endpoints
- **Agent**: Health `GET /health`, WebSocket `GET /ws` with `Authorization` header (Bearer token)
- **MCP servers**: Health `GET /health`, MCP protocol `POST /mcp`, Tools list `GET /tools`

## File Processing
- **Supported types**: txt, csv, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx
- **Size limit**: 4MB maximum
- **S3 integration**: Boto3 client with proper error handling
- **Content extraction**: Type-specific handlers with fallback error handling

## MCP Integration
- **Protocol**: HTTP-based MCP over REST APIs
- **Authentication**: Bearer token with configurable API keys
- **Server lifecycle**: Health checks, initialization, tool routing
- **Tool categories**: Core manufacturing data, email services
- **Error handling**: Graceful degradation, honest limitation reporting

## Notable patterns
- **Guardrails default**: Off (opt-in per-message via `rag_params.guardrails`)
- **Error handling**: Allow requests on errors to avoid blocking valid traffic
- **Dynamic prompts**: System prompt changes based on tool availability
- **Docker preference**: Use `docker compose` (not `docker-compose`)
- **Logging**: Comprehensive tool usage logging for debugging
- **Virtual environments**: `.venv` in `services/agent` for local development
