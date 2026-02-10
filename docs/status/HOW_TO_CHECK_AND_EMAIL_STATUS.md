# How to Check Server Status and Email Others

## Quick Guide

### Step 1: Check Server Status

Run this command to check the server and generate reports:

```bash
./scripts/check_and_report_status.sh
```

This will:
- ✅ Test network connectivity
- ✅ Test HTTP application
- ✅ Test SSH access
- ✅ Check container status
- ✅ Generate text and HTML reports

### Step 2: Send Email to Others

You have several options:

#### Option A: Use Email Script (Interactive)
```bash
./scripts/send_status_email.sh
```

This will guide you through:
1. Generating the status report
2. Choosing email method
3. Sending the email

#### Option B: Manual Email (Easiest)

1. **Open the HTML Report:**
   ```bash
   # On Linux
   xdg-open SERVER_STATUS_REPORT.html
   
   # On Mac
   open SERVER_STATUS_REPORT.html
   
   # Or just open the file in your browser
   ```

2. **Copy the content:**
   - Select all (Ctrl+A / Cmd+A)
   - Copy (Ctrl+C / Cmd+C)

3. **Paste into your email:**
   - Open your email client (Gmail, Outlook, etc.)
   - Create new email
   - Paste the content
   - Send to your team

#### Option C: Attach Report File

1. **Attach the HTML file:**
   - Create new email
   - Attach: `SERVER_STATUS_REPORT.html`
   - Add subject: "Server Status Report - [STATUS]"
   - Send

#### Option D: Use Simple Email Template

1. **Open the template:**
   ```bash
   cat EMAIL_TEMPLATE_SIMPLE.txt
   ```

2. **Copy and customize:**
   - Copy the template
   - Add recipient emails
   - Add current status
   - Send via your email client

## What the Reports Include

### Status Information
- ✅ Overall status (OPERATIONAL / PARTIALLY WORKING / NOT WORKING)
- ✅ Network connectivity test results
- ✅ HTTP application test results
- ✅ SSH access test results
- ✅ Container status

### Test Instructions for Others
- 🌐 Application URL to test
- 📋 Step-by-step testing instructions
- ⚠️ What each status means

## Example Email Content

You can use this template:

```
Subject: Server Status Report - ARIS RAG Application

Dear Team,

Please find the current status of the ARIS RAG application server.

Application URL: http://35.175.133.235/

Please test the application by accessing the URL above.

Current Status: [STATUS FROM REPORT]

If you encounter any issues, please reply to this email.

Best regards,
[Your Name]

---
See attached report for detailed information.
```

## Files Generated

After running the check script, you'll have:

1. **SERVER_STATUS_REPORT.txt** - Text version (good for email body)
2. **SERVER_STATUS_REPORT.html** - HTML version (good for email or web)
3. **EMAIL_TEMPLATE_SIMPLE.txt** - Simple email template

## Quick Commands

### Check Status Only
```bash
./scripts/check_and_report_status.sh
```

### Check and Email
```bash
./scripts/send_status_email.sh
```

### View Reports
```bash
# View text report
cat SERVER_STATUS_REPORT.txt

# View HTML report (opens in browser)
xdg-open SERVER_STATUS_REPORT.html  # Linux
open SERVER_STATUS_REPORT.html       # Mac
```

## Testing Instructions for Others

When you send the email, include these instructions:

### How to Test the Application

1. **Open your web browser** (Chrome, Firefox, Safari, etc.)

2. **Go to this URL:**
   ```
   http://35.175.133.235/
   ```

3. **What you should see:**
   - ✅ **If working:** ARIS RAG application interface
   - ❌ **If not working:** Error message or "This site can't be reached"

4. **Report back:**
   - If you can access it: "✅ Working"
   - If you can't: "❌ Not working" + screenshot of error

### Quick Test Commands (for technical users)

```bash
# Test HTTP
curl -I http://35.175.133.235/

# Test Ping
ping -c 3 35.175.133.235
```

## Status Meanings

### ✅ OPERATIONAL
- Application is working normally
- Everyone can use it
- No action needed

### ⚠️ PARTIALLY WORKING
- Server is running but may have issues
- Some features might not work
- Contact administrator if you see problems

### ❌ NOT WORKING
- Server is down or unreachable
- Cannot access the application
- Administrator needs to start/restart the server

## Automated Status Checking

You can set up automatic status checks:

### Add to Crontab (Check every hour)
```bash
# Edit crontab
crontab -e

# Add this line (check every hour)
0 * * * * cd /home/senarios/Desktop/aris && ./scripts/check_and_report_status.sh >> /tmp/status_check.log 2>&1
```

### Daily Email Report
```bash
# Add to crontab (send daily at 9 AM)
0 9 * * * cd /home/senarios/Desktop/aris && ./scripts/send_status_email.sh
```

## Troubleshooting

### Email Not Sending?

1. **Use manual method:**
   - Open HTML report
   - Copy content
   - Paste into email client

2. **Check email tools:**
   ```bash
   # Check if mail command exists
   which mail
   
   # Check if mutt exists
   which mutt
   ```

3. **Install email tools (if needed):**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install mailutils mutt
   
   # CentOS/RHEL
   sudo yum install mailx mutt
   ```

### Reports Not Generating?

1. **Check script permissions:**
   ```bash
   chmod +x scripts/check_and_report_status.sh
   ```

2. **Run manually:**
   ```bash
   bash scripts/check_and_report_status.sh
   ```

## Summary

1. **Check status:** `./scripts/check_and_report_status.sh`
2. **View report:** Open `SERVER_STATUS_REPORT.html`
3. **Send email:** Copy content or attach file
4. **Include test URL:** http://35.175.133.235/

That's it! The reports are ready to share with your team.


