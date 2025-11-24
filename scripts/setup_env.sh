#!/bin/bash

# Setup script for RAG system virtual environment
# This script creates and configures the virtual environment

set -e  # Exit on error

echo "🚀 Setting up RAG system virtual environment..."
echo ""

# Check Python version
echo "📋 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Found Python $PYTHON_VERSION"

# Check if Python 3.10+
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    echo "❌ Error: Python 3.10+ is required. Found Python $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python version check passed"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "ℹ️  Virtual environment already exists"
fi

echo ""

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Verify activation
if [ "$VIRTUAL_ENV" != "" ]; then
    echo "✅ Virtual environment activated: $VIRTUAL_ENV"
    PYTHON_PATH=$(which python)
    echo "   Python path: $PYTHON_PATH"
else
    echo "❌ Error: Failed to activate virtual environment"
    exit 1
fi

echo ""

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip --quiet
echo "✅ pip upgraded"

echo ""

# Install dependencies
echo "📥 Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
else
    echo "⚠️  Warning: requirements.txt not found"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To activate the virtual environment manually, run:"
echo "   source venv/bin/activate"
echo ""
echo "To run the RAG application:"
echo "   ./run_rag.sh"
echo "   OR"
echo "   source venv/bin/activate && streamlit run app.py"

