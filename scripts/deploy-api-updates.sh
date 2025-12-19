#!/bin/bash

# Quick API Deployment - Updates only API files and restarts container
# Usage: ./scripts/deploy-api-updates.sh

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
echo -e "${BLUE}║  Quick API Deployment                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo -e "${RED}❌ PEM file not found: $PEM_FILE${NC}"
    exit 1
fi

chmod 600 "$PEM_FILE" 2>/dev/null || true

START_TIME=$(date +%s)

echo -e "${BLUE}🔄 Step 1: Copying updated API files...${NC}"

# Copy API files
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/api/main.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/api/main.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/api/schemas.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/api/schemas.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/api/service.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/api/service.py"

echo "   ✅ API files copied"

echo ""
echo -e "${BLUE}🔄 Step 2: Copying updated vectorstore files...${NC}"

# Copy vectorstore files
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/vectorstores/opensearch_store.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/vectorstores/opensearch_store.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/vectorstores/opensearch_images_store.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/vectorstores/opensearch_images_store.py"

echo "   ✅ Vectorstore files copied"

echo ""
echo -e "${BLUE}🔄 Step 2.5: Copying new utility files...${NC}"

# Copy new utility files for verification
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/utils/pdf_metadata_extractor.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/utils/pdf_metadata_extractor.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/utils/pdf_content_extractor.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/utils/pdf_content_extractor.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/utils/ocr_verifier.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/utils/ocr_verifier.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/utils/ocr_auto_fix.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/utils/ocr_auto_fix.py"

echo "   ✅ Utility files copied"

echo ""
echo -e "${BLUE}🔄 Step 2.6: Copying config files...${NC}"

# Copy config file
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/config/accuracy_config.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/config/accuracy_config.py"

echo "   ✅ Config files copied"

echo ""
echo -e "${BLUE}🔄 Step 2.7: Copying updated storage files...${NC}"

# Copy updated document registry
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/storage/document_registry.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/storage/document_registry.py"

echo "   ✅ Storage files copied"

echo ""
echo -e "${BLUE}🔄 Step 2.8: Copying parser files (required for image extraction)...${NC}"

# Copy parser files (needed for direct DoclingParser usage)
scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/parsers/docling_parser.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/parsers/docling_parser.py"

scp -i "$PEM_FILE" -o StrictHostKeyChecking=no \
    "$PROJECT_ROOT/parsers/base_parser.py" \
    "$SERVER_USER@$SERVER_IP:$SERVER_DIR/parsers/base_parser.py"

echo "   ✅ Parser files copied"

echo ""
echo -e "${BLUE}🔄 Step 3: Restarting Docker container...${NC}"

ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
    set -e
    cd $SERVER_DIR
    
    # Copy files into Docker container
    echo "   Copying files into Docker container..."
    sudo docker cp api/main.py aris-rag-app:/app/api/main.py
    sudo docker cp api/schemas.py aris-rag-app:/app/api/schemas.py
    sudo docker cp api/service.py aris-rag-app:/app/api/service.py
    sudo docker cp vectorstores/opensearch_store.py aris-rag-app:/app/vectorstores/opensearch_store.py
    sudo docker cp vectorstores/opensearch_images_store.py aris-rag-app:/app/vectorstores/opensearch_images_store.py
    sudo docker cp utils/pdf_metadata_extractor.py aris-rag-app:/app/utils/pdf_metadata_extractor.py
    sudo docker cp utils/pdf_content_extractor.py aris-rag-app:/app/utils/pdf_content_extractor.py
    sudo docker cp utils/ocr_verifier.py aris-rag-app:/app/utils/ocr_verifier.py
    sudo docker cp utils/ocr_auto_fix.py aris-rag-app:/app/utils/ocr_auto_fix.py
    sudo docker cp config/accuracy_config.py aris-rag-app:/app/config/accuracy_config.py
    sudo docker cp storage/document_registry.py aris-rag-app:/app/storage/document_registry.py
    sudo docker cp parsers/docling_parser.py aris-rag-app:/app/parsers/docling_parser.py
    sudo docker cp parsers/base_parser.py aris-rag-app:/app/parsers/base_parser.py
    
    echo "   ✅ Files copied into container"
    
    # Restart container to pick up new code
    echo "   Restarting container..."
    sudo docker restart aris-rag-app 2>/dev/null || {
        echo "   Container not running, starting..."
        sudo docker start aris-rag-app 2>/dev/null || {
            echo "   Container doesn't exist, need to rebuild"
            exit 1
        }
    }
    
    echo "   ✅ Container restarted"
    
    # Wait a moment for services to start
    sleep 5
    
    # Check if container is running
    if sudo docker ps | grep -q aris-rag-app; then
        echo "   ✅ Container is running"
    else
        echo "   ⚠️  Container may not be running, check logs"
    fi
EOF

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${GREEN}✅ Deployment completed in ${DURATION} seconds${NC}"
echo ""
echo -e "${BLUE}📊 Next steps:${NC}"
echo "   1. Wait 10-15 seconds for services to fully start"
echo "   2. Test health: curl http://$SERVER_IP:8500/health"
echo "   3. Check new endpoints: curl http://$SERVER_IP:8500/docs"
echo "   4. Run test: python3 test_text_image_separation_e2e.py"
