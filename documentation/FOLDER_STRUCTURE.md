# ARIS RAG System - Organized Folder Structure

## 📁 Root Directory Structure

```
aris/
├── api/                          # FastAPI application code
├── config/                       # Configuration files
├── parsers/                      # Document parsers (PyMuPDF, Docling, etc.)
├── rag/                          # RAG system core
├── vectorstores/                 # Vector store implementations
├── utils/                        # Utility functions
├── ingestion/                    # Document ingestion pipeline
├── tests/                        # All test files
├── documentation/                # All documentation (NEW - ORGANIZED)
│   ├── api-fixes/               # API bug fixes documentation
│   ├── deployment/              # Deployment guides and packages
│   ├── testing/                 # Test results and reports
│   └── guides/                  # How-to guides and tutorials
├── temp-archive/                # Old/duplicate files (can be deleted)
├── storage/                     # Document registry and metadata
├── logs/                        # Application logs
├── scripts/                     # Utility scripts
└── samples/                     # Sample documents
```

---

## 📂 Documentation Folder (Organized)

### `documentation/api-fixes/`
- `ALL_ISSUES_FIXED.md` - Complete list of all fixes
- `API_FIXES_PRIORITY_PLAN.md` - Original fix prioritization
- `COMPREHENSIVE_FIXES_SUMMARY.md` - Detailed fix documentation
- `FAILING_TEST_ANALYSIS.md` - Analysis of failing tests
- `FIXES_APPLIED.md` - Applied fixes summary
- `QUERY_ENDPOINTS_FIX_SUMMARY.md` - Query endpoint fixes

### `documentation/deployment/`
- `aris_final_deployment.tar.gz` - **LATEST deployment package**
- `DEPLOYMENT_INSTRUCTIONS.md` - How to deploy
- `DEPLOY_AND_TEST_RESULTS.md` - Deployment test results
- `DEPLOY_COMMANDS.sh` - Deployment commands
- `MANUAL_DEPLOYMENT_STEPS.md` - Step-by-step deployment
- `COMPLETE_SOLUTION.md` - Complete solution overview

### `documentation/testing/`
- `test_report_20251226_160657.json` - Latest test results
- `TEST_RESULTS_BEFORE_DEPLOYMENT.md` - Baseline test results
- `AUTOMATED_TEST_REPORT.md` - Automated test reports
- `COMPREHENSIVE_TEST_REPORT.md` - Comprehensive testing
- `E2E_TEST_RESULTS.md` - End-to-end test results

### `documentation/guides/`
- `HOW_TO_*.md` - Various how-to guides
- `POSTMAN_*.md` - Postman collection guides
- `OCR_*.md` - OCR accuracy testing guides
- `QUICK_*.md` - Quick reference guides
- `PAGE_QUERY_ENDPOINT_GUIDE.md` - Page query endpoint usage
- `GET_ALL_IMAGES_ENDPOINT_GUIDE.md` - Image endpoint usage

---

## 🧪 Tests Folder

### `tests/`
- `comprehensive_api_test.py` - **Main comprehensive test suite**
- `test_all.py` - All endpoint tests
- `test_image_*.py` - Image-related tests
- `test_ocr_*.py` - OCR accuracy tests
- `test_server_*.py` - Server integration tests
- Other specialized test files

---

## 📦 Temp Archive (Can be Deleted)

The `temp-archive/` folder contains:
- Old test results (JSON, log files)
- Duplicate documentation
- Old CURL command files
- Deprecated reports

**These can be safely deleted after reviewing.**

---

## 🎯 Quick Access

### To Deploy Latest Code:
```bash
cd /home/senarios/Desktop/aris/documentation/deployment
cat DEPLOY_COMMANDS.sh
```

### To Run Comprehensive Tests:
```bash
cd /home/senarios/Desktop/aris
python3 tests/comprehensive_api_test.py
```

### To View Latest Fixes:
```bash
cat documentation/api-fixes/ALL_ISSUES_FIXED.md
```

### To View Test Results:
```bash
cat documentation/testing/TEST_RESULTS_BEFORE_DEPLOYMENT.md
```

---

## 🗑️ Cleanup Recommendations

1. **Delete temp-archive/** - Contains old/duplicate files
2. **Review extracted_image_info/** - May contain old extraction data
3. **Clean logs/** - Old log files can be archived

---

## ✅ What's Organized

- ✅ All API fixes documentation in one place
- ✅ All deployment files and packages together
- ✅ All test results and reports organized
- ✅ All guides and tutorials in guides folder
- ✅ Main test suite moved to tests folder
- ✅ Old files archived in temp-archive

---

**Last Updated:** December 26, 2025, 4:45 PM
**Status:** Folder organized and cleaned up
