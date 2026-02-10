# Check if Service is Running on Server

## Current Status: ❌ Port 8501 is CLOSED

This means either:
1. Service is not running on server, OR
2. Port 8501 is not open in AWS Security Group

## How to Check Service Status

### Method 1: SSH to Server and Check

```bash
# 1. SSH to server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235

# 2. Check if containers are running
docker ps | grep aris-rag

# 3. Check all containers (including stopped)
docker ps -a | grep aris-rag

# 4. Check Streamlit health
docker exec aris-rag-app curl http://localhost:8501/_stcore/health

# 5. Check logs
docker logs --tail=50 aris-rag-app

# 6. Check what's listening on port 8501
sudo netstat -tlnp | grep 8501
```

### Method 2: Using Check Script (if PEM file exists)

```bash
./scripts/check_server_status.sh
```

## What You Should See if Service is Running

**✅ Service Running:**
```
CONTAINER ID   IMAGE              STATUS         PORTS
xxxxx          aris-rag:latest   Up 5 minutes   0.0.0.0:8501->8501/tcp
```

**❌ Service Not Running:**
```
(No output or containers show "Exited" status)
```

## If Service is NOT Running

### Start the Service:

```bash
# SSH to server
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235

# Navigate to app directory
cd /opt/aris-rag

# Make sure .env file exists with API keys
nano .env  # Add OPENAI_API_KEY=your_key_here

# Start with Docker
docker-compose -f docker-compose.prod.direct.yml up -d

# Check status
docker ps
docker logs -f aris-rag-app
```

## If Service IS Running but Port is Closed

### Open Port 8501 in AWS:

1. **AWS Console** → EC2 → Security Groups
2. Find your instance's security group
3. **Edit Inbound Rules** → **Add Rule**
4. Configure:
   - **Type:** Custom TCP
   - **Port:** 8501
   - **Source:** 0.0.0.0/0
5. **Save rules**
6. Wait 10-30 seconds
7. Test: `http://35.175.133.235:8501`

## Quick Status Commands

**From your local machine (if PEM file exists):**
```bash
# Check containers
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 "docker ps | grep aris-rag"

# Check health
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 "docker exec aris-rag-app curl -s http://localhost:8501/_stcore/health"

# View logs
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235 "cd /opt/aris-rag && docker logs --tail=20 aris-rag-app"
```

## Final URL (When Running)

Once service is running and port is open:
```
http://35.175.133.235:8501
```






