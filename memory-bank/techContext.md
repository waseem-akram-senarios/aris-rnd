# Tech Context

## Languages & Runtimes
- Python 3.11 across services and CDK
- Node.js (for NPX-based MCP servers, if needed)

## Dependencies (agent)
- **Core**: aiohttp, python-dotenv, python-jose, requests, boto3
- **Database**: asyncpg, sqlalchemy[asyncio], alembic (PostgreSQL integration)
- **File processing**: pymupdf, python-docx, pandas, openpyxl, xlrd, python-pptx, striprtf
- **MCP integration**: fastmcp>=2.11.0 (FastMCP client library)

## Dependencies (MCP servers)
- **FastMCP stack**: fastmcp>=2.11.0, pydantic>=2.5.0, aiohttp>=3.9.0, starlette>=0.27.0
- **Authentication**: Bearer token authentication via FastMCP
- **Advanced Features**: Enum support, Field validation, structured responses, output schemas
- **File Generator**: reportlab (PDF generation), boto3 (S3 storage)
- **RAG Services**: opensearch-py, asyncpg, qdrant-client, openai, sentence-transformers, torch

## Infra dependencies
- aws-cdk-lib v2, constructs v10

## Services & SDKs
- **PostgreSQL**: Database backend for persistent storage (chats, plans, actions, memory)
- **AWS Cognito**: JWT validation via JWKS
- **AWS Bedrock Runtime**: LLM interactions, tool calling, guardrails
- **AWS S3**: Document storage and retrieval with presigned URL generation
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
- **MCP containers**: Separate FastMCP builds for `intelycx-core` and `intelycx-email` with volume mounting
- **Health checks**: Configured in docker-compose.yml with reduced log noise
- **Entrypoint script**: `aris-agent` (from `pyproject.toml` console script)
- **Container naming**: `aris-mcp-[server-name]` convention

## Endpoints
- **Agent**: Health `GET /health`, WebSocket `GET /ws` with `Authorization` header (Bearer token)
- **MCP servers**: Health `GET /health`, MCP protocol `POST /mcp`, Tools list `GET /tools`

## Core Libraries Architecture

### File Processing (`app/core/files/`)
- **Supported types**: txt, csv, json, xml, html, markdown, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx
- **Size limit**: 4MB maximum
- **S3 integration**: Boto3 client with proper error handling
- **Content extraction**: Type-specific handlers with fallback error handling
- **Modular structure**: `handlers/`, `models.py`, `factory.py`, `processor.py`

### Memory Management (`app/core/memory/`)
- **SessionMemoryManager**: Main memory interface with pluggable backends
- **Storage options**: InMemoryStorage (default), FileStorage for persistence
- **Automatic integration**: Tools with `result_variable_name` auto-store results
- **Metadata tracking**: Full lifecycle and access analytics

## MCP Integration
- **Protocol**: FastMCP over HTTP with automatic client management
- **Authentication**: Bearer token with configurable API keys
- **Server lifecycle**: Health checks, initialization, tool routing
- **Tool categories**: Core manufacturing data (intelycx-core), email services (intelycx-email), PDF generation (intelycx-file-generator), RAG services (intelycx-rag)
- **Error handling**: Graceful degradation, honest limitation reporting
- **Client library**: FastMCP handles connection management and protocol details
- **Advanced Implementation**: Production-ready tools with type safety, validation, and structured outputs
- **Tool Enhancement**: Comprehensive metadata, annotations, progress tracking, and notification system

## MCP Server Details
- **intelycx-core**: Authentication and manufacturing data tools (port 8080)
- **intelycx-email**: Email sending with attachments (port 8081)
- **intelycx-file-generator**: PDF creation with ReportLab and S3 storage (port 8080)
- **intelycx-rag**: RAG services with vector stores, embeddings, chunking (port 8082)

## Notable patterns
- **Guardrails default**: Off (opt-in per-message via `rag_params.guardrails`)
- **Error handling**: Allow requests on errors to avoid blocking valid traffic
- **Dynamic prompts**: System prompt changes based on tool availability
- **Docker preference**: Use `docker compose` (not `docker-compose`)
- **Logging**: Comprehensive tool usage logging for debugging
- **Virtual environments**: `.venv` in `services/agent` for local development
- **Docker networking**: ARIS containers must be on `intelycx_intelycx_default` network for API communication
- **FastMCP compliance**: Use Pydantic models, avoid invalid `output_schema` parameters
- **Object conversion**: FastMCP Pydantic models require manual conversion to JSON-serializable dictionaries for Bedrock integration
