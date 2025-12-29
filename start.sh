#!/bin/bash

mkdir -p /app/logs

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

sleep 3

if kill -0 $FASTAPI_PID 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ FastAPI is running"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ FastAPI failed to start, check /tmp/fastapi.log"
    cat /tmp/fastapi.log 2>/dev/null || true
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Streamlit (api/app.py) on port 80..."
export PATH="/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
export PYTHONPATH="/app:${PYTHONPATH}"
streamlit run api/app.py \
    --server.port=80 \
    --server.address=0.0.0.0 \
    --logger.level=info \
    --server.headless=true
