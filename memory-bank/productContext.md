# Product Context

## Why this exists
Manufacturing organizations need an assistant to answer questions about equipment, maintenance, OEE, procedures, and internal documents, while avoiding unrelated topics. The assistant should be able to process manufacturing documents, access real-time production data, and send notifications/reports.

## Target users
- Manufacturing engineers, maintenance technicians, shift supervisors
- Internal business users integrating ARIS into dashboards or tools
- Quality assurance teams reviewing documents and production metrics

## Key experiences
- Low-latency chat over WebSocket with progressive streaming
- Document processing: Upload manufacturing documents (procedures, reports, specs) and ask questions about their content
- Real-time data access: Query machine status, production metrics, maintenance schedules
- Email notifications: Send reports, alerts, and summaries to relevant teams
- Secure-by-default: JWT validation at connection time
- Guardrails maintain focus on manufacturing topics

## UX principles
- Fast feedback (heartbeat, pings, partial token streams)
- Rich data responses instead of hallucinations (use tools when available)
- Document content seamlessly integrated into conversations
- Clear failure modes (auth errors, guardrail messages, file processing errors)
- Minimal configuration to get started locally

## Edge cases to consider
- Transient Bedrock failures (guardrails should default-allow)
- Non-boolean outputs from the LLM (fallback to heuristic)
- Empty or malformed messages (ignore/close gracefully)
- Large document processing (4MB limit, timeout handling)
- MCP server failures (graceful degradation, honest about limitations)
- Unsupported file types (clear error messages)
- S3 access issues (proper error handling and user feedback)
