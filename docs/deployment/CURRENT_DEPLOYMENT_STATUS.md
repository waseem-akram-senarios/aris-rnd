# Current Deployment Status

**Last Updated**: November 28, 2025  
**Server IP**: 35.175.133.235  
**Application URL**: http://35.175.133.235/

---

## 🚀 Deployment Architecture

### **Current Setup: Direct Streamlit on Port 80**

Your application is deployed using a **simplified direct deployment** method:

- ✅ **No Nginx reverse proxy** (simpler setup)
- ✅ **Streamlit runs directly on port 80**
- ✅ **Single container deployment**
- ✅ **Resource-optimized configuration**

---

## 📦 Deployment Configuration

### **Docker Compose File**
- **File**: `docker-compose.prod.port80.yml`
- **Method**: Direct Streamlit access (bypasses Nginx)
- **Port Mapping**: `Host:80 → Container:8501`

### **Container Details**
- **Container Name**: `aris-rag-app`
- **Image**: `aris-rag:latest`
- **Status**: ✅ Running (healthy)
- **Uptime**: 15+ hours

### **Resource Limits**
- **CPU**: 2 cores (limit), 1 core (reserved)
- **Memory**: 4GB (limit), 2GB (reserved)
- **Health Check**: Every 30 seconds

---

## 🔧 Deployment Process

### **Step 1: File Transfer**
The deployment script (`scripts/deploy.sh`) uses `rsync` to transfer files:

```bash
rsync -avz --progress \
    -e "ssh -i scripts/ec2_wah_pk.pem" \
    --exclude patterns... \
    ./ \
    ec2-user@35.175.133.235:/opt/aris-rag/
```

**Excluded from transfer:**
- `.git/`, `venv/`, `__pycache__/`
- `vectorstore/`, `data/`, `tests/`
- `.env` (must be created manually on server)
- `*.pem`, `*.key` files
- Documentation files (`*.md`)

### **Step 2: Docker Build**
On the server, Docker builds the image:

```bash
cd /opt/aris-rag
docker compose -f docker-compose.prod.port80.yml build
```

**Build Process:**
- Multi-stage Dockerfile
- Stage 1: Builder (installs dependencies)
- Stage 2: Runtime (production image)
- Includes all Python packages and system libraries

### **Step 3: Container Startup**
```bash
docker compose -f docker-compose.prod.port80.yml up -d
```

**What happens:**
1. Creates container `aris-rag-app`
2. Maps port 80 (host) → 8501 (container)
3. Mounts volumes:
   - `./vectorstore` → `/app/vectorstore`
   - `./data` → `/app/data`
   - `./.env` → `/app/.env:ro` (read-only)
4. Sets environment variables from `.env`
5. Starts Streamlit with health checks

---

## 🌐 Network Configuration

### **Port Mapping**
```
External (Internet) → Host Port 80 → Container Port 8501 → Streamlit
```

### **Access Points**
- **External URL**: http://35.175.133.235/
- **Internal URL**: http://localhost:8501
- **SSH Access**: `ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235`

### **Network Mode**
- Uses Docker's default bridge network
- Container name: `aris-network`

---

## 📁 Directory Structure on Server

```
/opt/aris-rag/
├── app.py                    # Main Streamlit application
├── rag_system.py             # RAG system core
├── Dockerfile                # Container image definition
├── docker-compose.prod.port80.yml  # Deployment config
├── .env                      # Environment variables (not synced)
├── vectorstore/              # FAISS vector store data
├── data/                     # Uploaded documents
├── ingestion/                # Document processing
├── parsers/                  # PDF/document parsers
├── utils/                    # Utilities
├── metrics/                  # Metrics collection
└── vectorstores/             # Vector store implementations
```

---

## 🔐 Environment Variables

**Required:**
- `OPENAI_API_KEY` - OpenAI API key for embeddings/LLM

**Optional:**
- `CEREBRAS_API_KEY` - Cerebras API (if used)
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` - For Textract parser
- `AWS_REGION` - AWS region
- `AWS_OPENSEARCH_*` - OpenSearch credentials (if using)

**Location**: `/opt/aris-rag/.env` (created manually on server)

---

## 🏥 Health Monitoring

### **Container Health Check**
- **Interval**: Every 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3
- **Start Period**: 40 seconds (grace period)
- **Test**: `curl http://localhost:8501/_stcore/health`

### **Current Status**
- ✅ Container: Running (healthy)
- ✅ Application: HTTP 200
- ✅ Port 80: Listening
- ✅ Uptime: 15+ hours

---

## 🔄 Deployment Workflow

### **To Deploy Updates:**

1. **Make changes locally**
2. **Run deployment script:**
   ```bash
   ./scripts/deploy.sh
   ```

3. **The script will:**
   - Transfer files via rsync
   - SSH into server
   - Build Docker image
   - Restart containers
   - Verify deployment

### **Manual Deployment Steps:**

```bash
# 1. Transfer files
./scripts/deploy.sh

# 2. SSH to server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235

# 3. Navigate to project
cd /opt/aris-rag

# 4. Rebuild and restart
docker compose -f docker-compose.prod.port80.yml down
docker compose -f docker-compose.prod.port80.yml build
docker compose -f docker-compose.prod.port80.yml up -d

# 5. Check logs
docker logs -f aris-rag-app

# 6. Check status
docker ps
curl http://localhost/
```

---

## 📊 Advantages of Current Setup

### ✅ **Pros:**
- **Simple**: One container, no reverse proxy complexity
- **Fast**: Direct access, no proxy overhead
- **Resource Efficient**: Less memory/CPU usage
- **Easy Debugging**: Direct container logs
- **Quick Deployment**: Faster startup time

### ⚠️ **Cons:**
- **No SSL/HTTPS**: HTTP only (port 80)
- **No Security Headers**: No nginx security features
- **No Rate Limiting**: Streamlit handles all traffic
- **Development Server**: Streamlit is not production-optimized

---

## 🔍 Monitoring & Logs

### **View Container Logs:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
docker logs -f aris-rag-app
```

### **Check Container Status:**
```bash
docker ps --filter "name=aris-rag-app"
docker inspect aris-rag-app
```

### **Check Application Health:**
```bash
curl http://localhost/
curl http://localhost/_stcore/health
```

### **Check Resource Usage:**
```bash
docker stats aris-rag-app
```

---

## 🛠️ Alternative Deployment Options

### **Option 1: Nginx Reverse Proxy** (More Production-Ready)
- **File**: `docker-compose.prod.yml`
- **Features**: SSL, security headers, rate limiting
- **Access**: http://35.175.133.235/ (same URL)

### **Option 2: Alternative Ports** (If 80 is blocked)
- **File**: `docker-compose.prod.alt-ports.yml`
- **Ports**: 8080 (HTTP), 8443 (HTTPS)
- **Access**: http://35.175.133.235:8080/

### **Option 3: Direct Streamlit** (Current)
- **File**: `docker-compose.prod.port80.yml` ✅ **ACTIVE**
- **Port**: 80
- **Access**: http://35.175.133.235/

---

## 📝 Configuration Files

### **Streamlit Config** (`.streamlit/config.toml`)
- `fileWatcherType = "none"` - Prevents inotify issues
- `runOnSave = false` - Prevents auto-reload during processing
- `maxUploadSize = 100` - 100MB max file size
- `fastReruns = false` - Allows long-running operations
- `magicEnabled = false` - Disables auto-imports

### **Docker Compose** (`docker-compose.prod.port80.yml`)
- Resource limits: 2 CPUs, 4GB RAM
- Restart policy: `unless-stopped`
- Health checks enabled
- Volume mounts for persistence

---

## 🚨 Troubleshooting

### **If Application is Down:**

1. **Check container status:**
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   docker ps -a
   ```

2. **Check logs:**
   ```bash
   docker logs aris-rag-app
   ```

3. **Restart container:**
   ```bash
   cd /opt/aris-rag
   docker compose -f docker-compose.prod.port80.yml restart
   ```

4. **Full restart:**
   ```bash
   docker compose -f docker-compose.prod.port80.yml down
   docker compose -f docker-compose.prod.port80.yml up -d
   ```

### **If Port 80 is Blocked:**

1. Check AWS Security Group (inbound rules)
2. Ensure port 80 is open for `0.0.0.0/0` (HTTP)
3. Check server firewall: `sudo firewall-cmd --list-all`

---

## 📧 Status Reporting

### **Generate Status Report:**
```bash
./scripts/check_and_report_status.sh
```

This creates:
- `SERVER_STATUS_REPORT.html` - HTML report
- `SERVER_STATUS_REPORT.txt` - Text report

### **Send Status Email:**
```bash
./scripts/send_status_email.sh
```

---

## ✅ Summary

**Current Deployment:**
- ✅ Direct Streamlit on port 80
- ✅ Single container (`aris-rag-app`)
- ✅ Resource limits: 2 CPUs, 4GB RAM
- ✅ Health checks enabled
- ✅ Auto-restart on failure
- ✅ Persistent volumes for data

**Status:**
- ✅ **OPERATIONAL**
- ✅ Application accessible at http://35.175.133.235/
- ✅ Container healthy and running
- ✅ All services functioning

**Next Steps:**
- Monitor application performance
- Check logs periodically
- Update deployment as needed
- Consider Nginx for production hardening (optional)

---

**Last Verified**: November 28, 2025  
**Server IP**: 35.175.133.235  
**Container Status**: ✅ Healthy  
**Application Status**: ✅ Operational

