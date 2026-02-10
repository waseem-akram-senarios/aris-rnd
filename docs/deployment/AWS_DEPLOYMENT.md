# AWS EC2 Deployment Guide

This guide explains how to deploy the ARIS RAG system on AWS EC2.

## Current Deployment Method (Recommended)

**Use `deploy-fast.sh`** - This is your current deployment method that:
- Uses `docker run` directly (no docker-compose needed)
- Automatically detects server specs
- Dynamically allocates maximum resources
- Fastest and most efficient for AWS EC2

### Quick Deploy:
```bash
./scripts/deploy-fast.sh
```

This script:
1. Syncs code to server
2. Builds Docker image
3. Detects server specs (CPU, RAM)
4. Allocates optimal resources automatically
5. Starts container with maximum available resources

## Alternative: Using Docker Compose on AWS

If you prefer using docker-compose on AWS EC2, use **`docker-compose.prod.yml`**.

### Setup on AWS EC2:

1. **SSH into your EC2 instance:**
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@your-ec2-ip
   ```

2. **Install Docker Compose (if not installed):**
   ```bash
   sudo yum install docker-compose-plugin -y
   # OR for Ubuntu:
   sudo apt-get install docker-compose-plugin
   ```

3. **Navigate to project directory:**
   ```bash
   cd /opt/aris-rag
   ```

4. **Adjust resource limits in docker-compose.prod.yml:**
   ```yaml
   # For 16 CPU / 61 GB instance (your current server):
   cpus: '15'        # 16 - 1 (leave 1 for system)
   mem_limit: '59g'  # 61 - 2 (leave 2GB for system)
   ```

5. **Deploy:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

## Resource Configuration for AWS

### Current Server (16 CPU / 61 GB):
```yaml
cpus: '15'
mem_limit: '59g'
```

### Common AWS Instance Types:

**t3.xlarge (4 vCPU / 16 GB):**
```yaml
cpus: '3'
mem_limit: '14g'
```

**t3.2xlarge (8 vCPU / 32 GB):**
```yaml
cpus: '7'
mem_limit: '30g'
```

**c5.4xlarge (16 vCPU / 32 GB):**
```yaml
cpus: '15'
mem_limit: '30g'
```

**m5.4xlarge (16 vCPU / 64 GB):**
```yaml
cpus: '15'
mem_limit: '62g'
```

## Port Configuration

The docker-compose.prod.yml file exposes:
- **Port 80**: Streamlit UI (http://your-ec2-ip/)
- **Port 8500**: FastAPI API (http://your-ec2-ip:8500)

### Opening Ports in AWS

1. Go to **EC2** → **Security Groups**
2. Select your instance's security group
3. Edit **Inbound Rules**
4. Add rules:
   - **Port 80** (HTTP) - Source: 0.0.0.0/0
   - **Port 8500** (FastAPI) - Source: 0.0.0.0/0
   - **Port 22** (SSH) - Source: Your IP

## Deployment Commands

### Using deploy-fast.sh (Recommended):
```bash
# From your local machine
./scripts/deploy-fast.sh
```

### Using docker-compose (Alternative):
```bash
# On EC2 instance
cd /opt/aris-rag
docker compose -f docker-compose.prod.yml up -d --build
```

### View Logs:
```bash
docker compose -f docker-compose.prod.yml logs -f
```

### Restart:
```bash
docker compose -f docker-compose.prod.yml restart
```

### Stop:
```bash
docker compose -f docker-compose.prod.yml down
```

## Comparison: deploy-fast.sh vs docker-compose

| Feature | deploy-fast.sh | docker-compose.prod.yml |
|---------|----------------|------------------------|
| **Method** | docker run | docker-compose |
| **Resource Detection** | ✅ Automatic | ❌ Manual configuration |
| **Resource Allocation** | ✅ Dynamic (max available) | ⚠️ Fixed in YAML |
| **Ports** | 80:8501, 8500:8000 | 80:8501, 8500:8000 |
| **Best For** | AWS EC2 (current) | Alternative method |
| **Setup** | ✅ One command | ⚠️ Requires manual config |

## Recommendation

**For AWS EC2, use `deploy-fast.sh`** because:
- ✅ Automatically detects server specs
- ✅ Uses maximum available resources
- ✅ No manual configuration needed
- ✅ Faster deployment
- ✅ Already working on your server

**Use `docker-compose.prod.yml`** only if:
- You prefer docker-compose workflow
- You want YAML-based configuration
- You're deploying to multiple environments

## Current Server Status

Your current server (44.221.84.58) is using:
- **Method**: `deploy-fast.sh` (docker run)
- **Resources**: 15 CPUs, 59 GB RAM (automatically allocated)
- **Status**: ✅ Working correctly

---

**Last Updated:** December 4, 2025

