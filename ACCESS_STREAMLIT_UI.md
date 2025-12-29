# 🖥️ Access Streamlit UI on Server

**Your Streamlit UI is now running on the server!**

---

## 🌐 Access URLs

### **Streamlit UI (with OCR):**
**URL:** http://44.221.84.58:8501

### **API (FastAPI):**
**URL:** http://44.221.84.58 (port 80)
**Docs:** http://44.221.84.58/docs

---

## 📍 Where to Find OCR in Streamlit

### **Step 1: Open Streamlit**
Go to: **http://44.221.84.58:8501**

### **Step 2: Look at LEFT SIDEBAR**

```
┌─────────────────────────────────────┐
│  ⚙️ Settings                        │  ← LEFT SIDEBAR
│                                     │
│  🔧 Parser Settings    ← HERE!      │
│  ┌─────────────────────────────┐   │
│  │ Choose Parser:              │   │
│  │ [Docling            ▼]      │   │  ← CLICK THIS!
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

### **Step 3: Click Dropdown**
Click the "Choose Parser:" dropdown

### **Step 4: Select OCRmyPDF**
You'll see:
- Docling
- PyMuPDF
- **OCRmyPDF** ← Select this!
- Textract

### **Step 5: OCR Settings Appear**
After selecting OCRmyPDF:
- Tesseract Languages input
- DPI slider
- Feature information

---

## 🚀 Quick Access

**Streamlit UI:** http://44.221.84.58:8501  
**API:** http://44.221.84.58  
**API Docs:** http://44.221.84.58/docs

---

## 🔧 If Streamlit Stops

To restart Streamlit on the server:

```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58
docker exec -d aris-rag-app streamlit run api/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

---

## ✅ Summary

- ✅ API is on port 80: http://44.221.84.58
- ✅ Streamlit UI is on port 8501: http://44.221.84.58:8501
- ✅ OCR integration is in the UI sidebar
- ✅ Select "OCRmyPDF" from parser dropdown

**Open http://44.221.84.58:8501 in your browser now!** 🎉
