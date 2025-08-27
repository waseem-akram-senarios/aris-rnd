# System Patterns

## Architecture
- **WebSocket server**: `aiohttp` with `WebSocketResponse` and heartbeat pings
- **Agent orchestration**: `AgentFactory` produces agents (default `manufacturing`)
- **Security**: `CognitoAuthService` verifies JWT using AWS Cognito JWKS with caching
- **Guardrails**: `GuardrailService` runs a fast Bedrock boolean relevance check with heuristic fallback; allow-on-error
- **LLM access**: `BedrockClient.converse` wraps `bedrock-runtime`, supports tool calling, returns concatenated text content
- **File processing**: Modular `FileProcessor` with type-specific handlers for document extraction
- **MCP integration**: `MCPServerManager` manages HTTP-based MCP servers with initialization and tool routing
- **Tool calling**: Dynamic system prompts based on tool availability, comprehensive logging
- **Streaming UX**: Splits agent final text by words and emits in small chunks, then sends a final message
- **Chain of thought**: Real-time progress updates via WebSocket during authentication, tool loading, and execution

## Key flows
- **Auth on connect**: JWT pulled from `Authorization` header or query; invalid → `HTTPUnauthorized`
- **Message handling**: accepts `{ "message": string }` or legacy `{ "action": "agent", "question": string }`
- **Chain of thought**: Initial "Thinking..." message, then progress updates during authentication, tool loading, and execution
- **Document processing**: `{ doc_bucket, doc_key }` triggers S3 download, content extraction, and injection into conversation
- **MCP tool calling**: Agent routes tool calls to appropriate MCP servers, handles initialization and error cases
- **Guardrails toggle**: `payload.rag_params.guardrails` (bool). When true and irrelevant, return `get_guardrail_message()` and skip processing
- **Model selection**: `payload.model_id` or `rag_params.model_params.model_id` forwarded to agent runtime options

## File Processing Patterns
- **Factory pattern**: `FileHandlerFactory` routes by extension to specific handlers
- **Handler hierarchy**: `BaseFileHandler` → `TextHandler`, `PDFHandler`, `OfficeHandler`, etc.
- **Content structure**: `FileContent` dataclass with metadata, text content, and error handling
- **Size limits**: 4MB maximum, enforced before processing
- **S3 integration**: Boto3 client with proper error handling and logging

## MCP Integration Patterns
- **Server management**: HTTP-based servers in separate Docker containers
- **Initialization**: Required before tool calls, handled automatically by `MCPServerManager`
- **Tool routing**: Server-specific tool mappings (core tools → intelycx-core, email → intelycx-email)
- **Authentication**: Bearer token authentication with configurable API keys
- **Error handling**: Graceful degradation when servers unavailable, honest limitation reporting
- **JWT authentication**: AI Agent manages Intelycx Core credentials, automatic token refresh on expiration

## Configuration
- `.env` loaded best-effort via `Settings.load_settings()` with search order: `DOTENV_PATH` → `config/.env` → `.env`
- Relevant env vars: `USER_POOL_ID`, `USER_POOL_CLIENT_ID`, `REGION`, `BEDROCK_REGION`, `AGENT_TYPE`, `INTELYCX_CORE_*`, `MCP_API_KEY`
- MCP servers configured in `services/agent/mcp_servers.json` with URL-based connections

## Containerization
- **Agent container**: `services/agent/Dockerfile` builds editable install from `pyproject.toml`, exposes 443 with self-signed cert
- **MCP containers**: Separate FastAPI servers for different tool categories
- **Docker compose**: Multi-container setup with internal networking, health checks, dependency management
- **Development**: Live code reload for agent, `docker compose` (not `docker-compose`) preferred

## Infra (CDK)
- `infra/app.py` instantiates `AgentStack` with context `env` (default `dev`)
- `infra/stacks/agent_stack.py` is a placeholder to be extended with ECS service, ALB, and secrets
