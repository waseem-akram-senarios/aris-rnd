#!/bin/bash
# Automated Deployment and Testing Script

set -e

SERVER="44.221.84.58"
USER="ubuntu"
REMOTE_PATH="/home/ubuntu/aris"

echo "=============================================="
echo "AUTOMATED DEPLOYMENT AND TESTING"
echo "=============================================="
echo ""

# Step 1: Create deployment package
echo "[1/5] Creating deployment package..."
tar -czf aris_deployment.tar.gz api/schemas.py api/main.py
echo "✅ Package created: aris_deployment.tar.gz"

# Step 2: Display deployment command
echo ""
echo "[2/5] Deployment command ready!"
echo ""
echo "Run this command to deploy:"
echo "-------------------------------------------"
echo "scp aris_deployment.tar.gz $USER@$SERVER:/tmp/ && ssh $USER@$SERVER 'cd /tmp && tar -xzf aris_deployment.tar.gz && sudo cp schemas.py main.py $REMOTE_PATH/api/ && sudo systemctl restart aris-fastapi && echo \"✅ Deployed!\"'"
echo "-------------------------------------------"
echo ""

# Step 3: Wait for user to deploy
echo "[3/5] Waiting for deployment..."
echo "Press ENTER after you've run the deployment command above..."
read

# Step 4: Verify server is responding
echo ""
echo "[4/5] Verifying server..."
if curl -s --max-time 5 http://$SERVER:8500/docs > /dev/null; then
    echo "✅ Server is responding"
else
    echo "❌ Server not responding"
    exit 1
fi

# Step 5: Run comprehensive tests
echo ""
echo "[5/5] Running comprehensive API tests..."
echo "=============================================="
python3 comprehensive_api_test.py

echo ""
echo "=============================================="
echo "DEPLOYMENT AND TESTING COMPLETE"
echo "=============================================="
