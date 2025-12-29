#!/bin/bash
# Deploy Focused API to Server

echo "=========================================="
echo "DEPLOYING FOCUSED API TO SERVER"
echo "=========================================="
echo ""

# Step 1: Copy deployment package
echo "Step 1: Copying deployment package to server..."
scp focused_api_deployment.tar.gz ubuntu@44.221.84.58:/tmp/

if [ $? -ne 0 ]; then
    echo "❌ Failed to copy files. Please check SSH access."
    exit 1
fi

echo "✅ Files copied successfully"
echo ""

# Step 2: Deploy on server
echo "Step 2: Deploying on server..."
ssh ubuntu@44.221.84.58 << 'ENDSSH'
cd /tmp
tar -xzf focused_api_deployment.tar.gz
sudo cp api/focused_endpoints.py /home/ubuntu/aris/api/
sudo cp api/main.py /home/ubuntu/aris/api/
sudo systemctl restart aris-fastapi
echo "✅ Deployment complete!"
echo ""
echo "Waiting 5 seconds for service to start..."
sleep 5
ENDSSH

echo ""
echo "=========================================="
echo "TESTING DEPLOYED ENDPOINTS"
echo "=========================================="
echo ""

# Test 1: System status
echo "Test 1: System Status"
echo "---------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/status" | python3 -m json.tool
echo ""

# Test 2: Get configuration
echo "Test 2: Get All Configuration"
echo "------------------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/config" | python3 -m json.tool | head -40
echo ""

# Test 3: Get library
echo "Test 3: Get Document Library"
echo "-----------------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/library" | python3 -m json.tool | head -30
echo ""

# Test 4: Get metrics
echo "Test 4: Get Metrics"
echo "-------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/metrics" | python3 -m json.tool
echo ""

# Test 5: Update configuration
echo "Test 5: Update Configuration"
echo "----------------------------"
curl -s -X POST "http://44.221.84.58:8500/v1/config" \
  -H "Content-Type: application/json" \
  -d '{"api": {"provider": "cerebras"}}' | python3 -m json.tool
echo ""

# Test 6: Verify update
echo "Test 6: Verify Configuration Update"
echo "------------------------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/config?section=api" | python3 -m json.tool
echo ""

echo "=========================================="
echo "✅ DEPLOYMENT AND TESTING COMPLETE"
echo "=========================================="
echo ""
echo "Available endpoints:"
echo "  GET/POST /v1/config       - Configuration"
echo "  GET      /v1/library      - Document library"
echo "  GET      /v1/library/{id} - Document details"
echo "  GET      /v1/metrics      - Metrics"
echo "  GET      /v1/status       - System status"
echo ""
echo "Plus existing endpoints:"
echo "  POST /documents           - Upload"
echo "  POST /query              - Query"
echo ""
