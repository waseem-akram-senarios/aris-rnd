# ARIS Infrastructure Deployment

This directory contains AWS CDK infrastructure code for deploying ARIS services to AWS ECS.

## Overview

The CDK stack deploys ARIS services to the existing `intelycx-dev-cluster` ECS cluster:

- **aris-agent**: Main WebSocket agent service (port 443)
- **aris-mcp-intelycx-core**: Manufacturing data MCP server (port 8080)
- **aris-mcp-intelycx-email**: Email service MCP server (port 8081)
- **aris-mcp-intelycx-file-generator**: File generation MCP server (port 8080)
- **aris-mcp-intelycx-rag**: RAG/document processing MCP server (port 8082)

## Prerequisites

1. **AWS CLI configured** with appropriate credentials
2. **CDK CLI installed**: `npm install -g aws-cdk`
3. **Python dependencies**: `pip install -e .` (from infra directory)
4. **Docker images built and pushed** to ECR repositories (see below)

## Infrastructure Components

The stack creates:

- **ECR Repositories**: Container image repositories for each service
- **ECS Task Definitions**: Fargate task definitions with CPU/memory allocation
- **ECS Services**: Fargate services running in the existing cluster
- **Application Load Balancer Target Groups**: For routing traffic to services
- **IAM Roles**: Execution role (for ECS) and task role (for application permissions)
- **CloudWatch Log Groups**: Centralized logging for all services
- **Secrets Manager Secrets**: For sensitive configuration (database passwords, etc.)

## Configuration

### Context Variables

You can override default values using CDK context:

```bash
cdk deploy --context env=dev \
  --context cluster_name=intelycx-dev-cluster \
  --context vpc_id=vpc-0aad20b9963e29f38 \
  --context alb_arn=arn:aws:elasticloadbalancing:us-east-2:975049910508:loadbalancer/app/intelycx-alb-dev/d03a8658af509291 \
  --context http_listener_arn=arn:aws:elasticloadbalancing:us-east-2:975049910508:listener/app/intelycx-alb-dev/d03a8658af509291/a14de0845f19d39e \
  --context https_listener_arn=arn:aws:elasticloadbalancing:us-east-2:975049910508:listener/app/intelycx-alb-dev/d03a8658af509291/f2803351d3adc0d8
```

**Note**: If listener ARNs are not provided, the stack will attempt to look them up automatically. Providing them explicitly is more reliable.

### Default Values

- **Cluster**: `intelycx-dev-cluster`
- **VPC**: `vpc-0aad20b9963e29f38`
- **Subnets**: Private subnets across 3 AZs
- **Security Group**: `sg-05cb45ca06004c701`
- **ALB**: `intelycx-alb-dev`

## Deployment Steps

### 1. Build and Push Docker Images

Before deploying, you need to build and push Docker images to ECR:

```bash
# Set variables
export AWS_ACCOUNT=975049910508
export AWS_REGION=us-east-2
export ENV=dev

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push each service
cd ../services/agent
docker build -t intelycx-aris-agent-$ENV:latest .
docker tag intelycx-aris-agent-$ENV:latest $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aris-agent-$ENV:latest
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/aris-agent-$ENV:latest

# Repeat for other services:
# - aris-mcp-intelycx-core
# - aris-mcp-intelycx-email
# - aris-mcp-intelycx-file-generator
# - aris-mcp-intelycx-rag
```

### 2. Configure Secrets

Create secrets in AWS Secrets Manager:

```bash
# Database password
aws secretsmanager create-secret \
  --name intelycx-aris-dev-database \
  --secret-string '{"password":"aris_dev_password_2024"}' \
  --region us-east-2

# AWS credentials (if not using IAM roles)
aws secretsmanager create-secret \
  --name intelycx-aris-dev-aws-credentials \
  --secret-string '{"access_key_id":"...","secret_access_key":"..."}' \
  --region us-east-2
```

### 3. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://975049910508/us-east-2
```

### 4. Synthesize CloudFormation Template

```bash
cdk synth
```

### 5. Review Changes

```bash
cdk diff
```

### 6. Deploy Stack

```bash
cdk deploy --context env=dev
```

## Post-Deployment

### ALB Listener Configuration

**Automatic Configuration**: The stack automatically creates ALB listener rules for routing traffic to ARIS services. The following path patterns are configured:

- `/aris/agent/*` and `/aris/ws/*` → aris-agent service
- `/aris/core/*` and `/aris/mcp/core/*` → aris-mcp-intelycx-core service
- `/aris/email/*` and `/aris/mcp/email/*` → aris-mcp-intelycx-email service
- `/aris/file/*` and `/aris/mcp/file/*` → aris-mcp-intelycx-file-generator service
- `/aris/rag/*` and `/aris/mcp/rag/*` → aris-mcp-intelycx-rag service

**Manual Configuration** (if automatic creation fails): If listener rules are not created automatically, you can create them manually using the target group ARNs from stack outputs:

```bash
# Get target group ARN from stack outputs
TARGET_GROUP_ARN=$(aws cloudformation describe-stacks \
  --stack-name intelycx-aris-agent-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`arisagentTargetGroupArn`].OutputValue' \
  --output text)

# Create listener rule (adjust listener ARN and priority as needed)
aws elbv2 create-rule \
  --listener-arn <LISTENER_ARN> \
  --priority 100 \
  --conditions Field=path-pattern,Values='/aris/agent/*' \
  --actions Type=forward,TargetGroupArn=$TARGET_GROUP_ARN \
  --region us-east-2
```

### Database Setup

The stack assumes PostgreSQL is available. You may need to:

1. **Use existing RDS instance** (if available)
2. **Deploy RDS via separate stack** (recommended for production)
3. **Use existing ECS service** for PostgreSQL

Update the `DATABASE_URL` environment variable in the stack to point to your database.

### Environment Variables

The stack sets common environment variables, but you may need to add:

- `USER_POOL_ID`: Cognito User Pool ID
- `USER_POOL_CLIENT_ID`: Cognito Client ID
- `INTEELYCX_CORE_BASE_URL`: Intelycx Core API URL
- `INTEELYCX_CORE_API_KEY`: API key (consider using Secrets Manager)
- `MCP_API_KEY`: MCP server authentication key

These can be added via:
1. **Secrets Manager** (recommended for sensitive values)
2. **SSM Parameter Store** (for non-sensitive configuration)
3. **Direct environment variables** in task definition (for non-sensitive values)

## Service Configuration

### Resource Allocation

Default CPU/memory allocation:

- **aris-agent**: 1 vCPU, 2 GB RAM (2 instances)
- **aris-mcp-intelycx-core**: 0.5 vCPU, 1 GB RAM (2 instances)
- **aris-mcp-intelycx-email**: 0.25 vCPU, 0.5 GB RAM (1 instance)
- **aris-mcp-intelycx-file-generator**: 0.5 vCPU, 1 GB RAM (1 instance)
- **aris-mcp-intelycx-rag**: 1 vCPU, 2 GB RAM (1 instance)

Adjust in `agent_stack.py` based on your workload.

### Health Checks

All services have health check endpoints at `/health`. Health checks are configured:

- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Healthy threshold**: 2 consecutive successes
- **Unhealthy threshold**: 3 consecutive failures
- **Grace period**: 60 seconds

## Monitoring

### CloudWatch Logs

Logs are available in CloudWatch Log Groups:

- `/ecs/intelycx-aris-dev/aris-agent`
- `/ecs/intelycx-aris-dev/aris-mcp-intelycx-core`
- `/ecs/intelycx-aris-dev/aris-mcp-intelycx-email`
- `/ecs/intelycx-aris-dev/aris-mcp-intelycx-file-generator`
- `/ecs/intelycx-aris-dev/aris-mcp-intelycx-rag`

### ECS Service Metrics

Monitor service health via:

- ECS Console → Cluster → Service → Metrics
- CloudWatch → Metrics → ECS/ContainerInsights

## Troubleshooting

### Service Won't Start

1. Check CloudWatch logs for errors
2. Verify ECR image exists and is accessible
3. Check IAM role permissions
4. Verify security group allows traffic
5. Check task definition resource limits

### Health Check Failures

1. Verify health check endpoint is accessible
2. Check container logs for application errors
3. Verify port mappings are correct
4. Check security group rules

### ALB 502 Errors

1. Verify target group health checks are passing
2. Check security group allows ALB → ECS traffic
3. Verify service is running and healthy
4. Check target group registration

## Cleanup

To destroy the stack:

```bash
cdk destroy --context env=dev
```

**Note**: ECR repositories are retained by default (RemovalPolicy.RETAIN) to preserve images.

## Next Steps

- [ ] Set up CI/CD pipeline for automated deployments
- [ ] Configure auto-scaling policies
- [ ] Set up RDS PostgreSQL instance
- [ ] Configure ALB listener rules automatically
- [ ] Add monitoring and alerting
- [ ] Set up backup and disaster recovery

