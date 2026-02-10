# Deployment Checklist

## Current Status: ❌ Not Deployed

**Error:** `ERR_CONNECTION_REFUSED` when accessing `http://35.175.133.235:8501`

## Required Steps

### Step 1: Verify PEM File
```bash
ls -la scripts/ec2_wah_pk.pem
```
If missing, add your SSH key:
```bash
cp /path/to/your-key.pem scripts/ec2_wah_pk.pem
chmod 600 scripts/ec2_wah_pk.pem
```

### Step 2: Deploy Application
```bash
./scripts/deploy-adaptive.sh
```

This will:
- Transfer files to server
- Build Docker images
- Start containers on port 8501

### Step 3: Open Port 8501 in AWS Security Group

**In AWS Console:**
1. Go to **EC2 → Security Groups**
2. Find your instance's security group (check instance details)
3. Click **Edit inbound rules**
4. Click **Add rule**
5. Configure:
   - **Type:** Custom TCP
   - **Port range:** 8501
   - **Source:** 0.0.0.0/0 (or your IP for security)
6. Click **Save rules**

### Step 4: Verify Deployment

**Check containers on server:**
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
docker ps | grep aris-rag
```

**Check logs:**
```bash
cd /opt/aris-rag
docker-compose -f docker-compose.prod.direct.yml logs
```

### Step 5: Access Application

**Correct URL:**
```
http://35.175.133.235:8501
```

**Note:** Streamlit doesn't have `/docs` endpoint. Use the root URL above.

## Quick Deploy Command

If you have the PEM file ready:
```bash
./scripts/deploy-adaptive.sh
```

## Troubleshooting

### If deployment fails:
1. Check PEM file exists and has correct permissions (600)
2. Verify SSH access: `ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235`
3. Check if Docker is installed on server (run `server_setup.sh` if needed)

### If connection still refused after deployment:
1. Verify port 8501 is open in AWS Security Group
2. Check containers are running: `docker ps` on server
3. Check container logs for errors
4. Verify firewall on server allows port 8501






