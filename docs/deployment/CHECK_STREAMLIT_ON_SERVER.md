# Check if Streamlit Service is Running on Server

## Quick Check Commands

**SSH to server first:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

**Then run these commands on the server:**

### 1. Check if containers are running
```bash
docker ps | grep aris-rag
```

**Expected output if running:**
```
CONTAINER ID   IMAGE              STATUS         PORTS
xxxxx          aris-rag:latest   Up 5 minutes   0.0.0.0:8501->8501/tcp
```

**If nothing shows:** Service is NOT running

### 2. Check all containers (including stopped)
```bash
docker ps -a | grep aris-rag
```

### 3. Check if Streamlit is responding
```bash
docker exec aris-rag-app curl http://localhost:8501/_stcore/health
```

**Expected output if healthy:**
```
{"status": "healthy"}
```
or HTTP 200 response

### 4. Check what's listening on port 8501
```bash
sudo netstat -tlnp | grep 8501
# OR
sudo ss -tlnp | grep 8501
```

**Expected output if listening:**
```
tcp6       0      0 :::8501                 :::*                    LISTEN      xxxxx/docker-proxy
```

### 5. Check container logs
```bash
docker logs --tail=50 aris-rag-app
```

### 6. Check container status in detail
```bash
docker ps --filter "name=aris-rag" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

## One-Line Status Check

```bash
docker ps --filter "name=aris-rag-app" && echo "✅ Running" || echo "❌ Not running"
```

## If Service is NOT Running

**Start the service:**
```bash
cd /opt/aris-rag

# Check if .env file exists
ls -la .env

# If missing, create it
nano .env  # Add: OPENAI_API_KEY=your_key_here

# Start with Docker
docker-compose -f docker-compose.prod.direct.yml up -d

# Check status
docker ps
docker logs -f aris-rag-app
```

## If Service IS Running

**Test locally on server:**
```bash
curl http://localhost:8501/_stcore/health
```

**If this works but external access doesn't:**
- Port 8501 is not open in AWS Security Group
- Open it following: `docs/HOW_TO_OPEN_PORTS.md`

## Complete Check Script (Run on Server)

```bash
#!/bin/bash
echo "=== Streamlit Service Check ==="
echo ""

# Check containers
echo "1. Containers:"
docker ps -a | grep aris-rag || echo "   No containers found"

echo ""
echo "2. Health check:"
docker exec aris-rag-app curl -s http://localhost:8501/_stcore/health 2>/dev/null && echo "   ✅ Healthy" || echo "   ❌ Not responding"

echo ""
echo "3. Port 8501:"
sudo netstat -tlnp | grep 8501 || echo "   ❌ Not listening"

echo ""
echo "4. Recent logs:"
docker logs --tail=5 aris-rag-app 2>&1 | tail -5
```

## Final URL

Once service is running and port 8501 is open:
```
http://35.175.133.235:8501
```






