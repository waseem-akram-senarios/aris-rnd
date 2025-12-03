# GitHub Actions CI/CD Setup Guide

## Overview

This guide explains how to set up GitHub Actions for automatic deployment to your EC2 server.

## Prerequisites

- GitHub repository: `waseem-intelycx/aris-rnd`
- EC2 server with SSH access
- PEM key file for SSH authentication

## Step 1: Configure GitHub Secrets

GitHub Actions requires secrets to be configured in your repository settings.

### Access Secrets Settings

1. Go to your GitHub repository: `https://github.com/waseem-intelycx/aris-rnd`
2. Click **Settings** (top menu)
3. Click **Secrets and variables** → **Actions** (left sidebar)
4. Click **New repository secret** for each secret below

### Required Secrets

Add these secrets one by one:

#### 1. SERVER_IP
- **Name**: `SERVER_IP`
- **Value**: `35.175.133.235`
- **Description**: EC2 server IP address

#### 2. SERVER_USER
- **Name**: `SERVER_USER`
- **Value**: `ec2-user`
- **Description**: SSH username for EC2 server

#### 3. SERVER_DIR
- **Name**: `SERVER_DIR`
- **Value**: `/opt/aris-rag`
- **Description**: Deployment directory on server

#### 4. EC2_PEM_KEY
- **Name**: `EC2_PEM_KEY`
- **Value**: (Full content of `scripts/ec2_wah_pk.pem` file)
- **Description**: SSH private key for EC2 access

**To get PEM key content:**
```bash
cat scripts/ec2_wah_pk.pem
# Copy the entire output (including -----BEGIN RSA PRIVATE KEY----- and -----END RSA PRIVATE KEY-----)
```

**Important**: 
- Copy the ENTIRE file content (including BEGIN/END lines)
- No extra spaces or newlines
- Keep it secure - never commit to Git

## Step 2: Verify Workflow File

The workflow file is already created at `.github/workflows/deploy.yml`.

It will:
- Trigger on push to `main` branch
- Sync code using `rsync` (no Git auth needed)
- Build Docker image
- Deploy container
- Verify health check

## Step 3: Test Deployment

### Automatic Deployment

1. **Push to main branch:**
   ```bash
   git add .
   git commit -m "Test CI/CD deployment"
   git push origin main
   ```

2. **Check GitHub Actions:**
   - Go to: `https://github.com/waseem-intelycx/aris-rnd/actions`
   - You should see "Deploy to Production" workflow running
   - Click on it to see progress

### Manual Trigger

1. Go to: `https://github.com/waseem-intelycx/aris-rnd/actions`
2. Click **Deploy to Production** (left sidebar)
3. Click **Run workflow** (right side)
4. Select branch: `main`
5. Click **Run workflow**

## Troubleshooting

### Workflow Fails: "Secrets not found"

**Problem**: Missing GitHub secrets

**Solution**: 
- Go to Settings → Secrets and variables → Actions
- Verify all 4 secrets are added:
  - `SERVER_IP`
  - `SERVER_USER`
  - `SERVER_DIR`
  - `EC2_PEM_KEY`

### Workflow Fails: "SSH connection failed"

**Problem**: SSH authentication issue

**Solution**:
1. Verify PEM key secret is correct:
   - Must include BEGIN/END lines
   - No extra spaces
   - Full file content

2. Test SSH manually:
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   ```

3. Check server is running:
   ```bash
   ping 35.175.133.235
   ```

### Workflow Fails: "Docker build failed"

**Problem**: Docker build error on server

**Solution**:
1. Check server logs in GitHub Actions output
2. SSH to server and check:
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   cd /opt/aris-rag
   sudo docker build -t aris-rag:latest .
   ```

### Workflow Fails: "Health check failed"

**Problem**: Application not starting

**Solution**:
1. Check container logs:
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   sudo docker logs aris-rag-app
   ```

2. Check if port 80 is accessible:
   ```bash
   curl http://35.175.133.235/
   ```

3. Verify .env file exists on server:
   ```bash
   ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
   ls -la /opt/aris-rag/.env
   ```

## Workflow Details

### What It Does

1. **Checkout code**: Gets latest code from repository
2. **Setup SSH**: Configures SSH key for server access
3. **Setup rsync**: Installs rsync on GitHub runner
4. **Sync code**: Uses rsync to transfer code (faster than Git, no auth needed)
5. **Build Docker**: Builds Docker image on server
6. **Deploy container**: Starts container with resource limits
7. **Health check**: Verifies application is running

### Deployment Time

- **Total**: ~3-5 minutes
- **Code sync**: ~30 seconds
- **Docker build**: ~2-3 minutes
- **Container start**: ~30 seconds
- **Health check**: ~15 seconds

### Resource Limits

- **CPUs**: 7
- **Memory**: 12GB
- **Memory Reservation**: 8GB
- **Port**: 80:8501

## Comparison: CI/CD vs Manual

| Method | Speed | Automation | Best For |
|--------|-------|------------|----------|
| **GitHub Actions** | ~3-5 min | Automatic | Production, scheduled deployments |
| **deploy-fast.sh** | ~1-2 min | Manual | R&D, quick testing |

## Security Notes

- ✅ PEM key stored as GitHub secret (encrypted)
- ✅ Secrets never exposed in logs
- ✅ .env file not synced (protected)
- ✅ SSH key permissions set correctly (600)
- ✅ No credentials in code

## Disabling CI/CD

If you want to disable automatic deployment:

1. Go to: `https://github.com/waseem-intelycx/aris-rnd/settings/actions`
2. Under **Workflow permissions**, select **Disable Actions**
3. Or edit `.github/workflows/deploy.yml` and comment out the `push` trigger

## Manual Deployment (Alternative)

If CI/CD is not working, use manual deployment:

```bash
./scripts/deploy-fast.sh
```

This is faster (~1-2 minutes) and doesn't require GitHub secrets setup.




