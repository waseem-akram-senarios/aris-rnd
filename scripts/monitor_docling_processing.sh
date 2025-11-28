#!/bin/bash
# Monitor Docling processing on server

SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
PEM_FILE="scripts/ec2_wah_pk.pem"

echo "🔍 Monitoring Docling Processing on Server"
echo "=========================================="
echo ""

ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<'EOF'
cd /opt/aris-rag

echo "📊 Container Status:"
sudo docker ps --filter "name=aris-rag-app" --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "📋 Recent Docling Processing Logs:"
echo "-----------------------------------"
sudo docker logs --tail=100 aris-rag-app 2>&1 | grep -i "docling" | tail -20

echo ""
echo "⏱️  Processing Status:"
echo "---------------------"
# Check for recent processing activity
LAST_PROCESS=$(sudo docker logs --tail=200 aris-rag-app 2>&1 | grep -i "Processing document\|Docling: Starting conversion" | tail -1)
if [ -n "$LAST_PROCESS" ]; then
    echo "Last processing: $LAST_PROCESS"
    
    # Check if it completed
    if sudo docker logs aris-rag-app 2>&1 | grep -q "Docling: Document conversion successful"; then
        echo "✅ Last conversion completed successfully"
    elif sudo docker logs aris-rag-app 2>&1 | grep -q "Docling:.*timed out\|Docling:.*failed"; then
        echo "❌ Last conversion failed or timed out"
        sudo docker logs --tail=50 aris-rag-app 2>&1 | grep -i "docling.*timeout\|docling.*failed" | tail -3
    else
        echo "⏳ Last conversion may still be in progress"
        echo "   Check logs: sudo docker logs -f aris-rag-app"
    fi
else
    echo "No recent processing found"
fi

echo ""
echo "💾 Resource Usage:"
sudo docker stats --no-stream aris-rag-app --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

echo ""
echo "📝 To watch logs in real-time:"
echo "   sudo docker logs -f aris-rag-app | grep -i docling"
EOF



