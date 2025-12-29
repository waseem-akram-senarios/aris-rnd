#!/bin/bash
# Deployment script for OCR Integration
# Run this on your EC2 server: ubuntu@44.221.84.58

set -e

echo "=========================================="
echo "Deploying OCR Integration to ARIS Server"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
SERVER="ubuntu@44.221.84.58"
KEY_FILE="ec2_wah_pk.pem"
DEPLOY_PACKAGE="ocr_integration_deployment.tar.gz"
REMOTE_DIR="/home/ubuntu/aris"

echo "Step 1: Uploading deployment package..."
scp -i $KEY_FILE $DEPLOY_PACKAGE $SERVER:/home/ubuntu/

echo ""
echo "Step 2: Connecting to server and deploying..."
ssh -i $KEY_FILE $SERVER << 'ENDSSH'
    cd /home/ubuntu/aris
    
    echo "Extracting deployment package..."
    tar -xzf ../ocr_integration_deployment.tar.gz
    
    echo "Installing OCR dependencies..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
    pip install ocrmypdf>=16.0.0
    
    echo "Installing Python dependencies..."
    pip install -r config/requirements.txt
    
    echo "Restarting API service..."
    sudo systemctl restart aris-api || echo "Manual restart required"
    
    echo "Verifying installation..."
    python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; print('✅ OCRmyPDF parser installed')"
    tesseract --version | head -n 1
    
    echo ""
    echo "✅ Deployment complete!"
ENDSSH

echo ""
echo "=========================================="
echo "Testing API endpoints..."
echo "=========================================="

# Test health endpoint
echo ""
echo "Testing /health endpoint..."
curl -s http://44.221.84.58:8500/health | jq '.'

# Test documents endpoint
echo ""
echo "Testing /documents endpoint..."
curl -s http://44.221.84.58:8500/documents | jq '.total'

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "OCR Integration is now live at:"
echo "  API: http://44.221.84.58:8500"
echo "  Docs: http://44.221.84.58:8500/docs"
echo ""
echo "Test OCR endpoint:"
echo "  curl -X POST http://44.221.84.58:8500/documents \\"
echo "    -F 'file=@scanned.pdf' \\"
echo "    -F 'parser_preference=ocrmypdf'"
echo ""
