# Active Context

## Current focus
- ✅ Document processing system fully implemented with modular file handlers
- ✅ MCP integration with separate Docker containers for different tool categories
- ✅ HTTP MCP server initialization fixed - tools now return rich data instead of null
- ✅ Microservices architecture with intelycx-core and intelycx-email MCP servers
- ✅ Dynamic system prompts based on tool availability to prevent hallucinations
- ✅ Guardrails implemented and integrated in WebSocket flow; toggle via `rag_params.guardrails`
- ✅ Agent supports streaming of token-like chunks followed by final message
- ✅ Cognito JWT verification implemented with JWKS caching
- ✅ **JWT authentication for Intelycx Core API** - AI Agent manages credentials and tokens automatically
- ✅ **Chain of thought messaging** - Real-time progress updates during authentication, tool loading, and execution
- ✅ **Session memory management** - Variable storage and retrieval system for complex multi-step workflows

## Recent achievements
- File processing for 10 document types (txt, csv, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx)
- S3 integration with 4MB file size limits and proper error handling
- MCP server architecture with HTTP-based communication and API key authentication
- Tool calling capabilities for manufacturing data (machines, groups, production summaries)
- Email service integration for notifications and reports
- Comprehensive logging for tool usage and debugging
- **JWT authentication system** for Intelycx Core API with automatic token management and refresh
- **Chain of thought messaging** providing real-time user feedback during system operations
- **Session memory management** with variable storage, metadata tracking, and memory management tools

## Open decisions
- Should guardrails be enabled by default via a config flag (e.g., `GUARDRAILS_DEFAULT=true`) and overridable per request?
- Model selection defaults: clarify and document supported model IDs for Bedrock
- Authentication strategy for MCP servers in production (currently using simple API keys)

## Next steps (proposed)
- **Migrate old agent tools** using the new memory management foundation for complex workflows
- **Implement manufacturing data MCP servers** with production summary, machine details, and analytics tools
- Add config-level guardrails default and server-side override rules
- Flesh out `AgentStack` with ECS/ALB and secret wiring; add CI/CD pipeline
- Complete real API integrations (Intelycx Core API authentication now implemented)
- Add unit tests for file processing, MCP integration, JWT authentication, memory management, and existing services
- Implement more sophisticated MCP server authentication (JWT, mTLS)
- Add observability and monitoring for MCP server health and performance
