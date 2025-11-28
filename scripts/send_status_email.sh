#!/bin/bash

# Script to send server status report via email
# Supports multiple email methods

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_FILE="$SCRIPT_DIR/../SERVER_STATUS_REPORT.txt"
HTML_REPORT_FILE="$SCRIPT_DIR/../SERVER_STATUS_REPORT.html"
SERVER_IP="35.175.133.235"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "==================================================================="
echo "  Send Server Status Report via Email"
echo "==================================================================="
echo ""

# First, generate the status report
echo "📊 Generating status report..."
"$SCRIPT_DIR/check_and_report_status.sh" > /dev/null 2>&1

# Check if reports exist
if [ ! -f "$REPORT_FILE" ]; then
    echo "❌ Status report not found. Generating..."
    "$SCRIPT_DIR/check_and_report_status.sh"
fi

# Read overall status from report
OVERALL_STATUS=$(grep "OVERALL STATUS:" "$REPORT_FILE" | cut -d':' -f2 | xargs)

echo "Current Status: $OVERALL_STATUS"
echo ""

# Email configuration
echo "📧 Email Configuration"
echo "---------------------"
echo ""
echo "Choose email method:"
echo "1. Gmail (via mail command)"
echo "2. Send via mutt"
echo "3. Copy email content to clipboard (for manual sending)"
echo "4. Generate email template file"
echo ""
read -p "Select option (1-4): " EMAIL_METHOD

case $EMAIL_METHOD in
    1)
        echo ""
        read -p "Recipient email: " RECIPIENT
        read -p "Your email (Gmail): " SENDER
        echo ""
        echo "Sending email via mail command..."
        
        SUBJECT="Server Status Report - $OVERALL_STATUS - $(date +%Y-%m-%d)"
        
        {
            echo "Subject: $SUBJECT"
            echo "To: $RECIPIENT"
            echo "From: $SENDER"
            echo "Content-Type: text/html"
            echo ""
            cat "$HTML_REPORT_FILE"
        } | sendmail -t "$RECIPIENT" 2>/dev/null || {
            echo "⚠️  mail command not available. Using alternative method..."
            echo ""
            echo "Email content prepared. Please send manually:"
            echo "Subject: $SUBJECT"
            echo "To: $RECIPIENT"
            echo ""
            cat "$HTML_REPORT_FILE"
        }
        ;;
        
    2)
        if ! command -v mutt &> /dev/null; then
            echo "❌ mutt is not installed"
            echo "Install with: sudo apt-get install mutt (Ubuntu/Debian)"
            echo "Or: sudo yum install mutt (CentOS/RHEL)"
            exit 1
        fi
        
        read -p "Recipient email: " RECIPIENT
        read -p "Subject (press Enter for default): " SUBJECT_INPUT
        
        SUBJECT="${SUBJECT_INPUT:-Server Status Report - $OVERALL_STATUS - $(date +%Y-%m-%d)}"
        
        echo ""
        echo "Sending email via mutt..."
        echo "$SUBJECT" | mutt -e "set content_type=text/html" -s "$SUBJECT" "$RECIPIENT" < "$HTML_REPORT_FILE"
        echo "✅ Email sent!"
        ;;
        
    3)
        if command -v xclip &> /dev/null; then
            cat "$HTML_REPORT_FILE" | xclip -selection clipboard
            echo "✅ HTML report copied to clipboard!"
            echo ""
            echo "You can now paste it into your email client."
        elif command -v pbcopy &> /dev/null; then
            cat "$HTML_REPORT_FILE" | pbcopy
            echo "✅ HTML report copied to clipboard!"
            echo ""
            echo "You can now paste it into your email client."
        else
            echo "⚠️  Clipboard tool not available"
            echo "Opening report file for manual copy..."
            if command -v xdg-open &> /dev/null; then
                xdg-open "$HTML_REPORT_FILE"
            elif command -v open &> /dev/null; then
                open "$HTML_REPORT_FILE"
            else
                echo "Please open: $HTML_REPORT_FILE"
            fi
        fi
        ;;
        
    4)
        EMAIL_TEMPLATE="$SCRIPT_DIR/../EMAIL_TEMPLATE.txt"
        SUBJECT="Server Status Report - $OVERALL_STATUS - $(date +%Y-%m-%d)"
        
        cat > "$EMAIL_TEMPLATE" <<EOF
Subject: $SUBJECT
To: [RECIPIENT_EMAIL]
From: [YOUR_EMAIL]

Dear Team,

Please find below the current status of the ARIS RAG application server.

===================================================================
SERVER STATUS: $OVERALL_STATUS
===================================================================

Application URL: http://$SERVER_IP/

Please test the application by accessing the URL above.

===================================================================

$(cat "$REPORT_FILE")

===================================================================

If you encounter any issues, please contact the system administrator.

Best regards,
System Administrator

---
This is an automated status report generated on $(date)
EOF

        echo "✅ Email template created: $EMAIL_TEMPLATE"
        echo ""
        echo "To send:"
        echo "1. Edit the template and add recipient email"
        echo "2. Send via your email client"
        echo ""
        echo "Or attach the HTML report: $HTML_REPORT_FILE"
        ;;
        
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "==================================================================="
echo "  Email Information"
echo "==================================================================="
echo ""
echo "Subject: Server Status Report - $OVERALL_STATUS - $(date +%Y-%m-%d)"
echo ""
echo "Files available:"
echo "  📄 Text Report: $REPORT_FILE"
echo "  🌐 HTML Report: $HTML_REPORT_FILE"
echo ""
echo "Application URL for testing:"
echo "  http://$SERVER_IP/"
echo ""


