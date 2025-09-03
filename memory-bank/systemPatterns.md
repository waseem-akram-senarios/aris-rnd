# System Patterns

## Architecture
- **WebSocket server**: `aiohttp` with `WebSocketResponse` and heartbeat pings
- **Agent orchestration**: `AgentFactory` produces agents (default `manufacturing`)
- **Security**: `CognitoAuthService` verifies JWT using AWS Cognito JWKS with caching
- **Guardrails**: `GuardrailService` runs a fast Bedrock boolean relevance check with heuristic fallback; allow-on-error
- **LLM access**: `BedrockClient.converse` wraps `bedrock-runtime`, supports tool calling, returns concatenated text content
- **Core libraries**: Modular `app/core/` with reusable memory and file processing libraries
- **Memory management**: `SessionMemoryManager` handles transparent session storage with pluggable backends
- **File processing**: `FileProcessor` with comprehensive format support and S3 integration
- **MCP integration**: `MCPServerManager` manages HTTP-based MCP servers with FastMCP client
- **Tool calling**: Dynamic system prompts based on tool availability, comprehensive logging
- **Streaming UX**: Splits agent final text by words and emits in small chunks, then sends a final message
- **Chain of thought**: Real-time progress updates via WebSocket during authentication, tool loading, and execution

## Key flows
- **Auth on connect**: JWT pulled from `Authorization` header or query; invalid → `HTTPUnauthorized`
- **Message handling**: accepts `{ "message": string }` or legacy `{ "action": "agent", "question": string }`
- **Chain of thought**: Initial "Thinking..." message, then progress updates during authentication, tool loading, and execution
- **Memory management**: Tools with `result_variable_name` automatically store results; memory handled internally by `SessionMemoryManager`
- **Document processing**: `{ doc_bucket, doc_key }` triggers S3 download, content extraction, and injection into conversation
- **MCP tool calling**: Agent routes tool calls to appropriate MCP servers, handles initialization and error cases
- **Guardrails toggle**: `payload.rag_params.guardrails` (bool). When true and irrelevant, return `get_guardrail_message()` and skip processing
- **Model selection**: `payload.model_id` or `rag_params.model_params.model_id` forwarded to agent runtime options

## Core Library Patterns

### File Processing (`app/core/files/`)
- **Factory pattern**: `FileHandlerFactory` routes by extension to specific handlers
- **Handler hierarchy**: `BaseFileHandler` → `TextHandler`, `PDFHandler`, `WordHandler`, etc.
- **Content structure**: `FileContent` dataclass with metadata, text content, and error handling
- **Comprehensive format support**: Text, CSV, JSON, XML, HTML, Markdown, PDF, Word, Excel, PowerPoint, RTF
- **Size limits**: 4MB maximum, enforced before processing
- **S3 integration**: Boto3 client with proper error handling and logging
- **Modular design**: Easy to extend with new file format handlers

## MCP Integration Patterns
- **Server management**: HTTP-based FastMCP servers in separate Docker containers with volume mounting
- **Initialization**: Required before tool calls, handled automatically by `MCPServerManager`
- **Tool routing**: Dynamic tool discovery and server-specific routing (core tools → intelycx-core, email → intelycx-email)
- **Authentication**: Bearer token authentication with configurable API keys
- **JWT handling**: Special logic for login tool (generates tokens) vs data tools (requires tokens)
- **Context logging**: Multi-stage FastMCP Context logging with structured metadata and progress reporting
- **Progress reporting**: 6-stage data generation workflow and 5-stage email workflow with rich feedback
- **Structured logging**: Extra parameters provide detailed metadata for debugging and monitoring
- **Health monitoring**: Health checks configured in docker-compose.yml with reduced log noise
- **Log optimization**: Reduced duplication between LLM Bedrock and MCP Server Manager
- **Error handling**: Graceful degradation when servers unavailable, honest limitation reporting
- **Development**: Live code reload via volume mounting for rapid iteration
- **Network Configuration**: ARIS containers must be on `intelycx_intelycx_default` network to communicate with Intelycx API
- **FastMCP Object Conversion**: Comprehensive recursive conversion of FastMCP Pydantic models to JSON-serializable dictionaries for Bedrock LLM compatibility

### Advanced FastMCP Implementation Patterns
- **Type Safety**: Pydantic Field validation with constraints (min_length, max_length, pattern matching)
- **Tool Metadata**: Comprehensive `@mcp.tool` decorators with name, description, tags, meta, and annotations
- **Structured Responses**: Pydantic models for consistent API contracts (LoginResponse, ManufacturingDataResponse, EmailResponse)
- **Output Schemas**: JSON schemas defined in tool decorators for better LLM understanding
- **Enum Constraints**: Type-safe parameter validation using Python enums (DataType, EmailPriority)
- **Context Enhancement**: Multi-stage progress with notifications (`ctx.notify()`) and structured logging
- **Error Architecture**: Consistent error handling patterns with structured error responses
- **Parameter Placement**: Context parameter always last for consistency across all tools
- **Version Management**: Tool versioning via meta field and semantic versioning practices
- **Annotation System**: Tool behavior hints (readOnlyHint, destructiveHint, idempotentHint, openWorldHint)

### Memory Management (`app/core/memory/`)
- **SessionMemoryManager**: Centralized memory management with pluggable storage backends
- **Automatic storage**: Tools with `result_variable_name` parameter automatically store results
- **Metadata tracking**: Creation time, tool source, data type, size, and access information for each variable
- **Storage backends**: InMemoryStorage (default) and FileStorage for persistence
- **Internal API**: Memory not exposed as tools to LLM; handled transparently by agent
- **Search capabilities**: Search by tool, tag, or key patterns
- **Memory statistics**: Usage tracking, size monitoring, and access analytics
- **Error handling**: Only successful tool results are stored; errors are not cached

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
