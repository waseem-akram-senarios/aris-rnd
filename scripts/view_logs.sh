#!/bin/bash

# Detailed Log Viewer for ARIS RAG System
# Shows formatted logs from both Streamlit and FastAPI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  ARIS RAG System - Detailed Log Viewer                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to show menu
show_menu() {
    echo -e "${CYAN}Select log type to view:${NC}"
    echo ""
    echo "  1) Container logs (all services)"
    echo "  2) FastAPI logs only"
    echo "  3) Streamlit logs only"
    echo "  4) FastAPI process log (from /tmp/fastapi.log)"
    echo "  5) System logs (docker, systemd)"
    echo "  6) Real-time tail (all logs)"
    echo "  7) Recent errors only"
    echo "  8) All logs (last 100 lines)"
    echo "  9) Exit"
    echo ""
}

# Function to format logs
format_logs() {
    while IFS= read -r line; do
        # Color code different log levels
        if echo "$line" | grep -qi "error\|exception\|failed\|fail"; then
            echo -e "${RED}$line${NC}"
        elif echo "$line" | grep -qi "warning\|warn"; then
            echo -e "${YELLOW}$line${NC}"
        elif echo "$line" | grep -qi "info\|starting\|started"; then
            echo -e "${GREEN}$line${NC}"
        elif echo "$line" | grep -qi "GET\|POST\|PUT\|DELETE"; then
            echo -e "${CYAN}$line${NC}"
        else
            echo "$line"
        fi
    done
}

# Main menu loop
while true; do
    show_menu
    read -p "Enter choice [1-9]: " choice
    echo ""
    
    case $choice in
        1)
            echo -e "${BLUE}📋 Container Logs (Last 50 lines)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs --tail 50 aris-rag-app 2>&1" | format_logs
            echo ""
            ;;
        2)
            echo -e "${BLUE}🚀 FastAPI Logs (Last 50 lines)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs --tail 50 aris-rag-app 2>&1 | grep -i 'fastapi\|uvicorn\|api\|8000' || sudo docker exec aris-rag-app cat /tmp/fastapi.log 2>&1 | tail -50" | format_logs
            echo ""
            ;;
        3)
            echo -e "${BLUE}📊 Streamlit Logs (Last 50 lines)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs --tail 50 aris-rag-app 2>&1 | grep -i 'streamlit\|8501' || sudo docker logs --tail 50 aris-rag-app 2>&1" | format_logs
            echo ""
            ;;
        4)
            echo -e "${BLUE}📝 FastAPI Process Log${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker exec aris-rag-app cat /tmp/fastapi.log 2>&1 | tail -100" | format_logs
            echo ""
            ;;
        5)
            echo -e "${BLUE}⚙️  System Logs${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo journalctl -u docker --no-pager -n 50 2>&1 | tail -50" | format_logs
            echo ""
            ;;
        6)
            echo -e "${BLUE}👁️  Real-time Log Tail (Press Ctrl+C to exit)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs -f aris-rag-app 2>&1" | format_logs
            ;;
        7)
            echo -e "${BLUE}❌ Recent Errors (Last 100 lines)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs --tail 200 aris-rag-app 2>&1 | grep -i 'error\|exception\|failed\|fail\|traceback' | tail -50" | format_logs
            echo ""
            ;;
        8)
            echo -e "${BLUE}📋 All Logs (Last 100 lines)${NC}"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
                "sudo docker logs --tail 100 aris-rag-app 2>&1" | format_logs
            echo ""
            ;;
        9)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter 1-9.${NC}"
            echo ""
            ;;
    esac
    
    read -p "Press Enter to continue..."
    clear
done

