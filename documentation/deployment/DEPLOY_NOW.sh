#!/bin/bash
# Complete Deployment Script for ARIS API Fixes
# This script deploys all fixes to the server

set -e  # Exit on error

SERVER="44.221.84.58"
USER="ubuntu"
REMOTE_PATH="/home/ubuntu/aris"

echo "=============================================="
echo "ARIS API FIXES - COMPLETE DEPLOYMENT"
echo "=============================================="
echo ""

# Check if we can reach the server
echo "[1/6] Checking server connectivity..."
if curl -s --max-time 5 http://$SERVER:8500/docs > /dev/null; then
    echo "✅ Server is reachable"
else
    echo "❌ Cannot reach server at http://$SERVER:8500"
    exit 1
fi

echo ""
echo "[2/6] Creating deployment package..."
tar -czf aris_api_fixes.tar.gz api/schemas.py api/main.py
echo "✅ Created: aris_api_fixes.tar.gz"

echo ""
echo "[3/6] Deployment package ready!"
echo "📦 Package location: $(pwd)/aris_api_fixes.tar.gz"
echo "📦 Package size: $(ls -lh aris_api_fixes.tar.gz | awk '{print $5}')"

echo ""
echo "=============================================="
echo "DEPLOYMENT INSTRUCTIONS"
echo "=============================================="
echo ""
echo "Since SSH key is not configured, please deploy manually:"
echo ""
echo "METHOD 1: Using SCP (if you have SSH access)"
echo "-------------------------------------------"
echo "scp aris_api_fixes.tar.gz $USER@$SERVER:/tmp/"
echo "ssh $USER@$SERVER << 'ENDSSH'"
echo "cd /tmp"
echo "tar -xzf aris_api_fixes.tar.gz"
echo "sudo cp schemas.py $REMOTE_PATH/api/"
echo "sudo cp main.py $REMOTE_PATH/api/"
echo "sudo systemctl restart aris-fastapi"
echo "echo 'Deployment complete!'"
echo "ENDSSH"
echo ""
echo "METHOD 2: Using Git (if server has git access)"
echo "-------------------------------------------"
echo "ssh $USER@$SERVER << 'ENDSSH'"
echo "cd $REMOTE_PATH"
echo "git stash  # Save any local changes"
echo "git pull origin main"
echo "sudo systemctl restart aris-fastapi"
echo "echo 'Deployment complete!'"
echo "ENDSSH"
echo ""
echo "METHOD 3: Manual File Upload"
echo "-------------------------------------------"
echo "1. Upload aris_api_fixes.tar.gz to server"
echo "2. Extract: tar -xzf aris_api_fixes.tar.gz"
echo "3. Copy files:"
echo "   sudo cp schemas.py $REMOTE_PATH/api/"
echo "   sudo cp main.py $REMOTE_PATH/api/"
echo "4. Restart: sudo systemctl restart aris-fastapi"
echo ""
echo "=============================================="
echo ""

# Create a simple deployment verification script
cat > verify_deployment.sh << 'EOF'
#!/bin/bash
echo "Verifying deployment..."
echo ""
echo "Testing search_mode fix..."
response=$(curl -s -X POST http://44.221.84.58:8500/query \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "search_mode": "hybrid", "k": 3}' \
  --max-time 10)

if echo "$response" | grep -q "answer"; then
    echo "✅ Query endpoint working!"
else
    echo "⚠️  Query endpoint response: $response"
fi

echo ""
echo "Running full test suite..."
python3 test_api_fixes.py
EOF

chmod +x verify_deployment.sh

echo "[4/6] Created verification script: verify_deployment.sh"
echo ""
echo "[5/6] After deployment, run: ./verify_deployment.sh"
echo ""
echo "[6/6] Ready for deployment!"
echo ""
echo "=============================================="
echo "QUICK DEPLOYMENT (Copy & Paste)"
echo "=============================================="
echo ""
echo "If you have SSH access, copy and paste this:"
echo ""
echo "scp aris_api_fixes.tar.gz $USER@$SERVER:/tmp/ && ssh $USER@$SERVER 'cd /tmp && tar -xzf aris_api_fixes.tar.gz && sudo cp schemas.py main.py $REMOTE_PATH/api/ && sudo systemctl restart aris-fastapi && echo \"✅ Deployment complete!\"'"
echo ""
echo "=============================================="
