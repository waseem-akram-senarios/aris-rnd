#!/bin/bash

# Fast Git-based Deployment for R&D
# Uses rsync for code transfer (no Git auth needed on server)
# Optimized for speed: ~1-2 minutes total
# Usage: ./scripts/deploy-fast.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-44.221.84.58}"
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
echo -e "${BLUE}📊 Step 4: Detecting server specs and calculating optimal resources...${NC}"

# Detect server specs dynamically
CPU_COUNT=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "nproc" 2>/dev/null || echo "8")

TOTAL_MEM_GB=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "free -g | awk '/^Mem:/ {print \$2}'" 2>/dev/null || echo "14")

# Calculate optimal allocation (leave 1 CPU and 2GB for system)
ALLOCATED_CPUS=$((CPU_COUNT - 1))
ALLOCATED_MEM_GB=$((TOTAL_MEM_GB - 2))
MEM_RESERVATION_GB=$((ALLOCATED_MEM_GB - 4))  # Reserve 4GB less than limit

# Ensure minimum values
if [ $ALLOCATED_CPUS -lt 1 ]; then
    ALLOCATED_CPUS=1
fi
if [ $ALLOCATED_MEM_GB -lt 4 ]; then
    ALLOCATED_MEM_GB=4
fi
if [ $MEM_RESERVATION_GB -lt 2 ]; then
    MEM_RESERVATION_GB=2
fi

echo "   Server Specs:"
echo "   - Total CPUs: $CPU_COUNT"
echo "   - Total Memory: ${TOTAL_MEM_GB} GB"
echo "   - Allocated CPUs: $ALLOCATED_CPUS (leaving 1 for system)"
echo "   - Allocated Memory: ${ALLOCATED_MEM_GB} GB (leaving 2 GB for system)"
echo "   - Memory Reservation: ${MEM_RESERVATION_GB} GB"

echo ""
echo -e "${BLUE}🚀 Step 5: Starting container with optimal resources...${NC}"
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    set -e
    cd $SERVER_DIR
    
    # Start container with dynamically calculated resource limits
    # Port 80 -> Streamlit (80), Port 8500 -> FastAPI (8500) - no port mapping
    sudo docker run -d \
        --name aris-rag-app \
        --restart unless-stopped \
        -p 80:80 \
        -p 8500:8500 \
        --cpus="$ALLOCATED_CPUS" \
        --memory="${ALLOCATED_MEM_GB}g" \
        --memory-reservation="${MEM_RESERVATION_GB}g" \
        -v \$(pwd)/vectorstore:/app/vectorstore \
        -v \$(pwd)/data:/app/data \
        -v \$(pwd)/.env:/app/.env:ro \
        --env-file .env \
        --health-cmd="python -c 'import requests; requests.get(\"http://localhost:80/_stcore/health\")'" \
        --health-interval=30s \
        --health-timeout=10s \
        --health-retries=3 \
        --health-start-period=40s \
        aris-rag:latest >/dev/null 2>&1
    
    echo "   ✅ Container started with $ALLOCATED_CPUS CPUs and ${ALLOCATED_MEM_GB}GB memory"
EOF

echo ""
echo -e "${BLUE}⏳ Step 6: Health check with retry...${NC}"

# Health check with retries
MAX_HEALTH_RETRIES=5
HEALTH_RETRY_DELAY=10
HTTP_CODE="000"
HEALTH_SUCCESS=false

for i in $(seq 1 $MAX_HEALTH_RETRIES); do
    sleep $HEALTH_RETRY_DELAY
    
    # Check from server itself first (more reliable)
    HTTP_CODE=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
        "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:80/_stcore/health 2>/dev/null || echo '000'")
    
    # Also check external access
    EXTERNAL_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 --connect-timeout 5 "http://$SERVER_IP/" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$EXTERNAL_CODE" = "200" ] || [ "$EXTERNAL_CODE" = "302" ]; then
        HEALTH_SUCCESS=true
        HTTP_CODE="$HTTP_CODE"
        break
    fi
    
    if [ $i -lt $MAX_HEALTH_RETRIES ]; then
        echo "   ⏳ Health check attempt $i/$MAX_HEALTH_RETRIES failed (HTTP $HTTP_CODE), retrying in ${HEALTH_RETRY_DELAY}s..."
    fi
done

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
if [ "$HEALTH_SUCCESS" = true ]; then
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Deployment Successful!            ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo "   Status: HTTP $HTTP_CODE"
    echo "   Time: ${DURATION}s"
    echo "   URL: http://$SERVER_IP/"
else
    echo -e "${YELLOW}⚠️  Deployment completed (${DURATION}s) but health check failed${NC}"
    echo "   HTTP Code: $HTTP_CODE"
    echo "   The container may still be starting. It will auto-recover."
    echo "   Check logs: ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP 'sudo docker logs aris-rag-app'"
    echo "   Or run auto-redeploy: bash scripts/auto-redeploy.sh"
fi
