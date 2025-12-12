# Project Organization

This document describes the organization of the ARIS RAG project folder structure.

## Root Directory

The root directory contains only essential project files:

- **Core Application Files:**
  - `app.py` - Streamlit main application
- `rag_system.py` - RAG system core
  - `start.sh` - Startup script
  - `Dockerfile` - Docker configuration
  - `docker-compose.yml` - Docker Compose configuration

- **Configuration:**
  - `pytest.ini` - Pytest configuration
  - `.env` - Environment variables (not in git)

## Documentation Structure

### `docs/` - Main Documentation
- Guides and how-to documents
- API documentation
- Feature documentation
- Setup instructions

### `docs/status/` - Status & Test Results
- `DEPLOYMENT_STATUS.md` - Current deployment status
- `SERVER_SPECS.md` - Server specifications
- `FASTAPI_ACCESS.md` - FastAPI access information
- `TEST_RESULTS.md` - Test results
- `FINAL_TEST_RESULTS.md` - Final test results

### `docs/implementation/` - Implementation Summaries
- `IMPLEMENTATION_SUMMARY.md` - Overall implementation summary
- `LOGGING_IMPLEMENTATION.md` - Logging implementation details
- `SYNCHRONIZATION_IMPLEMENTATION.md` - Sync implementation
- `GITHUB_ACTIONS_FIX_SUMMARY.md` - GitHub Actions fixes
- `RESOURCE_OPTIMIZATION.md` - Resource optimization details

### `docs/deployment/` - Deployment Documentation
- Deployment guides and procedures
- Server setup instructions
- Configuration details

### `docs/testing/` - Testing Documentation
- Test procedures and results
- Testing guides

## Code Structure

### `api/` - FastAPI Application
- REST API endpoints
- Service layer
- Schemas

### `config/` - Configuration
- Settings
- Requirements

### `ingestion/` - Document Processing
- Document processor
- Processing logic

### `parsers/` - Document Parsers
- PDF parsers (PyMuPDF, Docling, Textract)
- Parser factory
- Base parser classes

### `vectorstores/` - Vector Store Implementations
- FAISS implementation
- OpenSearch implementation
- Vector store factory

### `metrics/` - Metrics Collection
- Metrics collector
- Analytics

### `storage/` - Storage Layer
- Document registry
- Storage utilities

### `utils/` - Utilities
- Helper functions
- Token counting
- Text splitting

## Scripts

### `scripts/` - Utility Scripts
- Deployment scripts
- Setup scripts
- Log viewing scripts
- Server management scripts

## Tests

### `tests/` - Test Suite
- Unit tests
- Integration tests
- Test utilities

## Other Directories

- `logs/` - Application logs
- `reports/` - Test reports and analysis
- `samples/` - Sample documents
- `diagrams/` - Architecture diagrams
- `emails/` - Email templates
- `nginx/` - Nginx configuration
- `venv/` - Python virtual environment (not in git)

## File Naming Conventions

- **Documentation:** `UPPERCASE_WITH_UNDERSCORES.md`
- **Scripts:** `lowercase_with_underscores.sh` or `.py`
- **Code:** `snake_case.py`
- **Tests:** `test_*.py`

## Quick Reference

| Category | Location |
|----------|----------|
| Status & Test Results | `docs/status/` |
| Implementation Details | `docs/implementation/` |
| Deployment Guides | `docs/deployment/` |
| Utility Scripts | `scripts/` |
| Application Code | Root + `api/`, `ingestion/`, etc. |
| Tests | `tests/` |
| Logs | `logs/` |

---

**Last Updated:** December 4, 2025
