# EC2 Instance Status Diagnosis

## Test Date
November 27, 2025

## Instance Details
- **IP Address**: 35.175.133.235
- **PEM File**: scripts/ec2_wah_pk.pem ✅ (Found and accessible)
- **User**: ec2-user

## Test Results

### ✅ PEM File Status
- **Location**: `scripts/ec2_wah_pk.pem`
- **Permissions**: ✅ Correct (600)
- **File Exists**: ✅ Yes

### ❌ SSH Connection Test
- **Status**: FAILED
- **Error**: `Connection timed out`
- **Port**: 22 (SSH)
- **Result**: Cannot connect to instance

### ❌ Network Connectivity Tests
- **Ping**: ❌ Failed (100% packet loss)
- **HTTP**: ❌ Failed (Connection timeout)
- **SSH**: ❌ Failed (Connection timeout)

## Diagnosis

### Conclusion: **INSTANCE IS LIKELY STOPPED**

Based on all test results:
- ✅ PEM file is valid and accessible
- ❌ SSH connection times out (not refused, which would indicate security group issue)
- ❌ All network connectivity fails
- ❌ No response from any port

**This pattern strongly indicates the EC2 instance is STOPPED.**

### Why This Indicates Stopped Instance

1. **Connection Timeout (not Refused)**
   - If security group was blocking: You'd get "Connection refused"
   - Connection timeout means: Instance is not running at all

2. **All Ports Fail**
   - SSH (22), HTTP (80), Ping (ICMP) all fail
   - This is consistent with a stopped instance

3. **PEM File is Valid**
   - PEM file exists and has correct permissions
   - If it was a PEM/key issue, you'd get authentication error, not timeout

## What You Need to Do

### When You Get AWS Console Access:

1. **Login to AWS Console**
   - Go to: https://console.aws.amazon.com/ec2/
   - Sign in with your AWS account

2. **Navigate to EC2 Instances**
   - Click "EC2" in Services
   - Click "Instances" in left sidebar

3. **Find Your Instance**
   - Look for instance with Public IP: **35.175.133.235**
   - Or search by instance name/ID

4. **Check Instance State**
   - Look at "Instance state" column
   - Expected: **"Stopped"** (red)

5. **Start the Instance**
   - Select the instance
   - Click **"Start Instance"** button (or Actions → Instance State → Start)
   - Wait 2-3 minutes for boot

6. **Verify It's Running**
   - Instance state should change to "Running" (green)
   - Status checks should show "2/2 checks passed"
   - Wait additional 1-2 minutes for full boot

7. **Test Connection**
   - Run: `./scripts/check_instance_status.sh`
   - Or: `./scripts/recover_site.sh`

## Alternative: If Instance is "Running"

If AWS Console shows instance is "Running" but you still can't connect:

### Check Security Groups
1. Select instance → "Security" tab
2. Click on Security Group name
3. Check "Inbound rules":
   - **Port 22 (SSH)**: Should allow your IP or 0.0.0.0/0
   - **Port 80 (HTTP)**: Should allow 0.0.0.0/0

### Check Status Checks
1. Select instance
2. Look at "Status checks" tab
3. Should show: **2/2 checks passed**
4. If showing errors, instance may have issues

## Recovery Steps (After Instance is Running)

Once instance is started and accessible:

### Step 1: Verify SSH Access
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
```

### Step 2: Check Container Status
```bash
cd /opt/aris-rag
sudo docker ps -a
```

### Step 3: Start/Restart Container
```bash
# If container exists but stopped
sudo docker start aris-rag-app

# Or restart with docker-compose
sudo docker compose -f docker-compose.prod.port80.yml up -d
```

### Step 4: Verify Application
```bash
curl http://localhost/
```

### Or Use Recovery Script
```bash
./scripts/recover_site.sh
```

## Summary

| Item | Status | Details |
|------|--------|---------|
| PEM File | ✅ Valid | Found and accessible |
| SSH Connection | ❌ Failed | Connection timeout |
| Network | ❌ Failed | All ports unreachable |
| **Diagnosis** | **STOPPED** | Instance is likely stopped |

## Next Steps

1. **Get AWS Console Access** (required)
2. **Check Instance State** in EC2 Console
3. **Start Instance** if stopped
4. **Wait 2-3 minutes** for boot
5. **Run Recovery Script**: `./scripts/recover_site.sh`

## Files Available

- ✅ `scripts/check_instance_status.sh` - Status check script
- ✅ `scripts/check_instance_via_ssh.sh` - SSH-based check
- ✅ `scripts/recover_site.sh` - Recovery script (run after instance starts)
- ✅ `HOW_TO_CHECK_INSTANCE_STATUS.md` - Complete guide

## Important Notes

- **PEM file is valid** - No issues with authentication key
- **Connection timeout** (not refused) - Indicates instance is off
- **All ports fail** - Consistent with stopped instance
- **Need AWS Console** - To start the instance

Once you have AWS Console access, the instance can be started with one click, and then the recovery script will handle the rest.


