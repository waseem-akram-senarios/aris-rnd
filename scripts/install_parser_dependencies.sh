#!/bin/bash
# Server Dependency Installation Script for ARIS Parsers
# This script installs all system dependencies required for document parsers

set -e

echo "=================================="
echo "ARIS Parser Dependencies Installer"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERROR: This script must be run with sudo${NC}"
    echo "Usage: sudo ./scripts/install_parser_dependencies.sh"
    exit 1
fi

echo -e "${YELLOW}[1/4] Updating package lists...${NC}"
apt-get update -qq

echo ""
echo -e "${YELLOW}[2/4] Installing Tesseract OCR (for OCRMyPDF & Docling)...${NC}"
apt-get install -y -qq \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-por \
    tesseract-ocr-ara \
    tesseract-ocr-chi-sim \
    tesseract-ocr-jpn \
    tesseract-ocr-kor

# Verify Tesseract installation
if command -v tesseract &> /dev/null; then
    TESSERACT_VERSION=$(tesseract --version 2>&1 | head -n 1)
    echo -e "${GREEN}✅ Tesseract installed: $TESSERACT_VERSION${NC}"
    
    # List installed languages
    echo "   Available languages:"
    tesseract --list-langs 2>&1 | grep -v "List of available languages" | sed 's/^/   - /'
else
    echo -e "${RED}❌ Tesseract installation failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[3/4] Installing Ollama (for LlamaScan)...${NC}"

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✅ Ollama already installed${NC}"
else
    echo "   Downloading and installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    
    if command -v ollama &> /dev/null; then
        echo -e "${GREEN}✅ Ollama installed successfully${NC}"
    else
        echo -e "${RED}❌ Ollama installation failed${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${YELLOW}[4/4] Setting up Ollama service and models...${NC}"

# Start Ollama service if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "   Starting Ollama service..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
    
    if pgrep -x "ollama" > /dev/null; then
        echo -e "${GREEN}✅ Ollama service started${NC}"
    else
        echo -e "${RED}❌ Failed to start Ollama service${NC}"
        echo "   Check logs: /tmp/ollama.log"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Ollama service already running${NC}"
fi

# Pull required vision model
echo "   Pulling llava:latest model (this may take a few minutes)..."
ollama pull llava:latest

if ollama list | grep -q "llava"; then
    echo -e "${GREEN}✅ llava:latest model installed${NC}"
else
    echo -e "${RED}❌ Failed to pull llava model${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=================================="
echo "✅ All dependencies installed!"
echo "==================================${NC}"
echo ""
echo "Summary:"
echo "  ✅ Tesseract OCR (for OCRMyPDF & Docling)"
echo "  ✅ Ollama + llava:latest (for LlamaScan)"
echo ""
echo "You can now run the parser benchmarks:"
echo "  python3 tests/benchmark_parsers.py"
echo ""
