# Project Brief: Intelycx ARIS

## Purpose
ARIS is an AI-assisted agent platform focused on manufacturing use cases. This repository provides:
- A Python aiohttp WebSocket agent service with streaming responses and optional domain guardrails
- Document processing system for manufacturing files (PDF, Office docs, text files)
- Model Context Protocol (MCP) integration for external tools and services
- Microservices architecture with separate MCP servers for different functionalities
- Initial AWS CDK scaffolding for infrastructure
- Placeholders for Lambda/Step Functions workloads

## Goals and Success Criteria
- Real-time conversational agent over WebSocket with authenticated access (Cognito JWT verification)
- Document processing from S3 with content injection into conversations
- Tool calling capabilities via MCP servers (production data, email, etc.)
- Optional lightweight guardrails to keep interactions on manufacturing topics
- Seamless local run via Docker and `docker compose`
- Clear path to production via CDK-defined infrastructure

Success is measured by:
- Stable local development experience (build/run instructions work)
- WebSocket interactions with partial streaming and final message
- Document processing works for supported file types (txt, csv, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx)
- MCP tool calling provides rich manufacturing data instead of hallucinations
- Guardrails can be toggled and correctly block irrelevant queries without breaking valid flows
- CDK app synthesizes and is ready to be extended with concrete resources (ECS/ALB, Lambda, Secrets)

## Non-Goals (current scope)
- Full production infra (ALB/ECS/ECR, scaling, observability) — to be added iteratively
- Real external API integrations — currently using dummy data for development

## High-Level Architecture
- `services/agent`: aiohttp server, Cognito auth, agent orchestration, guardrails, Bedrock client, file processing, MCP client
- `services/mcp-servers/`: Separate MCP server containers for different tool categories
  - `intelycx-core`: Manufacturing data API (machines, groups, production)
  - `intelycx-email`: Email sending capabilities
- `services/lambdas`: Lambda placeholders (e.g., `podcast`)
- `infra`: AWS CDK application and stacks
- `docker/`: Local dev `docker-compose.yml` with multi-container setup

## Primary User Workflow
1. Client authenticates (Cognito JWT)
2. Client opens a WebSocket to `/ws`
3. Client sends message with optional document references (`doc_bucket`, `doc_key`)
4. Agent downloads and processes documents from S3, injects content into conversation
5. Agent processes messages, calls MCP tools when needed, optionally applies guardrails
6. Agent streams partial tokens, then sends final message with tool results
7. Connection closes cleanly per message exchange

## Constraints
- Python 3.11 for services and infra (CDK Py)
- AWS Bedrock for LLM interactions and guardrails (with keyword fallback)
- File size limit: 4MB for document processing
- Supported file types: txt, csv, rtf, pdf, xls, xlsx, doc, docx, ppt, pptx
- Docker compose (not docker-compose) for container orchestration


