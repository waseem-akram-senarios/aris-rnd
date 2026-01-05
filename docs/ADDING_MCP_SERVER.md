# Adding a New MCP Server

This guide explains how to add a new MCP server to work in both local (Docker Compose) and production (ECS) environments.

## Overview

When adding a new MCP server, you need to configure it in multiple places:

1. **Local Development** (Docker Compose)
2. **Production** (CDK Stack)
3. **Agent Configuration** (JSON + Environment Variables)

## Step-by-Step Guide

### Example: Adding `aris-mcp-new-service`

### 1. Local Development (Docker Compose)

**File: `docker/docker-compose.yml`**

Add the service definition:

```yaml
aris-mcp-new-service:
  build:
    context: ../services/mcp-servers/new-service
    dockerfile: Dockerfile
  image: aris-mcp-new-service:dev
  container_name: aris-mcp-new-service
  ports:
    - "8084:8084"  # Choose an available port
  env_file:
    - ../config/.env
  restart: unless-stopped
  networks:
    - mcp_internal
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8084/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 15s
```

**File: `services/agent/mcp_servers.json`**

Add the server entry:

```json
{
  "mcpServers": {
    "intelycx-core": {
      "url": "http://aris-mcp-intelycx-core:8080/mcp"
    },
    "intelycx-new-service": {
      "url": "http://aris-mcp-new-service:8084/mcp"
    }
  }
}
```

**Note:** The server name in JSON (`intelycx-new-service`) should match the Docker service name (`aris-mcp-new-service`) but without the `aris-mcp-` prefix.

### 2. Production (CDK Stack)

**File: `infra/stacks/agent_stack.py`**

#### a) Add to ECR repositories list (around line 192):

```python
service_names = [
    "aris-agent",
    "aris-mcp-intelycx-core",
    "aris-mcp-intelycx-email",
    "aris-mcp-intelycx-file-generator",
    "aris-mcp-intelycx-rag",
    "aris-mcp-new-service",  # Add here
]
```

#### b) Add to Docker image directories (around line 216):

```python
service_dirs = {
    "aris-agent": "../services/agent",
    "aris-mcp-intelycx-core": "../services/mcp-servers/intelycx-core",
    # ... existing entries ...
    "aris-mcp-new-service": "../services/mcp-servers/new-service",  # Add here
}
```

#### c) Add to service configurations (around line 561):

```python
service_configs = {
    # ... existing services ...
    "aris-mcp-new-service": {
        "port": 8084,
        "cpu": 512,
        "memory": 1024,
        "desired_count": 1,
        "health_check_path": "/health",
    },
}
```

#### d) Add ALB path patterns (if needed, around line 760):

```python
path_patterns = {
    # ... existing patterns ...
    "aris-mcp-new-service": ["/aris/new-service/*", "/aris/mcp/new-service/*"],
}
```

#### e) Add environment variable for agent (around line 876):

```python
service_specific = {
    "aris-agent": {
        # ... existing env vars ...
        "MCP_SERVER_INTELYCX_NEW_SERVICE_URL": f"http://aris-mcp-new-service-{env_name}.aris-{env_name}.local:8084/mcp",
    },
    # Add service-specific env vars if needed
    "aris-mcp-new-service": {
        "HOST": "0.0.0.0",
        "PORT": "8084",
        "UVICORN_ACCESS_LOG": "false",
    },
}
```

### 3. Environment Variable Naming Convention

The environment variable format is:
```
MCP_SERVER_<SERVER_NAME>_URL
```

Where `<SERVER_NAME>` is the server name from JSON converted to uppercase with underscores:
- JSON: `"intelycx-new-service"` → Env Var: `MCP_SERVER_INTELYCX_NEW_SERVICE_URL`
- JSON: `"intelycx-core"` → Env Var: `MCP_SERVER_INTELYCX_CORE_URL`

### 4. Cloud Map DNS Names

In production, services are discoverable via Cloud Map DNS:
```
<service-name>-<env>.aris-<env>.local
```

Example: `aris-mcp-new-service-dev.aris-dev.local`

## Quick Reference

| Location | What to Add | Example |
|----------|-------------|---------|
| `docker/docker-compose.yml` | Service definition | `aris-mcp-new-service:` |
| `services/agent/mcp_servers.json` | Server URL for local | `"intelycx-new-service": { "url": "http://aris-mcp-new-service:8084/mcp" }` |
| `infra/stacks/agent_stack.py` | ECR repo name | `"aris-mcp-new-service"` |
| `infra/stacks/agent_stack.py` | Docker directory | `"aris-mcp-new-service": "../services/mcp-servers/new-service"` |
| `infra/stacks/agent_stack.py` | Service config | Port, CPU, memory, desired_count |
| `infra/stacks/agent_stack.py` | ALB path patterns | `"/aris/new-service/*"` |
| `infra/stacks/agent_stack.py` | Agent env var | `MCP_SERVER_INTELYCX_NEW_SERVICE_URL` |

## Testing

After adding a new MCP server:

1. **Local**: Restart Docker Compose and verify the agent can connect
2. **Production**: Deploy CDK stack and check CloudWatch logs for connection success

## Notes

- The agent will automatically discover servers configured via environment variables
- Environment variables take precedence over the JSON file
- Cloud Map service discovery is automatically configured for all MCP services
- The JSON file is primarily for local development convenience

