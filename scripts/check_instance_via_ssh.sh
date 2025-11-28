#!/bin/bash

# Check EC2 instance status via SSH (if accessible)
# This script tries to connect and check server status

set -e

SERVER_IP="35.175.133.235"
SERVER_USER="ec2-user"
PEM_FILE="$(dirname "$0")/ec2_wah_pk.pem"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  EC2 Instance Status Check (Via SSH)"
echo "==================================================================="
echo ""
echo "Instance IP: $SERVER_IP"
echo "PEM File: $PEM_FILE"
echo ""

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ PEM file not found at: $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

# Test 1: SSH Connection
echo -e "${BLUE}🔍 Test 1: SSH Connection${NC}"
if timeout 10 ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes "$SERVER_USER@$SERVER_IP" "echo 'Connected'" 2>/dev/null; then
    echo -e "${GREEN}   ✅ SSH connection successful${NC}"
    SSH_WORKS=true
else
    SSH_ERROR=$(timeout 10 ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes "$SERVER_USER@$SERVER_IP" "echo 'Connected'" 2>&1 || true)
    echo -e "${RED}   ❌ SSH connection failed${NC}"
    echo "   Error: $SSH_ERROR" | head -3
    SSH_WORKS=false
fi

echo ""

# If SSH works, check server status
if [ "$SSH_WORKS" = true ]; then
    echo -e "${BLUE}🔍 Test 2: Server Status (via SSH)${NC}"
    ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<'ENDSSH'
echo "Checking server status..."
echo ""

# Check if instance metadata is available (confirms we're on EC2)
echo "1. EC2 Instance Metadata:"
if curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-id &>/dev/null; then
    INSTANCE_ID=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-id)
    echo "   ✅ Instance ID: $INSTANCE_ID"
    AVAILABILITY_ZONE=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/placement/availability-zone)
    echo "   ✅ Availability Zone: $AVAILABILITY_ZONE"
    INSTANCE_TYPE=$(curl -s --max-time 2 http://169.254.169.254/latest/meta-data/instance-type)
    echo "   ✅ Instance Type: $INSTANCE_TYPE"
else
    echo "   ⚠️  Cannot access instance metadata"
fi

echo ""
echo "2. System Uptime:"
uptime

echo ""
echo "3. Docker Service:"
sudo systemctl status docker --no-pager | head -5 || echo "   ⚠️  Docker service check failed"

echo ""
echo "4. Container Status:"
sudo docker ps -a --filter "name=aris-rag-app" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "   ⚠️  Docker not available or container not found"

echo ""
echo "5. Port 80 Status:"
if sudo netstat -tuln 2>/dev/null | grep ":80 " || sudo ss -tuln 2>/dev/null | grep ":80 "; then
    echo "   ✅ Port 80 is listening"
else
    echo "   ❌ Port 80 is not listening"
fi

echo ""
echo "6. Application Health (local):"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "307" ]; then
    echo "   ✅ Application responding (HTTP $HTTP_CODE)"
else
    echo "   ❌ Application not responding (HTTP $HTTP_CODE)"
fi

echo ""
echo "7. Recent Container Logs (last 10 lines):"
sudo docker logs --tail=10 aris-rag-app 2>&1 | tail -10 || echo "   ⚠️  Cannot access logs"

ENDSSH

else
    echo -e "${YELLOW}⚠️  Cannot check server status - SSH connection failed${NC}"
    echo ""
    echo "This usually means:"
    echo "  1. EC2 instance is stopped"
    echo "  2. Security group is blocking SSH (port 22)"
    echo "  3. Instance is terminated"
    echo ""
    echo "To confirm instance status, you need AWS Console access."
fi

echo ""
echo "==================================================================="
echo "  Summary"
echo "==================================================================="
echo ""

if [ "$SSH_WORKS" = true ]; then
    echo -e "${GREEN}✅ INSTANCE IS RUNNING${NC}"
    echo ""
    echo "SSH connection successful - instance is up and running."
    echo "Check the server status above for application details."
else
    echo -e "${RED}❌ INSTANCE APPEARS TO BE STOPPED OR UNREACHABLE${NC}"
    echo ""
    echo "SSH connection failed - this strongly indicates:"
    echo "  • EC2 instance is stopped (most likely)"
    echo "  • Security group blocking SSH access"
    echo "  • Instance is terminated"
    echo ""
    echo "To start the instance, you need AWS Console access:"
    echo "  1. Go to: https://console.aws.amazon.com/ec2/"
    echo "  2. Navigate to: EC2 → Instances"
    echo "  3. Find instance with IP: $SERVER_IP"
    echo "  4. If 'Stopped': Click 'Start Instance'"
fi

echo ""


