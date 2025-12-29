#!/bin/bash
# Deploy Consolidated API to Server

echo "=========================================="
echo "DEPLOY CONSOLIDATED API"
echo "=========================================="
echo ""

# Step 1: Copy deployment package to server
echo "Step 1: Copying files to server..."
scp consolidated_api_deployment.tar.gz ubuntu@44.221.84.58:/tmp/

# Step 2: SSH into server and deploy
echo ""
echo "Step 2: Deploying on server..."
ssh ubuntu@44.221.84.58 << 'ENDSSH'
cd /tmp
tar -xzf consolidated_api_deployment.tar.gz
sudo cp api/consolidated_endpoints.py /home/ubuntu/aris/api/
sudo cp api/main.py /home/ubuntu/aris/api/
sudo cp api/schemas.py /home/ubuntu/aris/api/
sudo cp api/service.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
echo "✅ Deployment complete!"
echo ""
echo "Waiting 5 seconds for service to start..."
sleep 5
ENDSSH

echo ""
echo "=========================================="
echo "TESTING CONSOLIDATED API"
echo "=========================================="
echo ""

# Test 1: Get all configuration
echo "Test 1: Get All Configuration"
echo "------------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/config" | python3 -m json.tool | head -30
echo ""

# Test 2: Get specific config section
echo "Test 2: Get Model Settings Only"
echo "--------------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/config?section=model" | python3 -m json.tool
echo ""

# Test 3: Get system info
echo "Test 3: Get Complete System Info"
echo "---------------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/system" | python3 -m json.tool | head -40
echo ""

# Test 4: Get library only
echo "Test 4: Get Document Library Only"
echo "----------------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/system?include=library" | python3 -m json.tool | head -20
echo ""

# Test 5: Get metrics only
echo "Test 5: Get Metrics Only"
echo "------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/system?include=metrics" | python3 -m json.tool
echo ""

# Test 6: Update configuration
echo "Test 6: Update Configuration (Change temperature)"
echo "--------------------------------------------------"
curl -s -X POST "http://44.221.84.58:8500/api/config" \
  -H "Content-Type: application/json" \
  -d '{"model": {"temperature": 0.3}}' | python3 -m json.tool
echo ""

# Test 7: Verify update
echo "Test 7: Verify Configuration Update"
echo "------------------------------------"
curl -s -X GET "http://44.221.84.58:8500/api/config?section=model" | python3 -m json.tool
echo ""

echo "=========================================="
echo "DEPLOYMENT AND TESTING COMPLETE"
echo "=========================================="
