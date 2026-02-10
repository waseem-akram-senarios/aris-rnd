# Logging Guide for ARIS RAG System

## Overview

The ARIS RAG system now includes comprehensive, well-formatted logging for both FastAPI and Streamlit components. All logs are structured with timestamps, log levels, and contextual information.

## Log Format

All logs follow this format:
```
YYYY-MM-DD HH:MM:SS | LEVEL     | MODULE | filename.py:line | message
```

### Log Levels

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (✅ for success, ℹ️ for info)
- **WARNING**: Warning messages (⚠️)
- **ERROR**: Error messages (❌)
- **CRITICAL**: Critical errors

## Viewing Logs

### 1. Interactive Log Viewer (Recommended)

Use the interactive log viewer script:

```bash
./view_logs.sh
```

This provides a menu-driven interface to view:
- Container logs (all services)
- FastAPI logs only
- Streamlit logs only
- FastAPI process log
- System logs
- Real-time tail
- Recent errors only
- All logs

### 2. Quick Log Viewer

For quick access to recent logs:

```bash
./scripts/view_server_logs.sh [lines] [follow]
```

Examples:
```bash
# Last 50 lines
./scripts/view_server_logs.sh 50

# Last 100 lines with color formatting
./scripts/view_server_logs.sh 100

# Follow logs in real-time
./scripts/view_server_logs.sh 50 -f
```

### 3. Direct Docker Commands

```bash
# View all container logs
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 \
    "sudo docker logs --tail 100 aris-rag-app"

# Follow logs in real-time
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 \
    "sudo docker logs -f aris-rag-app"

# View FastAPI-specific logs
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 \
    "sudo docker logs aris-rag-app 2>&1 | grep -i 'fastapi\|api\|uvicorn'"

# View errors only
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 \
    "sudo docker logs aris-rag-app 2>&1 | grep -i 'error\|exception\|failed'"
```

## Log Locations

### Container Logs
- **Docker logs**: `sudo docker logs aris-rag-app`
- **FastAPI process log**: `/tmp/fastapi.log` (inside container)

### Log Files (if configured)
- **Application logs**: `/app/logs/` (inside container)
- **System logs**: `/var/log/` (on host)

## What Gets Logged

### FastAPI Logging

#### Startup/Shutdown
- Application startup with configuration
- Service container initialization
- Vectorstore loading/saving
- Document registry loading
- Application shutdown

#### Document Operations
- **Upload**: File validation, processing start, completion, vectorstore save
- **List**: Document listing requests
- **Get**: Document retrieval by ID
- **Delete**: Document deletion

#### Query Operations
- Query requests with parameters
- RAG query execution
- Response generation
- Citations and sources

#### Sync Operations
- Sync status checks
- Vectorstore reload
- Vectorstore save
- Registry reload
- Conflict detection

#### Errors
- All exceptions with full stack traces
- Validation errors
- File read errors
- Processing errors

### Streamlit Logging

Streamlit logs are captured in the container logs and include:
- Document uploads
- Parser selection
- Processing progress
- Chunking and embedding
- Query operations
- UI interactions

## Log Examples

### Successful Document Upload
```
2025-12-04 12:25:03 | INFO     | api.main | main.py:137 | POST /documents - Upload request: file=document.pdf, parser=docling, size=2451290
2025-12-04 12:25:03 | INFO     | api.main | main.py:164 | Reading file content: document.pdf
2025-12-04 12:25:03 | INFO     | api.main | main.py:166 | File read successfully: 2451290 bytes
2025-12-04 12:25:03 | INFO     | api.main | main.py:170 | Generated document ID: abc123-def456-...
2025-12-04 12:25:03 | INFO     | api.main | main.py:173 | Starting document processing: id=abc123..., parser=docling
2025-12-04 12:25:03 | INFO     | api.main | main.py:205 | Storing document metadata: id=abc123..., name=document.pdf
2025-12-04 12:25:03 | INFO     | api.main | main.py:213 | Saving vectorstore to: /app/vectorstore
2025-12-04 12:25:03 | INFO     | api.main | main.py:215 | ✅ Vectorstore saved successfully
2025-12-04 12:25:03 | INFO     | api.main | main.py:219 | ✅ Document processed successfully: abc123...
```

### Query Execution
```
2025-12-04 12:30:15 | INFO     | api.main | main.py:303 | POST /query - Query: 'What is the main topic?' (k=5, mmr=False)
2025-12-04 12:30:15 | INFO     | api.main | main.py:337 | Executing RAG query: k=5, mmr=False
2025-12-04 12:30:18 | INFO     | api.main | main.py:350 | ✅ Query completed: 3 citations, 2.45s
```

### Error Example
```
2025-12-04 12:35:20 | ERROR    | api.main | main.py:224 | ❌ Error processing document: File format not supported
Traceback (most recent call last):
  File "/app/api/main.py", line 173, in upload_document
    ...
```

## Color Coding

The log viewer automatically color-codes logs:
- **Green**: INFO messages, success indicators (✅)
- **Yellow**: WARNING messages (⚠️)
- **Red**: ERROR messages, failures (❌)
- **Cyan**: HTTP requests (GET, POST, etc.)

## Filtering Logs

### By Component
```bash
# FastAPI only
sudo docker logs aris-rag-app 2>&1 | grep -i "fastapi\|api\|uvicorn"

# Streamlit only
sudo docker logs aris-rag-app 2>&1 | grep -i "streamlit\|8501"
```

### By Log Level
```bash
# Errors only
sudo docker logs aris-rag-app 2>&1 | grep -i "error\|exception\|failed"

# Warnings
sudo docker logs aris-rag-app 2>&1 | grep -i "warning\|warn"
```

### By Operation
```bash
# Document uploads
sudo docker logs aris-rag-app 2>&1 | grep -i "upload\|document\|processing"

# Queries
sudo docker logs aris-rag-app 2>&1 | grep -i "query\|question"

# Sync operations
sudo docker logs aris-rag-app 2>&1 | grep -i "sync\|vectorstore\|registry"
```

## Monitoring Best Practices

1. **Real-time Monitoring**: Use `-f` flag to follow logs during operations
2. **Error Tracking**: Regularly check for errors and warnings
3. **Performance**: Monitor query response times
4. **Sync Status**: Check sync status after operations
5. **Resource Usage**: Monitor memory and CPU usage alongside logs

## Troubleshooting

### No Logs Appearing
- Check if container is running: `sudo docker ps`
- Verify services are started: Check `/tmp/fastapi.log` inside container
- Check Docker logs: `sudo docker logs aris-rag-app`

### Logs Too Verbose
- Adjust log level in `api/main.py` (change `logging.INFO` to `logging.WARNING`)
- Filter logs using grep patterns

### Missing Logs
- Ensure logging is enabled in startup script
- Check file permissions for log directories
- Verify log rotation isn't deleting old logs

## Log Retention

Currently, logs are stored in Docker's log driver. To persist logs:
1. Configure Docker log driver with rotation
2. Mount log directory as volume
3. Set up log rotation policies

## Next Steps

For production, consider:
- Centralized logging (ELK stack, CloudWatch, etc.)
- Log aggregation
- Alerting on errors
- Performance metrics dashboards
- Log retention policies

---

**Last Updated**: December 4, 2025

