# 422 Errors Fixed - Test Script Update

## Issue Summary

During comprehensive testing of Spanish documents, some test configurations encountered **422 (Unprocessable Entity)** errors, preventing the tests from completing successfully.

## Root Cause Analysis

### Schema Validation Constraint

The `QueryRequest` schema in `shared/schemas.py` defines strict validation for the `k` parameter:

```python
k: int = Field(default=6, ge=1, le=20, description="Number of chunks to retrieve")
```

**Constraint**: `k` must be between 1 and 20 (inclusive).

### Test Script Issue

The comprehensive test script (`tests/test_client_spanish_docs_comprehensive.py`) was attempting to use `k` values that exceeded this limit:

- ❌ `k=30` (exceeds max of 20)
- ❌ `k=40` (exceeds max of 20)
- ❌ `k=50` (exceeds max of 20)

These invalid values caused FastAPI's Pydantic validation to reject the requests with 422 errors.

## Fix Applied

### Updated Test Configurations

**File**: `tests/test_client_spanish_docs_comprehensive.py`

**Changes**:
- Replaced all `k` values > 20 with valid values (10, 15, 20)
- Updated all test configurations to comply with schema validation
- Maintained comprehensive test coverage with valid parameter combinations

**Before**:
```python
TestConfig("pymupdf", "hybrid", 0.2, 30, True, 0.1, None, False),  # ❌ Invalid
TestConfig("pymupdf", "hybrid", 0.2, 40, True, 0.1, None, False),  # ❌ Invalid
TestConfig("pymupdf", "hybrid", 0.2, 50, True, 0.1, None, False),  # ❌ Invalid
```

**After**:
```python
TestConfig("pymupdf", "hybrid", 0.2, 10, True, 0.1, None, False),  # ✅ Valid
TestConfig("pymupdf", "hybrid", 0.2, 15, True, 0.1, None, False),  # ✅ Valid
TestConfig("pymupdf", "hybrid", 0.2, 20, True, 0.1, None, False),  # ✅ Valid
```

### Updated Test Configurations Summary

All test configurations now use valid `k` values:
- **k=10**: Lower chunk count for focused queries
- **k=15**: Medium chunk count
- **k=20**: Maximum allowed chunk count (optimal for comprehensive retrieval)

## Impact

### ✅ **Resolved Issues**

1. **422 Errors**: All test configurations now pass schema validation
2. **Test Completeness**: Comprehensive tests can now run without validation errors
3. **Parameter Coverage**: Still maintains comprehensive parameter grid testing with valid values

### 📊 **Test Coverage Maintained**

The fix maintains comprehensive testing across:
- ✅ Multiple parsers (PyMuPDF, Docling, OCRmyPDF)
- ✅ Different search modes (semantic, keyword, hybrid)
- ✅ Various semantic weights (0.1, 0.2, 0.3, 0.4)
- ✅ Valid k values (10, 15, 20)
- ✅ Auto-translate variations
- ✅ Response language variations
- ✅ Agentic RAG testing

## Validation

### Schema Compliance

All test configurations now comply with:
- ✅ `k: ge=1, le=20` (1 ≤ k ≤ 20)
- ✅ `semantic_weight: ge=0.0, le=1.0` (0.0 ≤ sw ≤ 1.0)
- ✅ `temperature: ge=0.0, le=2.0` (0.0 ≤ temp ≤ 2.0)
- ✅ `search_mode: Literal['semantic', 'keyword', 'hybrid']`

### Expected Behavior

With these fixes:
1. ✅ All API requests will pass Pydantic validation
2. ✅ No more 422 errors during comprehensive testing
3. ✅ Tests can complete successfully and generate results
4. ✅ Parameter optimization can proceed with valid configurations

## Related Issues

### Citation Issues (Separate Investigation)

While fixing the 422 errors, the following citation-related issues were identified and require separate investigation:

1. **Page Number Accuracy**: Answer on page 4, but citation shows different page
2. **Citation Language Mismatch**: Spanish text in citations for English queries
3. **Missing Content**: Missing section about solvents
4. **Terminology**: "Residues" vs "deposits" terminology issue

These will be addressed in a follow-up investigation focusing on citation accuracy improvements.

## Next Steps

1. ✅ **422 Errors Fixed**: Test script updated and ready for comprehensive testing
2. 🔄 **Run Comprehensive Tests**: Execute updated test script to validate all configurations
3. 📊 **Analyze Results**: Generate comprehensive analysis with valid parameter combinations
4. 🔍 **Investigate Citation Issues**: Address page number and language mismatch issues separately

## Files Modified

1. `tests/test_client_spanish_docs_comprehensive.py`
   - Updated all test configurations to use valid `k` values (max 20)
   - Added comment explaining schema constraint

2. `SPANISH_DOCS_TEST_RESULTS.md`
   - Updated "Issues Identified" section with fix details
   - Documented citation issues for follow-up investigation

---

**Status**: ✅ **FIXED** - Ready for comprehensive testing
**Date**: 2026-01-14

