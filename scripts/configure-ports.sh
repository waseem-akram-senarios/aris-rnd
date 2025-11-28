#!/bin/bash

# Interactive Port Configuration Helper
# Helps select and configure the appropriate port setup for deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  Port Configuration Helper"
echo "==================================================================="
echo ""
echo "This script helps you select the appropriate port configuration"
echo "for your deployment based on available ports."
echo ""

# Function to test port accessibility
test_port() {
    local port=$1
    timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/$port" 2>/dev/null
    return $?
}

# Check available ports
echo "🔍 Checking port availability on server ($SERVER_IP)..."
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
    echo -e "${RED}❌ Port 80 (HTTP) is not accessible${NC}"
fi

if test_port 443; then
    PORTS_443=true
    echo -e "${GREEN}✅ Port 443 (HTTPS) is accessible${NC}"
else
    echo -e "${RED}❌ Port 443 (HTTPS) is not accessible${NC}"
fi

if test_port 8080; then
    PORTS_8080=true
    echo -e "${GREEN}✅ Port 8080 (HTTP alt) is accessible${NC}"
else
    echo -e "${RED}❌ Port 8080 (HTTP alt) is not accessible${NC}"
fi

if test_port 8443; then
    PORTS_8443=true
    echo -e "${GREEN}✅ Port 8443 (HTTPS alt) is accessible${NC}"
else
    echo -e "${RED}❌ Port 8443 (HTTPS alt) is not accessible${NC}"
fi

if test_port 8501; then
    PORTS_8501=true
    echo -e "${GREEN}✅ Port 8501 (Streamlit) is accessible${NC}"
else
    echo -e "${RED}❌ Port 8501 (Streamlit) is not accessible${NC}"
fi

echo ""

# Determine available options
# Priority: 8501 (Streamlit default) first since it's usually open
OPTIONS=()
OPTION_DESCS=()
OPTION_FILES=()
OPTION_URLS=()

if [ "$PORTS_8501" = true ]; then
    OPTIONS+=("1")
    OPTION_DESCS+=("Direct Streamlit (8501) - Recommended! Simple setup, no nginx, fastest deployment")
    OPTION_FILES+=("docker-compose.prod.direct.yml")
    OPTION_URLS+=("http://$SERVER_IP:8501")
fi

if [ "$PORTS_80" = true ] && [ "$PORTS_443" = true ]; then
    OPTIONS+=("2")
    OPTION_DESCS+=("Standard Ports (80/443) - Production-ready with nginx and HTTPS")
    OPTION_FILES+=("docker-compose.prod.yml")
    OPTION_URLS+=("http://$SERVER_IP or https://$SERVER_IP")
fi

if [ "$PORTS_8080" = true ] && [ "$PORTS_8443" = true ]; then
    OPTIONS+=("3")
    OPTION_DESCS+=("Alternative Ports (8080/8443) - Good if 80/443 are blocked")
    OPTION_FILES+=("docker-compose.prod.alt-ports.yml")
    OPTION_URLS+=("http://$SERVER_IP:8080 or https://$SERVER_IP:8443")
fi

if [ ${#OPTIONS[@]} -eq 0 ]; then
    echo -e "${RED}❌ No suitable port configuration available${NC}"
    echo ""
    echo "   You need to open at least one of these port combinations:"
    echo "   - Ports 80 and 443 (standard)"
    echo "   - Ports 8080 and 8443 (alternative)"
    echo "   - Port 8501 (direct Streamlit)"
    echo ""
    echo "   To open ports in AWS:"
    echo "   1. Go to EC2 → Security Groups"
    echo "   2. Select your instance's security group"
    echo "   3. Edit Inbound Rules"
    echo "   4. Add rules for the ports you want to use"
    echo ""
    exit 1
fi

# Display options
echo "==================================================================="
echo "  Available Configuration Options"
echo "==================================================================="
echo ""

for i in "${!OPTIONS[@]}"; do
    echo "   ${OPTIONS[$i]}) ${OPTION_DESCS[$i]}"
    echo "      File: ${OPTION_FILES[$i]}"
    echo "      URL: ${OPTION_URLS[$i]}"
    echo ""
done

# Get user selection
echo "==================================================================="
read -p "Select configuration [${OPTIONS[0]}-${OPTIONS[-1]}]: " selection
echo ""

# Validate selection
SELECTED_INDEX=-1
for i in "${!OPTIONS[@]}"; do
    if [ "$selection" = "${OPTIONS[$i]}" ]; then
        SELECTED_INDEX=$i
        break
    fi
done

if [ $SELECTED_INDEX -eq -1 ]; then
    echo -e "${RED}❌ Invalid selection${NC}"
    exit 1
fi

SELECTED_FILE="${OPTION_FILES[$SELECTED_INDEX]}"
SELECTED_URL="${OPTION_URLS[$SELECTED_INDEX]}"

echo -e "${GREEN}✅ Selected: ${OPTION_DESCS[$SELECTED_INDEX]}${NC}"
echo "   Configuration file: $SELECTED_FILE"
echo "   Access URL: $SELECTED_URL"
echo ""

# Ask if user wants to deploy now
read -p "Deploy with this configuration now? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🚀 Starting deployment..."
    echo ""
    
    # Run adaptive deployment script
    if [ -f "$SCRIPT_DIR/deploy-adaptive.sh" ]; then
        "$SCRIPT_DIR/deploy-adaptive.sh"
    else
        echo -e "${YELLOW}⚠️  deploy-adaptive.sh not found${NC}"
        echo "   You can deploy manually with:"
        echo "   docker-compose -f $SELECTED_FILE up -d"
    fi
else
    echo ""
    echo "📋 Configuration Summary:"
    echo "   Use compose file: $SELECTED_FILE"
    echo "   Access URL: $SELECTED_URL"
    echo ""
    echo "   To deploy manually:"
    echo "   cd /opt/aris-rag"
    echo "   docker-compose -f $SELECTED_FILE up -d"
    echo ""
fi

