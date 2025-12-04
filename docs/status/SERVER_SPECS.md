# Server Specifications

**Server IP**: 44.221.84.58  
**Date Checked**: December 4, 2025  
**Status**: ✅ Using Maximum Resources Dynamically

---

## Hardware Specifications

### CPU
- **Model**: AMD EPYC 9R14
- **Total CPU Cores**: 16
- **Cores per Socket**: 16
- **Sockets**: 1
- **Threads per Core**: 1
- **Architecture**: x86_64
- **Allocated to Container**: 15 CPUs (leaving 1 for system)

### Memory (RAM)
- **Total RAM**: 61 GB
- **Used RAM**: 1.1 GB (2%)
- **Available RAM**: 59 GB (97%)
- **Buff/Cache**: 1.0 GB
- **Swap**: 0 GB (disabled)
- **Allocated to Container**: 59 GB (leaving 2 GB for system)
- **Memory Reservation**: 55 GB

### Storage
- **Total Disk Space**: 100 GB
- **Used Disk Space**: 20 GB (20%)
- **Available Disk Space**: 81 GB (80%)
- **Filesystem**: /dev/nvme0n1p1 (ext4)
- **Mount Point**: /

### Operating System
- **OS**: Amazon Linux 2023
- **Version**: 2023.9.20251110
- **Kernel**: Linux (6.8.0-87-generic)
- **Vendor**: AWS

---

## Software Stack

### Docker
- **Version**: 25.0.13 (build 0bab007)
- **Containers Running**: 1 (aris-rag-app)
- **Container Status**: Healthy (Up 41+ minutes)

### Running Services
- **Streamlit**: Port 80 (mapped from container port 8501)
- **FastAPI**: Port 8500 (mapped from container port 8000)

---

## Network Configuration

### Network Interfaces
- **Primary Interface**: ens3
  - IP: 172.31.66.163/20
  - Type: Dynamic
- **Docker Bridge**: docker0
  - IP: 172.17.0.1/16
- **Loopback**: lo
  - IP: 127.0.0.1/8

### Listening Ports
- **Port 22**: SSH (sshd)
- **Port 80**: Streamlit (docker-proxy) → Container port 8501
- **Port 8500**: FastAPI (docker-proxy) → Container port 8000
- **Port 35627**: containerd (localhost only)

### Open Ports (External Access)
- **Port 80**: ✅ Open (Streamlit)
- **Port 8500**: ✅ Open (FastAPI)
- **Ports 8500-8510**: ✅ Available

---

## Resource Usage

### Current System Load
- **1 minute**: 2.25
- **5 minute**: 3.14
- **15 minute**: 3.86
- **Load Status**: Moderate (8 CPU cores, so load < 8 is acceptable)

### Memory Usage
- **System Total**: 14 GB
- **System Used**: 8.0 GB (57%)
- **System Available**: 6.3 GB (43%)
- **Container Memory**: 7.5 GB / 12 GB (62.66%)

### CPU Usage
- **Container CPU**: 199.75% (using ~2 cores out of 7 allocated)
- **FastAPI Process**: 170% CPU, 30.1% memory (4.6 GB)
- **Streamlit Process**: 151% CPU, 28.7% memory (4.4 GB)

### Disk Usage
- **Total**: 30 GB
- **Used**: 20 GB (66%)
- **Available**: 11 GB (34%)
- **Status**: ⚠️ Moderate usage (should monitor)

---

## Container Resources (Dynamic Configuration)

### ARIS RAG Container (aris-rag-app)
- **Status**: ✅ Healthy with Maximum Resources
- **CPU Limit**: 15 cores (out of 16 available) - **DYNAMICALLY ALLOCATED**
- **Memory Limit**: 59 GB (out of 61 GB available) - **DYNAMICALLY ALLOCATED**
- **Memory Reservation**: 55 GB
- **Resource Allocation**: Automatically detects server specs and uses maximum available
- **Port Mappings**:
  - `0.0.0.0:80->8501/tcp` (Streamlit)
  - `0.0.0.0:8500->8000/tcp` (FastAPI)

### Running Processes in Container
1. **FastAPI (uvicorn)**: 
   - CPU: 170%
   - Memory: 4.6 GB (30.1%)
   - Port: 8000
   
2. **Streamlit**:
   - CPU: 151%
   - Memory: 4.4 GB (28.7%)
   - Port: 8501

---

## Performance Metrics

### System Health
- **Uptime**: 6 days, 16 hours, 50 minutes
- **Load Average**: 2.25 / 3.14 / 3.86 (1/5/15 min)
- **Status**: ✅ Healthy and stable

### Top Resource Consumers
1. **FastAPI (uvicorn)**: 170% CPU, 4.6 GB RAM
2. **Streamlit**: 151% CPU, 4.4 GB RAM
3. **Docker daemon**: 0.1% CPU, 251 MB RAM

---

## Recommendations

### Current Status: ✅ Good
- Server is healthy and stable
- Both services running correctly
- Resources within acceptable limits

### Monitoring Points
- **Disk Space**: 66% used - monitor and clean up if needed
- **Memory**: 57% used - adequate headroom available
- **CPU Load**: Moderate but acceptable for 8-core system

### Optimization Opportunities
- Consider cleaning Docker images/cache if disk space becomes tight
- Current resource allocation is appropriate for the workload

---

## Access Information

### Streamlit
- **URL**: http://44.221.84.58/
- **Container Port**: 8501
- **External Port**: 80

### FastAPI
- **URL**: http://44.221.84.58:8500
- **Swagger UI**: http://44.221.84.58:8500/docs
- **Container Port**: 8000
- **External Port**: 8500

---

## Dynamic Resource Allocation

The deployment script now **automatically detects** server specifications and allocates maximum available resources:

1. **CPU Detection**: Uses `nproc` to detect total CPU cores
2. **Memory Detection**: Uses `free -g` to detect total RAM
3. **Smart Allocation**:
   - Leaves 1 CPU core for system operations
   - Leaves 2 GB RAM for system operations
   - Allocates all remaining resources to the container
4. **Minimum Safety**: Ensures at least 1 CPU and 4 GB RAM are allocated

**Benefits**:
- ✅ Automatically adapts to any server size
- ✅ Uses maximum available resources for better performance
- ✅ No manual configuration needed
- ✅ Safe system resource reservation

---

**Last Updated**: December 4, 2025  
**Status**: ✅ All systems operational

