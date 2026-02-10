# Troubleshooting: Connection Timeout

## Error: `ERR_CONNECTION_TIMED_OUT`

This error means the application is **not running** on the server yet. Follow these steps to deploy:

## Step-by-Step Deployment

### Step 1: Verify Server Access

First, make sure you can SSH to the server:

```bash
# From your local machine
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

If this fails, check:
- PEM file exists: `ls -la scripts/ec2_wah_pk.pem`
- Security group allows SSH (port 22)
- Server is running

### Step 2: Initial Server Setup (One-Time)

**On the server**, run the setup script:

```bash
# SSH to server first
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235

# Then run setup
sudo bash /opt/aris-rag/scripts/server_setup.sh
```

**OR** if the directory doesn't exist yet, copy the script to server:

```bash
# From local machine
scp -i scripts/ec2_wah_pk.pem scripts/server_setup.sh ec2-user@35.175.133.235:/tmp/
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 "sudo bash /tmp/server_setup.sh"
```

This installs:
- Docker
- Docker Compose
- Configures firewall
- Creates directories

### Step 3: Deploy Application

**From your local machine**, run:

```bash
cd /home/senarios/Desktop/aris
./scripts/deploy.sh
```

This will:
1. Transfer files to server
2. Copy `.env` file
3. Build Docker images
4. Start containers

### Step 4: Verify Deployment

**On the server**, check if containers are running:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
docker ps
```

You should see:
- `aris-rag-app` (Streamlit)
- `aris-rag-nginx` (Nginx)

### Step 5: Check Security Group / Firewall

**IMPORTANT**: Make sure your AWS Security Group allows:
- Port **80** (HTTP)
- Port **443** (HTTPS)
- Port **22** (SSH)

**In AWS Console:**
1. Go to EC2 → Security Groups
2. Find your instance's security group
3. Edit Inbound Rules
4. Add rules for ports 80, 443 (source: 0.0.0.0/0)

### Step 6: Test Locally on Server

**On the server**, test if the application responds:

```bash
# Check if containers are running
docker ps

# Check nginx logs
docker logs aris-rag-nginx

# Test local connection
curl http://localhost/health
```

If this works but external access doesn't, it's a firewall/security group issue.

## Quick Fix Commands

### If containers are not running:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
docker-compose -f docker-compose.prod.yml up -d
```

### If you need to restart:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
docker-compose -f docker-compose.prod.yml restart
```

### Check logs for errors:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
docker-compose -f docker-compose.prod.yml logs
```

## Common Issues

### Issue 1: "Docker not found"
**Solution**: Run `server_setup.sh` on the server

### Issue 2: "Permission denied"
**Solution**: Make sure user is in docker group:
```bash
sudo usermod -aG docker ec2-user
# Then logout and login again
```

### Issue 3: "Port already in use"
**Solution**: Check what's using the port:
```bash
sudo netstat -tlnp | grep -E ':(80|443)'
```

### Issue 4: "Cannot connect from outside"
**Solution**: Check AWS Security Group allows ports 80 and 443

## Expected URLs After Deployment

- **HTTP**: `http://35.175.133.235`
- **HTTPS**: `https://35.175.133.235` (after SSL setup)

## Need Help?

Run the diagnostic script:
```bash
./scripts/check_deployment.sh
```

This will check:
- SSH connectivity
- Docker installation
- Container status
- Port accessibility
- Application health

