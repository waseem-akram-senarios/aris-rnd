# Docker Setup for ARIS RAG System

This guide explains how to build and run the ARIS RAG system using Docker.

## Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (version 2.0+, optional but recommended)
- Environment variables configured (see below)

## Quick Start

### Using Docker Compose (Recommended)

1. **Create `.env` file** in the project root:
```bash
OPENAI_API_KEY=your_openai_key_here
CEREBRAS_API_KEY=your_cerebras_key_here  # Optional
AWS_ACCESS_KEY_ID=your_aws_key  # Optional, for Textract
AWS_SECRET_ACCESS_KEY=your_aws_secret  # Optional
AWS_OPENSEARCH_ACCESS_KEY_ID=your_opensearch_key  # Optional
AWS_OPENSEARCH_SECRET_ACCESS_KEY=your_opensearch_secret  # Optional
```

2. **Build and run**:
```bash
docker-compose up --build
```

3. **Access the application**:
   - Open your browser to `http://localhost:8501`

### Using Docker Directly

1. **Build the image**:
```bash
docker build -t aris-rag:latest .
```

2. **Run the container**:
```bash
docker run -d \
  --name aris-rag-app \
  -p 8501:8501 \
  -e OPENAI_API_KEY=your_openai_key \
  -e CEREBRAS_API_KEY=your_cerebras_key \
  -v $(pwd)/vectorstore:/app/vectorstore \
  -v $(pwd)/data:/app/data \
  aris-rag:latest
```

3. **Access the application**:
   - Open your browser to `http://localhost:8501`

## Environment Variables

### Required
- `OPENAI_API_KEY` - OpenAI API key for embeddings and LLM

### Optional
- `CEREBRAS_API_KEY` - Cerebras API key (if using Cerebras LLM)
- `AWS_ACCESS_KEY_ID` - AWS access key (for Textract parser)
- `AWS_SECRET_ACCESS_KEY` - AWS secret key (for Textract parser)
- `AWS_REGION` - AWS region (default: us-east-1)
- `AWS_OPENSEARCH_ACCESS_KEY_ID` - OpenSearch access key
- `AWS_OPENSEARCH_SECRET_ACCESS_KEY` - OpenSearch secret key
- `AWS_OPENSEARCH_REGION` - OpenSearch region (default: us-east-2)

## Volumes

The Docker setup mounts the following volumes:

- `./vectorstore:/app/vectorstore` - Persists FAISS vector store data
- `./data:/app/data` - Directory for uploaded documents (optional)
- `./.env:/app/.env:ro` - Environment variables (read-only)

## Building for Production

### Multi-Stage Build

The Dockerfile uses a multi-stage build:
- **Stage 1 (builder)**: Installs all dependencies and builds packages
- **Stage 2 (runtime)**: Creates a minimal production image with only runtime dependencies

This results in a smaller final image while ensuring all dependencies are properly built.

### Build Arguments

You can customize the build with build arguments:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.10 \
  -t aris-rag:latest .
```

## Development Workflow

### Running in Development Mode

For development, you may want to mount the source code:

```bash
docker run -d \
  --name aris-rag-dev \
  -p 8501:8501 \
  -v $(pwd):/app \
  -e OPENAI_API_KEY=your_key \
  aris-rag:latest
```

### Viewing Logs

```bash
# Using docker-compose
docker-compose logs -f

# Using docker directly
docker logs -f aris-rag-app
```

### Stopping the Container

```bash
# Using docker-compose
docker-compose down

# Using docker directly
docker stop aris-rag-app
docker rm aris-rag-app
```

## Troubleshooting

### Container Won't Start

1. **Check logs**:
```bash
docker logs aris-rag-app
```

2. **Verify environment variables**:
```bash
docker exec aris-rag-app env | grep API_KEY
```

3. **Check port availability**:
```bash
# Make sure port 8501 is not in use
lsof -i :8501
```

### Missing Dependencies

If you encounter import errors, rebuild the image:
```bash
docker-compose build --no-cache
```

### Vector Store Not Persisting

Ensure the volume is mounted correctly:
```bash
docker inspect aris-rag-app | grep -A 10 Mounts
```

### Performance Issues

For better performance, especially with large documents:
- Increase container memory: `docker run --memory=4g ...`
- Use GPU if available (requires nvidia-docker)

## Health Check

The container includes a health check that verifies Streamlit is running:
- Check status: `docker ps` (look for "healthy" status)
- Manual check: `docker exec aris-rag-app curl http://localhost:8501/_stcore/health`

## Security Considerations

1. **Never commit `.env` file** - It contains sensitive API keys
2. **Use secrets management** in production (Docker secrets, AWS Secrets Manager, etc.)
3. **Limit exposed ports** - Only expose port 8501 if needed
4. **Use read-only mounts** for sensitive data
5. **Regularly update base images** for security patches

## Production Deployment

### Recommended Settings

1. **Use a reverse proxy** (nginx, traefik) in front of Streamlit
2. **Enable HTTPS** using the reverse proxy
3. **Set resource limits**:
```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

4. **Use Docker secrets** for sensitive data
5. **Set up monitoring** and logging
6. **Regular backups** of the vectorstore volume

## Image Size

The multi-stage build results in a smaller image:
- Builder stage: ~1.5GB (includes build tools)
- Runtime stage: ~800MB (only runtime dependencies)

## Updating the Image

To update dependencies:
```bash
# Update requirements.txt
# Then rebuild
docker-compose build --no-cache
docker-compose up -d
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Streamlit Deployment](https://docs.streamlit.io/deploy)
- [Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)




