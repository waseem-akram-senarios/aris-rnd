#!/bin/bash

# Deployment Script for ARIS RAG System
# Transfers files to server and deploys the application

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "==================================================================="
echo "  ARIS RAG System - Production Deployment"
echo "==================================================================="
echo ""
echo "Server: $SERVER_USER@$SERVER_IP"
echo "Target Directory: $SERVER_DIR"
echo ""

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ Error: PEM file not found at $PEM_FILE${NC}"
    echo "   Please ensure ec2_wah_pk.pem is in the scripts/ directory"
    exit 1
fi

# Set correct permissions for PEM file
chmod 600 "$PEM_FILE" 2>/dev/null || true

# Check if .env file exists locally
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env file not found in project root${NC}"
    echo "   You'll need to create it on the server manually"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Files to exclude from deployment
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

echo "📦 Step 1: Creating directory structure on server..."
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
    "sudo mkdir -p $SERVER_DIR/{nginx/ssl,nginx/logs,vectorstore,data} && \
     sudo chown -R $SERVER_USER:$SERVER_USER $SERVER_DIR" || {
    echo -e "${RED}❌ Failed to create directories on server${NC}"
    exit 1
}

echo -e "${GREEN}✅ Directory structure created${NC}"
echo ""

echo "📤 Step 2: Transferring files to server..."
rsync -avz --progress \
    -e "ssh -i $PEM_FILE -o StrictHostKeyChecking=no" \
    "${EXCLUDE_PATTERNS[@]}" \
    "$PROJECT_ROOT/" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/" || {
    echo -e "${RED}❌ Failed to transfer files${NC}"
    exit 1
}

echo -e "${GREEN}✅ Files transferred${NC}"
echo ""

echo "🔐 Step 3: Setting up environment variables..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    echo "   Copying .env file to server..."
    scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
        "$PROJECT_ROOT/.env" \
        "$SERVER_USER@$SERVER_IP:$SERVER_DIR/.env" || {
        echo -e "${YELLOW}⚠️  Warning: Failed to copy .env file${NC}"
        echo "   You'll need to create it manually on the server"
    }
else
    echo -e "${YELLOW}⚠️  No .env file found locally${NC}"
    echo "   Please create $SERVER_DIR/.env on the server with required variables"
fi

echo ""

echo "🐳 Step 4: Building and starting Docker containers..."
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    cd $SERVER_DIR
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker not found. Please run server_setup.sh first${NC}"
        exit 1
    fi
    
    # Check if docker-compose is installed
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}❌ Docker Compose not found. Please run server_setup.sh first${NC}"
        exit 1
    fi
    
    # Use docker compose (v2) or docker-compose (v1)
    COMPOSE_CMD="docker-compose"
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    fi
    
    # Build images
    echo "   Building Docker images..."
    \$COMPOSE_CMD -f docker-compose.prod.yml build --no-cache || {
        echo -e "${RED}❌ Docker build failed${NC}"
        exit 1
    }
    
    # Stop existing containers
    echo "   Stopping existing containers..."
    \$COMPOSE_CMD -f docker-compose.prod.yml down 2>/dev/null || true
    
    # Start containers
    echo "   Starting containers..."
    \$COMPOSE_CMD -f docker-compose.prod.yml up -d || {
        echo -e "${RED}❌ Failed to start containers${NC}"
        exit 1
    }
    
    echo -e "${GREEN}✅ Containers started${NC}"
EOF

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Deployment failed${NC}"
    exit 1
fi

echo ""

echo "🏥 Step 5: Checking deployment health..."
sleep 5  # Wait for containers to start

ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    cd $SERVER_DIR
    
    # Check container status
    echo "   Container status:"
    docker ps --filter "name=aris-rag" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
    echo ""
    echo "   Health checks:"
    
    # Check nginx health
    if docker exec aris-rag-nginx wget -q -O- http://localhost/health &>/dev/null; then
        echo -e "   ${GREEN}✅ Nginx: Healthy${NC}"
    else
        echo -e "   ${YELLOW}⚠️  Nginx: Health check failed${NC}"
    fi
    
    # Check Streamlit health
    if docker exec aris-rag-app python -c "import requests; requests.get('http://localhost:8501/_stcore/health')" &>/dev/null; then
        echo -e "   ${GREEN}✅ Streamlit: Healthy${NC}"
    else
        echo -e "   ${YELLOW}⚠️  Streamlit: Health check failed${NC}"
    fi
    
    # Show logs
    echo ""
    echo "   Recent logs (last 10 lines):"
    docker-compose -f docker-compose.prod.yml logs --tail=10
EOF

echo ""
echo "==================================================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "==================================================================="
echo ""
echo "📋 Next steps:"
echo "   1. Set up SSL certificates:"
echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
echo "      cd $SERVER_DIR && sudo ./scripts/setup_ssl.sh <your-domain>"
echo ""
echo "   2. Access the application:"
echo "      HTTP:  http://$SERVER_IP"
echo "      HTTPS: https://$SERVER_IP (after SSL setup)"
echo ""
echo "   3. View logs:"
echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
echo "      cd $SERVER_DIR && docker-compose -f docker-compose.prod.yml logs -f"
echo ""
echo "   4. Stop the application:"
echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
echo "      cd $SERVER_DIR && docker-compose -f docker-compose.prod.yml down"
echo ""

