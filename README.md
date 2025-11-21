# ARIS R&D - RAG Document Q&A System

## Overview
ARIS R&D is a comprehensive RAG (Retrieval-Augmented Generation) system for document processing and question-answering. It supports multiple parsers (PyMuPDF, Docling, AWS Textract), token tracking, and advanced metrics collection.

## Features
- **Multiple Document Parsers**: PyMuPDF, Docling, AWS Textract with intelligent fallback
- **Token Tracking**: Real-time token counting and cost estimation
- **Progress Feedback**: Enhanced progress tracking for chunking and embedding operations
- **Metrics Dashboard**: Comprehensive R&D analytics and performance metrics
- **Streamlit UI**: User-friendly web interface

## Server Information
- **IP Address:** 18.210.22.221
- **Type:** AWS EC2 Instance
- **PEM File:** ec2_wah_pk.pem
- **Status:** Server is reachable via SSH

## Connection Methods

### Method 1: Using the connection script (Easiest)
```bash
./connect_server.sh
```

The script automatically uses the `ec2_wah_pk.pem` file in the same directory.

Or with a specific username (default is `ec2-user`):
```bash
./connect_server.sh ubuntu
```

### Method 2: Direct SSH connection with PEM file
```bash
ssh -i ec2_wah_pk.pem ec2-user@18.210.22.221
```

For Ubuntu/Debian instances, you might need:
```bash
ssh -i ec2_wah_pk.pem ubuntu@18.210.22.221
```

### Method 3: Using SSH config (Recommended for frequent use)
1. Copy the SSH config to your ~/.ssh/config:
   ```bash
   cat ssh_config >> ~/.ssh/config
   ```

2. Then connect using:
   ```bash
   ssh server-aris
   ```

## Important Notes

- **PEM File Permissions:** The PEM file must have restricted permissions (600). The script handles this automatically.
- **Username:** AWS EC2 instances typically use:
  - `ec2-user` for Amazon Linux
  - `ubuntu` for Ubuntu
  - `admin` for Debian
  - `centos` for CentOS

## Troubleshooting

- **Permission denied:** Ensure the PEM file has correct permissions: `chmod 600 ec2_wah_pk.pem`
- **Wrong username:** Try different usernames (`ec2-user`, `ubuntu`, `admin`, `root`)
- **Connection timeout:** Check security group settings in AWS console
- **Host key verification:** The script uses `StrictHostKeyChecking=no` for convenience

## Quick Start

See `QUICK_START.md` for detailed setup instructions.

## Documentation

- `SETUP.md` - Installation and configuration
- `QUICK_START.md` - Getting started guide
- `METRICS_GUIDE.md` - Metrics and analytics
- `HOW_TO_USE_DOCLING.md` - Docling parser usage
- `diagrams/` - Architecture diagrams
