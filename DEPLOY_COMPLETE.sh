#!/bin/bash
# Complete deployment script for OCR integration
# Deploys to: ubuntu@44.221.84.58

set -e

SERVER="ubuntu@44.221.84.58"
KEY="ec2_wah_pk.pem"
REMOTE_DIR="/home/ubuntu/aris"

echo "=========================================="
echo "Deploying OCR Integration to Server"
echo "=========================================="
echo ""

# Step 1: Upload files directly
echo "Step 1: Uploading files to server..."

# Upload parser files
echo "  - Uploading parsers..."
scp -i $KEY parsers/ocrmypdf_parser.py $SERVER:$REMOTE_DIR/parsers/
scp -i $KEY parsers/parser_factory.py $SERVER:$REMOTE_DIR/parsers/

# Upload API files
echo "  - Uploading API files..."
scp -i $KEY api/main.py $SERVER:$REMOTE_DIR/api/
scp -i $KEY api/app.py $SERVER:$REMOTE_DIR/api/

# Upload config
echo "  - Uploading config..."
scp -i $KEY config/requirements.txt $SERVER:$REMOTE_DIR/config/

# Upload scripts
echo "  - Uploading scripts..."
scp -i $KEY scripts/install_ocr_dependencies.sh $SERVER:$REMOTE_DIR/scripts/

echo "✅ Files uploaded"
echo ""

# Step 2: Install dependencies and restart
echo "Step 2: Installing dependencies on server..."
ssh -i $KEY $SERVER << 'ENDSSH'
    cd /home/ubuntu/aris
    
    # Install OCR dependencies
    echo "Installing Tesseract..."
    sudo apt-get update -qq
    sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
    
    echo "Installing OCRmyPDF..."
    pip install ocrmypdf>=16.0.0 --quiet
    
    echo "Installing Python dependencies..."
    pip install -r config/requirements.txt --quiet
    
    # Restart API
    echo "Restarting API service..."
    sudo systemctl restart aris-api 2>/dev/null || \
    pm2 restart aris-api 2>/dev/null || \
    (pkill -f "uvicorn api.main:app" && \
     nohup uvicorn api.main:app --host 0.0.0.0 --port 8500 > api.log 2>&1 &)
    
    sleep 3
    
    # Verify
    echo ""
    echo "Verifying installation..."
    python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; print('✅ OCRmyPDF parser OK')"
    tesseract --version | head -n 1
    
    echo ""
    echo "Testing API..."
    curl -s http://localhost:8500/health | grep -q "healthy" && echo "✅ API is healthy"
ENDSSH

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Your OCR integration is now live:"
echo "  - API: http://44.221.84.58:8500"
echo "  - Docs: http://44.221.84.58:8500/docs"
echo ""
echo "Test OCR endpoint:"
echo "  curl -X POST http://44.221.84.58:8500/documents \\"
echo "    -F 'file=@scanned.pdf' \\"
echo "    -F 'parser_preference=ocrmypdf'"
echo ""
echo "UI (Streamlit) - Run on server:"
echo "  ssh -i $KEY $SERVER"
echo "  cd /home/ubuntu/aris"
echo "  streamlit run api/app.py --server.port 8501"
echo ""
