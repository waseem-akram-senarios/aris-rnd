#!/bin/bash
# Continuous monitoring script that auto-redeploys on connection failure
# Can be run as a background service or cron job

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="${LOG_FILE:-$PROJECT_ROOT/logs/auto-redeploy.log}"

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Configuration
SERVER_URL="${SERVER_URL:-http://44.221.84.58}"
CHECK_INTERVAL="${CHECK_INTERVAL:-300}"  # 5 minutes default
MAX_FAILURES="${MAX_FAILURES:-2}"  # Redeploy after 2 consecutive failures

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_health() {
    if "$SCRIPT_DIR/health-check.sh" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

main() {
    log "Starting auto-redeployment monitor (checking every ${CHECK_INTERVAL}s)"
    
    consecutive_failures=0
    
    while true; do
        if check_health; then
            if [ $consecutive_failures -gt 0 ]; then
                log "✅ Server recovered (was down for $consecutive_failures checks)"
            fi
            consecutive_failures=0
        else
            consecutive_failures=$((consecutive_failures + 1))
            log "❌ Health check failed ($consecutive_failures/$MAX_FAILURES)"
            
            if [ $consecutive_failures -ge $MAX_FAILURES ]; then
                log "🚨 Server unreachable - triggering automatic redeployment..."
                if "$SCRIPT_DIR/auto-redeploy.sh"; then
                    log "✅ Auto-redeployment successful"
                    consecutive_failures=0
                else
                    log "❌ Auto-redeployment failed - will retry on next cycle"
                fi
            fi
        fi
        
        sleep $CHECK_INTERVAL
    done
}

# Handle signals gracefully
trap 'log "Monitor stopped"; exit 0' SIGINT SIGTERM

main

