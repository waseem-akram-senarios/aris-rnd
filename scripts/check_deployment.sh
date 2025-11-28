#!/bin/bash

# Quick deployment check script
# Checks if the application is deployed and running on the server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  ARIS RAG System - Deployment Status Check"
echo "==================================================================="
echo ""
echo "Server: $SERVER_USER@$SERVER_IP"
echo ""

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ Error: PEM file not found at $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

echo "🔍 Checking server status..."
echo ""

# Check SSH connectivity
echo "1. Testing SSH connection..."
if ssh -i "$PEM_FILE" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "echo 'SSH OK'" &>/dev/null; then
    echo -e "${GREEN}   ✅ SSH connection successful${NC}"
else
    echo -e "${RED}   ❌ Cannot connect to server via SSH${NC}"
    echo "   Please check:"
    echo "   - Server is running"
    echo "   - Security group allows SSH (port 22)"
    echo "   - PEM file is correct"
    exit 1
fi

echo ""

# Check Docker installation
echo "2. Checking Docker installation..."
DOCKER_STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "command -v docker &>/dev/null && echo 'installed' || echo 'not_installed'")

if [ "$DOCKER_STATUS" == "installed" ]; then
    echo -e "${GREEN}   ✅ Docker is installed${NC}"
    DOCKER_VERSION=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "docker --version")
    echo "   Version: $DOCKER_VERSION"
else
    echo -e "${YELLOW}   ⚠️  Docker is not installed${NC}"
    echo "   Run: sudo bash scripts/server_setup.sh on the server"
fi

echo ""

# Check if application directory exists
echo "3. Checking application directory..."
if ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "[ -d /opt/aris-rag ]" 2>/dev/null; then
    echo -e "${GREEN}   ✅ Application directory exists${NC}"
else
    echo -e "${YELLOW}   ⚠️  Application directory not found${NC}"
    echo "   Run: ./scripts/deploy.sh to deploy"
fi

echo ""

# Check if containers are running
echo "4. Checking Docker containers..."
CONTAINERS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "cd /opt/aris-rag 2>/dev/null && docker ps --filter 'name=aris-rag' --format '{{.Names}}' 2>/dev/null || echo ''")

if [ -z "$CONTAINERS" ]; then
    echo -e "${RED}   ❌ No containers running${NC}"
    echo "   The application has not been deployed or containers are stopped"
    echo ""
    echo "   To deploy, run: ./scripts/deploy.sh"
else
    echo -e "${GREEN}   ✅ Containers found:${NC}"
    echo "$CONTAINERS" | while read container; do
        if [ -n "$container" ]; then
            STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "docker inspect --format='{{.State.Status}}' $container 2>/dev/null")
            echo "      - $container: $STATUS"
        fi
    done
fi

echo ""

# Check port accessibility
echo "5. Checking port accessibility..."
PORTS_TO_CHECK=(80 443 8501)

for port in "${PORTS_TO_CHECK[@]}"; do
    if timeout 3 bash -c "echo >/dev/tcp/$SERVER_IP/$port" 2>/dev/null; then
        echo -e "${GREEN}   ✅ Port $port is open${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Port $port is not accessible${NC}"
    fi
done

echo ""

# Check nginx status
echo "6. Checking nginx service..."
NGINX_STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "docker ps --filter 'name=aris-rag-nginx' --format '{{.Status}}' 2>/dev/null || echo 'not_running'")

if [ "$NGINX_STATUS" != "not_running" ] && [ -n "$NGINX_STATUS" ]; then
    echo -e "${GREEN}   ✅ Nginx container: $NGINX_STATUS${NC}"
else
    echo -e "${RED}   ❌ Nginx container is not running${NC}"
fi

echo ""

# Check application health
echo "7. Checking application health..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://$SERVER_IP/health" 2>/dev/null || echo "000")

if [ "$HTTP_RESPONSE" == "200" ]; then
    echo -e "${GREEN}   ✅ Application is responding (HTTP $HTTP_RESPONSE)${NC}"
elif [ "$HTTP_RESPONSE" == "000" ]; then
    echo -e "${RED}   ❌ Application is not responding (connection timeout)${NC}"
else
    echo -e "${YELLOW}   ⚠️  Application returned HTTP $HTTP_RESPONSE${NC}"
fi

echo ""

# Summary and recommendations
echo "==================================================================="
echo "  Summary & Recommendations"
echo "==================================================================="
echo ""

if [ "$DOCKER_STATUS" != "installed" ]; then
    echo -e "${YELLOW}⚠️  ACTION REQUIRED:${NC}"
    echo "   1. SSH to server: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
    echo "   2. Run: sudo bash /opt/aris-rag/scripts/server_setup.sh"
    echo ""
fi

if [ -z "$CONTAINERS" ]; then
    echo -e "${YELLOW}⚠️  ACTION REQUIRED:${NC}"
    echo "   Deploy the application: ./scripts/deploy.sh"
    echo ""
fi

if [ "$HTTP_RESPONSE" != "200" ]; then
    echo -e "${YELLOW}⚠️  TROUBLESHOOTING:${NC}"
    echo "   1. Check security group/firewall allows ports 80, 443"
    echo "   2. Verify containers are running:"
    echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
    echo "      cd /opt/aris-rag && docker-compose -f docker-compose.prod.yml ps"
    echo "   3. Check container logs:"
    echo "      docker-compose -f docker-compose.prod.yml logs"
    echo ""
fi

echo "📋 Quick Commands:"
echo "   Check containers: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd /opt/aris-rag && docker ps'"
echo "   View logs: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd /opt/aris-rag && docker-compose -f docker-compose.prod.yml logs'"
echo "   Restart: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd /opt/aris-rag && docker-compose -f docker-compose.prod.yml restart'"
echo ""

