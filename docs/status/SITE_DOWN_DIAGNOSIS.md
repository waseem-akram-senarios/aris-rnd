# Site Down - Diagnosis and Recovery

## Issue
**Site is down**: http://35.175.133.235/
**SSH Connection**: Timed out

## Possible Causes

### 1. EC2 Instance Stopped/Terminated
- **Check**: AWS Console → EC2 → Instances
- **Status**: Check if instance is "running", "stopped", or "terminated"
- **Fix**: Start the instance if stopped

### 2. Security Group Issues
- **Check**: AWS Console → EC2 → Security Groups
- **Ports needed**:
  - Port 22 (SSH) - for management
  - Port 80 (HTTP) - for application
- **Fix**: Ensure both ports are open to your IP or 0.0.0.0/0

### 3. Network/Internet Issues
- **Check**: Can you ping the IP?
- **Fix**: Check your internet connection

### 4. Container Stopped
- **Check**: If SSH works, check Docker container
- **Fix**: Restart container

## Recovery Steps

### Step 1: Check EC2 Instance Status
1. Go to AWS Console
2. Navigate to EC2 → Instances
3. Find instance with IP: 35.175.133.235
4. Check status:
   - ✅ **Running**: Continue to Step 2
   - ⚠️ **Stopped**: Click "Start Instance"
   - ❌ **Terminated**: Need to create new instance

### Step 2: Check Security Groups
1. Select the instance
2. Go to "Security" tab
3. Click on Security Group
4. Check Inbound Rules:
   - Port 22 (SSH) from your IP or 0.0.0.0/0
   - Port 80 (HTTP) from 0.0.0.0/0
5. If missing, add rules

### Step 3: Restart Container (if SSH works)
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
sudo docker ps -a
sudo docker start aris-rag-app
# Or restart
sudo docker restart aris-rag-app
```

### Step 4: Redeploy (if needed)
```bash
cd /home/senarios/Desktop/aris
./scripts/deploy.sh
```

## Quick Checks

### Check Instance Status (AWS Console)
- Instance State: Should be "running"
- Status Checks: Should be "2/2 checks passed"
- Public IP: Should be 35.175.133.235

### Check Security Groups
- Inbound Rules:
  - Type: SSH, Port: 22, Source: Your IP or 0.0.0.0/0
  - Type: HTTP, Port: 80, Source: 0.0.0.0/0

### Check Container (if SSH works)
```bash
sudo docker ps -a | grep aris-rag
sudo docker logs aris-rag-app --tail=50
```

## Most Likely Issue

**EC2 Instance is stopped or security group is blocking access.**

## Next Steps

1. **Check AWS Console** - Verify instance is running
2. **Check Security Groups** - Verify ports 22 and 80 are open
3. **Start Instance** - If stopped, start it
4. **Wait 2-3 minutes** - For instance to fully boot
5. **Test Connection** - Try accessing http://35.175.133.235/ again

## If Instance is Running

If the instance shows as "running" in AWS Console but still can't connect:

1. **Check Status Checks** - Should be "2/2 checks passed"
2. **Check System Logs** - In EC2 Console → Instance → Actions → Monitor and troubleshoot → Get system log
3. **Check Security Groups** - Ensure ports are open
4. **Try SSH** - After confirming security group allows SSH

## Recovery Script

Once SSH is working, run:
```bash
cd /opt/aris-rag
sudo docker ps -a
sudo docker start aris-rag-app || sudo docker-compose -f docker-compose.prod.port80.yml up -d
```


