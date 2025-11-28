# Fast R&D Git Deployment Setup

## Overview

Fast Git-based deployment system optimized for R&D testing cycles. Deploy changes to server in ~1-2 minutes.

## Quick Start

### Daily R&D Workflow (1-2 minutes)

```bash
# 1. Make changes locally
# Edit your code...

# 2. Push to Git
git add .
git commit -m "Test change"
git push origin main

# 3. Deploy fast
./scripts/deploy-fast.sh

# 4. Test on server immediately
# Visit: http://35.175.133.235/
```

**Total time: ~1-2 minutes**

## One-Time Server Setup

### Step 1: Initialize Git on Server

SSH to server:
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

On server:
```bash
cd /opt/aris-rag

# Initialize git if not already done
if [ ! -d ".git" ]; then
  sudo git init
  sudo git remote add origin https://github.com/waseem-intelycx/aris-rnd.git
  sudo git fetch origin
  sudo git checkout -b main origin/main || sudo git checkout main
  sudo chown -R ec2-user:ec2-user .
fi

# Ensure .env exists
if [ ! -f ".env" ]; then
  echo "⚠️  Create .env file with your API keys"
  nano .env
  # Add: OPENAI_API_KEY=your_key_here
fi
```

### Step 2: Verify Setup

```bash
# On server, check git status
cd /opt/aris-rag
git status

# Should show: "On branch main" and "Your branch is up to date with 'origin/main'"
```

## Usage

### Fast Deployment (Primary Method)

```bash
# After pushing to Git
./scripts/deploy-fast.sh
```

**What it does:**
1. Pulls latest code from Git on server
2. Backs up .env file
3. Builds Docker image
4. Restarts container
5. Health check

**Time: ~1-2 minutes**

### Optional: CI/CD Automation

If you want automatic deployment on every push:

1. **Add GitHub Secrets:**
   - Go to: `Settings → Secrets and variables → Actions`
   - Add secrets:
     - `SERVER_IP`: `35.175.133.235`
     - `SERVER_USER`: `ec2-user`
     - `SERVER_DIR`: `/opt/aris-rag`
     - `EC2_PEM_KEY`: (paste full content of `scripts/ec2_wah_pk.pem`)

2. **Enable CI/CD:**
   - Push workflow to Git (already created)
   - Every push to `main` will auto-deploy

3. **Manual Trigger:**
   - Go to: `Actions` tab in GitHub
   - Select: `Deploy to Production`
   - Click: `Run workflow`

## Configuration

**Server Details:**
- IP: `35.175.133.235`
- User: `ec2-user`
- Directory: `/opt/aris-rag`
- PEM File: `scripts/ec2_wah_pk.pem`

**Docker Configuration:**
- Container: `aris-rag-app`
- Port: `80:8501`
- Resources: 7 CPUs, 12GB RAM
- Health Check: Streamlit endpoint

## Troubleshooting

### Deployment Fails

1. **Check Git on server:**
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   cd /opt/aris-rag
   git status
   ```

2. **Check container:**
   ```bash
   sudo docker ps -a
   sudo docker logs aris-rag-app
   ```

3. **Check .env file:**
   ```bash
   ls -la .env
   # Should exist and have API keys
   ```

### .env File Missing

- Create manually on server:
  ```bash
  ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
  cd /opt/aris-rag
  nano .env
  # Add: OPENAI_API_KEY=your_key_here
  ```

### Git Not Initialized

- Run one-time setup (see above)
- Or clone fresh:
  ```bash
  cd /opt
  sudo rm -rf aris-rag
  sudo git clone https://github.com/waseem-intelycx/aris-rnd.git aris-rag
  sudo chown -R ec2-user:ec2-user aris-rag
  cd aris-rag
  ```

## Speed Tips

1. **Use fast script:** `./scripts/deploy-fast.sh` (faster than CI/CD)
2. **Skip local testing:** Deploy directly for quick R&D iterations
3. **Small commits:** Push frequently for faster feedback
4. **Monitor logs:** `sudo docker logs -f aris-rag-app` on server

## Security

- ✅ `.env` file is NOT in Git (protected by .gitignore)
- ✅ `.env` is backed up before each deployment
- ✅ `.env` is restored from backup (never from Git)
- ✅ PEM key stays local (not in Git)
- ✅ No credentials in code or logs

## Workflow Comparison

| Method | Speed | Automation | Best For |
|--------|-------|------------|----------|
| **deploy-fast.sh** | ~1-2 min | Manual | R&D, quick testing |
| **CI/CD** | ~2-3 min | Automatic | Production, team use |

**For R&D:** Use `deploy-fast.sh` for fastest iteration.

## Summary

**Fastest R&D Workflow:**
1. Make changes
2. `git push origin main`
3. `./scripts/deploy-fast.sh`
4. Test on server

**Time: ~1-2 minutes per iteration**

---

**Last Updated:** November 28, 2025

