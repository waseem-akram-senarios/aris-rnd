# How Current Deployment Was Done

**Date**: November 28, 2025  
**Server IP**: 35.175.133.235  
**Application URL**: http://35.175.133.235/

---

## 🎯 Deployment Method

**Current Setup**: **Direct Streamlit on Port 80** (No Nginx Reverse Proxy)

- ✅ Single container deployment
- ✅ Streamlit runs directly on port 80
- ✅ Simplified architecture
- ✅ Maximum resource allocation (7 CPUs, 12GB RAM)

---

## 📋 Step-by-Step Deployment Process

### **Step 1: Server Preparation**

1. **EC2 Instance Setup**
   - Server: Amazon Linux 2023
   - IP Address: 35.175.133.235
   - User: ec2-user
   - Target Directory: `/opt/aris-rag`

2. **Docker Installation**
   ```bash
   # Docker and Docker Compose installed via server_setup.sh
   # Docker version: 25.0.13
   # Docker Compose version: v2.40.3
   ```

3. **Directory Structure Created**
   ```bash
   /opt/aris-rag/
   ├── vectorstore/    # For FAISS data
   ├── data/           # For uploaded documents
   └── .env            # Environment variables (created manually)
   ```

---

### **Step 2: Code Transfer**

**Method**: Automated deployment script (`scripts/deploy.sh`)

**Process**:
```bash
# Uses rsync to transfer files
rsync -avz --progress \
    -e "ssh -i scripts/ec2_wah_pk.pem" \
    --exclude patterns... \
    ./ \
    ec2-user@35.175.133.235:/opt/aris-rag/
```

**What Gets Transferred**:
- ✅ Application code (`app.py`, `rag_system.py`)
- ✅ Python modules (`parsers/`, `ingestion/`, `utils/`, etc.)
- ✅ Docker files (`Dockerfile`, `docker-compose*.yml`)
- ✅ Configuration files (`.streamlit/config.toml`)

**What Gets Excluded**:
- ❌ `.git/`, `venv/`, `__pycache__/`
- ❌ `vectorstore/`, `data/`, `tests/`
- ❌ `.env` (must be created manually on server)
- ❌ `*.pem`, `*.key` files
- ❌ Documentation files (`*.md`)

---

### **Step 3: Environment Variables**

**File**: `/opt/aris-rag/.env` (created manually on server)

**Required Variables**:
```bash
OPENAI_API_KEY=sk-proj-...
```

**Optional Variables**:
```bash
CEREBRAS_API_KEY=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
AWS_OPENSEARCH_ACCESS_KEY_ID=...
AWS_OPENSEARCH_SECRET_ACCESS_KEY=...
AWS_OPENSEARCH_REGION=us-east-2
```

---

### **Step 4: Docker Image Build**

**Dockerfile**: Multi-stage build

**Stage 1: Builder**
```dockerfile
FROM python:3.10-slim AS builder
# Installs build dependencies
# Compiles Python packages
```

**Stage 2: Runtime**
```dockerfile
FROM python:3.10-slim
# Copies compiled packages from builder
# Installs runtime dependencies
# Copies application code
```

**Build Command** (on server):
```bash
cd /opt/aris-rag
docker build -t aris-rag:latest .
```

**Result**: Image `aris-rag:latest` (~8.85GB)

---

### **Step 5: Container Deployment**

**Method**: Direct Docker run (bypassing docker-compose build issues)

**Command Used**:
```bash
docker run -d \
    --name aris-rag-app \
    --restart unless-stopped \
    -p 80:8501 \
    --cpus="7" \
    --memory="12g" \
    --memory-reservation="8g" \
    -v /opt/aris-rag/vectorstore:/app/vectorstore \
    -v /opt/aris-rag/data:/app/data \
    -v /opt/aris-rag/.env:/app/.env:ro \
    --env-file /opt/aris-rag/.env \
    --health-cmd="python -c 'import requests; requests.get(\"http://localhost:8501/_stcore/health\")'" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=40s \
    aris-rag:latest
```

**Configuration Details**:
- **Container Name**: `aris-rag-app`
- **Port Mapping**: `80:8501` (Host:Container)
- **Resource Limits**: 7 CPUs, 12GB memory
- **Resource Reservation**: 4 CPUs, 8GB memory
- **Restart Policy**: `unless-stopped`
- **Health Checks**: Every 30 seconds

---

### **Step 6: Volume Mounts**

**Persistent Data**:
1. **Vectorstore**: `/opt/aris-rag/vectorstore` → `/app/vectorstore`
   - Stores FAISS vector database
   - Persists across container restarts

2. **Data**: `/opt/aris-rag/data` → `/app/data`
   - Stores uploaded documents
   - Persists across container restarts

3. **Environment**: `/opt/aris-rag/.env` → `/app/.env:ro`
   - Read-only mount
   - Provides environment variables

---

### **Step 7: Network Configuration**

**Port Mapping**:
```
Internet → Port 80 (Host) → Port 8501 (Container) → Streamlit
```

**Access**:
- **External**: http://35.175.133.235/
- **Internal**: http://localhost:8501

**Network Mode**: Docker bridge network (default)

---

## 🔧 Configuration Files

### **1. Docker Compose** (`docker-compose.prod.port80.yml`)

```yaml
services:
  aris-rag:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: aris-rag-app
    ports:
      - "80:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # ... other env vars
    volumes:
      - ./vectorstore:/app/vectorstore
      - ./data:/app/data
      - ./.env:/app/.env:ro
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '7'
          memory: 12G
        reservations:
          cpus: '4'
          memory: 8G
```

### **2. Dockerfile**

- Multi-stage build
- Python 3.10-slim base
- Installs system dependencies for PDF/OCR
- Copies application code
- Sets Streamlit environment variables
- Exposes port 8501
- Health check configured

### **3. Streamlit Config** (`.streamlit/config.toml`)

```toml
[server]
fileWatcherType = "none"
runOnSave = false
maxUploadSize = 100
enableXsrfProtection = false

[runner]
fastReruns = false
magicEnabled = false
```

**Optimizations**:
- Disables file watcher (prevents inotify issues)
- Allows long-running operations
- Increases upload size limit

---

## 📊 Current Deployment Status

### **Container Information**
- **Name**: `aris-rag-app`
- **Image**: `aris-rag:latest`
- **Status**: ✅ Running (healthy)
- **Uptime**: 22+ minutes
- **Health**: ✅ Passing

### **Resource Usage**
- **CPU**: 0.01% (idle)
- **Memory**: 1.349GB / 12GB (11.24%)
- **CPU Limit**: 7 CPUs available
- **Memory Limit**: 12GB
- **Memory Reservation**: 8GB

### **Application Status**
- **HTTP Status**: 200 ✅
- **Port 80**: Listening ✅
- **Health Check**: Passing ✅

---

## 🚀 Deployment Scripts Used

### **Main Deployment Script**: `scripts/deploy.sh`

**What it does**:
1. Checks PEM file exists
2. Creates server directories
3. Transfers files via rsync
4. Copies `.env` file
5. Builds Docker image
6. Starts containers
7. Verifies deployment

**Usage**:
```bash
./scripts/deploy.sh
```

### **Alternative**: Manual Deployment

If automated script fails, manual steps:
```bash
# 1. Transfer files
rsync -avz -e "ssh -i scripts/ec2_wah_pk.pem" \
    --exclude patterns... \
    ./ ec2-user@35.175.133.235:/opt/aris-rag/

# 2. SSH to server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235

# 3. Build and run
cd /opt/aris-rag
docker build -t aris-rag:latest .
docker run -d --name aris-rag-app \
    -p 80:8501 \
    --cpus="7" --memory="12g" \
    -v $(pwd)/vectorstore:/app/vectorstore \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/.env:/app/.env:ro \
    --env-file .env \
    aris-rag:latest
```

---

## 🔄 Updates and Maintenance

### **To Update Deployment**:

1. **Make changes locally**
2. **Run deployment script**:
   ```bash
   ./scripts/deploy.sh
   ```

3. **Or manually update**:
   ```bash
   # Transfer files
   rsync ... (as above)
   
   # SSH to server
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   
   # Rebuild and restart
   cd /opt/aris-rag
   docker stop aris-rag-app
   docker rm aris-rag-app
   docker build -t aris-rag:latest .
   docker run ... (same command as above)
   ```

### **To Check Status**:

```bash
# Check container
docker ps --filter "name=aris-rag-app"

# Check logs
docker logs -f aris-rag-app

# Check resources
docker stats aris-rag-app

# Check application
curl http://localhost/
```

---

## 🎯 Key Decisions Made

1. **Direct Streamlit** (not Nginx)
   - Simpler setup
   - Faster deployment
   - Less resource usage
   - Trade-off: No SSL/HTTPS, no security headers

2. **Maximum Resources**
   - 7 CPUs (out of 8)
   - 12GB memory (out of 14GB)
   - Optimized for performance

3. **Port 80**
   - Standard HTTP port
   - No port number in URL
   - Clean access

4. **Persistent Volumes**
   - Vectorstore persists
   - Data persists
   - No data loss on restart

---

## ✅ Deployment Checklist

- [x] Server prepared (Docker installed)
- [x] Code transferred to server
- [x] Environment variables configured
- [x] Docker image built
- [x] Container deployed with resource limits
- [x] Port 80 mapped correctly
- [x] Volumes mounted
- [x] Health checks configured
- [x] Application responding (HTTP 200)
- [x] Container running and healthy

---

## 📝 Summary

**Deployment Method**: Direct Docker run with maximum resources

**Key Steps**:
1. ✅ Code transfer via rsync
2. ✅ Docker image build (multi-stage)
3. ✅ Container deployment with resource limits
4. ✅ Port 80 mapping
5. ✅ Volume mounts for persistence
6. ✅ Health checks enabled

**Result**: 
- ✅ Application running on http://35.175.133.235/
- ✅ Container healthy and operational
- ✅ Maximum resources allocated (7 CPUs, 12GB RAM)
- ✅ All services functioning correctly

---

**Last Updated**: November 28, 2025  
**Deployment Status**: ✅ **OPERATIONAL**

