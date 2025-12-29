# 🖥️ UI OCR Integration Guide

**Your OCR integration is already in the UI!** Here's how to see and use it.

---

## 🚀 Quick Start

### **Step 1: Start the UI**

```bash
# Option 1: Use the start script
bash START_UI_WITH_OCR.sh

# Option 2: Start directly
streamlit run api/app.py
```

The UI will open at: **http://localhost:8501**

---

## 📍 Where to Find OCR Options

### **In the Sidebar:**

1. **Look for "🔧 Parser Settings"** section
2. **Click the dropdown** that says "Choose Parser:"
3. **You'll see 4 options:**
   - Docling
   - PyMuPDF
   - **OCRmyPDF** ← This is the new OCR option!
   - Textract

### **Select OCRmyPDF:**

When you select **OCRmyPDF**, you'll see:

```
🔍 OCR Settings
├── Tesseract Languages: [text input]
│   └── Default: "eng"
│   └── Examples: "eng+spa", "eng+fra"
│
├── OCR DPI: [slider]
│   └── Range: 150-600
│   └── Default: 300
│
└── 💡 OCRmyPDF Features:
    - Automatic deskew and rotation correction
    - Noise removal for better accuracy
    - Text layer embedding in PDFs
    - Optimized for scanned documents
```

---

## 🎯 How to Use OCR in UI

### **Upload a Scanned PDF:**

1. **Start the UI:** `streamlit run api/app.py`
2. **Go to sidebar** → "🔧 Parser Settings"
3. **Select "OCRmyPDF"** from dropdown
4. **Configure OCR settings** (optional):
   - Languages: `eng` (or `eng+spa` for multi-language)
   - DPI: `300` (recommended)
5. **Upload your scanned PDF** in the main area
6. **Watch real-time OCR progress!**

---

## 📸 Visual Guide

### **Sidebar - Parser Settings:**

```
⚙️ Settings
├── 🤖 Model Settings
│   └── [OpenAI/Cerebras selection]
│
├── 🔧 Parser Settings          ← LOOK HERE!
│   └── Choose Parser:
│       ├── Docling
│       ├── PyMuPDF
│       ├── OCRmyPDF           ← SELECT THIS!
│       └── Textract
│
└── 📚 Document Library
```

### **When OCRmyPDF is Selected:**

```
🔧 Parser Settings
└── Choose Parser: OCRmyPDF ✓

    🔍 OCR Settings (expanded)
    ├── Tesseract Languages: [eng____]
    ├── OCR DPI: [====|====] 300
    └── 💡 OCRmyPDF Features:
        - Automatic deskew and rotation correction
        - Noise removal for better accuracy
        - Text layer embedding in PDFs
        - Optimized for scanned documents
```

---

## 🧪 Test OCR in UI

### **Test 1: Basic OCR**

1. Start UI: `streamlit run api/app.py`
2. Select **OCRmyPDF** parser
3. Upload a scanned PDF
4. Watch OCR progress in real-time

### **Test 2: Multi-Language OCR**

1. Select **OCRmyPDF** parser
2. Set languages to: `eng+spa`
3. Upload bilingual document
4. OCR will process both languages

### **Test 3: High-Quality Scan**

1. Select **OCRmyPDF** parser
2. Set DPI to: `400` or `600`
3. Upload high-resolution scan
4. Get maximum accuracy

---

## 🔍 Troubleshooting

### **Issue: Can't see OCRmyPDF in dropdown**

**Solution:** Restart the UI
```bash
# Stop current UI (Ctrl+C)
# Start again
streamlit run api/app.py
```

### **Issue: OCR settings panel doesn't appear**

**Check:**
1. Make sure you selected **OCRmyPDF** (not PyMuPDF or Docling)
2. Look for "🔍 OCR Settings" expander
3. Click to expand if collapsed

### **Issue: UI shows old version**

**Clear cache and restart:**
```bash
# Stop UI (Ctrl+C)
# Clear Streamlit cache
rm -rf .streamlit/cache
# Restart
streamlit run api/app.py
```

---

## 📊 UI Features

### **Real-Time Progress Tracking**

When processing with OCRmyPDF, you'll see:

```
📄 Processing: document.pdf (1/1)

🔍 OCRmyPDF parsing... (45%)
Processing all pages (elapsed: 2m 15s, estimated: 5-10 min)

📊 Extracting text from page 23/50...
```

### **OCR Settings Panel**

```
🔍 OCR Settings

Tesseract Languages:
[eng                    ]
Language codes for Tesseract OCR.
Examples: 'eng', 'eng+spa', 'eng+fra'

OCR DPI:
150 [========|====] 600
        300
DPI for OCR processing. Higher DPI = better
accuracy but slower. 300 DPI is recommended.

💡 OCRmyPDF Features:
- Automatic deskew and rotation correction
- Noise removal for better accuracy
- Text layer embedding in PDFs
- Optimized for scanned documents
```

---

## ✅ Verification Checklist

- [ ] UI starts successfully
- [ ] Sidebar shows "🔧 Parser Settings"
- [ ] Dropdown shows 4 parsers (including OCRmyPDF)
- [ ] Can select OCRmyPDF
- [ ] OCR settings panel appears
- [ ] Can configure languages
- [ ] Can adjust DPI slider
- [ ] Can upload PDF
- [ ] Real-time progress shows

---

## 🎯 Quick Commands

```bash
# Start UI
streamlit run api/app.py

# Start UI with auto-reload
streamlit run api/app.py --server.runOnSave true

# Start UI on different port
streamlit run api/app.py --server.port 8502

# Clear cache and start
rm -rf .streamlit/cache && streamlit run api/app.py
```

---

## 📞 Need Help?

If OCRmyPDF doesn't appear in the UI:

1. **Check the file:** `api/app.py` line 602
   - Should show: `["Docling", "PyMuPDF", "OCRmyPDF", "Textract"]`

2. **Verify syntax:**
   ```bash
   python3 -m py_compile api/app.py
   ```

3. **Restart UI:**
   ```bash
   # Stop (Ctrl+C) and restart
   streamlit run api/app.py
   ```

4. **Check logs:**
   - Look for any errors in terminal where UI is running

---

## 🎉 Summary

**Your OCR integration is ready in the UI!**

**Location:** Sidebar → "🔧 Parser Settings" → "OCRmyPDF"

**To use:**
1. Start UI: `streamlit run api/app.py`
2. Select OCRmyPDF from dropdown
3. Configure OCR settings
4. Upload scanned PDF
5. Watch OCR magic happen!

**UI opens at:** http://localhost:8501
