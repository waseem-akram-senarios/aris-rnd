# Direct Streamlit on Port 80 Setup

## Overview

This configuration runs Streamlit directly on port 80 without Nginx reverse proxy. This simplifies the setup but removes some features.

## Pros and Cons

### ✅ Pros:
- **Simpler Setup**: One less container to manage
- **Clean URL**: Access at `http://your-server-ip` (no port number)
- **Less Resources**: No Nginx container running
- **Faster Startup**: One less service to start
- **Easier Debugging**: Direct access to Streamlit logs

### ⚠️ Cons:
- **No SSL/HTTPS**: Streamlit doesn't natively support HTTPS (would need a separate solution)
- **No Security Headers**: No Nginx security headers (X-Frame-Options, etc.)
- **No Rate Limiting**: No built-in protection against abuse
- **Development Server**: Streamlit is designed as a development server, not production-optimized
- **Less Control**: No advanced routing, load balancing, or caching

## Setup Instructions

### Step 1: Stop Current Deployment

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
sudo docker-compose -f docker-compose.prod.yml down
```

### Step 2: Deploy Direct Port 80 Configuration

```bash
# From your local machine
cd /home/senarios/Desktop/aris

# Copy the new docker-compose file to server
scp -i scripts/ec2_wah_pk.pem docker-compose.prod.port80.yml ec2-user@35.175.133.235:/opt/aris-rag/

# SSH to server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag

# Start with new configuration
sudo docker-compose -f docker-compose.prod.port80.yml up -d

# Check status
sudo docker ps
```

### Step 3: Verify

```bash
# Check container is running
sudo docker ps --filter "name=aris-rag-app"

# Check logs
sudo docker logs -f aris-rag-app

# Test access
curl http://localhost/
```

### Step 4: Access Application

**URL**: `http://35.175.133.235/` (no port number needed!)

## Configuration Details

### Port Mapping
- **Host Port**: 80 (standard HTTP port)
- **Container Port**: 8501 (Streamlit's default port)
- **Mapping**: `80:8501` in docker-compose

### Streamlit Configuration

The Streamlit app runs with these settings (from `.streamlit/config.toml`):
- Port: 8501 (inside container)
- Address: 0.0.0.0 (accessible from outside)
- File watcher: Disabled (for production)

## Comparison: Nginx vs Direct

| Feature | With Nginx | Direct Port 80 |
|---------|-----------|----------------|
| Setup Complexity | Medium | Simple |
| SSL/HTTPS | ✅ Yes | ❌ No |
| Security Headers | ✅ Yes | ❌ No |
| Rate Limiting | ✅ Yes | ❌ No |
| URL | `http://ip/` | `http://ip/` |
| Resource Usage | Higher | Lower |
| Production Ready | ✅ Yes | ⚠️ Limited |

## When to Use Direct Port 80

**Use Direct Port 80 if:**
- ✅ You want the simplest setup
- ✅ You don't need HTTPS/SSL
- ✅ You're okay with development server
- ✅ You want to save resources
- ✅ You're testing or in development

**Use Nginx if:**
- ✅ You need HTTPS/SSL
- ✅ You want production-grade security
- ✅ You need rate limiting
- ✅ You want security headers
- ✅ You're in production

## Switching Back to Nginx

If you want to switch back to Nginx:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag

# Stop direct configuration
sudo docker-compose -f docker-compose.prod.port80.yml down

# Start with Nginx
sudo docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Port 80 Already in Use

If you get "port 80 already in use":

```bash
# Check what's using port 80
sudo lsof -i :80
# or
sudo netstat -tulpn | grep :80

# Stop the service (e.g., httpd)
sudo systemctl stop httpd
# or
sudo service httpd stop
```

### Container Won't Start

```bash
# Check logs
sudo docker logs aris-rag-app

# Check if port 80 is accessible
sudo docker ps --filter "name=aris-rag-app"
```

### Can't Access from Browser

1. **Check AWS Security Group**: Port 80 must be open
2. **Check Firewall**: `sudo ufw status` or `sudo firewall-cmd --list-all`
3. **Check Container**: `sudo docker ps` - container should be running
4. **Check Logs**: `sudo docker logs aris-rag-app`

## Security Considerations

When running Streamlit directly on port 80:

1. **No HTTPS**: All traffic is unencrypted
2. **No Security Headers**: Missing X-Frame-Options, CSP, etc.
3. **No Rate Limiting**: Vulnerable to abuse
4. **Development Server**: Not optimized for production

**Recommendations:**
- Use only for internal/testing environments
- Consider adding a firewall
- Monitor for abuse
- Consider switching to Nginx for production

## Summary

Running Streamlit directly on port 80 is simpler but less secure. It's great for:
- Development/testing
- Internal tools
- Quick deployments
- Resource-constrained environments

For production, consider using Nginx for better security and features.



