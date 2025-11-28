# Port Configuration Guide

This guide explains the different port configurations available for deploying the ARIS RAG system and how to choose the right one for your environment.

## Overview

The ARIS RAG system supports three deployment configurations based on available ports:

1. **Standard Ports (80/443)** - Production-ready with nginx
2. **Alternative Ports (8080/8443)** - When standard ports are blocked
3. **Direct Streamlit (8501)** - Simple setup without nginx

## Port Scenarios

### Scenario 1: Standard Ports (80/443)

**Best for:** Production deployments

**Configuration File:** `docker-compose.prod.yml`

**Ports Used:**
- Port 80: HTTP (redirects to HTTPS)
- Port 443: HTTPS

**Features:**
- Full nginx reverse proxy
- SSL/HTTPS support
- Security headers
- Rate limiting
- Production-ready

**Access URLs:**
- HTTP: `http://your-server-ip` (redirects to HTTPS)
- HTTPS: `https://your-server-ip`

**Requirements:**
- Ports 80 and 443 must be open in AWS Security Group
- Ports 80 and 443 must be accessible from internet

**Setup:**
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

### Scenario 2: Alternative Ports (8080/8443)

**Best for:** When ports 80/443 are blocked or unavailable

**Configuration File:** `docker-compose.prod.alt-ports.yml`

**Ports Used:**
- Port 8080: HTTP (redirects to HTTPS)
- Port 8443: HTTPS

**Features:**
- Full nginx reverse proxy
- SSL/HTTPS support
- Security headers
- Rate limiting
- Same functionality as standard ports

**Access URLs:**
- HTTP: `http://your-server-ip:8080` (redirects to HTTPS)
- HTTPS: `https://your-server-ip:8443`

**Requirements:**
- Ports 8080 and 8443 must be open in AWS Security Group
- Ports 8080 and 8443 must be accessible from internet

**Setup:**
```bash
docker-compose -f docker-compose.prod.alt-ports.yml up -d
```

**Note:** Users will need to specify the port in the URL (e.g., `https://example.com:8443`)

---

### Scenario 3: Direct Streamlit (8501)

**Best for:** Testing, development, or when nginx is not needed

**Configuration File:** `docker-compose.prod.direct.yml`

**Ports Used:**
- Port 8501: Streamlit directly (HTTP only)

**Features:**
- No nginx (simpler setup)
- Direct Streamlit access
- Faster startup
- Less resource usage

**Access URLs:**
- HTTP: `http://your-server-ip:8501`

**Requirements:**
- Port 8501 must be open in AWS Security Group
- Port 8501 must be accessible from internet

**Setup:**
```bash
docker-compose -f docker-compose.prod.direct.yml up -d
```

**Limitations:**
- No HTTPS/SSL support
- No nginx security headers
- No rate limiting
- Users must specify port in URL

---

## Choosing the Right Configuration

### Use Standard Ports (80/443) if:
- ✅ You have control over AWS Security Group
- ✅ You want production-ready setup
- ✅ You need HTTPS/SSL
- ✅ You want clean URLs (no port numbers)

### Use Alternative Ports (8080/8443) if:
- ✅ Ports 80/443 are blocked by firewall/ISP
- ✅ You still want full nginx features
- ✅ You need HTTPS/SSL
- ✅ You can accept port numbers in URLs

### Use Direct Streamlit (8501) if:
- ✅ You're testing or developing
- ✅ You don't need HTTPS
- ✅ You want the simplest setup
- ✅ You have limited resources

---

## Port Detection

### Automatic Detection

Use the adaptive deployment script to automatically detect available ports:

```bash
./scripts/deploy-adaptive.sh
```

This script will:
1. Test which ports are accessible
2. Select the best configuration
3. Deploy automatically

### Manual Detection

Check ports manually:

```bash
# Test port accessibility
timeout 2 bash -c "echo >/dev/tcp/your-server-ip/80" && echo "Port 80 open" || echo "Port 80 closed"
timeout 2 bash -c "echo >/dev/tcp/your-server-ip/443" && echo "Port 443 open" || echo "Port 443 closed"
timeout 2 bash -c "echo >/dev/tcp/your-server-ip/8080" && echo "Port 8080 open" || echo "Port 8080 closed"
timeout 2 bash -c "echo >/dev/tcp/your-server-ip/8443" && echo "Port 8443 open" || echo "Port 8443 closed"
timeout 2 bash -c "echo >/dev/tcp/your-server-ip/8501" && echo "Port 8501 open" || echo "Port 8501 closed"
```

### Interactive Selection

Use the port configuration helper:

```bash
./scripts/configure-ports.sh
```

This provides an interactive menu to select the configuration.

---

## AWS Security Group Configuration

### Opening Ports in AWS

1. **Go to AWS Console:**
   - EC2 → Security Groups
   - Select your instance's security group

2. **Edit Inbound Rules:**
   - Click "Edit inbound rules"
   - Click "Add rule"

3. **Add Rules:**

   **For Standard Ports:**
   - Type: HTTP, Port: 80, Source: 0.0.0.0/0
   - Type: HTTPS, Port: 443, Source: 0.0.0.0/0

   **For Alternative Ports:**
   - Type: Custom TCP, Port: 8080, Source: 0.0.0.0/0
   - Type: Custom TCP, Port: 8443, Source: 0.0.0.0/0

   **For Direct Streamlit:**
   - Type: Custom TCP, Port: 8501, Source: 0.0.0.0/0

4. **Save Rules**

---

## Switching Between Configurations

### Stop Current Configuration

```bash
cd /opt/aris-rag
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.alt-ports.yml down
docker-compose -f docker-compose.prod.direct.yml down
```

### Start New Configuration

```bash
# For standard ports
docker-compose -f docker-compose.prod.yml up -d

# For alternative ports
docker-compose -f docker-compose.prod.alt-ports.yml up -d

# For direct Streamlit
docker-compose -f docker-compose.prod.direct.yml up -d
```

---

## Troubleshooting

### Port Not Accessible

1. **Check AWS Security Group:**
   - Verify inbound rules allow the port
   - Check source IP (should be 0.0.0.0/0 for public access)

2. **Check Server Firewall:**
   ```bash
   # UFW
   sudo ufw status
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   
   # firewalld
   sudo firewall-cmd --list-all
   sudo firewall-cmd --permanent --add-port=80/tcp
   sudo firewall-cmd --permanent --add-port=443/tcp
   sudo firewall-cmd --reload
   ```

3. **Check Container Status:**
   ```bash
   docker ps
   docker logs aris-rag-nginx  # if using nginx
   docker logs aris-rag-app    # Streamlit container
   ```

### Port Already in Use

If a port is already in use:

```bash
# Find what's using the port
sudo netstat -tlnp | grep :80
sudo ss -tlnp | grep :80

# Stop the conflicting service or use different ports
```

### Testing Port Accessibility

From your local machine:

```bash
# Test HTTP
curl -I http://your-server-ip:80
curl -I http://your-server-ip:8080

# Test HTTPS
curl -I -k https://your-server-ip:443
curl -I -k https://your-server-ip:8443

# Test Streamlit
curl -I http://your-server-ip:8501
```

---

## Comparison Table

| Feature | Standard (80/443) | Alternative (8080/8443) | Direct (8501) |
|---------|-------------------|------------------------|---------------|
| nginx | ✅ Yes | ✅ Yes | ❌ No |
| HTTPS/SSL | ✅ Yes | ✅ Yes | ❌ No |
| Security Headers | ✅ Yes | ✅ Yes | ❌ No |
| Rate Limiting | ✅ Yes | ✅ Yes | ❌ No |
| Clean URLs | ✅ Yes | ⚠️ Port in URL | ⚠️ Port in URL |
| Resource Usage | Medium | Medium | Low |
| Setup Complexity | Medium | Medium | Low |
| Production Ready | ✅ Yes | ✅ Yes | ⚠️ Testing Only |

---

## Quick Reference

### Standard Ports
```bash
docker-compose -f docker-compose.prod.yml up -d
# Access: http://server-ip or https://server-ip
```

### Alternative Ports
```bash
docker-compose -f docker-compose.prod.alt-ports.yml up -d
# Access: http://server-ip:8080 or https://server-ip:8443
```

### Direct Streamlit
```bash
docker-compose -f docker-compose.prod.direct.yml up -d
# Access: http://server-ip:8501
```

### Adaptive Deployment (Auto-detect)
```bash
./scripts/deploy-adaptive.sh
# Automatically selects best configuration
```

---

## Additional Resources

- [Deployment Guide](DEPLOYMENT.md) - Complete deployment instructions
- [Troubleshooting Guide](../TROUBLESHOOTING_DEPLOYMENT.md) - Common issues and solutions
- [Docker Documentation](DOCKER.md) - Docker setup and configuration

