# Automatic Redeployment System

## Overview
The automatic redeployment system monitors server health and automatically redeploys when the server becomes unreachable, preventing users from seeing "ERR_CONNECTION_REFUSED" errors.

## Components

### 1. Health Check Script (`scripts/health-check.sh`)
- Checks if server is reachable
- Verifies HTTP response codes
- Returns exit code 0 if healthy, 1 if unhealthy

**Usage:**
```bash
bash scripts/health-check.sh
```

### 2. Auto-Redeploy Script (`scripts/auto-redeploy.sh`)
- Checks server health
- Automatically redeploys if connection is refused
- Retries with exponential backoff
- Waits for server to become healthy

**Usage:**
```bash
bash scripts/auto-redeploy.sh
```

**Configuration:**
- `MAX_RETRIES`: Maximum deployment attempts (default: 3)
- `RETRY_DELAY`: Delay between retries in seconds (default: 30)
- `SERVER_URL`: Server URL to check (default: http://44.221.84.58)

### 3. Monitor Script (`scripts/monitor-and-redeploy.sh`)
- Continuously monitors server health
- Automatically triggers redeployment on failures
- Runs as background service or cron job

**Usage:**
```bash
# Run in background
nohup bash scripts/monitor-and-redeploy.sh > /dev/null 2>&1 &

# Or run in foreground
bash scripts/monitor-and-redeploy.sh
```

**Configuration:**
- `CHECK_INTERVAL`: Health check interval in seconds (default: 300 = 5 minutes)
- `MAX_FAILURES`: Consecutive failures before redeploy (default: 2)
- `LOG_FILE`: Log file path (default: logs/auto-redeploy.log)

## Enhanced Deployment Script

The `deploy-fast.sh` script now includes:
- **Automatic retry on health check failure**
- **Multiple health check attempts** (5 attempts with 10s delay)
- **Better error handling** to prevent showing errors to users
- **Graceful degradation** - continues even if health check fails initially

## Setup Instructions

### Option 1: Manual Monitoring
Run the monitor script manually when needed:
```bash
bash scripts/monitor-and-redeploy.sh
```

### Option 2: Systemd Service (Linux)
Create a systemd service for automatic monitoring:

```bash
sudo nano /etc/systemd/system/aris-auto-redeploy.service
```

Add:
```ini
[Unit]
Description=ARIS Auto-Redeployment Monitor
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/aris
ExecStart=/bin/bash /path/to/aris/scripts/monitor-and-redeploy.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable aris-auto-redeploy
sudo systemctl start aris-auto-redeploy
sudo systemctl status aris-auto-redeploy
```

### Option 3: Cron Job
Add to crontab for periodic checks:
```bash
crontab -e
```

Add:
```cron
# Check every 5 minutes and auto-redeploy if needed
*/5 * * * * /path/to/aris/scripts/auto-redeploy.sh >> /path/to/aris/logs/cron-redeploy.log 2>&1
```

## How It Works

1. **Health Check**: Script checks if server responds with HTTP 200/302
2. **Failure Detection**: If connection is refused or timeout occurs
3. **Automatic Redeployment**: Triggers `deploy-fast.sh` automatically
4. **Retry Logic**: Retries deployment up to 3 times with delays
5. **Health Verification**: Waits for server to become healthy after deployment
6. **Logging**: All actions are logged for troubleshooting

## Benefits

✅ **No User-Facing Errors**: Server automatically recovers before users notice
✅ **Automatic Recovery**: No manual intervention needed
✅ **Retry Logic**: Handles transient failures gracefully
✅ **Comprehensive Logging**: Full audit trail of all actions
✅ **Configurable**: Adjustable intervals and thresholds

## Troubleshooting

### Check Logs
```bash
tail -f logs/auto-redeploy.log
```

### Manual Health Check
```bash
bash scripts/health-check.sh
```

### Force Redeployment
```bash
bash scripts/auto-redeploy.sh
```

### Check Server Status
```bash
curl -I http://44.221.84.58/
```

## Configuration Examples

### More Aggressive Monitoring (check every 1 minute)
```bash
CHECK_INTERVAL=60 bash scripts/monitor-and-redeploy.sh
```

### Less Aggressive (check every 10 minutes)
```bash
CHECK_INTERVAL=600 bash scripts/monitor-and-redeploy.sh
```

### Custom Server URL
```bash
SERVER_URL=http://your-server.com bash scripts/auto-redeploy.sh
```

## Notes

- The monitor script runs continuously until stopped
- Use `Ctrl+C` or `kill` to stop the monitor
- Logs are automatically rotated (manual cleanup may be needed)
- The system is designed to be resilient and self-healing

