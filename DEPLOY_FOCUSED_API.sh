#!/bin/bash
# Deploy Focused API - 5 Clean Endpoints

echo "=========================================="
echo "DEPLOY FOCUSED API"
echo "=========================================="
echo ""

# One-line deployment
scp focused_api_deployment.tar.gz ubuntu@44.221.84.58:/tmp/ && \
ssh ubuntu@44.221.84.58 'cd /tmp && tar -xzf focused_api_deployment.tar.gz && sudo cp api/focused_endpoints.py api/main.py /home/ubuntu/aris/api/ && sudo systemctl restart aris-fastapi && echo "✅ Deployed!"'

echo ""
echo "=========================================="
echo "TESTING FOCUSED API"
echo "=========================================="
echo ""

# Test 1: Health check
echo "Test 1: Health Check"
echo "--------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/health" | python3 -m json.tool
echo ""

# Test 2: Get complete system info
echo "Test 2: Complete System Info"
echo "-----------------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/system" | python3 -m json.tool | head -50
echo ""

# Test 3: Get settings only
echo "Test 3: Settings Only"
echo "---------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/system?include=settings" | python3 -m json.tool
echo ""

# Test 4: Get library only
echo "Test 4: Library Only"
echo "--------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/system?include=library" | python3 -m json.tool | head -30
echo ""

# Test 5: Get metrics only
echo "Test 5: Metrics Only"
echo "--------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/system?include=metrics" | python3 -m json.tool
echo ""

# Test 6: List documents
echo "Test 6: List Documents"
echo "----------------------"
curl -s -X GET "http://44.221.84.58:8500/v1/documents" | python3 -m json.tool | head -30
echo ""

# Test 7: Update settings
echo "Test 7: Update Settings"
echo "-----------------------"
curl -s -X POST "http://44.221.84.58:8500/v1/system/settings" \
  -H "Content-Type: application/json" \
  -d '{"api_provider": "cerebras", "model": {"temperature": 0.3}}' | python3 -m json.tool
echo ""

echo "=========================================="
echo "DEPLOYMENT AND TESTING COMPLETE"
echo "=========================================="
