# 🖥️ Streamlit UI Server Access

**Important: Port 8501 needs to be exposed in Docker**

---

## 🔍 Current Situation

**API (FastAPI):** ✅ Working on http://44.221.84.58 (port 80)  
**Streamlit UI:** ⚠️ Running but port 8501 not exposed

---

## 🎯 Two Options to Access Streamlit UI

### **Option 1: Access via SSH Tunnel (Recommended)**

This creates a secure tunnel to access Streamlit:

```bash
# Run this on your LOCAL machine:
ssh -i scripts/ec2_wah_pk.pem -L 8501:localhost:8501 ec2-user@44.221.84.58

# Keep this terminal open
# Then open in browser: http://localhost:8501
```

**Steps:**
1. Open terminal on your local machine
2. Run the SSH tunnel command above
3. Keep terminal open
4. Open browser: http://localhost:8501
5. You'll see Streamlit UI with OCR!

### **Option 2: Expose Port in Docker (Requires Restart)**

To make Streamlit accessible directly on http://44.221.84.58:8501, the Docker container needs to expose port 8501.

This requires modifying the Docker run command and restarting the container.

---

## ✅ Recommended: Use SSH Tunnel

**Quick Start:**

```bash
# On your LOCAL machine:
ssh -i scripts/ec2_wah_pk.pem -L 8501:localhost:8501 ec2-user@44.221.84.58
```

**Then open:** http://localhost:8501

**Where to find OCR:**
1. Look at LEFT SIDEBAR
2. Find "🔧 Parser Settings"
3. Click "Choose Parser:" dropdown
4. Select "OCRmyPDF"
5. OCR settings panel appears!

---

## 🚀 Alternative: Run Streamlit Locally

Since the code is deployed, you can also run Streamlit locally:

```bash
cd /home/senarios/Desktop/aris
streamlit run api/app.py
```

Opens at: http://localhost:8501

**Benefits:**
- ✅ Faster
- ✅ No SSH tunnel needed
- ✅ Same OCR features
- ✅ Uses deployed API on server

---

## 📋 Summary

**API:** http://44.221.84.58 ✅ WORKING  
**Streamlit via SSH tunnel:** http://localhost:8501 (after SSH tunnel)  
**Streamlit locally:** `streamlit run api/app.py`

**OCR Location:** Sidebar → Parser Settings → OCRmyPDF

---

**Use SSH tunnel or run locally to see the UI with OCR!** 🎉
