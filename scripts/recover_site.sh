#!/bin/bash

# Recovery Script for ARIS RAG System
# Use this after the EC2 instance is back up

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "==================================================================="
echo "  ARIS RAG System - Site Recovery"
echo "==================================================================="
echo ""

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ Error: PEM file not found at $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

# Test SSH connection
echo "🔍 Testing SSH connection..."
if ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$SERVER_USER@$SERVER_IP" "echo 'SSH connection successful'" 2>/dev/null; then
    echo -e "${GREEN}✅ SSH connection successful${NC}"
else
    echo -e "${RED}❌ Cannot connect via SSH${NC}"
    echo "   Please check:"
    echo "   1. EC2 instance is running"
    echo "   2. Security group allows SSH (port 22)"
    echo "   3. Your IP is allowed in security group"
    exit 1
fi

echo ""
echo "🔍 Checking container status..."
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<'ENDSSH'
cd /opt/aris-rag

echo "1. Docker service status:"
sudo systemctl status docker --no-pager | head -3 || echo "⚠️  Docker service check failed"

echo ""
echo "2. Container status:"
sudo docker ps -a --filter "name=aris-rag-app" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "3. Checking if container is running:"
if sudo docker ps --filter "name=aris-rag-app" --format "{{.Names}}" | grep -q "aris-rag-app"; then
    echo "✅ Container is running"
    CONTAINER_STATUS="running"
else
    echo "❌ Container is not running"
    CONTAINER_STATUS="stopped"
fi

echo ""
if [ "$CONTAINER_STATUS" = "stopped" ]; then
    echo "🔄 Starting container..."
    if [ -f "docker-compose.prod.port80.yml" ]; then
        sudo docker compose -f docker-compose.prod.port80.yml up -d
    else
        sudo docker start aris-rag-app || sudo docker compose -f docker-compose.prod.yml up -d
    fi
    sleep 10
    echo "✅ Container started"
fi

echo ""
echo "4. Checking container health:"
sudo docker ps --filter "name=aris-rag-app" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "5. Checking port 80:"
if sudo netstat -tuln 2>/dev/null | grep -q ":80 " || sudo ss -tuln 2>/dev/null | grep ":80 "; then
    echo "✅ Port 80 is listening"
else
    echo "❌ Port 80 is not listening"
fi

echo ""
echo "6. Testing application locally:"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "307" ]; then
    echo "✅ Application responding (HTTP $HTTP_CODE)"
else
    echo "❌ Application not responding (HTTP $HTTP_CODE)"
    echo ""
    echo "Recent logs:"
    sudo docker logs --tail=20 aris-rag-app 2>&1 | tail -10
fi

ENDSSH

echo ""
echo "🔍 Testing external access..."
sleep 2
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$SERVER_IP/ 2>&1 || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "307" ]; then
    echo -e "${GREEN}✅ Site is accessible: http://$SERVER_IP/${NC}"
    echo -e "${GREEN}✅ Recovery successful!${NC}"
else
    echo -e "${YELLOW}⚠️  Site may still be starting up${NC}"
    echo "   HTTP Status: $HTTP_CODE"
    echo "   Please wait 1-2 minutes and try again"
    echo "   Or check security group allows port 80"
fi

echo ""
echo "==================================================================="
echo "  Recovery Complete"
echo "==================================================================="


