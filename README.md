# ARIS RAG System

Advanced Retrieval-Augmented Generation system with document processing, OCR, and multi-modal search capabilities.

---

## 🚀 Quick Start

### Run Server:
```bash
./scripts/start.sh
```

### Run Tests:
```bash
python3 tests/comprehensive_api_test.py
```

### Deploy Latest Code:
```bash
cd documentation/deployment
cat DEPLOY_COMMANDS.sh
```

---

## 📁 Folder Structure

```
aris/
├── api/              # FastAPI application (main.py, schemas.py, service.py)
├── parsers/          # Document parsers (Docling, PyMuPDF)
├── vectorstores/     # OpenSearch integration
├── rag/              # RAG system core
├── tests/            # All test files (70+ tests)
├── scripts/          # Utility and testing scripts
├── documentation/    # All documentation
│   ├── api-fixes/   # Bug fixes (11 fixes)
│   ├── deployment/  # Deployment packages & guides
│   ├── testing/     # Test results
│   └── guides/      # How-to guides
├── data/             # Extracted data
├── storage/          # Document registry
└── logs/             # Application logs
```

---

## 📦 Latest Deployment Package

**Location:** `documentation/deployment/aris_final_deployment.tar.gz`

**Contains:**
- `api/schemas.py` - Fixed search_mode validation
- `api/main.py` - 9 endpoint fixes
- `api/service.py` - Storage status fix

**Fixes Applied:** 11 total fixes
- ✅ search_mode validation
- ✅ Storage status 500 error
- ✅ Accuracy check 500 error
- ✅ Images summary 422 error
- ✅ All query endpoints improved
- ✅ Better error handling everywhere

---

## 🧪 Testing

### Main Test Suite:
```bash
python3 tests/comprehensive_api_test.py
```

**Expected Results:** 13/14 tests pass (93%)

### Test Results:
See `documentation/testing/test_report_*.json`

---

## 📚 Documentation

### API Fixes:
- `documentation/api-fixes/ALL_ISSUES_FIXED.md` - Complete fix list
- `documentation/api-fixes/FAILING_TEST_ANALYSIS.md` - Test analysis

### Deployment:
- `documentation/deployment/DEPLOYMENT_INSTRUCTIONS.md`
- `documentation/deployment/DEPLOY_COMMANDS.sh`

### Guides:
- `documentation/guides/HOW_TO_*.md` - Various how-to guides
- `documentation/guides/POSTMAN_*.md` - Postman collection guides

---

## 🔧 Configuration

Environment variables in `.env`:
- OpenSearch credentials
- OpenAI API key
- AWS credentials (if using S3)

---

## 🎯 Key Features

- **Multi-Parser Support:** Docling, PyMuPDF, PyPDF2
- **OCR Integration:** Image text extraction
- **Vector Search:** OpenSearch with hybrid search
- **Image Queries:** Search within document images
- **Page-Level Queries:** Get content by page number
- **Accuracy Verification:** OCR quality checking

---

## 📊 API Endpoints

- `POST /query` - General RAG query
- `POST /query/text` - Text-only query
- `POST /query/images` - Image-only query
- `GET /documents/{id}` - Get document metadata
- `GET /documents/{id}/storage/status` - Storage status
- `GET /documents/{id}/pages/{page}` - Page content
- `GET /documents/{id}/images-summary` - Images summary

Full API docs: `http://localhost:8500/docs`

---

## 🐛 Recent Fixes

All 11 API issues fixed:
1. search_mode validation
2. Get document crashes
3. Storage status errors
4. Accuracy check errors
5. Image query improvements
6. Page content diagnostics
7. Re-store text diagnostics
8. Verify endpoint errors
9. Storage status NoneType fix
10. Images summary route fix
11. Parser field safety

---

## 📞 Support

- Documentation: `documentation/`
- Test Reports: `documentation/testing/`
- Guides: `documentation/guides/`

---

**Last Updated:** December 26, 2025
**Status:** All fixes applied, ready for deployment
**Version:** Latest with 11 fixes
