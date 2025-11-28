#!/bin/bash

# Adaptive Deployment Script for ARIS RAG System
# Automatically detects available ports and deploys with appropriate configuration

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
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "==================================================================="
echo "  ARIS RAG System - Adaptive Deployment"
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

chmod 600 "$PEM_FILE" 2>/dev/null || true

# Function to test port accessibility
test_port() {
    local port=$1
    timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/$port" 2>/dev/null
    return $?
}

# Detect available ports
echo "🔍 Detecting available ports..."
echo ""

PORTS_80=false
PORTS_443=false
PORTS_8080=false
PORTS_8443=false
PORTS_8501=false

if test_port 80; then
    PORTS_80=true
    echo -e "${GREEN}✅ Port 80 (HTTP) is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Port 80 (HTTP) is not accessible${NC}"
fi

if test_port 443; then
    PORTS_443=true
    echo -e "${GREEN}✅ Port 443 (HTTPS) is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Port 443 (HTTPS) is not accessible${NC}"
fi

if test_port 8080; then
    PORTS_8080=true
    echo -e "${GREEN}✅ Port 8080 (HTTP alt) is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Port 8080 (HTTP alt) is not accessible${NC}"
fi

if test_port 8443; then
    PORTS_8443=true
    echo -e "${GREEN}✅ Port 8443 (HTTPS alt) is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Port 8443 (HTTPS alt) is not accessible${NC}"
fi

if test_port 8501; then
    PORTS_8501=true
    echo -e "${GREEN}✅ Port 8501 (Streamlit) is accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Port 8501 (Streamlit) is not accessible${NC}"
fi

echo ""

# Determine deployment configuration
# Priority: 8501 (Streamlit default) > 80/443 (standard) > 8080/8443 (alternative)
COMPOSE_FILE=""
DEPLOYMENT_TYPE=""
ACCESS_URL=""

if [ "$PORTS_8501" = true ]; then
    COMPOSE_FILE="docker-compose.prod.direct.yml"
    DEPLOYMENT_TYPE="Direct Streamlit (Port 8501)"
    ACCESS_URL="http://$SERVER_IP:8501"
    echo -e "${GREEN}📋 Selected: Direct Streamlit access (port 8501) - Fastest setup!${NC}"
elif [ "$PORTS_80" = true ] && [ "$PORTS_443" = true ]; then
    COMPOSE_FILE="docker-compose.prod.yml"
    DEPLOYMENT_TYPE="Standard (Ports 80/443)"
    ACCESS_URL="http://$SERVER_IP or https://$SERVER_IP"
    echo -e "${GREEN}📋 Selected: Standard deployment (ports 80/443)${NC}"
elif [ "$PORTS_8080" = true ] && [ "$PORTS_8443" = true ]; then
    COMPOSE_FILE="docker-compose.prod.alt-ports.yml"
    DEPLOYMENT_TYPE="Alternative Ports (8080/8443)"
    ACCESS_URL="http://$SERVER_IP:8080 or https://$SERVER_IP:8443"
    echo -e "${GREEN}📋 Selected: Alternative ports deployment (8080/8443)${NC}"
else
    # If no ports are accessible, default to port 8501
    # User can open it in AWS Security Group after deployment
    echo -e "${YELLOW}⚠️  No ports are currently accessible from outside${NC}"
    echo ""
    echo "   Defaulting to port 8501 (Streamlit default)"
    echo "   After deployment, open port 8501 in AWS Security Group:"
    echo "   1. Go to EC2 → Security Groups"
    echo "   2. Select your instance's security group"
    echo "   3. Edit Inbound Rules"
    echo "   4. Add: Custom TCP, Port 8501, Source 0.0.0.0/0"
    echo ""
    COMPOSE_FILE="docker-compose.prod.direct.yml"
    DEPLOYMENT_TYPE="Direct Streamlit (Port 8501)"
    ACCESS_URL="http://$SERVER_IP:8501"
    echo -e "${GREEN}📋 Will deploy: Direct Streamlit access (port 8501)${NC}"
fi

echo ""
echo "==================================================================="
echo "  Deployment Configuration"
echo "==================================================================="
echo ""
echo "Type: $DEPLOYMENT_TYPE"
echo "Compose File: $COMPOSE_FILE"
echo "Access URL: $ACCESS_URL"
echo ""

# Ask for confirmation
read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""

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
    "!docs/DEPLOYMENT.md"
    "!docs/PORT_CONFIGURATION.md"
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
    \$COMPOSE_CMD -f $COMPOSE_FILE build --no-cache || {
        echo -e "${RED}❌ Docker build failed${NC}"
        exit 1
    }
    
    # Stop existing containers
    echo "   Stopping existing containers..."
    \$COMPOSE_CMD -f docker-compose.prod.yml down 2>/dev/null || true
    \$COMPOSE_CMD -f docker-compose.prod.alt-ports.yml down 2>/dev/null || true
    \$COMPOSE_CMD -f docker-compose.prod.direct.yml down 2>/dev/null || true
    
    # Start containers with selected configuration
    echo "   Starting containers with $COMPOSE_FILE..."
    \$COMPOSE_CMD -f $COMPOSE_FILE up -d || {
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
    
    # Check health based on deployment type
    if [ "$COMPOSE_FILE" = "docker-compose.prod.direct.yml" ]; then
        # Direct Streamlit
        if docker exec aris-rag-app python -c "import requests; requests.get('http://localhost:8501/_stcore/health')" &>/dev/null; then
            echo -e "   ${GREEN}✅ Streamlit: Healthy${NC}"
        else
            echo -e "   ${YELLOW}⚠️  Streamlit: Health check failed${NC}"
        fi
    else
        # Nginx-based deployments
        if docker exec aris-rag-nginx wget -q -O- http://localhost/health &>/dev/null; then
            echo -e "   ${GREEN}✅ Nginx: Healthy${NC}"
        else
            echo -e "   ${YELLOW}⚠️  Nginx: Health check failed${NC}"
        fi
        
        if docker exec aris-rag-app python -c "import requests; requests.get('http://localhost:8501/_stcore/health')" &>/dev/null; then
            echo -e "   ${GREEN}✅ Streamlit: Healthy${NC}"
        else
            echo -e "   ${YELLOW}⚠️  Streamlit: Health check failed${NC}"
        fi
    fi
    
    # Show logs
    echo ""
    echo "   Recent logs (last 10 lines):"
    docker-compose -f $COMPOSE_FILE logs --tail=10 2>/dev/null || docker compose -f $COMPOSE_FILE logs --tail=10
EOF

echo ""
echo "==================================================================="
echo -e "${GREEN}  Deployment Complete!${NC}"
echo "==================================================================="
echo ""
echo "📋 Deployment Summary:"
echo "   Type: $DEPLOYMENT_TYPE"
echo "   Compose File: $COMPOSE_FILE"
echo ""
echo "🌐 Access your application:"
echo "   $ACCESS_URL"
echo ""
echo "📝 Next steps:"
if [ "$COMPOSE_FILE" != "docker-compose.prod.direct.yml" ]; then
    echo "   1. Set up SSL certificates (if using HTTPS):"
    echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
    echo "      cd $SERVER_DIR && sudo ./scripts/setup_ssl.sh <your-domain>"
    echo ""
fi
echo "   2. View logs:"
echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
echo "      cd $SERVER_DIR && docker-compose -f $COMPOSE_FILE logs -f"
echo ""
echo "   3. Restart services:"
echo "      ssh -i $PEM_FILE $SERVER_USER@$SERVER_IP"
echo "      cd $SERVER_DIR && docker-compose -f $COMPOSE_FILE restart"
echo ""

