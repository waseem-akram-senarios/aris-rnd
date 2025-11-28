#!/bin/bash

# Check which ports are open on the server
# Tests both from outside and checks server-side configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
PEM_FILE="$SCRIPT_DIR/ec2_wah_pk.pem"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  Port Availability Check"
echo "==================================================================="
echo ""
echo "Server: $SERVER_IP"
echo ""

# Function to test port from outside
test_port_external() {
    local port=$1
    timeout 2 bash -c "echo >/dev/tcp/$SERVER_IP/$port" 2>/dev/null
    return $?
}

# Test common ports from outside
echo "🌐 Testing ports from outside (your location):"
echo ""

PORTS_TO_TEST=(22 80 443 8080 8443 8501 3000 5000)

for port in "${PORTS_TO_TEST[@]}"; do
    if test_port_external $port; then
        echo -e "   ${GREEN}✅ Port $port: OPEN (accessible from internet)${NC}"
    else
        echo -e "   ${RED}❌ Port $port: CLOSED (not accessible from internet)${NC}"
    fi
done

echo ""

# Check server-side if PEM file exists
if [ -f "$PEM_FILE" ]; then
    chmod 600 "$PEM_FILE" 2>/dev/null || true
    
    echo "🔍 Checking ports on server (what's listening):"
    echo ""
    
    # Check what ports are listening on server
    LISTENING_PORTS=$(ssh -i "$PEM_FILE" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
        "sudo netstat -tlnp 2>/dev/null | grep LISTEN | awk '{print \$4}' | cut -d: -f2 | sort -u || \
         sudo ss -tlnp 2>/dev/null | grep LISTEN | awk '{print \$4}' | cut -d: -f2 | sort -u || \
         echo ''" 2>/dev/null || echo '')
    
    if [ -n "$LISTENING_PORTS" ]; then
        echo "   Ports listening on server:"
        echo "$LISTENING_PORTS" | while read port; do
            if [ -n "$port" ]; then
                echo "      - $port"
            fi
        done
    else
        echo -e "   ${YELLOW}⚠️  Could not check listening ports (may need sudo)${NC}"
    fi
    
    echo ""
    
    # Check firewall status
    echo "🔥 Checking firewall configuration:"
    echo ""
    
    # Check UFW
    UFW_STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
        "sudo ufw status 2>/dev/null | head -1 || echo 'not_installed'" 2>/dev/null || echo 'not_installed')
    
    if [[ "$UFW_STATUS" == *"Status: active"* ]]; then
        echo -e "   ${BLUE}UFW (Ubuntu/Debian firewall):${NC}"
        UFW_RULES=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
            "sudo ufw status numbered 2>/dev/null | grep -E '^\[.*\].*ALLOW' | head -10 || echo ''" 2>/dev/null || echo '')
        if [ -n "$UFW_RULES" ]; then
            echo "$UFW_RULES"
        else
            echo "      No rules found"
        fi
    elif [[ "$UFW_STATUS" == *"Status: inactive"* ]]; then
        echo -e "   ${YELLOW}UFW is installed but inactive${NC}"
    else
        echo "   UFW: not installed or not accessible"
    fi
    
    echo ""
    
    # Check firewalld
    FIREWALLD_STATUS=$(ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" \
        "sudo firewall-cmd --list-all 2>/dev/null || echo 'not_installed'" 2>/dev/null || echo 'not_installed')
    
    if [[ "$FIREWALLD_STATUS" != "not_installed" ]] && [[ "$FIREWALLD_STATUS" != "" ]]; then
        echo -e "   ${BLUE}firewalld (CentOS/RHEL firewall):${NC}"
        echo "$FIREWALLD_STATUS" | grep -E "ports:|services:" | head -5
    fi
    
    echo ""
fi

# Summary and recommendations
echo "==================================================================="
echo "  Summary & How to Open Ports"
echo "==================================================================="
echo ""

OPEN_PORTS=()
for port in "${PORTS_TO_TEST[@]}"; do
    if test_port_external $port; then
        OPEN_PORTS+=($port)
    fi
done

if [ ${#OPEN_PORTS[@]} -eq 0 ]; then
    echo -e "${RED}⚠️  No ports are currently accessible from outside${NC}"
    echo ""
    echo "   This is normal - you need to open ports in AWS Security Group"
else
    echo -e "${GREEN}✅ Open ports: ${OPEN_PORTS[*]}${NC}"
    echo ""
fi

echo "📋 How to Open Ports in AWS (You Can Do This Yourself!):"
echo ""
echo "   1. Go to AWS Console:"
echo "      https://console.aws.amazon.com/ec2/"
echo ""
echo "   2. Navigate to Security Groups:"
echo "      EC2 → Security Groups (left sidebar)"
echo ""
echo "   3. Find Your Instance's Security Group:"
echo "      - Go to EC2 → Instances"
echo "      - Click on your instance (35.175.133.235)"
echo "      - Look at 'Security' tab → Click the security group name"
echo ""
echo "   4. Edit Inbound Rules:"
echo "      - Click 'Edit inbound rules' button"
echo "      - Click 'Add rule'"
echo ""
echo "   5. Configure the Rule:"
echo "      - Type: Custom TCP (or select from dropdown)"
echo "      - Port range: 8501 (or the port you want)"
echo "      - Source: 0.0.0.0/0 (for public access)"
echo "                 OR your IP address (for security)"
echo "      - Description: Streamlit App (optional)"
echo ""
echo "   6. Save Rules:"
echo "      - Click 'Save rules' button"
echo ""
echo "   7. Test:"
echo "      - Wait 10-30 seconds for changes to apply"
echo "      - Try accessing: http://$SERVER_IP:8501"
echo ""

echo "📋 Recommended Ports to Open:"
echo ""
echo "   For Streamlit (Direct Access):"
echo "   - Port 8501: Custom TCP, Source 0.0.0.0/0"
echo ""
echo "   For Production (with nginx):"
echo "   - Port 80: HTTP, Source 0.0.0.0/0"
echo "   - Port 443: HTTPS, Source 0.0.0.0/0"
echo ""
echo "   For SSH (if not already open):"
echo "   - Port 22: SSH, Source Your-IP/32 (for security)"
echo ""

echo "🔧 Alternative: Open Ports via AWS CLI"
echo ""
echo "   If you have AWS CLI configured:"
echo ""
echo "   # Get your security group ID first"
echo "   aws ec2 describe-instances --instance-ids i-xxxxx --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId'"
echo ""
echo "   # Add rule for port 8501"
echo "   aws ec2 authorize-security-group-ingress \\"
echo "     --group-id sg-xxxxx \\"
echo "     --protocol tcp \\"
echo "     --port 8501 \\"
echo "     --cidr 0.0.0.0/0"
echo ""

echo "✅ After opening port 8501, your app will be accessible at:"
echo "   http://$SERVER_IP:8501"
echo ""






