# How to Open Ports in AWS for Deployment

## Quick Answer: Yes, You Can Open Ports Yourself!

You have full control to open ports in AWS Security Groups. No admin needed!

## Method 1: AWS Console (Easiest)

### Step-by-Step Instructions

1. **Go to AWS Console**
   - Visit: https://console.aws.amazon.com/ec2/
   - Sign in with your AWS account

2. **Find Your Instance**
   - Click "Instances" in left sidebar
   - Find your instance (IP: 35.175.133.235)
   - Click on the instance name/ID

3. **Open Security Group**
   - In the instance details, find "Security" tab
   - Click on the Security Group name (e.g., `sg-xxxxx`)
   - This opens the Security Group page

4. **Edit Inbound Rules**
   - Click "Edit inbound rules" button (top right)
   - Click "Add rule" button

5. **Configure the Rule**
   - **Type:** Select "Custom TCP" from dropdown
   - **Port range:** Enter `8501` (or the port you need)
   - **Source:** 
     - For public access: `0.0.0.0/0`
     - For your IP only: `Your-IP/32` (more secure)
   - **Description:** `Streamlit App` (optional)

6. **Save**
   - Click "Save rules" button
   - Wait 10-30 seconds for changes to apply

7. **Test**
   - Try accessing: `http://35.175.133.235:8501`

## Method 2: AWS CLI

If you have AWS CLI installed and configured:

```bash
# First, get your security group ID
INSTANCE_ID="i-xxxxx"  # Your instance ID
SG_ID=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text)

# Add rule for port 8501
aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8501 \
    --cidr 0.0.0.0/0 \
    --description "Streamlit App"
```

## Check Which Ports Are Open

### From Your Local Machine

Run the port check script:
```bash
./scripts/check_open_ports.sh
```

This will show:
- Which ports are accessible from outside
- What's listening on the server
- Firewall status

### Manual Check

Test a specific port:
```bash
timeout 2 bash -c "echo >/dev/tcp/35.175.133.235/8501" && echo "Port 8501 is open" || echo "Port 8501 is closed"
```

### On the Server

SSH to server and check:
```bash
# What ports are listening
sudo netstat -tlnp | grep LISTEN
# OR
sudo ss -tlnp | grep LISTEN

# Check firewall rules
sudo ufw status        # Ubuntu/Debian
sudo firewall-cmd --list-all  # CentOS/RHEL
```

## Recommended Ports to Open

### For Streamlit Direct Access (Current Setup)
- **Port 8501**: Custom TCP, Source 0.0.0.0/0

### For Production with nginx
- **Port 80**: HTTP, Source 0.0.0.0/0
- **Port 443**: HTTPS, Source 0.0.0.0/0

### For SSH (if not already open)
- **Port 22**: SSH, Source Your-IP/32 (recommended for security)

## Security Best Practices

1. **Limit Source IP** (if possible):
   - Instead of `0.0.0.0/0`, use your specific IP: `Your-IP/32`
   - This prevents unauthorized access

2. **Use Security Groups**:
   - Don't disable the firewall
   - Only open ports you actually need

3. **Regular Review**:
   - Periodically review open ports
   - Close ports that are no longer needed

## Troubleshooting

### Port Still Not Accessible After Opening

1. **Wait a few seconds** - Changes can take 10-30 seconds
2. **Check the correct Security Group** - Instance might have multiple SGs
3. **Check server firewall** - UFW or firewalld might be blocking
4. **Verify application is running** - Port open but nothing listening

### Check Server Firewall

```bash
# On server
sudo ufw status
sudo ufw allow 8501/tcp  # If UFW is blocking

# OR
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
```

## Quick Reference

**Open Port 8501 for Streamlit:**
1. EC2 → Security Groups → Your SG → Edit Inbound Rules
2. Add: Custom TCP, Port 8501, Source 0.0.0.0/0
3. Save
4. Access: `http://35.175.133.235:8501`

**Check if port is open:**
```bash
./scripts/check_open_ports.sh
```

