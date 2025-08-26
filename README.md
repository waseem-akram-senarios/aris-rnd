# Intelycx ARIS Agent

Minimal scaffolding for the ARIS WebSocket agent and Lambda/Step Functions code, plus CDK infra stubs.

## Local run (agent)

1. Create `.env` from `config/.env.example`
2. Build and run container:

```bash
cd services/agent
docker build -t intelycx-aris-agent:dev .
docker run --rm -p 8080:8080 --env-file ../../config/.env intelycx-aris-agent:dev
```

Health check: GET `http://localhost:8080/health`
WebSocket: `ws://localhost:8080/ws` with `Authorization: <token>` header.

## Structure
- `services/agent`: aiohttp WS server with agent framework
- `services/lambdas`: Lambda functions (podcast placeholder)
- `infra`: CDK app + stacks (placeholder)
- `config/.env.example`: local configuration template

## Next steps
- Implement Cognito JWT verification and agent OOP framework per design
- Add CDK resources (ECS + ALB, Lambda + Step Functions)
- Implement Intelycx Core API client wrappers
