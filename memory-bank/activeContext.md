# Active Context

## Current focus
- ✅ **Complete FastMCP architecture** - Both intelycx-core and intelycx-email servers operational
- ✅ **Working multi-tool pipeline** - Login → fake data → email chain functional
- ✅ **Volume-mounted development** - Live code reload for all MCP servers
- ✅ **Fixed tool execution** - Resolved JWT token injection and routing issues
- ✅ **Core libraries architecture** - Memory and file processing extracted to `app/core/`
- ✅ **Enhanced document processing** with 12+ file types including JSON, XML, HTML, Markdown
- ✅ **Modern MCP integration** using FastMCP client library for better performance
- ✅ **Transparent memory management** - No longer exposed as tools; handled automatically
- ✅ **Clean codebase structure** - Removed utils folder, proper separation of concerns
- ✅ Dynamic system prompts based on tool availability to prevent hallucinations
- ✅ Guardrails implemented and integrated in WebSocket flow; toggle via `rag_params.guardrails`
- ✅ Agent supports streaming of token-like chunks followed by final message
- ✅ Cognito JWT verification implemented with JWKS caching
- ✅ **JWT authentication for Intelycx Core API** - AI Agent manages credentials and tokens automatically
- ✅ **Chain of thought messaging** - Real-time progress updates during authentication, tool loading, and execution

## Recent achievements
- **Enhanced multi-stage FastMCP Context** - 6-stage data generation and 5-stage email workflows
- **Implemented structured logging** - Rich metadata with extra parameters for comprehensive debugging
- **Optimized logging verbosity** - Reduced duplication between LLM Bedrock and MCP Server Manager
- **Optimized health check configuration** - Moved to docker-compose.yml with reduced log noise
- **Simplified logging strategy** - Context-first approach for better AI agent visibility
- **Completed Intelycx-Core MCP server** - FastMCP implementation with login and fake data tools
- **Fixed tool execution pipeline** - Resolved JWT token injection for login vs data tools
- **Implemented volume mounting** - Live development for all MCP servers
- **Core libraries extraction** - Memory and file processing moved to `app/core/` for reusability
- **Enhanced file processing** for 12+ document types (added JSON, XML, HTML, Markdown support)
- **FastMCP integration** - Modern MCP client library for better performance and reliability
- **Transparent memory management** - SessionMemoryManager with pluggable backends, no longer exposed as tools
- **Clean architecture** - Removed utils folder, proper separation of concerns
- S3 integration with 4MB file size limits and proper error handling
- **JWT authentication system** for Intelycx Core API with automatic token management and refresh
- **Chain of thought messaging** providing real-time user feedback during system operations

## Open decisions
- Should guardrails be enabled by default via a config flag (e.g., `GUARDRAILS_DEFAULT=true`) and overridable per request?
- Model selection defaults: clarify and document supported model IDs for Bedrock
- Authentication strategy for MCP servers in production (currently using simple API keys)

## Next steps (proposed)
- **Migrate additional tools** from old agent implementation using core libraries
- **Add unit tests** for core libraries (memory management, file processing, MCP servers)
- **Implement real API endpoints** beyond fake data (machine details, production summaries)
- Add config-level guardrails default and server-side override rules
- Flesh out `AgentStack` with ECS/ALB and secret wiring; add CI/CD pipeline
- Complete real API integrations (Intelycx Core API authentication now implemented)
- Implement more sophisticated MCP server authentication (JWT, mTLS)
- Add observability and monitoring for MCP server health and performance
- **Performance optimization** for core libraries (caching, connection pooling)
