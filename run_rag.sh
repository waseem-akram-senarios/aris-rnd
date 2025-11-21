#!/bin/bash

# Quick start script for RAG application

echo "🚀 Starting ARIS R&D - RAG Document Q&A System..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with your API keys."
    echo "You can copy .env.example to .env and fill in your keys."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "🔌 Activating virtual environment..."
    source venv/bin/activate
    if [ "$VIRTUAL_ENV" != "" ]; then
        echo "✅ Virtual environment activated"
    else
        echo "⚠️  Warning: Failed to activate virtual environment"
    fi
else
    echo "⚠️  Warning: Virtual environment not found."
    echo "   Run ./setup_env.sh to create it."
fi

echo ""

# Check if packages are installed
echo "📦 Checking dependencies..."
python3 -c "import streamlit" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed. Installing..."
    pip install -r requirements.txt
fi

echo ""
echo "✅ Starting Streamlit app..."
echo "📝 The app will open in your browser automatically"
echo ""

# Run streamlit
streamlit run app.py


