# Project Organization

This document describes the organized folder structure of the ARIS RAG project.

## 📁 Directory Structure

### Root Directory
Contains only essential project files:
- `app.py` - Main Streamlit application
- `rag_system.py` - RAG system core
- `Dockerfile` - Docker image definition
- `docker-compose*.yml` - Docker Compose configurations
- Configuration files

### 📂 Documentation (`docs/`)

#### `docs/deployment/`
Deployment-related documentation:
- `CHECK_SERVICE_STATUS.md` - How to check service status
- `CHECK_STREAMLIT_ON_SERVER.md` - Streamlit server checks
- `CURRENT_DEPLOYMENT_STATUS.md` - Current deployment configuration
- `DEPLOYMENT_CHECKLIST.md` - Deployment checklist
- `RUN_ON_SERVER.md` - Running on server guide
- `TROUBLESHOOTING_DEPLOYMENT.md` - Deployment troubleshooting

#### `docs/status/`
Server status and monitoring documentation:
- `HOW_TO_CHECK_AND_EMAIL_STATUS.md` - Status checking and email reporting
- `HOW_TO_CHECK_INSTANCE_STATUS.md` - Instance status checks
- `INSTANCE_STATUS_DIAGNOSIS.md` - Instance diagnosis guide
- `IP_UPDATE_COMPLETE.md` - IP address update documentation
- `RESOURCE_UPDATE_COMPLETE.md` - Resource update documentation
- `SITE_DOWN_DIAGNOSIS.md` - Site downtime diagnosis

#### `docs/testing/`
Testing documentation and reports:
- `END_TO_END_TEST_FINAL_REPORT.md` - Final E2E test report
- `END_TO_END_TEST_REPORT.md` - E2E test report
- `END_TO_END_TEST_RESULTS.md` - E2E test results
- `FINAL_TEST_REPORT.md` - Final comprehensive test report
- `FIXES_AND_TESTING_COMPLETE.md` - Testing completion summary
- `TESTING_GUIDE.md` - Testing guide

#### `docs/` (Root)
General documentation:
- `DOCLING_COMPLETION_FIX.md` - Docling completion fixes
- `DOCLING_FIXES_SUMMARY.md` - Docling fixes summary
- `DOCLING_PROCESSING_FIX.md` - Docling processing fixes
- `HOW_TO_TEST_AND_SHARE_PERMISSIONS.md` - OpenSearch permissions guide
- Other general documentation files

### 📊 Reports (`reports/`)
Generated reports and JSON files:
- `SERVER_STATUS_REPORT.html` - HTML status report
- `SERVER_STATUS_REPORT.txt` - Text status report
- `e2e_test_report.json` - E2E test results (JSON)
- `opensearch_permissions_report.json` - OpenSearch permissions report

### 📧 Emails (`emails/`)
Email templates and communications:
- `EMAIL_TEMPLATE_SIMPLE.txt` - Simple email template
- `EMAIL_OPENSEARCH_PERMISSIONS_REQUEST.txt` - OpenSearch permissions request
- Other email templates

### 🔧 Scripts (`scripts/`)
Deployment and utility scripts:
- `deploy.sh` - Main deployment script
- `deploy-adaptive.sh` - Adaptive deployment
- `check_and_report_status.sh` - Status reporting
- Other utility scripts

### 🧪 Tests (`tests/`)
Test files and test reports:
- Test Python files
- Test JSON reports

### 📐 Diagrams (`diagrams/`)
Architecture and flow diagrams:
- Mermaid diagram files (.mmd)

## 🎯 Benefits of Organization

1. **Clean Root Directory**: Only essential files in root
2. **Easy Navigation**: Related files grouped together
3. **Better Maintainability**: Clear structure for future development
4. **Professional Structure**: Industry-standard organization
5. **Easy Documentation**: All docs in one place with subcategories

## 📝 File Locations Reference

### Deployment Docs
→ `docs/deployment/`

### Status/Monitoring Docs
→ `docs/status/`

### Testing Docs
→ `docs/testing/`

### Reports
→ `reports/`

### Email Templates
→ `emails/`

---

**Last Updated**: November 28, 2025

