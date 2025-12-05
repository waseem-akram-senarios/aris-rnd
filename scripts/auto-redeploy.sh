#!/bin/bash
# Automatic redeployment script with health check
# Monitors server health and automatically redeploys if connection is refused

set -e

# Configuration
SERVER_URL="${SERVER_URL:-http://44.221.84.58}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-30}"
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-60}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Auto-Redeployment Monitor            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Function to check server health
check_health() {
    if "$SCRIPT_DIR/health-check.sh" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to deploy
deploy() {
    echo -e "${YELLOW}🔄 Starting automatic redeployment...${NC}"
    cd "$PROJECT_ROOT"
    bash "$SCRIPT_DIR/deploy-fast.sh"
}

# Function to wait for server to be healthy
wait_for_health() {
    local max_wait=${1:-300}  # 5 minutes default
    local elapsed=0
    local check_interval=10
    
    echo -e "${BLUE}⏳ Waiting for server to become healthy...${NC}"
    
    while [ $elapsed -lt $max_wait ]; do
        if check_health; then
            echo -e "${GREEN}✅ Server is now healthy!${NC}"
            return 0
        fi
        
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
        echo -e "${YELLOW}   Still waiting... (${elapsed}s / ${max_wait}s)${NC}"
    done
    
    echo -e "${RED}❌ Server did not become healthy within ${max_wait}s${NC}"
    return 1
}

# Main logic
main() {
    # Check if server is currently healthy
    echo -e "${BLUE}🔍 Checking server health...${NC}"
    if check_health; then
        echo -e "${GREEN}✅ Server is healthy - no action needed${NC}"
        exit 0
    fi
    
    echo -e "${RED}❌ Server is unreachable - initiating automatic redeployment${NC}"
    echo ""
    
    # Attempt redeployment with retries
    local attempt=1
    local success=false
    
    while [ $attempt -le $MAX_RETRIES ]; do
        echo -e "${YELLOW}📦 Deployment attempt $attempt of $MAX_RETRIES${NC}"
        
        if deploy; then
            echo -e "${GREEN}✅ Deployment completed successfully${NC}"
            
            # Wait for server to become healthy
            if wait_for_health 300; then
                echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
                echo -e "${GREEN}║  ✅ Auto-Redeployment Successful!    ║${NC}"
                echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
                success=true
                break
            else
                echo -e "${YELLOW}⚠️ Deployment completed but server not yet healthy${NC}"
            fi
        else
            echo -e "${RED}❌ Deployment attempt $attempt failed${NC}"
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            echo -e "${YELLOW}⏳ Waiting ${RETRY_DELAY}s before retry...${NC}"
            sleep $RETRY_DELAY
        fi
        
        attempt=$((attempt + 1))
    done
    
    if [ "$success" = false ]; then
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║  ❌ Auto-Redeployment Failed           ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        echo -e "${RED}All $MAX_RETRIES deployment attempts failed${NC}"
        exit 1
    fi
}

# Run main function
main

