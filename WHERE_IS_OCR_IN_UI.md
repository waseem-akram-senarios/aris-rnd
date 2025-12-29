# 🔍 Where to Find OCR in Streamlit UI

**Your OCR integration IS in the UI!** Here's exactly where to look.

---

## ✅ Confirmed: OCR is in Your UI

I've verified that OCR is in `api/app.py`:
- ✅ Line 602: OCRmyPDF in parser dropdown
- ✅ Lines 612-635: OCR settings panel
- ✅ 5 mentions of "OCRmyPDF" in the file

---

## 📍 Exact Location in UI

### **Step-by-Step:**

1. **Start Streamlit:**
   ```bash
   streamlit run api/app.py
   ```

2. **Look at the LEFT SIDEBAR** (not the main area)

3. **Scroll down in the sidebar** to find:
   ```
   ⚙️ Settings
   ├── 🤖 Model Settings
   │   └── [OpenAI/Cerebras options]
   │
   ├── 🔧 Parser Settings    ← LOOK HERE!
   │   └── Choose Parser:
   │       [Dropdown menu]   ← CLICK THIS!
   ```

4. **Click the dropdown** that says "Choose Parser:"

5. **You should see 4 options:**
   ```
   ┌─────────────────────┐
   │ Docling            │
   │ PyMuPDF            │
   │ OCRmyPDF           │ ← THIS ONE!
   │ Textract           │
   └─────────────────────┘
   ```

6. **Select "OCRmyPDF"**

7. **OCR Settings panel appears below:**
   ```
   🔍 OCR Settings
   ├── Tesseract Languages: [eng____]
   ├── OCR DPI: [slider 150-600]
   └── 💡 OCRmyPDF Features:
       - Automatic deskew...
       - Noise removal...
   ```

---

## 🔧 If You Still Can't See It

### **Problem 1: Streamlit is Cached**

**Solution:**
```bash
# Stop Streamlit (Ctrl+C)
# Run this script:
bash RESTART_UI.sh
```

OR manually:
```bash
# Stop Streamlit
pkill -f "streamlit run"

# Clear cache
rm -rf .streamlit/cache
rm -rf ~/.streamlit/cache

# Restart
streamlit run api/app.py
```

### **Problem 2: Looking in Wrong Place**

**Common mistakes:**
- ❌ Looking in the MAIN area (center of screen)
- ❌ Looking for a separate OCR tab
- ❌ Looking in the top menu

**Correct location:**
- ✅ LEFT SIDEBAR
- ✅ Under "🔧 Parser Settings"
- ✅ In the "Choose Parser:" dropdown

### **Problem 3: Sidebar is Collapsed**

**Solution:**
- Look for a **>** arrow in the top-left corner
- Click it to expand the sidebar

### **Problem 4: Wrong File Running**

**Check:**
```bash
# Make sure you're running the right file
ps aux | grep streamlit

# Should show: streamlit run api/app.py
```

---

## 🧪 Test Your UI

**Run this test script:**
```bash
python3 TEST_UI_OCR.py
```

**Expected output:**
```
✅ OCRmyPDF is in the dropdown
✅ OCR settings panel code found
✅ OCR language input found
✅ DPI slider found
```

---

## 📸 Visual Guide

### **What Your Sidebar Should Look Like:**

```
┌─────────────────────────────────────┐
│  ⚙️ Settings                        │
│                                     │
│  🤖 Model Settings                  │
│  ┌─────────────────────────────┐   │
│  │ Choose API:                 │   │
│  │ ○ OpenAI  ● Cerebras       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ───────────────────────────────   │
│                                     │
│  🔧 Parser Settings                 │
│  ┌─────────────────────────────┐   │
│  │ Choose Parser:              │   │
│  │ [Docling            ▼]      │   │ ← CLICK HERE!
│  └─────────────────────────────┘   │
│                                     │
│  When you click, you'll see:       │
│  ┌─────────────────────────────┐   │
│  │ Docling                     │   │
│  │ PyMuPDF                     │   │
│  │ OCRmyPDF         ← SELECT!  │   │
│  │ Textract                    │   │
│  └─────────────────────────────┘   │
│                                     │
│  After selecting OCRmyPDF:         │
│  🔍 OCR Settings                    │
│  ┌─────────────────────────────┐   │
│  │ Tesseract Languages:        │   │
│  │ [eng                    ]   │   │
│  │                             │   │
│  │ OCR DPI:                    │   │
│  │ 150 [====|====] 600         │   │
│  │         300                 │   │
│  └─────────────────────────────┘   │
│                                     │
│  💡 OCRmyPDF Features:              │
│  - Automatic deskew...              │
│  - Noise removal...                 │
│                                     │
└─────────────────────────────────────┘
```

---

## ✅ Quick Checklist

- [ ] Streamlit is running: `streamlit run api/app.py`
- [ ] Looking at LEFT SIDEBAR (not main area)
- [ ] Found "🔧 Parser Settings" section
- [ ] Clicked "Choose Parser:" dropdown
- [ ] Can see 4 parser options
- [ ] "OCRmyPDF" is one of the options
- [ ] Selected "OCRmyPDF"
- [ ] OCR settings panel appeared

---

## 🚀 Quick Commands

```bash
# Test if OCR is in UI
python3 TEST_UI_OCR.py

# Restart UI with cache cleared
bash RESTART_UI.sh

# Or manually:
pkill -f "streamlit run"
rm -rf .streamlit/cache
streamlit run api/app.py
```

---

## 📞 Still Can't See It?

**Take a screenshot of your Streamlit sidebar and check:**
1. Is the sidebar expanded? (not collapsed)
2. Can you see "🔧 Parser Settings"?
3. Can you see a dropdown that says "Choose Parser:"?
4. What options are in the dropdown?

**The OCR integration IS in your file - it's just about finding it in the UI!**

---

**File:** `api/app.py` lines 600-635  
**Status:** ✅ OCR INTEGRATION CONFIRMED IN UI
