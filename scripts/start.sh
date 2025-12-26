#!/bin/bash

# Startup script to run both Streamlit and FastAPI with detailed logging

# Create log directory
mkdir -p /app/logs

# Start FastAPI in background on port 8500
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting FastAPI on port 8500..."
uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8500 \
    --log-level info \
    --access-log \
    --use-colors \
    > /tmp/fastapi.log 2>&1 &

FASTAPI_PID=$!
echo "[$(date '+%Y-%m-%d %H:%M:%S')] FastAPI started with PID: $FASTAPI_PID"

# Wait a moment for FastAPI to start
sleep 3

# Verify FastAPI is running (use kill -0 instead of ps)
if kill -0 $FASTAPI_PID 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ FastAPI is running"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ FastAPI failed to start, check /tmp/fastapi.log"
    cat /tmp/fastapi.log 2>/dev/null || true
fi

# Start Streamlit in foreground (keeps container alive)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Streamlit on port 80..."
streamlit run app.py \
    --server.port=80 \
    --server.address=0.0.0.0 \
    --logger.level=info \
    --server.headless=true

