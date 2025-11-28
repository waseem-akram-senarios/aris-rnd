#!/bin/bash

# Complete deployment script that checks server-side ports and deploys accordingly

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  Complete Deployment with Port Detection"
echo "==================================================================="
echo ""
echo "Server: $SERVER_USER@$SERVER_IP"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ PEM file not found at $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

# Step 1: Check server-side ports (what's allowed/listening)
echo "🔍 Step 1: Checking server-side port availability..."
echo ""

# Check what ports are allowed in security group (via AWS CLI if available)
# Or check what's listening on server
echo "   Checking what ports are accessible on server..."

# Test ports from outside first
PORTS_8501_OPEN=false
PORTS_80_OPEN=false
PORTS_443_OPEN=false
PORTS_8080_OPEN=false
PORTS_8443_OPEN=false

if timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/8501" 2>/dev/null; then
    PORTS_8501_OPEN=true
    echo -e "   ${GREEN}✅ Port 8501: Accessible from outside${NC}"
else
    echo -e "   ${YELLOW}⚠️  Port 8501: Not accessible (will need to open in AWS)${NC}"
fi

if timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/80" 2>/dev/null; then
    PORTS_80_OPEN=true
    echo -e "   ${GREEN}✅ Port 80: Accessible from outside${NC}"
else
    echo -e "   ${YELLOW}⚠️  Port 80: Not accessible${NC}"
fi

if timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/443" 2>/dev/null; then
    PORTS_443_OPEN=true
    echo -e "   ${GREEN}✅ Port 443: Accessible from outside${NC}"
else
    echo -e "   ${YELLOW}⚠️  Port 443: Not accessible${NC}"
fi

echo ""

# Step 2: Copy code to server
echo "📦 Step 2: Copying code to server..."
echo ""

# Check if code already exists
CODE_EXISTS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "[ -f $SERVER_DIR/app.py ] && echo 'yes' || echo 'no'" 2>/dev/null || echo 'no')

if [ "$CODE_EXISTS" = "no" ]; then
    echo "   Code not found on server, copying..."
    ./scripts/copy_to_server.sh || {
        echo -e "${RED}❌ Failed to copy code${NC}"
        exit 1
    }
else
    echo -e "   ${GREEN}✅ Code already exists on server${NC}"
fi

echo ""

# Step 3: Deploy application
echo "🚀 Step 3: Deploying application..."
echo ""

# Determine which configuration to use
# Priority: 8501 (if open or can be opened) > 80/443 > 8080/8443
COMPOSE_FILE="docker-compose.prod.direct.yml"
DEPLOYMENT_TYPE="Direct Streamlit (Port 8501)"
ACCESS_URL="http://$SERVER_IP:8501"
PORT_TO_OPEN=8501

if [ "$PORTS_80_OPEN" = true ] && [ "$PORTS_443_OPEN" = true ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
    DEPLOYMENT_TYPE="Standard (Ports 80/443)"
    ACCESS_URL="http://$SERVER_IP or https://$SERVER_IP"
    PORT_TO_OPEN="80,443"
elif [ "$PORTS_8501_OPEN" = true ]; then
    COMPOSE_FILE="docker-compose.prod.direct.yml"
    DEPLOYMENT_TYPE="Direct Streamlit (Port 8501)"
    ACCESS_URL="http://$SERVER_IP:8501"
    PORT_TO_OPEN=8501
else
    # Default to 8501 - user can open it
    COMPOSE_FILE="docker-compose.prod.direct.yml"
    DEPLOYMENT_TYPE="Direct Streamlit (Port 8501)"
    ACCESS_URL="http://$SERVER_IP:8501"
    PORT_TO_OPEN=8501
fi

echo "   Using: $DEPLOYMENT_TYPE"
echo "   Compose file: $COMPOSE_FILE"
echo ""

# Deploy on server
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    cd $SERVER_DIR
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not installed. Installing...${NC}"
        sudo bash scripts/server_setup.sh || {
            echo -e "${RED}❌ Failed to install Docker${NC}"
            exit 1
        }
    fi
    
    # Check .env file
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠️  .env file not found${NC}"
        echo "Creating .env template..."
        cat > .env <<ENVEOF
OPENAI_API_KEY=your_openai_key_here
CEREBRAS_API_KEY=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
AWS_OPENSEARCH_ACCESS_KEY_ID=
AWS_OPENSEARCH_SECRET_ACCESS_KEY=
AWS_OPENSEARCH_REGION=us-east-2
ENVEOF
        echo -e "${RED}❌ Please edit .env file with your API keys first${NC}"
        echo "   Run: nano .env"
        exit 1
    fi
    
    # Use docker compose (v2) or docker-compose (v1)
    COMPOSE_CMD="docker-compose"
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    fi
    
    # Stop existing containers
    echo "   Stopping existing containers..."
    \$COMPOSE_CMD -f docker-compose.prod.yml down 2>/dev/null || true
    \$COMPOSE_CMD -f docker-compose.prod.alt-ports.yml down 2>/dev/null || true
    \$COMPOSE_CMD -f docker-compose.prod.direct.yml down 2>/dev/null || true
    
    # Build
    echo "   Building Docker image..."
    \$COMPOSE_CMD -f $COMPOSE_FILE build || {
        echo -e "${RED}❌ Build failed${NC}"
        exit 1
    }
    
    # Start
    echo "   Starting containers..."
    \$COMPOSE_CMD -f $COMPOSE_FILE up -d || {
        echo -e "${RED}❌ Failed to start${NC}"
        exit 1
    }
    
    echo ""
    echo "   Waiting for startup..."
    sleep 10
    
    echo ""
    echo "   Container status:"
    docker ps --filter "name=aris-rag" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "   Checking health..."
    sleep 5
    
    if [ "$COMPOSE_FILE" = "docker-compose.prod.direct.yml" ]; then
        if docker exec aris-rag-app python -c "import requests; requests.get('http://localhost:8501/_stcore/health')" &>/dev/null; then
            echo -e "   ${GREEN}✅ Streamlit is healthy${NC}"
        else
            echo -e "   ${YELLOW}⚠️  Streamlit health check failed (may still be starting)${NC}"
        fi
    else
        if docker exec aris-rag-nginx wget -q -O- http://localhost/health &>/dev/null; then
            echo -e "   ${GREEN}✅ Nginx is healthy${NC}"
        else
            echo -e "   ${YELLOW}⚠️  Nginx health check failed${NC}"
        fi
    fi
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

echo ""

# Step 4: Check if port needs to be opened
echo "🔓 Step 4: Port access check..."
echo ""

if [ "$PORT_TO_OPEN" = "8501" ] && [ "$PORTS_8501_OPEN" = false ]; then
    echo -e "${YELLOW}⚠️  Port 8501 is not accessible from outside${NC}"
    echo ""
    echo "   You need to open it in AWS Security Group:"
    echo ""
    echo "   Quick Steps:"
    echo "   1. AWS Console → EC2 → Security Groups"
    echo "   2. Find your instance's security group"
    echo "   3. Edit Inbound Rules → Add Rule"
    echo "   4. Type: Custom TCP, Port: 8501, Source: 0.0.0.0/0"
    echo "   5. Save rules"
    echo ""
    echo "   Or use AWS CLI:"
    echo "   aws ec2 authorize-security-group-ingress \\"
    echo "     --group-id <your-sg-id> \\"
    echo "     --protocol tcp \\"
    echo "     --port 8501 \\"
    echo "     --cidr 0.0.0.0/0"
    echo ""
elif [ "$PORT_TO_OPEN" = "80,443" ] && ([ "$PORTS_80_OPEN" = false ] || [ "$PORTS_443_OPEN" = false ]); then
    echo -e "${YELLOW}⚠️  Ports 80/443 need to be opened${NC}"
    echo "   Follow same steps above for ports 80 and 443"
    echo ""
else
    echo -e "${GREEN}✅ Port is accessible${NC}"
    echo ""
fi

# Final summary
echo "==================================================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "==================================================================="
echo ""
echo "📋 Deployment Summary:"
echo "   Type: $DEPLOYMENT_TYPE"
echo "   Compose File: $COMPOSE_FILE"
echo ""
echo "🌐 Final URL:"
if [ "$PORT_TO_OPEN" = "8501" ]; then
    if [ "$PORTS_8501_OPEN" = true ]; then
        echo -e "   ${GREEN}$ACCESS_URL${NC} ✅ Ready to access!"
    else
        echo -e "   ${YELLOW}$ACCESS_URL${NC} ⚠️  Open port 8501 first"
    fi
else
    echo -e "   ${GREEN}$ACCESS_URL${NC}"
fi
echo ""
echo "📝 Next Steps:"
if [ "$PORT_TO_OPEN" = "8501" ] && [ "$PORTS_8501_OPEN" = false ]; then
    echo "   1. Open port 8501 in AWS Security Group (see instructions above)"
    echo "   2. Wait 10-30 seconds"
    echo "   3. Access: $ACCESS_URL"
else
    echo "   1. Access your application: $ACCESS_URL"
fi
echo ""
echo "🔧 Useful Commands:"
echo "   View logs: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd $SERVER_DIR && docker logs -f aris-rag-app'"
echo "   Restart: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd $SERVER_DIR && docker-compose -f $COMPOSE_FILE restart'"
echo "   Stop: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd $SERVER_DIR && docker-compose -f $COMPOSE_FILE down'"
echo ""






