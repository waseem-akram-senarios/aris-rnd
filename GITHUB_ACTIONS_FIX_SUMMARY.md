# GitHub Actions Deployment Fix

## Problem
The GitHub Actions workflow failed because:
1. **Missing GitHub Secrets**: The workflow requires 4 secrets that may not be configured
2. **Git Authentication Issue**: The workflow tried to use Git on the server, which requires authentication

## Solution Applied

### 1. Updated Workflow to Use rsync
- Changed from `git pull` to `rsync` (matches `deploy-fast.sh`)
- No Git authentication needed on server
- Faster and more reliable

### 2. Fixed Variable Expansion
- Fixed SSH heredoc variable expansion
- Properly passes server directory path

### 3. Created Setup Documentation
- Added `docs/deployment/GITHUB_ACTIONS_SETUP.md`
- Step-by-step guide for configuring secrets

## Next Steps

### Option 1: Fix GitHub Secrets (Recommended for CI/CD)

1. **Go to GitHub Repository Settings:**
   - https://github.com/waseem-intelycx/aris-rnd/settings/secrets/actions

2. **Add these 4 secrets:**
   - `SERVER_IP`: `35.175.133.235`
   - `SERVER_USER`: `ec2-user`
   - `SERVER_DIR`: `/opt/aris-rag`
   - `EC2_PEM_KEY`: (Full content of `scripts/ec2_wah_pk.pem`)

3. **Get PEM key content:**
   ```bash
   cat scripts/ec2_wah_pk.pem
   # Copy entire output including BEGIN/END lines
   ```

4. **Push updated workflow:**
   ```bash
   git add .github/workflows/deploy.yml
   git commit -m "Fix: Update GitHub Actions to use rsync"
   git push origin main
   ```

### Option 2: Use Manual Deployment (Faster for R&D)

If you don't want to set up CI/CD right now:

```bash
./scripts/deploy-fast.sh
```

This is faster (~1-2 minutes) and doesn't require GitHub secrets.

## Files Changed

- ✅ `.github/workflows/deploy.yml` - Updated to use rsync
- ✅ `docs/deployment/GITHUB_ACTIONS_SETUP.md` - Setup guide created

## Current Status

- ✅ Workflow file fixed
- ⚠️  GitHub secrets need to be configured
- ✅ Manual deployment (`deploy-fast.sh`) still works

## Testing

After configuring secrets, the workflow will:
1. Trigger automatically on push to `main`
2. Sync code using rsync
3. Build Docker image
4. Deploy container
5. Verify health check

Expected time: ~3-5 minutes
