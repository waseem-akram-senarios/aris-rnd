# ARIS RAG System

Advanced RAG (Retrieval-Augmented Generation) system for document processing and intelligent querying.

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r config/requirements.txt

# Run Streamlit app
streamlit run app.py

# Run FastAPI (separate terminal)
uvicorn api.main:app --reload
```

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# Or for production
docker-compose -f docker-compose.prod.yml up -d
```

## Server Deployment

### Deploy to AWS EC2

```bash
# Fast deployment (recommended)
./scripts/deploy-fast.sh

# Or adaptive deployment with resource detection
./scripts/deploy-adaptive.sh
```

**Server Details:**
- **IP**: 44.221.84.58
- **Streamlit UI**: http://44.221.84.58/
- **FastAPI Docs**: http://44.221.84.58:8500/docs

## Viewing Logs

### Server Logs (Docker Container)

#### View All Logs
```bash
# Real-time logs (follow mode)
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app -f'

# Last 100 lines
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app --tail 100'

# Last 500 lines
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app --tail 500'
```

#### Filter Logs by Component

**Document Processing Logs:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "DocumentProcessor|STEP" | tail -50'
```

**Chunking Progress Logs:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "TokenTextSplitter|chunking|Chunking" | tail -50'
```

**PDF Parsing Logs:**
```bash
# Docling parser
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "Docling|docling" | tail -50'

# PyMuPDF parser
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "PyMuPDF|pymupdf" | tail -50'
```

**FastAPI Logs:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "FastAPI|uvicorn|api" | tail -50'
```

**Error Logs:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -E "ERROR|Error|error|Exception|Traceback" | tail -50'
```

**Progress Logs (Real-time during processing):**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app -f 2>&1 | grep -E "Progress|progress|STEP|%"'
```

#### Logs by Time Range

**Last 10 minutes:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app --since 10m'
```

**Last 1 hour:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app --since 1h'
```

**Since specific time:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app --since 2024-12-04T15:00:00'
```

### Application Log Files (Inside Container)

The application also writes logs to files inside the container:

```bash
# View document processor log
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker exec aris-rag-app tail -50 /app/logs/document_processor.log'

# View FastAPI log
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker exec aris-rag-app tail -50 /app/logs/fastapi.log'

# Follow document processor log (real-time)
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker exec aris-rag-app tail -f /app/logs/document_processor.log'
```

### Local Logs

If running locally, logs are written to:
- `logs/document_processor.log` - Document processing logs
- `logs/fastapi.log` - FastAPI logs

```bash
# View local logs
tail -f logs/document_processor.log
tail -f logs/fastapi.log
```

## Logging Features

### Enhanced Progress Logging

The system now provides detailed progress logging during document processing:

- **Progress Updates**: Every 3-5 seconds for large documents
- **Time Remaining**: Estimated time based on processing speed
- **Processing Speed**: Chunks per second and tokens per second
- **Percentage Complete**: Real-time progress percentage

**Example Progress Log:**
```
TokenTextSplitter: Progress - 25 chunks created, 12500/50000 tokens (25.0%) | Speed: 2.5 chunks/sec | ~30s remaining
```

### Performance Monitoring

The system tracks and logs performance metrics:

- **Chunking Time**: Total time for chunking operation
- **Performance Warnings**: Alerts if chunking takes >10 minutes
- **Speed Metrics**: Chunks/sec and tokens/sec

**Example Performance Log:**
```
TokenTextSplitter: Chunking completed - 84 chunks created from 42,914 tokens | Time: 33.45s | Speed: 2.51 chunks/sec, 1283 tokens/sec
```

## Monitoring Commands

### Check Container Status
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker ps --filter name=aris-rag-app'
```

### Check Container Health
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker inspect aris-rag-app --format "{{.State.Health.Status}}"'
```

### Check Resource Usage
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker stats aris-rag-app --no-stream'
```

### View Recent Errors Only
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker logs aris-rag-app 2>&1 | grep -i error | tail -20'
```

## Quick Reference

### Common Operations

**Restart Container:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker restart aris-rag-app'
```

**Stop Container:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker stop aris-rag-app'
```

**Start Container:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 'sudo docker start aris-rag-app'
```

**View Container Logs (Simplified):**
```bash
# Using the view_logs script
./scripts/view_logs.sh
```

## Features

- **Multi-Parser Support**: Docling, PyMuPDF, AWS Textract
- **Intelligent Chunking**: Token-aware text splitting with adaptive chunk sizes
- **Multiple Vector Stores**: FAISS (local) and OpenSearch (cloud)
- **Progress Tracking**: Real-time progress updates during processing
- **Performance Monitoring**: Detailed metrics and performance tracking
- **FastAPI API**: RESTful API for document management and querying
- **Streamlit UI**: User-friendly web interface

## Documentation

- [Deployment Guide](docs/deployment/AWS_DEPLOYMENT.md)
- [API Documentation](docs/API_USAGE.md)
- [Logging Guide](docs/LOGGING_GUIDE.md)
- [Project Structure](docs/PROJECT_STRUCTURE.md)

## Support

For issues or questions, check the logs using the commands above or review the documentation in the `docs/` directory.

