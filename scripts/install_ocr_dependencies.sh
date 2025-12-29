#!/bin/bash
# Installation script for OCRmyPDF + Tesseract OCR dependencies
# Run with: bash scripts/install_ocr_dependencies.sh

set -e  # Exit on error

echo "=========================================="
echo "Installing OCRmyPDF + Tesseract OCR"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    echo "⚠️  Please do not run as root. Run as regular user with sudo privileges."
    exit 1
fi

# Update package list
echo "📦 Updating package list..."
sudo apt-get update

# Install Tesseract OCR engine
echo ""
echo "🔍 Installing Tesseract OCR engine..."
sudo apt-get install -y tesseract-ocr

# Install English language pack (default)
echo ""
echo "🌐 Installing English language pack..."
sudo apt-get install -y tesseract-ocr-eng

# Optional: Install additional language packs
echo ""
echo "📚 Additional language packs available:"
echo "  - tesseract-ocr-spa (Spanish)"
echo "  - tesseract-ocr-fra (French)"
echo "  - tesseract-ocr-deu (German)"
echo "  - tesseract-ocr-chi-sim (Chinese Simplified)"
echo "  - tesseract-ocr-ara (Arabic)"
echo ""
read -p "Install additional languages? (y/N): " install_langs

if [[ $install_langs =~ ^[Yy]$ ]]; then
    echo "Available languages: spa fra deu chi-sim ara jpn kor rus ita por"
    read -p "Enter language codes (space-separated, e.g., 'spa fra'): " lang_codes
    
    if [ ! -z "$lang_codes" ]; then
        for lang in $lang_codes; do
            echo "Installing tesseract-ocr-$lang..."
            sudo apt-get install -y "tesseract-ocr-$lang" || echo "⚠️  Could not install $lang"
        done
    fi
fi

# Install system dependencies for OCRmyPDF
echo ""
echo "📦 Installing OCRmyPDF system dependencies..."
sudo apt-get install -y \
    ghostscript \
    img2pdf \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    unpaper \
    pngquant \
    python3-pip

# Install OCRmyPDF Python package
echo ""
echo "🐍 Installing OCRmyPDF Python package..."
pip install ocrmypdf>=16.0.0

# Verify installations
echo ""
echo "=========================================="
echo "✅ Verifying installations..."
echo "=========================================="

# Check Tesseract
if command -v tesseract &> /dev/null; then
    echo "✅ Tesseract OCR: $(tesseract --version | head -n 1)"
    echo "   Installed languages:"
    tesseract --list-langs 2>/dev/null | tail -n +2 | sed 's/^/      - /'
else
    echo "❌ Tesseract OCR not found"
    exit 1
fi

# Check OCRmyPDF
echo ""
if python3 -c "import ocrmypdf" 2>/dev/null; then
    echo "✅ OCRmyPDF: $(python3 -c "import ocrmypdf; print(ocrmypdf.__version__)")"
else
    echo "❌ OCRmyPDF not found"
    exit 1
fi

# Check Ghostscript
echo ""
if command -v gs &> /dev/null; then
    echo "✅ Ghostscript: $(gs --version)"
else
    echo "⚠️  Ghostscript not found (optional but recommended)"
fi

echo ""
echo "=========================================="
echo "🎉 Installation Complete!"
echo "=========================================="
echo ""
echo "You can now use OCRmyPDF in your ARIS RAG system:"
echo "  - API: Set parser_preference='ocrmypdf' when uploading documents"
echo "  - UI: Select 'OCRmyPDF' from the parser dropdown"
echo ""
echo "Test OCRmyPDF with:"
echo "  ocrmypdf --version"
echo "  ocrmypdf input.pdf output.pdf"
echo ""
