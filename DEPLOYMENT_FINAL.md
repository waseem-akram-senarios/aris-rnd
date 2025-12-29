# ✅ Final Deployment Instructions

**Your OCR integration is in ONE UI file: `api/app.py`**

---

## 📍 Current Status

✅ **OCR Integration Location:** `api/app.py` (your existing UI)  
✅ **No separate UI** - everything is in one file  
✅ **Ready to deploy** to server

---

## 🚀 Deploy to Server

### **Option 1: Automated Deployment (Recommended)**

```bash
bash DEPLOY_COMPLETE.sh
```

This will:
1. Upload all files to server
2. Install Tesseract + OCRmyPDF
3. Install Python dependencies
4. Restart API service
5. Verify everything works

### **Option 2: Manual Deployment**

```bash
# 1. Connect to server
ssh -i ec2_wah_pk.pem ubuntu@44.221.84.58

# 2. Navigate to ARIS directory
cd /home/ubuntu/aris

# 3. Backup current files
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz parsers/ api/ config/

# 4. Upload files (from local machine in new terminal)
scp -i ec2_wah_pk.pem parsers/ocrmypdf_parser.py ubuntu@44.221.84.58:/home/ubuntu/aris/parsers/
scp -i ec2_wah_pk.pem parsers/parser_factory.py ubuntu@44.221.84.58:/home/ubuntu/aris/parsers/
scp -i ec2_wah_pk.pem api/main.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/
scp -i ec2_wah_pk.pem api/app.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/
scp -i ec2_wah_pk.pem config/requirements.txt ubuntu@44.221.84.58:/home/ubuntu/aris/config/

# 5. Back on server - Install dependencies
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
pip install ocrmypdf>=16.0.0
pip install -r config/requirements.txt

# 6. Restart API
sudo systemctl restart aris-api
# OR: pm2 restart aris-api

# 7. Verify
python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; print('✅ OK')"
curl http://localhost:8500/health
```

---

## 🖥️ Access Your UI

### **After Deployment:**

**API (FastAPI):**
- URL: http://44.221.84.58:8500
- Docs: http://44.221.84.58:8500/docs
- Already running ✅

**UI (Streamlit):**
- File: `api/app.py` (same file, includes OCR)
- To run on server:
  ```bash
  ssh -i ec2_wah_pk.pem ubuntu@44.221.84.58
  cd /home/ubuntu/aris
  streamlit run api/app.py --server.port 8501 --server.address 0.0.0.0
  ```
- Access at: http://44.221.84.58:8501

**OR run locally:**
```bash
streamlit run api/app.py
# Opens at: http://localhost:8501
```

---

## 📋 What's in Your UI

**File:** `api/app.py` (ONE file, no separate UI)

**OCR Features:**
- ✅ OCRmyPDF in parser dropdown (line 602)
- ✅ OCR settings panel (lines 612-635)
- ✅ Language configuration
- ✅ DPI slider
- ✅ Real-time progress tracking

**To see OCR options:**
1. Start UI: `streamlit run api/app.py`
2. Look in **sidebar** → "🔧 Parser Settings"
3. Select **"OCRmyPDF"** from dropdown
4. OCR settings panel appears automatically

---

## ✅ Verification After Deployment

### **Test 1: API Health**
```bash
curl http://44.221.84.58:8500/health
# Expected: {"status":"healthy"}
```

### **Test 2: OCR Endpoint**
```bash
curl -X POST http://44.221.84.58:8500/documents/ocr-preprocess \
  -F "file=@test.pdf" \
  -F "languages=eng" \
  --output ocr_output.pdf
```

### **Test 3: Upload with OCRmyPDF**
```bash
curl -X POST http://44.221.84.58:8500/documents \
  -F "file=@scanned.pdf" \
  -F "parser_preference=ocrmypdf"
```

### **Test 4: Check API Docs**
Visit: http://44.221.84.58:8500/docs
- Should show `/documents/ocr-preprocess` endpoint
- Should show `use_ocr_preprocessing` parameter

---

## 🔍 Summary

**What You Have:**
- ✅ ONE UI file: `api/app.py`
- ✅ OCR integration already in it
- ✅ API file: `api/main.py` with OCR endpoints
- ✅ Parser: `parsers/ocrmypdf_parser.py`
- ✅ Ready to deploy

**What to Do:**
1. Run: `bash DEPLOY_COMPLETE.sh`
2. Wait for deployment to complete
3. Test API: `curl http://44.221.84.58:8500/health`
4. Start UI on server (optional): `streamlit run api/app.py`
5. Or run UI locally: `streamlit run api/app.py`

**Where to Find OCR in UI:**
- Sidebar → "Parser Settings" → Select "OCRmyPDF"

---

## 📞 Quick Commands

```bash
# Deploy everything
bash DEPLOY_COMPLETE.sh

# Test API
curl http://44.221.84.58:8500/health

# Run UI locally
streamlit run api/app.py

# Run UI on server
ssh -i ec2_wah_pk.pem ubuntu@44.221.84.58
cd /home/ubuntu/aris
streamlit run api/app.py --server.port 8501 --server.address 0.0.0.0
```

---

**Everything is in ONE UI file (`api/app.py`) and ready to deploy!** 🚀
