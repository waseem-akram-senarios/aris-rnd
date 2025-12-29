# 🚀 OCR Integration Deployment Instructions

**Date:** December 29, 2025  
**Package:** `ocr_integration_deployment.tar.gz` (48 KB)  
**Server:** ubuntu@44.221.84.58:8500

---

## 📦 Deployment Package Ready

✅ **Package Created:** `ocr_integration_deployment.tar.gz`  
✅ **Size:** 48 KB  
✅ **Contains:** 10 new files + 5 modified files

---

## 🔧 Manual Deployment Steps

Since SSH key authentication needs configuration, here are the manual deployment steps:

### **Option 1: Manual SSH Deployment**

```bash
# 1. Connect to your EC2 server
ssh -i ec2_wah_pk.pem ubuntu@44.221.84.58

# 2. Navigate to ARIS directory
cd /home/ubuntu/aris

# 3. Backup current code
tar -czf backup_$(date +%Y%m%d_%H%M%S).tar.gz parsers/ api/ config/

# 4. Upload the deployment package (from your local machine)
# Run this in a NEW terminal on your local machine:
scp -i ec2_wah_pk.pem ocr_integration_deployment.tar.gz ubuntu@44.221.84.58:/home/ubuntu/

# 5. Back on the server, extract the package
cd /home/ubuntu/aris
tar -xzf ../ocr_integration_deployment.tar.gz

# 6. Install OCR dependencies
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
pip install ocrmypdf>=16.0.0

# 7. Install Python dependencies
pip install -r config/requirements.txt

# 8. Restart the API service
sudo systemctl restart aris-api
# OR if using PM2:
pm2 restart aris-api
# OR if running manually:
pkill -f "uvicorn api.main:app"
cd /home/ubuntu/aris
nohup uvicorn api.main:app --host 0.0.0.0 --port 8500 &

# 9. Verify deployment
python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; print('✅ OCRmyPDF installed')"
tesseract --version
curl http://localhost:8500/health
```

---

### **Option 2: Direct File Upload via SCP**

If the tar.gz upload doesn't work, upload files individually:

```bash
# Upload parser
scp -i ec2_wah_pk.pem parsers/ocrmypdf_parser.py ubuntu@44.221.84.58:/home/ubuntu/aris/parsers/

# Upload modified parser factory
scp -i ec2_wah_pk.pem parsers/parser_factory.py ubuntu@44.221.84.58:/home/ubuntu/aris/parsers/

# Upload API files
scp -i ec2_wah_pk.pem api/main.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/
scp -i ec2_wah_pk.pem api/app.py ubuntu@44.221.84.58:/home/ubuntu/aris/api/

# Upload requirements
scp -i ec2_wah_pk.pem config/requirements.txt ubuntu@44.221.84.58:/home/ubuntu/aris/config/

# Upload scripts
scp -i ec2_wah_pk.pem scripts/install_ocr_dependencies.sh ubuntu@44.221.84.58:/home/ubuntu/aris/scripts/
```

---

### **Option 3: Git Push & Pull**

```bash
# On local machine
git add .
git commit -m "Add OCRmyPDF integration"
git push origin main

# On server
ssh -i ec2_wah_pk.pem ubuntu@44.221.84.58
cd /home/ubuntu/aris
git pull origin main
bash scripts/install_ocr_dependencies.sh
sudo systemctl restart aris-api
```

---

## ✅ Current API Status

**API Health Check:** ✅ HEALTHY
```json
{"status":"healthy"}
```

**Server:** http://44.221.84.58:8500  
**Docs:** http://44.221.84.58:8500/docs

---

## 🧪 Post-Deployment Testing

### **1. Test Health Endpoint**
```bash
curl http://44.221.84.58:8500/health
```

### **2. Test Documents Endpoint**
```bash
curl http://44.221.84.58:8500/documents
```

### **3. Test OCR Preprocessing Endpoint (NEW)**
```bash
curl -X POST http://44.221.84.58:8500/documents/ocr-preprocess \
  -F "file=@test.pdf" \
  -F "languages=eng" \
  --output ocr_output.pdf
```

### **4. Test Document Upload with OCRmyPDF**
```bash
curl -X POST http://44.221.84.58:8500/documents \
  -F "file=@scanned.pdf" \
  -F "parser_preference=ocrmypdf"
```

### **5. Test OCR Preprocessing + PyMuPDF**
```bash
curl -X POST http://44.221.84.58:8500/documents \
  -F "file=@mixed.pdf" \
  -F "parser_preference=pymupdf" \
  -F "use_ocr_preprocessing=true"
```

---

## 📋 Deployment Checklist

- [ ] Backup current code
- [ ] Upload deployment package
- [ ] Extract files
- [ ] Install Tesseract OCR (`sudo apt-get install tesseract-ocr`)
- [ ] Install OCRmyPDF (`pip install ocrmypdf>=16.0.0`)
- [ ] Update Python dependencies (`pip install -r config/requirements.txt`)
- [ ] Restart API service
- [ ] Test `/health` endpoint
- [ ] Test `/documents` endpoint
- [ ] Test `/documents/ocr-preprocess` endpoint (NEW)
- [ ] Verify OCRmyPDF parser works
- [ ] Check API docs at `/docs`

---

## 🔍 Verification Commands

```bash
# Check if Tesseract is installed
tesseract --version

# Check if OCRmyPDF is installed
python3 -c "import ocrmypdf; print(ocrmypdf.__version__)"

# Check if parser loads
python3 -c "from parsers.ocrmypdf_parser import OCRmyPDFParser; print('✅ OK')"

# Check API logs
tail -f /var/log/aris-api.log
# OR
pm2 logs aris-api
```

---

## 🐛 Troubleshooting

### Issue: Tesseract not found
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
```

### Issue: OCRmyPDF not found
```bash
pip install ocrmypdf>=16.0.0
```

### Issue: API not restarting
```bash
# Check if API is running
ps aux | grep uvicorn

# Kill old process
pkill -f "uvicorn api.main:app"

# Start new process
cd /home/ubuntu/aris
nohup uvicorn api.main:app --host 0.0.0.0 --port 8500 > api.log 2>&1 &
```

### Issue: Import errors
```bash
# Reinstall dependencies
pip install -r config/requirements.txt --force-reinstall
```

---

## 📊 What's New in This Deployment

### New Files (10)
1. `parsers/ocrmypdf_parser.py` - OCRmyPDF parser (270 lines)
2. `scripts/install_ocr_dependencies.sh` - Installation script
3. `scripts/test_ocr_integration.sh` - Integration tests
4. `scripts/test_ocr_api_endpoints.sh` - API tests
5. Documentation files (OCR_*.md)

### Modified Files (5)
1. `config/requirements.txt` - Added ocrmypdf>=16.0.0
2. `parsers/parser_factory.py` - Registered OCRmyPDF
3. `api/main.py` - Added OCR endpoints (+90 lines)
4. `api/app.py` - Added UI integration (+35 lines)
5. `README.md` - Updated documentation

### New API Endpoints
- `POST /documents` - Enhanced with `use_ocr_preprocessing` parameter
- `POST /documents/ocr-preprocess` - NEW standalone OCR endpoint

### New Features
- High-accuracy OCR with Tesseract
- Multi-language support (100+ languages)
- Automatic deskew and rotation correction
- Noise removal for better accuracy
- OCR preprocessing for any parser
- Real-time progress tracking in UI

---

## 🎯 Expected Results After Deployment

1. ✅ API responds at http://44.221.84.58:8500
2. ✅ `/health` returns `{"status":"healthy"}`
3. ✅ `/docs` shows new OCR endpoints
4. ✅ OCRmyPDF parser available in parser list
5. ✅ Can upload documents with `parser_preference=ocrmypdf`
6. ✅ Can use OCR preprocessing with any parser
7. ✅ Tesseract installed and working
8. ✅ Multi-language OCR support

---

## 📞 Support

If you encounter issues:
1. Check API logs
2. Verify Tesseract installation: `tesseract --version`
3. Verify OCRmyPDF installation: `python3 -c "import ocrmypdf"`
4. Check parser registration: `python3 -c "from parsers.parser_factory import ParserFactory; print(ParserFactory.get_parser('test.pdf', 'ocrmypdf'))"`
5. Review documentation: `OCR_INTEGRATION_GUIDE.md`

---

**Deployment Package:** `ocr_integration_deployment.tar.gz` (48 KB)  
**Ready for deployment!** 🚀
