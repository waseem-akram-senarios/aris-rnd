#!/bin/bash

# ARIS Microservices Local Startup Script
# Starts Ingestion, Retrieval, and Gateway services

# Set working directory to project root
cd "$(dirname "$0")/.."

# Create logs directory if it doesn't exist
mkdir -p logs

echo "============================================================"
echo "🚀 Starting ARIS Microservices..."
echo "============================================================"

# 1. Start Ingestion Service (Port 8001)
echo "[1/3] Starting Ingestion Service on port 8001..."
export PYTHONPATH=$PYTHONPATH:.
nohup python3 services/ingestion/main.py > logs/ingestion_service.log 2>&1 &
INGESTION_PID=$!
echo "   - Ingestion Service PID: $INGESTION_PID"

# 2. Start Retrieval Service (Port 8002)
echo "[2/3] Starting Retrieval Service on port 8002..."
nohup python3 services/retrieval/main.py > logs/retrieval_service.log 2>&1 &
RETRIEVAL_PID=$!
echo "   - Retrieval Service PID: $RETRIEVAL_PID"

# Wait a few seconds for services to initialize
echo "⏳ Waiting for services to initialize (5s)..."
sleep 5

# 3. Start Gateway Service (Port 8000)
echo "[3/3] Starting Gateway Service on port 8000..."
export INGESTION_SERVICE_URL="http://localhost:8001"
export RETRIEVAL_SERVICE_URL="http://localhost:8002"
nohup python3 services/gateway/main.py > logs/gateway_service.log 2>&1 &
GATEWAY_PID=$!
echo "   - Gateway Service PID: $GATEWAY_PID"

echo "============================================================"
echo "✅ All services started!"
echo "   - Gateway:   http://localhost:8000"
echo "   - Ingestion: http://localhost:8001"
echo "   - Retrieval: http://localhost:8002"
echo "============================================================"
echo "To stop all services, run: kill $INGESTION_PID $RETRIEVAL_PID $GATEWAY_PID"
echo "Logs are available in the logs/ directory."
