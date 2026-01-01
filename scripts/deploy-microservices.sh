#!/bin/bash

# Microservices Deployment Script for ARIS RAG
# Optimized for server deployment using Docker Compose

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-44.221.84.58}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$SCRIPT_DIR/all_scripts/ec2_wah_pk.pem"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Microservices Deployment             ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ PEM file not found: $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

START_TIME=$(date +%s)

echo -e "${BLUE}🔄 Step 1: Syncing code to server (rsync)...${NC}"
EXCLUDE_PATTERNS=(
    "--exclude=.git"
    "--exclude=venv"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=.pytest_cache"
    "--exclude=*.log"
    "--exclude=vectorstore"
    "--exclude=data"
    "--exclude=samples"
    "--exclude=tests"
    "--exclude=.env"
    "--exclude=*.pem"
    "--exclude=*.key"
    "--exclude=.vscode"
    "--exclude=.idea"
    "--exclude=*.swp"
    "--exclude=*.swo"
    "--exclude=.DS_Store"
    "--exclude=Thumbs.db"
    "--exclude=emails"
    "--exclude=diagrams"
    "--exclude=docs"
    "--exclude=*.md"
)

rsync -avz --progress \
    -e "ssh -i $PEM_FILE -o StrictHostKeyChecking=no" \
    "${EXCLUDE_PATTERNS[@]}" \
    "$PROJECT_ROOT/" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/" >/dev/null 2>&1

echo "   ✅ Code synced"

echo ""
echo -e "${BLUE}🔐 Step 2: Ensuring environment configuration...${NC}"
# Use existing .env on server if available, otherwise copy local
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    if [ ! -f "$SERVER_DIR/.env" ]; then
        echo "⚠️ .env not found on server. Please ensure it is created in $SERVER_DIR"
    else
        echo "✅ Existing .env found on server"
    fi
EOF

echo ""
echo -e "${BLUE}🧹 Step 3: Cleaning up old containers...${NC}"
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    cd $SERVER_DIR
    sudo docker-compose down --remove-orphans 2>/dev/null || true
    sudo docker stop aris-rag-app 2>/dev/null || true
    sudo docker rm aris-rag-app 2>/dev/null || true
    echo "   ✅ Old containers stopped and removed"
EOF

echo ""
echo -e "${BLUE}🐳 Step 4: Building and Deploying with Docker Compose...${NC}"
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    set -e
    cd $SERVER_DIR
    
    # Manually build the image first (since Compose version is old)
    echo "   Building microservice image..."
    sudo docker build -t aris-microservice:latest .
    
    # Start services using the pre-built image
    sudo docker-compose up -d
    
    echo "   ✅ Microservices deployed and running"
EOF

echo ""
echo -e "${BLUE}⏳ Step 5: Health check...${NC}"
sleep 15
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    echo "Checking Gateway health (port 8500)..."
    curl -s http://localhost:8500/health || echo "❌ Gateway health check failed"
    echo ""
    echo "Checking Ingestion health (port 8001)..."
    curl -s http://localhost:8001/health || echo "❌ Ingestion health check failed"
    echo ""
    echo "Checking Retrieval health (port 8002)..."
    curl -s http://localhost:8002/health || echo "❌ Retrieval health check failed"
EOF

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Deployment Complete!              ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo "   Time: ${DURATION}s"
echo "   Gateway URL: http://$SERVER_IP:8500"
echo "   Ingestion URL: http://$SERVER_IP:8501"
echo "   Retrieval URL: http://$SERVER_IP:8502"
echo ""
echo "Manage services on the server with:"
echo "   ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'cd $SERVER_DIR && sudo docker-compose logs -f'"
