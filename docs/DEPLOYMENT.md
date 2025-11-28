# Production Deployment Guide

This guide walks you through deploying the ARIS RAG system to a production server with Docker, nginx reverse proxy, and SSL/HTTPS support.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Deployment Steps](#deployment-steps)
- [SSL Certificate Setup](#ssl-certificate-setup)
- [Post-Deployment](#post-deployment)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Server Requirements

- **OS**: Ubuntu 20.04+, CentOS 7+, or Amazon Linux 2
- **RAM**: Minimum 4GB (8GB recommended)
- **CPU**: 2+ cores
- **Disk**: 20GB+ free space
- **Network**: Ports 80, 443, and 22 open

### Local Machine Requirements

- SSH access to the server
- SSH private key (PEM file) for server access
- `rsync` installed (for file transfer)
- `docker` and `docker-compose` installed (optional, for local testing)

### Domain Name (Optional)

- For Let's Encrypt SSL certificates, you need a domain name pointing to your server
- For self-signed certificates, you can use the server IP address

## Architecture Overview

```
Internet
   ↓
nginx (Port 443/80) - SSL Termination, Reverse Proxy
   ↓
Docker Network (aris-network)
   ↓
Streamlit Container (Port 8501 internal)
```

**Key Features:**
- nginx handles SSL/TLS termination
- Streamlit only accessible via internal Docker network
- Automatic HTTPS redirect
- Security headers and rate limiting
- Health checks for both services

## Deployment Steps

### Step 1: Initial Server Setup

**On the server**, run the setup script:

```bash
# Connect to server
ssh -i /path/to/your-key.pem user@your-server-ip

# Download or copy server_setup.sh to server
# Then run:
sudo bash server_setup.sh
```

This script will:
- Install Docker and Docker Compose
- Configure firewall rules
- Create necessary directories
- Set up user permissions

**Note**: If you added a user to the docker group, log out and back in for changes to take effect.

### Step 2: Prepare Environment Variables

**On your local machine**, create a `.env` file in the project root:

```bash
cp .env.production.example .env
```

Edit `.env` and fill in your API keys:

```env
OPENAI_API_KEY=sk-your-actual-key-here
# Add other optional keys as needed
```

**Important**: Never commit `.env` to version control!

### Step 3: Deploy Application

**On your local machine**, run the deployment script:

```bash
cd /path/to/aris
./scripts/deploy.sh
```

The script will:
- Transfer files to the server (excluding unnecessary files)
- Copy `.env` file securely
- Build Docker images on the server
- Start containers
- Verify deployment health

**Customize deployment** (optional):

```bash
# Set custom server details
export SERVER_IP=your-server-ip
export SERVER_USER=your-username
export SERVER_DIR=/custom/path
./scripts/deploy.sh
```

### Step 4: Set Up SSL Certificates

**On the server**, set up SSL certificates:

```bash
# Connect to server
ssh -i /path/to/your-key.pem user@your-server-ip
cd /opt/aris-rag

# Option 1: Let's Encrypt (requires domain name)
sudo ./scripts/setup_ssl.sh your-domain.com your-email@example.com

# Option 2: Self-signed (for testing)
sudo ./scripts/setup_ssl.sh
# Then select option 2
```

**For Let's Encrypt:**
- Domain must point to your server IP
- Port 80 must be accessible from internet
- Email is optional but recommended

**For self-signed:**
- Works immediately
- Browser will show security warning
- Suitable for internal/testing use

### Step 5: Restart Services

After SSL setup, restart nginx:

```bash
cd /opt/aris-rag
docker-compose -f docker-compose.prod.yml restart nginx
```

## SSL Certificate Setup

### Let's Encrypt (Recommended)

**Requirements:**
- Domain name pointing to server
- Port 80 accessible from internet
- Email address (optional)

**Setup:**
```bash
sudo ./scripts/setup_ssl.sh your-domain.com your-email@example.com
```

**Auto-renewal:**
- Certificates auto-renew via cron (monthly)
- nginx automatically restarts after renewal

### Self-Signed Certificates

**For testing/internal use:**

```bash
sudo ./scripts/setup_ssl.sh
# Select option 2 when prompted
```

**Note:** Browsers will show security warnings. Click "Advanced" → "Proceed" to continue.

## Post-Deployment

### Verify Deployment

1. **Check container status:**
   ```bash
   docker ps --filter "name=aris-rag"
   ```

2. **Check health endpoints:**
   ```bash
   # HTTP health check
   curl http://localhost/health
   
   # HTTPS health check (after SSL setup)
   curl -k https://localhost/health
   ```

3. **Access application:**
   - HTTP: `http://your-server-ip` (redirects to HTTPS)
   - HTTPS: `https://your-server-ip` or `https://your-domain.com`

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f aris-rag
docker-compose -f docker-compose.prod.yml logs -f nginx

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

### Monitor Resources

```bash
# Container resource usage
docker stats

# Disk usage
df -h
du -sh /opt/aris-rag/vectorstore
```

## Maintenance

### Updating the Application

1. **Pull latest changes** (if using git):
   ```bash
   cd /opt/aris-rag
   git pull
   ```

2. **Rebuild and restart:**
   ```bash
   docker-compose -f docker-compose.prod.yml build --no-cache
   docker-compose -f docker-compose.prod.yml up -d
   ```

3. **Or use deploy script** from local machine:
   ```bash
   ./scripts/deploy.sh
   ```

### Backup

**Important data to backup:**

```bash
# Vector store data
tar -czf vectorstore-backup-$(date +%Y%m%d).tar.gz /opt/aris-rag/vectorstore

# Environment variables
cp /opt/aris-rag/.env /opt/aris-rag/.env.backup

# SSL certificates (if Let's Encrypt)
tar -czf ssl-backup-$(date +%Y%m%d).tar.gz /etc/letsencrypt
```

### Restart Services

```bash
# Restart all services
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart aris-rag
docker-compose -f docker-compose.prod.yml restart nginx
```

### Stop Services

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml stop

# Stop and remove containers
docker-compose -f docker-compose.prod.yml down
```

## Troubleshooting

### Container Won't Start

1. **Check logs:**
   ```bash
   docker-compose -f docker-compose.prod.yml logs
   ```

2. **Check environment variables:**
   ```bash
   docker exec aris-rag-app env | grep API_KEY
   ```

3. **Verify .env file:**
   ```bash
   cat /opt/aris-rag/.env
   ```

### SSL Certificate Issues

1. **Certificate not found:**
   ```bash
   ls -la /opt/aris-rag/nginx/ssl/
   ```
   If missing, run `setup_ssl.sh` again.

2. **Let's Encrypt renewal failed:**
   ```bash
   sudo certbot renew --dry-run
   ```

3. **Self-signed certificate expired:**
   ```bash
   sudo ./scripts/setup_ssl.sh
   # Select option 2 to regenerate
   ```

### nginx Not Accessible

1. **Check nginx status:**
   ```bash
   docker ps | grep nginx
   docker logs aris-rag-nginx
   ```

2. **Check port binding:**
   ```bash
   netstat -tlnp | grep -E ':(80|443)'
   ```

3. **Check firewall:**
   ```bash
   # UFW
   sudo ufw status
   
   # firewalld
   sudo firewall-cmd --list-all
   ```

### Streamlit Not Responding

1. **Check Streamlit container:**
   ```bash
   docker ps | grep aris-rag-app
   docker logs aris-rag-app
   ```

2. **Test direct connection:**
   ```bash
   docker exec aris-rag-app curl http://localhost:8501/_stcore/health
   ```

3. **Check resource limits:**
   ```bash
   docker stats aris-rag-app
   ```

### High Memory Usage

1. **Check memory usage:**
   ```bash
   docker stats --no-stream
   ```

2. **Adjust resource limits** in `docker-compose.prod.yml`:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 4G
   ```

3. **Restart containers:**
   ```bash
   docker-compose -f docker-compose.prod.yml restart
   ```

### File Upload Issues

1. **Check file size limits:**
   - nginx: `client_max_body_size 100M` in `nginx.conf`
   - Streamlit: Check container logs

2. **Check disk space:**
   ```bash
   df -h
   ```

### Network Issues

1. **Test Docker network:**
   ```bash
   docker network inspect aris-network
   ```

2. **Test connectivity:**
   ```bash
   docker exec aris-rag-nginx ping -c 3 aris-rag
   ```

## Security Best Practices

1. **Keep Docker updated:**
   ```bash
   sudo apt-get update && sudo apt-get upgrade docker-ce
   ```

2. **Regular backups:**
   - Set up automated backups for vectorstore
   - Backup .env file securely

3. **Monitor logs:**
   - Set up log rotation
   - Monitor for suspicious activity

4. **Update application:**
   - Regularly pull security updates
   - Rebuild containers with latest base images

5. **Firewall rules:**
   - Only open necessary ports (22, 80, 443)
   - Consider restricting SSH access by IP

6. **SSL certificates:**
   - Use Let's Encrypt for production
   - Monitor certificate expiration
   - Set up alerts for renewal failures

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Streamlit Deployment Guide](https://docs.streamlit.io/deploy)

## Support

For issues or questions:
1. Check logs: `docker-compose -f docker-compose.prod.yml logs`
2. Review this troubleshooting guide
3. Check application logs in the Streamlit UI
4. Review nginx access/error logs in `nginx/logs/`

