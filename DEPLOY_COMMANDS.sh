#!/bin/bash
# Deploy Enhanced API - Run this script

echo "=========================================="
echo "DEPLOYING ENHANCED API"
echo "=========================================="
echo ""

# Copy to server
echo "Copying files to server..."
scp focused_api_enhanced.tar.gz ubuntu@44.221.84.58:/tmp/

if [ $? -ne 0 ]; then
    echo "❌ Failed to copy. Check SSH access."
    exit 1
fi

echo "✅ Files copied"
echo ""

# Deploy on server
echo "Deploying on server..."
ssh ubuntu@44.221.84.58 << 'ENDSSH'
cd /tmp
tar -xzf focused_api_enhanced.tar.gz
sudo cp api/focused_endpoints.py /home/ubuntu/aris/api/
sudo cp api/main.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
echo "✅ Deployed and restarted!"
sleep 3
ENDSSH

echo ""
echo "=========================================="
echo "TESTING DEPLOYMENT"
echo "=========================================="
echo ""

# Test status
echo "Testing GET /v1/status..."
curl -s http://44.221.84.58:8500/v1/status | python3 -m json.tool | head -20

echo ""
echo "=========================================="
echo "✅ DEPLOYMENT COMPLETE"
echo "=========================================="
echo ""
echo "Open Swagger UI to test:"
echo "http://44.221.84.58:8500/docs"
echo ""
