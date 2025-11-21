#!/bin/bash

# Server connection script for 18.210.22.221

SERVER_IP="18.210.22.221"
USERNAME="${1:-ec2-user}"  # Default to ec2-user for AWS EC2, but can specify username as first argument
PEM_FILE="$(dirname "$0")/ec2_wah_pk.pem"

echo "Connecting to server $SERVER_IP as user: $USERNAME"
echo "Using PEM file: $PEM_FILE"
echo ""

# Check if PEM file exists
if [ ! -f "$PEM_FILE" ]; then
    echo "Error: PEM file not found at $PEM_FILE"
    echo "Please ensure ec2_wah_pk.pem is in the same directory as this script."
    exit 1
fi

# Ensure PEM file has correct permissions
chmod 600 "$PEM_FILE" 2>/dev/null

# Connect using the PEM file
echo "Attempting connection with PEM key..."
ssh -i "$PEM_FILE" -o ConnectTimeout=10 -o StrictHostKeyChecking=no $USERNAME@$SERVER_IP

