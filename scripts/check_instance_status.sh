#!/bin/bash

# Script to check EC2 instance status
# Tests connectivity and provides diagnosis

set -e

SERVER_IP="35.175.133.235"
PEM_FILE="$(dirname "$0")/ec2_wah_pk.pem"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  EC2 Instance Status Check"
echo "==================================================================="
echo ""
echo "Instance IP: $SERVER_IP"
echo ""

# Test 1: Ping
echo -e "${BLUE}🔍 Test 1: Network Connectivity (Ping)${NC}"
if ping -c 3 -W 2 $SERVER_IP &>/dev/null; then
    echo -e "${GREEN}   ✅ Ping successful - Network is reachable${NC}"
    PING_STATUS="OK"
else
    echo -e "${RED}   ❌ Ping failed - Instance may be stopped or unreachable${NC}"
    PING_STATUS="FAIL"
fi

# Test 2: HTTP
echo ""
echo -e "${BLUE}🔍 Test 2: HTTP Application${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://$SERVER_IP/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "307" ]; then
    echo -e "${GREEN}   ✅ HTTP working (Status: $HTTP_CODE)${NC}"
    HTTP_STATUS="OK"
elif [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}   ❌ HTTP connection failed (Timeout/Refused)${NC}"
    HTTP_STATUS="FAIL"
else
    echo -e "${YELLOW}   ⚠️  HTTP returned status: $HTTP_CODE${NC}"
    HTTP_STATUS="WARN"
fi

# Test 3: SSH
echo ""
echo -e "${BLUE}🔍 Test 3: SSH Access${NC}"
if [ -f "$PEM_FILE" ]; then
    chmod 600 "$PEM_FILE" 2>/dev/null || true
    if ssh -i "$PEM_FILE" -o ConnectTimeout=5 -o StrictHostKeyChecking=no -o BatchMode=yes ec2-user@$SERVER_IP "echo 'OK'" &>/dev/null; then
        echo -e "${GREEN}   ✅ SSH working${NC}"
        SSH_STATUS="OK"
    else
        echo -e "${RED}   ❌ SSH connection failed (Timeout/Refused)${NC}"
        SSH_STATUS="FAIL"
    fi
else
    echo -e "${YELLOW}   ⚠️  PEM file not found at $PEM_FILE${NC}"
    SSH_STATUS="SKIP"
fi

# Summary
echo ""
echo "==================================================================="
echo "  Summary"
echo "==================================================================="
echo ""

if [ "$PING_STATUS" = "FAIL" ] && [ "$HTTP_STATUS" = "FAIL" ] && [ "$SSH_STATUS" = "FAIL" ]; then
    echo -e "${RED}❌ INSTANCE APPEARS TO BE STOPPED OR UNREACHABLE${NC}"
    echo ""
    echo "Most likely causes:"
    echo "  1. EC2 instance is stopped"
    echo "  2. EC2 instance is terminated"
    echo "  3. Security group blocking all access"
    echo ""
    echo "Action required:"
    echo "  → Check AWS Console: https://console.aws.amazon.com/ec2/"
    echo "  → Go to: EC2 → Instances"
    echo "  → Find instance with IP: $SERVER_IP"
    echo "  → Check 'Instance state' column"
    echo "  → If 'Stopped': Click 'Start Instance'"
    echo "  → If 'Running': Check Security Groups"
    
elif [ "$PING_STATUS" = "OK" ] && [ "$HTTP_STATUS" = "OK" ]; then
    echo -e "${GREEN}✅ INSTANCE IS RUNNING AND ACCESSIBLE${NC}"
    echo ""
    echo "Status:"
    echo "  ✅ Network: Reachable"
    echo "  ✅ Application: Working"
    if [ "$SSH_STATUS" = "OK" ]; then
        echo "  ✅ SSH: Working"
    fi
    echo ""
    echo "Application URL: http://$SERVER_IP/"
    
elif [ "$PING_STATUS" = "OK" ] && [ "$HTTP_STATUS" = "FAIL" ]; then
    echo -e "${YELLOW}⚠️  INSTANCE IS RUNNING BUT APPLICATION NOT RESPONDING${NC}"
    echo ""
    echo "Possible causes:"
    echo "  1. Container is stopped"
    echo "  2. Application crashed"
    echo "  3. Security group blocking port 80"
    echo ""
    echo "Action required:"
    echo "  → SSH into server and check container:"
    echo "    ssh -i $PEM_FILE ec2-user@$SERVER_IP"
    echo "    sudo docker ps -a"
    echo "    sudo docker logs aris-rag-app"
    echo "  → Or run recovery script:"
    echo "    ./scripts/recover_site.sh"
    
elif [ "$PING_STATUS" = "FAIL" ] && [ "$SSH_STATUS" = "OK" ]; then
    echo -e "${YELLOW}⚠️  SSH WORKS BUT PING FAILS${NC}"
    echo ""
    echo "This is normal - security group may block ICMP (ping)"
    echo "If SSH works, instance is running"
    echo ""
    echo "Action: Check application status via SSH"
    
else
    echo -e "${YELLOW}⚠️  MIXED RESULTS - NEEDS INVESTIGATION${NC}"
    echo ""
    echo "Status:"
    [ "$PING_STATUS" = "OK" ] && echo "  ✅ Ping: Working" || echo "  ❌ Ping: Failed"
    [ "$HTTP_STATUS" = "OK" ] && echo "  ✅ HTTP: Working" || echo "  ❌ HTTP: Failed"
    [ "$SSH_STATUS" = "OK" ] && echo "  ✅ SSH: Working" || echo "  ❌ SSH: Failed"
    echo ""
    echo "Action: Check AWS Console for instance state"
fi

echo ""
echo "==================================================================="
echo "  Next Steps"
echo "==================================================================="
echo ""
echo "1. Check AWS Console:"
echo "   https://console.aws.amazon.com/ec2/"
echo "   → EC2 → Instances → Find IP: $SERVER_IP"
echo ""
echo "2. Check instance state:"
echo "   - If 'Stopped': Start instance"
echo "   - If 'Running': Check security groups"
echo ""
echo "3. If instance is running but site is down:"
echo "   ./scripts/recover_site.sh"
echo ""


