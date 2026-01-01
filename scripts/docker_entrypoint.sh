#!/bin/bash
# Microservices Entrypoint Script

# Ensure log directory exists
mkdir -p /app/logs

# Default to gateway if not specified
export SERVICE_TYPE=${SERVICE_TYPE:-gateway}

echo "============================================================"
echo "🚀 Starting ARIS Microservice: $SERVICE_TYPE"
echo "============================================================"

if [ "$SERVICE_TYPE" == "gateway" ]; then
    # Gateway Service (Orchestrator)
    exec uvicorn services.gateway.main:app --host 0.0.0.0 --port 8500
elif [ "$SERVICE_TYPE" == "ingestion" ]; then
    # Ingestion Service
    exec uvicorn services.ingestion.main:app --host 0.0.0.0 --port 8501
elif [ "$SERVICE_TYPE" == "retrieval" ]; then
    # Retrieval Service
    exec uvicorn services.retrieval.main:app --host 0.0.0.0 --port 8502
elif [ "$SERVICE_TYPE" == "ui" ]; then
    # Streamlit UI
    exec streamlit run app.py --server.port 80 --server.address 0.0.0.0
else
    echo "❌ Unknown service type: $SERVICE_TYPE"
    echo "Please set SERVICE_TYPE to 'gateway', 'ingestion', 'retrieval', or 'ui'."
    exit 1
fi
