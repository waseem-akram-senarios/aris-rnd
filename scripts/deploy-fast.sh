#!/bin/bash

# Fast Git-based Deployment for R&D
# Uses rsync for code transfer (no Git auth needed on server)
# Optimized for speed: ~1-2 minutes total
# Usage: ./scripts/deploy-fast.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Fast R&D Deployment                  ║${NC}"
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
# Exclude patterns (same as deploy.sh)
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
echo -e "${BLUE}🔐 Step 2: Ensuring .env file exists...${NC}"
# Copy .env separately if it exists locally
if [ -f "$PROJECT_ROOT/.env" ]; then
    scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
        "$PROJECT_ROOT/.env" \
        "$SERVER_USER@$SERVER_IP:$SERVER_DIR/.env" >/dev/null 2>&1 && \
        echo "   ✅ .env copied" || \
        echo "   ℹ️  Using existing .env on server"
else
    echo "   ℹ️  Using existing .env on server"
fi

echo ""
echo -e "${BLUE}🐳 Step 3: Building Docker image...${NC}"
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    set -e
    cd $SERVER_DIR
    
    # Stop old container
    sudo docker stop aris-rag-app 2>/dev/null || true
    sudo docker rm aris-rag-app 2>/dev/null || true
    
    # Build image
    sudo docker build -t aris-rag:latest . >/dev/null 2>&1 || {
        echo "   Building with output..."
        sudo docker build -t aris-rag:latest .
    }
    echo "   ✅ Image built"
EOF

echo ""
echo -e "${BLUE}🚀 Step 4: Starting container...${NC}"
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    set -e
    cd $SERVER_DIR
    
    # Start container with resource limits
    sudo docker run -d \
        --name aris-rag-app \
        --restart unless-stopped \
        -p 80:8501 \
        --cpus="7" \
        --memory="12g" \
        --memory-reservation="8g" \
        -v \$(pwd)/vectorstore:/app/vectorstore \
        -v \$(pwd)/data:/app/data \
        -v \$(pwd)/.env:/app/.env:ro \
        --env-file .env \
        --health-cmd="python -c 'import requests; requests.get(\"http://localhost:8501/_stcore/health\")'" \
        --health-interval=30s \
        --health-timeout=10s \
        --health-retries=3 \
        --health-start-period=40s \
        aris-rag:latest >/dev/null 2>&1
    
    echo "   ✅ Container started"
EOF

echo ""
echo -e "${BLUE}⏳ Step 5: Health check...${NC}"
sleep 15

HTTP_CODE=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost/" 2>/dev/null || echo "000")

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Deployment Successful!            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "   Status: HTTP $HTTP_CODE"
    echo "   Time: ${DURATION}s"
    echo "   URL: http://$SERVER_IP/"
else
    echo -e "${YELLOW}⚠️  Deployment completed (${DURATION}s) but HTTP: $HTTP_CODE${NC}"
    echo "   Check logs: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'sudo docker logs aris-rag-app'"
fi
