# Comprehensive Testing Framework

This directory contains a complete testing framework covering all 10 testing types for the ARIS RAG system.

## Test Organization

```
tests/
├── unit/              # Unit tests (isolated function/method tests)
├── integration/       # Integration tests (module interactions)
├── functional/       # Functional tests (feature requirements)
├── api/              # API endpoint tests
├── regression/       # Regression tests (ensure old features work)
├── smoke/            # Smoke tests (basic build verification)
├── sanity/           # Sanity tests (quick checks after fixes)
├── performance/      # Performance tests (speed, load, scalability)
├── security/         # Security tests (vulnerability testing)
├── e2e/              # End-to-end tests (full user workflows)
├── fixtures/         # Shared test fixtures
└── utils/            # Test utilities
```

## Running Tests

### Run All Tests
```bash
python tests/run_all_tests_comprehensive.py
```

### Run by Type
```bash
# Unit tests
pytest tests/unit/ -m unit -v

# Integration tests
pytest tests/integration/ -m integration -v

# API tests
pytest tests/api/ -m api -v

# Performance tests
pytest tests/performance/ -m performance -v

# Security tests
pytest tests/security/ -m security -v

# E2E tests
pytest tests/e2e/ -m e2e -v
```

### Quick Tests (Smoke + Sanity + Unit)
```bash
python tests/run_quick_tests.py
```

### With Coverage
```bash
python tests/run_tests_with_coverage.py
```

### Performance Benchmarks
```bash
python tests/run_performance_tests.py
```

## Test Markers

Tests are organized using pytest markers:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.functional` - Functional tests
- `@pytest.mark.api` - API tests
- `@pytest.mark.regression` - Regression tests
- `@pytest.mark.smoke` - Smoke tests
- `@pytest.mark.sanity` - Sanity tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.security` - Security tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow running tests

## Test Coverage Goals

- **Unit Tests**: 80%+ coverage for core modules
- **Integration Tests**: All major workflows covered
- **API Tests**: 100% endpoint coverage
- **E2E Tests**: All critical user journeys

## Reports

Test reports are generated in `reports/`:
- `test_results.json` - Test execution results
- `coverage.json` - Code coverage data
- `benchmark_results.json` - Performance benchmarks
- `junit_*.xml` - JUnit XML reports for CI/CD

## CI/CD Integration

GitHub Actions workflow is configured in `.github/workflows/tests.yml`:
- Runs on push/PR to main/develop
- Tests on Python 3.9, 3.10, 3.11
- Generates coverage reports
- Uploads to Codecov

## Test Fixtures

Common fixtures are available in `tests/fixtures/conftest.py`:
- `service_container` - Service container with FAISS
- `api_client` - FastAPI test client
- `mock_embeddings` - Mock OpenAI embeddings
- `sample_documents` - Sample document texts
- `temp_dir` - Temporary directory for test files

## Writing New Tests

1. Place test file in appropriate directory (`tests/unit/`, `tests/integration/`, etc.)
2. Use appropriate marker: `@pytest.mark.unit`, etc.
3. Use fixtures from `conftest.py`
4. Follow naming convention: `test_*.py`
5. Use assertions from `tests/utils/assertions.py`

## Example Test

```python
import pytest
from tests.utils.assertions import assert_response_status

@pytest.mark.api
def test_example(api_client):
    response = api_client.get("/health")
    assert_response_status(response, 200)
    assert response.json()["status"] == "healthy"
```
