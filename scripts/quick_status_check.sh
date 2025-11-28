#!/bin/bash

# Quick status check - tries to check server without PEM file if possible

SERVER_IP="35.175.133.235"

echo "==================================================================="
echo "  Quick Server Status Check"
echo "==================================================================="
echo ""
echo "Server: $SERVER_IP"
echo ""

# Check if port 8501 is accessible from outside
echo "1️⃣  Checking if port 8501 is accessible..."
if timeout 3 bash -c "echo >/dev/tcp/$SERVER_IP/8501" 2>/dev/null; then
    echo -e "   ${GREEN}✅ Port 8501 is OPEN and accessible${NC}"
    echo ""
    echo "   Testing if service is responding..."
    HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://$SERVER_IP:8501/_stcore/health" 2>/dev/null || echo "000")
    
    if [ "$HTTP_RESPONSE" = "200" ]; then
        echo -e "   ${GREEN}✅ Service is RUNNING and responding (HTTP $HTTP_RESPONSE)${NC}"
        echo ""
        echo -e "${GREEN}✅✅✅ APPLICATION IS LIVE!${NC}"
        echo ""
        echo "🌐 Access your application at:"
        echo -e "   ${GREEN}http://$SERVER_IP:8501${NC}"
    elif [ "$HTTP_RESPONSE" = "000" ]; then
        echo -e "   ${YELLOW}⚠️  Port is open but service not responding${NC}"
        echo "      (Service may be starting or there's an issue)"
    else
        echo -e "   ${YELLOW}⚠️  Service returned HTTP $HTTP_RESPONSE${NC}"
    fi
else
    echo -e "   ${RED}❌ Port 8501 is CLOSED or service not running${NC}"
    echo ""
    echo "   Possible reasons:"
    echo "   1. Service is not running on server"
    echo "   2. Port 8501 is not open in AWS Security Group"
    echo "   3. Firewall blocking the port"
    echo ""
    echo "   To check on server (SSH required):"
    echo "   ssh -i scripts/ec2_wah_pk.pem ec2-user@$SERVER_IP"
    echo "   docker ps | grep aris-rag"
fi

echo ""

# If PEM file exists, do detailed check
if [ -f "scripts/ec2_wah_pk.pem" ]; then
    echo "2️⃣  Detailed server check (requires PEM file)..."
    echo ""
    ./scripts/check_server_status.sh
else
    echo "2️⃣  Detailed check skipped (PEM file not found)"
    echo ""
    echo "   To get detailed status, add PEM file and run:"
    echo "   ./scripts/check_server_status.sh"
fi

echo ""






