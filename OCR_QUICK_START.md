# 🚀 OCRmyPDF Quick Start Guide

**Get started with high-accuracy OCR in 5 minutes**

---

## ⚡ Quick Installation

```bash
# Run the automated installer
bash scripts/install_ocr_dependencies.sh
```

**Or manual installation:**

```bash
# Install Tesseract OCR
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng -y

# Install OCRmyPDF
pip install ocrmypdf>=16.0.0

# Verify
tesseract --version
ocrmypdf --version
```

---

## 🎯 Quick Usage

### API - Upload with OCRmyPDF

```bash
curl -X POST "http://44.221.84.58:8500/documents" \
  -F "file=@scanned_document.pdf" \
  -F "parser_preference=ocrmypdf"
```

### API - OCR Preprocessing Only

```bash
curl -X POST "http://44.221.84.58:8500/documents/ocr-preprocess" \
  -F "file=@scanned_document.pdf" \
  -F "languages=eng" \
  --output ocr_output.pdf
```

### UI - Streamlit

1. Start UI: `streamlit run api/app.py`
2. Select **OCRmyPDF** from parser dropdown
3. Upload scanned PDF
4. Watch OCR progress

---

## 🌐 Multi-Language Support

```bash
# Install additional languages
sudo apt-get install tesseract-ocr-spa -y  # Spanish
sudo apt-get install tesseract-ocr-fra -y  # French
sudo apt-get install tesseract-ocr-deu -y  # German

# Use multiple languages
curl -X POST "http://44.221.84.58:8500/documents/ocr-preprocess" \
  -F "file=@document.pdf" \
  -F "languages=eng+spa+fra" \
  --output ocr_output.pdf
```

---

## 🔧 Common Options

| Option | Values | Description |
|--------|--------|-------------|
| `parser_preference` | `ocrmypdf` | Use OCRmyPDF parser |
| `use_ocr_preprocessing` | `true`/`false` | Preprocess with OCR before parsing |
| `force_ocr` | `true`/`false` | Force OCR on all pages |
| `languages` | `eng`, `eng+spa`, etc. | Tesseract language codes |

---

## 📊 When to Use OCRmyPDF

✅ **Use OCRmyPDF for:**
- Scanned PDFs (documents from scanners/copiers)
- Image-heavy PDFs (photos, screenshots)
- Poor quality scans (skewed, rotated, noisy)
- Multi-language documents

❌ **Don't use OCRmyPDF for:**
- Text-based PDFs (use PyMuPDF - faster)
- Complex layouts with tables (use Docling)
- Already searchable PDFs (unnecessary processing)

---

## 🎯 Best Practices

1. **Scan Quality**: Use 300+ DPI for best results
2. **Skip Text**: Set `skip_text=true` to only OCR pages without text (faster)
3. **Languages**: Only specify languages present in document
4. **Preprocessing**: Use OCR preprocessing + fast parser for hybrid approach

---

## 🔍 Troubleshooting

**Tesseract not found?**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-eng -y
```

**OCRmyPDF not found?**
```bash
pip install ocrmypdf>=16.0.0
```

**Language pack missing?**
```bash
# List installed languages
tesseract --list-langs

# Install missing language
sudo apt-get install tesseract-ocr-<lang> -y
```

---

## 📚 Full Documentation

See `OCR_INTEGRATION_GUIDE.md` for complete documentation, examples, and advanced usage.

---

**Your ARIS RAG system now has enterprise-grade OCR! 🎉**
