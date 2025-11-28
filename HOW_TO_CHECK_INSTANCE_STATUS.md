# How to Check EC2 Instance Status

## Method 1: AWS Console (Easiest)

### Step-by-Step Instructions

1. **Login to AWS Console**
   - Go to: https://console.aws.amazon.com/
   - Sign in with your AWS account

2. **Navigate to EC2**
   - Click on "Services" (top menu)
   - Search for "EC2" and click on it
   - Or go directly to: https://console.aws.amazon.com/ec2/

3. **View Instances**
   - In the left sidebar, click "Instances"
   - You'll see a list of all EC2 instances

4. **Find Your Instance**
   - Look for instance with Public IPv4 address: **35.175.133.235**
   - Or search by instance name/ID if you know it

5. **Check Instance State**
   - Look at the "Instance state" column
   - Possible states:
     - ✅ **Running** (green) = Instance is on and should be reachable
     - ⚠️ **Stopped** (red) = Instance is off, needs to be started
     - ❌ **Terminated** (red) = Instance is deleted, cannot be recovered
     - ⚠️ **Stopping** (yellow) = Instance is shutting down
     - ⚠️ **Pending** (yellow) = Instance is starting up

6. **Check Status Checks** (if Running)
   - Click on the instance to select it
   - Look at the bottom panel → "Status checks" tab
   - Should show: **2/2 checks passed**
   - If shows warnings/errors, instance may have issues

### What Each State Means

| State | Meaning | Action Needed |
|-------|---------|---------------|
| **Running** | Instance is on | Check security groups if can't connect |
| **Stopped** | Instance is off | Click "Start Instance" |
| **Stopping** | Shutting down | Wait for it to stop, then start |
| **Pending** | Starting up | Wait 2-3 minutes |
| **Terminated** | Deleted | Need to create new instance |

## Method 2: AWS CLI (Command Line)

### Prerequisites
- AWS CLI installed: `aws --version`
- AWS credentials configured: `aws configure`

### Check Instance Status

```bash
# List all instances and their status
aws ec2 describe-instances \
  --filters "Name=ip-address,Values=35.175.133.235" \
  --query 'Reservations[*].Instances[*].[InstanceId,State.Name,PublicIpAddress]' \
  --output table

# Or search by IP address
aws ec2 describe-instances \
  --filters "Name=ip-address,Values=35.175.133.235" \
  --query 'Reservations[*].Instances[*].State.Name' \
  --output text
```

### Check Status Checks

```bash
# Get instance ID first
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=ip-address,Values=35.175.133.235" \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

# Check status checks
aws ec2 describe-instance-status \
  --instance-ids $INSTANCE_ID \
  --query 'InstanceStatuses[0].[InstanceStatus.Status,SystemStatus.Status]' \
  --output table
```

## Method 3: Network Connectivity Tests

### Test from Your Computer

```bash
# Test ping (should work if instance is running)
ping -c 4 35.175.133.235

# Test HTTP connection
curl -v http://35.175.133.235/ --max-time 5

# Test SSH connection
ssh -i scripts/ec2_wah_pk.pem -o ConnectTimeout=10 ec2-user@35.175.133.235 "echo 'Connected'"
```

### What Results Mean

| Test | Result | Meaning |
|------|--------|---------|
| **Ping** | Success | Instance is running and network is reachable |
| **Ping** | Failed | Instance may be stopped or security group blocking |
| **HTTP** | 200/302 | Application is working |
| **HTTP** | Timeout | Instance stopped or security group blocking port 80 |
| **SSH** | Connected | Instance is running and SSH is allowed |
| **SSH** | Timeout | Instance stopped or security group blocking port 22 |

## Method 4: Check Security Groups

Even if instance is "Running", security groups might block access.

### In AWS Console

1. Select your instance
2. Go to "Security" tab (bottom panel)
3. Click on the Security Group name
4. Check "Inbound rules":
   - **Port 22 (SSH)**: Should allow your IP or 0.0.0.0/0
   - **Port 80 (HTTP)**: Should allow 0.0.0.0/0

### With AWS CLI

```bash
# Get security group ID
SG_ID=$(aws ec2 describe-instances \
  --filters "Name=ip-address,Values=35.175.133.235" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
  --output text)

# Check inbound rules
aws ec2 describe-security-groups \
  --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissions' \
  --output table
```

## Quick Diagnostic Script

Run this script to check everything:

```bash
#!/bin/bash
echo "🔍 Checking EC2 Instance Status..."
echo ""

# Test ping
echo "1. Testing ping..."
if ping -c 2 -W 2 35.175.133.235 &>/dev/null; then
    echo "   ✅ Ping successful - Instance is reachable"
else
    echo "   ❌ Ping failed - Instance may be stopped"
fi

# Test HTTP
echo ""
echo "2. Testing HTTP..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://35.175.133.235/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "   ✅ HTTP working (Status: $HTTP_CODE)"
else
    echo "   ❌ HTTP not working (Status: $HTTP_CODE)"
fi

# Test SSH
echo ""
echo "3. Testing SSH..."
if ssh -i scripts/ec2_wah_pk.pem -o ConnectTimeout=5 -o StrictHostKeyChecking=no ec2-user@35.175.133.235 "echo 'OK'" &>/dev/null; then
    echo "   ✅ SSH working"
else
    echo "   ❌ SSH not working"
fi

echo ""
echo "📋 Next Steps:"
echo "   - If all tests fail: Check AWS Console for instance state"
echo "   - If instance is 'Stopped': Start it in AWS Console"
echo "   - If instance is 'Running' but tests fail: Check security groups"
```

## Common Scenarios

### Scenario 1: Instance is Stopped
- **AWS Console**: Shows "Stopped" (red)
- **Ping**: Fails
- **HTTP**: Timeout
- **SSH**: Timeout
- **Solution**: Start instance in AWS Console

### Scenario 2: Instance is Running but Can't Connect
- **AWS Console**: Shows "Running" (green)
- **Ping**: May fail (security group blocking ICMP)
- **HTTP**: Timeout
- **SSH**: Timeout
- **Solution**: Check security group rules

### Scenario 3: Instance is Terminated
- **AWS Console**: Shows "Terminated" (red)
- **Ping**: Fails
- **HTTP**: Timeout
- **SSH**: Timeout
- **Solution**: Create new instance (data may be lost)

## Visual Guide: AWS Console

```
EC2 Dashboard
├── Instances (running)
│   └── Your Instance
│       ├── Instance state: [Running/Stopped/Terminated]
│       ├── Status checks: [2/2 checks passed]
│       ├── Public IPv4 address: 35.175.133.235
│       └── Security tab
│           └── Security groups
│               └── Inbound rules
│                   ├── SSH (22) from [Your IP/0.0.0.0/0]
│                   └── HTTP (80) from [0.0.0.0/0]
```

## Quick Checklist

- [ ] Check AWS Console → EC2 → Instances
- [ ] Find instance with IP: 35.175.133.235
- [ ] Check "Instance state" column
- [ ] If "Stopped": Click "Start Instance"
- [ ] If "Running": Check "Status checks" (should be 2/2)
- [ ] If "Running" but can't connect: Check Security Groups
- [ ] Verify Inbound Rules allow:
  - Port 22 (SSH) from your IP or 0.0.0.0/0
  - Port 80 (HTTP) from 0.0.0.0/0


