#!/bin/bash
# Health check script for ARIS RAG server
# Returns 0 if healthy, 1 if unhealthy

set -e

SERVER_URL="${SERVER_URL:-http://44.221.84.58}"
TIMEOUT="${TIMEOUT:-10}"

# Check if server is reachable
if curl -s --max-time "$TIMEOUT" --connect-timeout 5 "$SERVER_URL" > /dev/null 2>&1; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$SERVER_URL" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
        echo "✅ Server is healthy (HTTP $HTTP_CODE)"
        exit 0
    else
        echo "⚠️ Server responded with HTTP $HTTP_CODE"
        exit 1
    fi
else
    echo "❌ Server is unreachable (connection refused or timeout)"
    exit 1
fi

