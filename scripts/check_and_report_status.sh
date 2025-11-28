#!/bin/bash

# Comprehensive Status Check and Email Report Script
# Checks server status and generates report for email

set -e

SERVER_IP="35.175.133.235"
SERVER_USER="ec2-user"
PEM_FILE="$(dirname "$0")/ec2_wah_pk.pem"
REPORT_FILE="$(dirname "$0")/../SERVER_STATUS_REPORT.txt"
HTML_REPORT_FILE="$(dirname "$0")/../SERVER_STATUS_REPORT.html"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  Server Status Check & Report Generator"
echo "==================================================================="
echo ""

# Initialize status variables
PING_STATUS="UNKNOWN"
HTTP_STATUS="UNKNOWN"
SSH_STATUS="UNKNOWN"
CONTAINER_STATUS="UNKNOWN"
OVERALL_STATUS="UNKNOWN"

# Test 1: Ping
echo -e "${BLUE}🔍 Testing Network Connectivity...${NC}"
if ping -c 3 -W 2 $SERVER_IP &>/dev/null; then
    PING_STATUS="✅ WORKING"
    echo -e "${GREEN}   ✅ Ping successful${NC}"
else
    PING_STATUS="❌ FAILED"
    echo -e "${RED}   ❌ Ping failed${NC}"
fi

# Test 2: HTTP
echo ""
echo -e "${BLUE}🔍 Testing HTTP Application...${NC}"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://$SERVER_IP/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "307" ]; then
    HTTP_STATUS="✅ WORKING"
    echo -e "${GREEN}   ✅ HTTP working (Status: $HTTP_CODE)${NC}"
elif [ "$HTTP_CODE" = "000" ]; then
    HTTP_STATUS="❌ FAILED"
    echo -e "${RED}   ❌ HTTP connection failed${NC}"
else
    HTTP_STATUS="⚠️  ISSUE (Status: $HTTP_CODE)"
    echo -e "${YELLOW}   ⚠️  HTTP returned: $HTTP_CODE${NC}"
fi

# Test 3: SSH
echo ""
echo -e "${BLUE}🔍 Testing SSH Access...${NC}"
if [ -f "$PEM_FILE" ]; then
    chmod 600 "$PEM_FILE" 2>/dev/null || true
    if timeout 10 ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes "$SERVER_USER@$SERVER_IP" "echo 'OK'" &>/dev/null; then
        SSH_STATUS="✅ WORKING"
        echo -e "${GREEN}   ✅ SSH working${NC}"
        SSH_WORKS=true
    else
        SSH_STATUS="❌ FAILED"
        echo -e "${RED}   ❌ SSH connection failed${NC}"
        SSH_WORKS=false
    fi
else
    SSH_STATUS="⚠️  PEM FILE NOT FOUND"
    SSH_WORKS=false
fi

# Test 4: Container Status (if SSH works)
if [ "$SSH_WORKS" = true ]; then
    echo ""
    echo -e "${BLUE}🔍 Checking Container Status...${NC}"
    CONTAINER_INFO=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<'ENDSSH'
cd /opt/aris-rag 2>/dev/null || echo "NOT_FOUND"
if [ "$?" = "0" ] && [ -d "/opt/aris-rag" ]; then
    CONTAINER_STATUS=$(sudo docker ps --filter "name=aris-rag-app" --format "{{.Status}}" 2>/dev/null || echo "NOT_RUNNING")
    if [ "$CONTAINER_STATUS" != "NOT_RUNNING" ] && [ -n "$CONTAINER_STATUS" ]; then
        echo "RUNNING|$CONTAINER_STATUS"
    else
        echo "STOPPED|Container not running"
    fi
else
    echo "NOT_FOUND|Directory not found"
fi
ENDSSH
)
    
    if echo "$CONTAINER_INFO" | grep -q "RUNNING"; then
        CONTAINER_STATUS="✅ RUNNING"
        CONTAINER_DETAILS=$(echo "$CONTAINER_INFO" | cut -d'|' -f2)
        echo -e "${GREEN}   ✅ Container is running${NC}"
    elif echo "$CONTAINER_INFO" | grep -q "STOPPED"; then
        CONTAINER_STATUS="❌ STOPPED"
        echo -e "${RED}   ❌ Container is stopped${NC}"
    else
        CONTAINER_STATUS="⚠️  UNKNOWN"
        echo -e "${YELLOW}   ⚠️  Cannot determine container status${NC}"
    fi
else
    CONTAINER_STATUS="⚠️  CANNOT CHECK (SSH failed)"
fi

# Determine Overall Status
echo ""
echo -e "${BLUE}🔍 Determining Overall Status...${NC}"

if [ "$HTTP_STATUS" = "✅ WORKING" ]; then
    OVERALL_STATUS="✅ OPERATIONAL"
    STATUS_COLOR="${GREEN}"
elif [ "$PING_STATUS" = "✅ WORKING" ] && [ "$SSH_STATUS" = "✅ WORKING" ]; then
    OVERALL_STATUS="⚠️  PARTIALLY WORKING"
    STATUS_COLOR="${YELLOW}"
else
    OVERALL_STATUS="❌ NOT WORKING"
    STATUS_COLOR="${RED}"
fi

echo -e "${STATUS_COLOR}   $OVERALL_STATUS${NC}"

# Generate Text Report
echo ""
echo -e "${BLUE}📝 Generating Status Report...${NC}"

cat > "$REPORT_FILE" <<EOF
===================================================================
  SERVER STATUS REPORT
===================================================================

Report Generated: $(date)
Server IP: $SERVER_IP
Application URL: http://$SERVER_IP/

===================================================================
  OVERALL STATUS: $OVERALL_STATUS
===================================================================

TEST RESULTS:
-------------
Network Connectivity (Ping): $PING_STATUS
HTTP Application:            $HTTP_STATUS
SSH Access:                   $SSH_STATUS
Container Status:             $CONTAINER_STATUS

===================================================================
  DETAILED INFORMATION
===================================================================

Application URL:
  http://$SERVER_IP/

Test Instructions:
  1. Open the URL in your web browser
  2. You should see the ARIS RAG application interface
  3. If you see an error or timeout, the server is down

Quick Test Commands:
  - Test HTTP: curl -I http://$SERVER_IP/
  - Test Ping: ping -c 3 $SERVER_IP

===================================================================
  STATUS EXPLANATION
===================================================================

✅ OPERATIONAL:
   - Application is accessible and working
   - You can use the application normally

⚠️  PARTIALLY WORKING:
   - Server is running but application may have issues
   - Check container status or contact administrator

❌ NOT WORKING:
   - Server is down or unreachable
   - Instance may be stopped
   - Contact administrator to start the instance

===================================================================
  CONTACT INFORMATION
===================================================================

If you encounter issues:
  1. Check this status report
  2. Try accessing: http://$SERVER_IP/
  3. Contact the system administrator

===================================================================
Report Generated: $(date)
EOF

# Generate HTML Report
cat > "$HTML_REPORT_FILE" <<EOF
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Server Status Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        .status { font-size: 24px; font-weight: bold; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .operational { background: #d4edda; color: #155724; border: 2px solid #c3e6cb; }
        .partial { background: #fff3cd; color: #856404; border: 2px solid #ffeaa7; }
        .down { background: #f8d7da; color: #721c24; border: 2px solid #f5c6cb; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #4CAF50; color: white; }
        tr:hover { background-color: #f5f5f5; }
        .test-url { background: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .test-url a { font-size: 18px; color: #0066cc; text-decoration: none; font-weight: bold; }
        .test-url a:hover { text-decoration: underline; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Server Status Report</h1>
        
        <p><strong>Report Generated:</strong> $(date)<br>
        <strong>Server IP:</strong> $SERVER_IP</p>
        
        <div class="status $(echo $OVERALL_STATUS | tr '[:upper:]' '[:lower:]' | tr -d '✅❌⚠️ ' | tr ' ' '-')">
            Overall Status: $OVERALL_STATUS
        </div>
        
        <div class="test-url">
            <strong>🌐 Test the Application:</strong><br>
            <a href="http://$SERVER_IP/" target="_blank">http://$SERVER_IP/</a>
        </div>
        
        <h2>Test Results</h2>
        <table>
            <tr>
                <th>Test</th>
                <th>Status</th>
            </tr>
            <tr>
                <td>Network Connectivity (Ping)</td>
                <td>$PING_STATUS</td>
            </tr>
            <tr>
                <td>HTTP Application</td>
                <td>$HTTP_STATUS</td>
            </tr>
            <tr>
                <td>SSH Access</td>
                <td>$SSH_STATUS</td>
            </tr>
            <tr>
                <td>Container Status</td>
                <td>$CONTAINER_STATUS</td>
            </tr>
        </table>
        
        <h2>How to Test</h2>
        <ol>
            <li>Click the URL above: <a href="http://$SERVER_IP/" target="_blank">http://$SERVER_IP/</a></li>
            <li>You should see the ARIS RAG application interface</li>
            <li>If you see an error or timeout, the server is down</li>
        </ol>
        
        <h2>Status Explanation</h2>
        <ul>
            <li><strong>✅ OPERATIONAL:</strong> Application is accessible and working normally</li>
            <li><strong>⚠️ PARTIALLY WORKING:</strong> Server is running but application may have issues</li>
            <li><strong>❌ NOT WORKING:</strong> Server is down or unreachable</li>
        </ul>
        
        <div class="footer">
            <p>Report generated automatically on $(date)</p>
            <p>If you encounter issues, please contact the system administrator.</p>
        </div>
    </div>
</body>
</html>
EOF

echo -e "${GREEN}✅ Reports generated!${NC}"
echo ""
echo "📄 Text Report: $REPORT_FILE"
echo "🌐 HTML Report: $HTML_REPORT_FILE"
echo ""

# Display summary
echo "==================================================================="
echo "  SUMMARY"
echo "==================================================================="
echo ""
echo "Overall Status: $OVERALL_STATUS"
echo ""
echo "Test Results:"
echo "  Network:     $PING_STATUS"
echo "  HTTP:        $HTTP_STATUS"
echo "  SSH:         $SSH_STATUS"
echo "  Container:   $CONTAINER_STATUS"
echo ""
echo "Application URL: http://$SERVER_IP/"
echo ""
echo "==================================================================="
echo ""
echo "📧 To send email:"
echo "   1. Open the HTML report: $HTML_REPORT_FILE"
echo "   2. Copy the content or attach the file"
echo "   3. Send email with subject: 'Server Status Report - $OVERALL_STATUS'"
echo ""
echo "Or use the text report: $REPORT_FILE"
echo ""


