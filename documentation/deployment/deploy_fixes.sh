#!/bin/bash
# Deploy API fixes to server

echo "=========================================="
echo "Deploying API Fixes to Server"
echo "=========================================="

SERVER="ubuntu@44.221.84.58"
REMOTE_PATH="/home/ubuntu/aris"

echo ""
echo "[Step 1/4] Copying fixed files to server..."
echo "Files to copy: api/schemas.py, api/main.py"

# Create a temporary directory with the files
mkdir -p /tmp/aris_deploy
cp api/schemas.py /tmp/aris_deploy/
cp api/main.py /tmp/aris_deploy/

# Since we don't have SSH key configured, we'll use an alternative approach
# Create a tar file that can be manually uploaded
cd /tmp/aris_deploy
tar -czf /tmp/aris_fixes.tar.gz schemas.py main.py
cd -

echo "✅ Created deployment package: /tmp/aris_fixes.tar.gz"
echo ""
echo "⚠️  SSH key not configured. Please manually deploy using one of these methods:"
echo ""
echo "METHOD 1: If you have SSH access configured elsewhere:"
echo "  scp /tmp/aris_fixes.tar.gz $SERVER:/tmp/"
echo "  ssh $SERVER 'cd /tmp && tar -xzf aris_fixes.tar.gz && mv schemas.py main.py $REMOTE_PATH/api/ && sudo systemctl restart aris-fastapi'"
echo ""
echo "METHOD 2: Use server's web interface or file manager to:"
echo "  1. Upload /tmp/aris_fixes.tar.gz to server"
echo "  2. Extract it: tar -xzf aris_fixes.tar.gz"
echo "  3. Move files to $REMOTE_PATH/api/"
echo "  4. Restart service: sudo systemctl restart aris-fastapi"
echo ""
echo "METHOD 3: Use git (if server has access):"
echo "  ssh $SERVER"
echo "  cd $REMOTE_PATH"
echo "  git pull origin main"
echo "  sudo systemctl restart aris-fastapi"
echo ""

# Clean up
rm -rf /tmp/aris_deploy

echo "=========================================="
echo "Deployment package ready!"
echo "=========================================="
