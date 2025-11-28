#!/bin/bash

# Comprehensive check and fix script for deployment issues

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
echo "  Deployment Diagnostic & Fix"
echo "==================================================================="
echo ""
echo "Server: $SERVER_IP"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ PEM file not found${NC}"
    echo ""
    echo "Please add your PEM file:"
    echo "  cp /path/to/your-key.pem scripts/ec2_wah_pk.pem"
    echo "  chmod 600 scripts/ec2_wah_pk.pem"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

# Test SSH connection
echo "1️⃣  Testing SSH connection..."
if ssh -i "$PEM_FILE" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "echo 'SSH OK'" &>/dev/null; then
    echo -e "${GREEN}   ✅ SSH connection successful${NC}"
else
    echo -e "${RED}   ❌ Cannot connect via SSH${NC}"
    exit 1
fi

echo ""

# Check if code exists on server
echo "2️⃣  Checking if code exists on server..."
CODE_EXISTS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "[ -f $SERVER_DIR/app.py ] && echo 'yes' || echo 'no'" 2>/dev/null)

if [ "$CODE_EXISTS" = "yes" ]; then
    echo -e "${GREEN}   ✅ Code found on server${NC}"
else
    echo -e "${YELLOW}   ⚠️  Code not found on server${NC}"
    echo ""
    read -p "Copy code to server now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/copy_to_server.sh
    else
        echo "Please copy code first: ./scripts/copy_to_server.sh"
        exit 1
    fi
fi

echo ""

# Check Docker
echo "3️⃣  Checking Docker installation..."
DOCKER_INSTALLED=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "command -v docker &>/dev/null && echo 'yes' || echo 'no'" 2>/dev/null)

if [ "$DOCKER_INSTALLED" = "yes" ]; then
    echo -e "${GREEN}   ✅ Docker is installed${NC}"
else
    echo -e "${RED}   ❌ Docker not installed${NC}"
    echo ""
    read -p "Install Docker on server? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        scp -i "$PEM_FILE" scripts/server_setup.sh "$SERVER_USER@$SERVER_IP:/tmp/"
        ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" "sudo bash /tmp/server_setup.sh"
    else
        echo "Please install Docker first"
        exit 1
    fi
fi

echo ""

# Check containers
echo "4️⃣  Checking if containers are running..."
CONTAINERS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "cd $SERVER_DIR 2>/dev/null && docker ps --filter 'name=aris-rag' --format '{{.Names}}' 2>/dev/null || echo ''")

if [ -n "$CONTAINERS" ]; then
    echo -e "${GREEN}   ✅ Containers are running:${NC}"
    echo "$CONTAINERS" | while read container; do
        if [ -n "$container" ]; then
            STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "docker inspect --format='{{.State.Status}}' $container 2>/dev/null")
            echo "      - $container: $STATUS"
        fi
    done
else
    echo -e "${YELLOW}   ⚠️  No containers running${NC}"
    echo ""
    read -p "Start containers now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
            cd $SERVER_DIR
            
            # Check .env file
            if [ ! -f ".env" ]; then
                echo -e "${YELLOW}⚠️  .env file not found${NC}"
                echo "Creating template..."
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
            
            # Stop existing
            \$COMPOSE_CMD -f docker-compose.prod.direct.yml down 2>/dev/null || true
            
            # Build and start
            echo "Building..."
            \$COMPOSE_CMD -f docker-compose.prod.direct.yml build
            
            echo "Starting..."
            \$COMPOSE_CMD -f docker-compose.prod.direct.yml up -d
            
            echo "Waiting for startup..."
            sleep 5
            
            docker ps --filter "name=aris-rag"
EOF
    fi
fi

echo ""

# Check port accessibility
echo "5️⃣  Checking port 8501 accessibility..."
if timeout 3 bash -c "echo >/dev/tcp/$SERVER_IP/8501" 2>/dev/null; then
    echo -e "${GREEN}   ✅ Port 8501 is accessible from outside${NC}"
else
    echo -e "${RED}   ❌ Port 8501 is NOT accessible from outside${NC}"
    echo ""
    echo "   ⚠️  ACTION REQUIRED: Open port 8501 in AWS Security Group"
    echo ""
    echo "   Steps:"
    echo "   1. Go to AWS Console → EC2 → Security Groups"
    echo "   2. Find your instance's security group"
    echo "   3. Edit Inbound Rules → Add Rule"
    echo "   4. Type: Custom TCP, Port: 8501, Source: 0.0.0.0/0"
    echo "   5. Save rules"
    echo ""
fi

echo ""

# Summary
echo "==================================================================="
echo "  Summary"
echo "==================================================================="
echo ""
echo "🌐 Application URL:"
echo "   http://$SERVER_IP:8501"
echo ""
echo "📋 Status:"
if [ -n "$CONTAINERS" ]; then
    echo -e "   ${GREEN}✅ Application is running${NC}"
else
    echo -e "   ${RED}❌ Application is not running${NC}"
fi

if timeout 3 bash -c "echo >/dev/tcp/$SERVER_IP/8501" 2>/dev/null; then
    echo -e "   ${GREEN}✅ Port 8501 is open${NC}"
else
    echo -e "   ${RED}❌ Port 8501 is closed (open in AWS Security Group)${NC}"
fi

echo ""
echo "📝 Next steps:"
if [ -z "$CONTAINERS" ]; then
    echo "   1. Start the application (run this script again and choose 'y')"
fi
if ! timeout 3 bash -c "echo >/dev/tcp/$SERVER_IP/8501" 2>/dev/null; then
    echo "   2. Open port 8501 in AWS Security Group"
fi
echo "   3. Access: http://$SERVER_IP:8501"
echo ""






