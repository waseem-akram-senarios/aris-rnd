# ARIS R&D - Quick Start Guide

## 🚀 Quick Run Commands

### First Time Setup (One-time)

```bash
# 1. Navigate to project directory
cd /home/senarios/Desktop/aris

# 2. Setup virtual environment and install dependencies
./setup_env.sh

# 3. Ensure .env file exists with API keys
# (Should already exist, but verify)
```

### Run the Project

**Option 1: Using the run script (Recommended)**
```bash
./run_rag.sh
```

**Option 2: Manual activation**
```bash
# Activate virtual environment
source venv/bin/activate

# Run Streamlit app
streamlit run app.py
```

**Option 3: One-liner**
```bash
source venv/bin/activate && streamlit run app.py
```

## 📋 Prerequisites Check

Before running, ensure:

1. ✅ Virtual environment exists: `ls venv/`
2. ✅ `.env` file exists with API keys: `cat .env`
3. ✅ Dependencies installed: `pip list | grep streamlit`

## 🔧 Troubleshooting

**If virtual environment doesn't exist:**
```bash
./setup_env.sh
```

**If dependencies are missing:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**If .env file is missing:**
```bash
# Create .env file with your API keys
nano .env
# Add:
# OPENAI_API_KEY=your_key_here
# CEREBRAS_API_KEY=your_key_here
```

## 🌐 Access the Application

Once running, the app will:
- Open automatically in your browser at `http://localhost:8501`
- Or manually navigate to: `http://localhost:8501`

## 🛑 Stop the Application

Press `Ctrl+C` in the terminal to stop the Streamlit server.



