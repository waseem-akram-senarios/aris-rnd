# 🔧 Parser Changes - Previous & Current

## 📋 Previous Changes (Optimizations)

### **PyMuPDF**
✅ Multi-method extraction (dict → text → blocks → rawdict)
✅ Formatting preservation (whitespace, ligatures)
✅ Better reading order (`sort=True`)
✅ Hidden text layer handling

### **OCRmyPDF**
✅ `force_ocr: False → True` (OCR all pages)
✅ `skip_text: True → False` (process all pages)
✅ `optimize: 1 → 0` (no quality loss)
✅ `tesseract_timeout: 180s → 300s` (5 min per page)
✅ Added deskew, clean, rotation detection
✅ CJK optimizations (2x oversample, remove background)
✅ Removed `redo_ocr` (incompatible)

### **Docling**
❌ Attempted OCR config (failed due to v2.68.0 bug)
- Tried: `force_full_page_ocr`, `TableFormerMode.ACCURATE`, etc.
- Error: `'OcrOptions' object has no attribute 'kind'`

### **Llama-Scan**
✅ Enhanced prompt (detailed accuracy requirements)
✅ 2x image resolution (`zoom: 1.0 → 2.0`)
✅ Multi-column handling
✅ Table preservation instructions

---

## 🔧 Current Changes (Bug Fixes)

### **Docling Parser**
**Issue:** `'OcrOptions' object has no attribute 'kind'` (Docling v2.68.0 bug)
**Fix:** Disabled OCR (`do_ocr = False`) to avoid bug
**Status:** ✅ Working (no OCR, but parser functional)

### **OCRmyPDF**
**Fix 1:** `unpaper_args` format (string → list)
**Fix 2:** Removed `redo_ocr` (incompatible with deskew/clean)
**Status:** ✅ Working

---

## 📊 Summary

| Parser | Previous | Current | Status |
|--------|----------|---------|--------|
| PyMuPDF | Optimized extraction | None | ✅ Working |
| OCRmyPDF | Force OCR, quality opt | Fixed params | ✅ Working |
| Docling | OCR config (failed) | OCR disabled | ✅ Working |
| Llama-Scan | Enhanced prompt, 2x res | None | ✅ Working |

**Recommendations:**
• Text PDFs → PyMuPDF
• Scanned PDFs → OCRmyPDF
• Complex tables → Docling (no OCR)


