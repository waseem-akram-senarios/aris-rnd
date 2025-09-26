# System Patterns

## Architecture
- **Database-First Architecture**: PostgreSQL with `chats`, `plans`, `actions`, `session_memory` tables
- **UnifiedPlanManager**: Centralized plan lifecycle management with database operations and WebSocket notifications
- **Template Variable System**: Complex inter-action data flow using `{{action_id.field_name}}` syntax with recursive resolution
- **WebSocket server**: `aiohttp` with `WebSocketResponse` and heartbeat pings
- **Agent orchestration**: `AgentFactory` produces agents (default `manufacturing`)
- **Security**: `CognitoAuthService` verifies JWT using AWS Cognito JWKS with caching
- **Guardrails**: `GuardrailService` runs a fast Bedrock boolean relevance check with heuristic fallback; allow-on-error
- **LLM access**: `BedrockClient.converse` wraps `bedrock-runtime`, supports tool calling, returns concatenated text content
- **Core libraries**: Modular `app/core/` with reusable memory and file processing libraries
- **Memory management**: `DatabaseSessionMemoryManager` handles persistent session storage with PostgreSQL backend
- **File processing**: `FileProcessor` with comprehensive format support and S3 integration
- **MCP integration**: `MCPServerManager` manages HTTP-based MCP servers with FastMCP client
- **Tool calling**: Dynamic system prompts based on tool availability, comprehensive logging
- **Streaming UX**: Splits agent final text by words and emits in small chunks, then sends a final message
- **Planning module**: Complete domain module at `app/planning/` with models, planner, executioner, and observers
- **Chain of thought**: Enhanced real-time progress with both legacy text updates and structured action-specific updates

## Concurrency & Session Management
- **Per-connection isolation**: Each WebSocket connection creates its own `ManufacturingAgent` instance
- **True concurrent processing**: Multiple users can connect and execute tasks simultaneously without blocking
- **Independent state**: Each agent has isolated conversation memory, session memory, and MCP connections
- **Lazy session initialization**: Agent created at connection, but MCP servers initialized only on first message
- **Session lifecycle**: Connection (agent created) → First message (MCP initialization) → Subsequent messages (session continues)
- **Resource efficiency**: Idle connections consume minimal resources (~5MB), full resources allocated on first use
- **No shared mutable state**: Agents operate independently with separate plan IDs, session IDs, and execution contexts
- **Async architecture**: Pure async/await throughout, no blocking between different user sessions

## Key flows
- **Auth on connect**: JWT pulled from `Authorization` header or query; invalid → `HTTPUnauthorized`
- **Message handling**: accepts `{ "message": string }` or legacy `{ "action": "agent", "question": string }`
- **Planning flow**: "Thinking..." → "Creating execution plan..." → Send "tool" type message with planned actions → "Executing plan..." → Structured chain-of-thought updates during execution
- **Chain of thought**: Legacy text updates plus new structured action updates with status (starting/in_progress/completed/failed)
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

### Database-First Architecture (`app/database/`)
- **PostgreSQL Integration**: Complete database schema with chats, plans, actions, and session_memory tables
- **UnifiedPlanManager**: Single source of truth for all plan and action operations with database-first enforcement
- **Database-First Rule**: Plans MUST be stored in database before execution; execution halts if storage fails
- **Plan Lifecycle**: new → in_progress → completed/failed with database updates and UI notifications
- **Action Tracking**: Complete execution history with timing, status, and result storage
- **Schema Validation**: SQLAlchemy models perfectly aligned with database schema (column names, types, constraints)
- **JSONB Storage**: Complex objects (arguments, results, metadata) stored as JSONB for efficient querying
- **Full-Text Search**: GIN indexes on user queries for efficient plan search and retrieval
- **Automatic Triggers**: updated_at columns with database triggers for audit trail

### Template Variable System
- **Inter-Action Data Flow**: Actions reference other action results using `{{action_id.field_name}}` syntax
- **Recursive Resolution**: Handles nested dictionaries and arrays in action arguments
- **Smart Mapping**: Fake template IDs mapped to real action IDs based on tool type and execution order
- **File URL Priority**: Template variables with `file_url` specifically prioritize `create_pdf` actions
- **Fallback Logic**: Multiple resolution strategies (direct mapping, tool-based, analysis-based, fallback)
- **Debug Tracing**: Comprehensive logging of template resolution process for troubleshooting

### Memory Management (`app/core/memory/` + `app/database/`)
- **DatabaseSessionMemoryManager**: PostgreSQL-backed session storage with automatic persistence
- **Automatic storage**: Tools with `result_variable_name` parameter automatically store results
- **Metadata tracking**: Creation time, tool source, data type, size, and access information for each variable
- **Cross-session persistence**: Session data survives agent restarts and container recreation
- **Search capabilities**: Search by tool, tag, or key patterns with database queries
- **Memory statistics**: Usage tracking, size monitoring, and access analytics
- **Error handling**: Only successful tool results are stored; errors are not cached
- **Serialization**: Complex Python objects (dataclasses, enums) automatically serialized to JSONB

## Scalability Considerations
- **Current capacity**: Handles moderate concurrency (< 50 users) efficiently with current architecture
- **Resource scaling**: Memory usage scales linearly with concurrent connections (~5MB per idle, ~15MB per active)
- **MCP connection overhead**: Each agent creates separate MCP server connections (session isolation)
- **Potential optimizations**: Connection pooling for MCP servers, agent instance caching, resource limits
- **Performance bottlenecks**: Agent initialization (~5-6s), MCP connection setup (~300ms per server)
- **Monitoring needs**: Connection count tracking, memory usage monitoring, MCP server health checks

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
