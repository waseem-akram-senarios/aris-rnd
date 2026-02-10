# Comprehensive R&D Test Plan - Client Spanish Documents

## Overview
This document describes the comprehensive testing strategy for achieving the highest accuracy on client Spanish documents located in `docs/testing/clientSpanishDocs/`.

## Test Documents
1. **EM10, degasing.pdf** - Document about degassing procedures
2. **EM11, top seal.pdf** - Document about top seal mechanisms
3. **VUORMAR.pdf** - Company/product documentation (likely contains contact information)

## Test Objectives
1. **Find optimal parameters** for highest accuracy
2. **Test cross-language queries** (English queries on Spanish documents)
3. **Compare parser performance** (Docling, PyMuPDF, OCRmyPDF)
4. **Identify bugs and errors** in the system
5. **Generate recommendations** for production configuration

## Test Strategy

### Phase 1: Document Upload
- Upload each document with 3 different parsers:
  - **PyMuPDF** (fast, text-based)
  - **Docling** (comprehensive, processes all pages)
  - **OCRmyPDF** (high-accuracy OCR for scanned documents)
- Total: 3 documents × 3 parsers = 9 document variants

### Phase 2: Parameter Grid Testing

#### Search Modes
- **Semantic** (pure semantic search)
- **Keyword** (pure keyword search)
- **Hybrid** (combination of both)

#### Semantic Weights (for Hybrid mode)
- 0.1, 0.2, 0.3, 0.4, 0.6 (testing optimal balance)

#### K Values (Number of chunks)
- 20, 30, 40, 50 (testing optimal retrieval depth)

#### Auto-Translate
- Enabled (True)
- Disabled (False)

#### Response Language
- Auto (detect from query)
- Spanish (explicit)
- English (explicit)

#### Agentic RAG
- Enabled (query decomposition)
- Disabled (single query)

### Phase 3: Query Testing

#### Query Types
1. **Contact Information Queries**
   - "Where is the email and contact of Vuormar?"
   - "What is the email address of Vuormar?"
   - Spanish equivalents

2. **Procedure Queries**
   - "How to increase or decrease the levels of air in bag?"
   - "What is the maintenance procedure?"
   - Spanish equivalents

3. **Definition Queries**
   - "What is degassing?"
   - "How does the top seal work?"
   - Spanish equivalents

4. **Specification Queries**
   - "What are the technical specifications?"
   - Spanish equivalents

#### Cross-Language Testing
- **Same-language**: Spanish queries on Spanish documents
- **Cross-language**: English queries on Spanish documents

### Phase 4: Metrics Collection

For each test, we collect:
- **Answer Quality Score** (0-100)
  - Based on keyword matching
  - Answer length and detail
  - Error detection
  - Contact information detection
- **Similarity Scores**
  - Average, maximum, minimum citation similarity
- **Citation Metrics**
  - Number of citations
  - Citation quality
- **Performance Metrics**
  - Response time
  - Processing time

### Phase 5: Analysis

#### Dimensional Analysis
1. **By Parser**: Which parser performs best?
2. **By Query Language**: Same-language vs cross-language performance
3. **By Search Mode**: Semantic vs Keyword vs Hybrid
4. **By Semantic Weight**: Optimal weight for hybrid search
5. **By K Value**: Optimal number of chunks
6. **By Auto-Translate**: Impact of translation
7. **By Response Language**: Impact of explicit language setting

#### Best Configuration Identification
- Top 10 configurations by average quality score
- Cross-language specific recommendations
- Parser-specific recommendations

## Expected Outcomes

### 1. Optimal Parameters
- Best semantic weight for cross-language queries
- Optimal K value for different query types
- Best search mode configuration
- Auto-translate recommendation

### 2. Parser Recommendations
- Best parser for Spanish documents
- Parser-specific parameter tuning
- Parser performance comparison

### 3. Cross-Language Optimization
- Strategies for improving English query accuracy on Spanish docs
- Optimal parameter sets for cross-language queries
- Response language handling recommendations

### 4. Bug Identification
- Any errors in document processing
- Query handling issues
- Citation accuracy problems
- Response quality issues

### 5. Production Configuration
- Recommended default parameters
- Query-type-specific configurations
- Parser selection guidelines

## Test Execution

### Running the Test
```bash
cd /home/senarios/Desktop/aris
python3 tests/test_client_spanish_docs_comprehensive.py
```

### Output Files
- **Test Log**: `tests/client_spanish_docs_test_output.log`
- **Results JSON**: `tests/client_spanish_docs_test_results_YYYYMMDD_HHMMSS.json`

### Test Duration
- **Estimated Time**: 2-4 hours (depending on document size and server performance)
- **Upload Phase**: ~30-60 minutes (9 documents × 3-5 minutes each)
- **Query Phase**: ~1-3 hours (hundreds of queries × 2-5 seconds each)

## Success Criteria

### Accuracy Targets
- **Same-language queries**: >85% quality score
- **Cross-language queries**: >75% quality score
- **Contact information queries**: >90% accuracy
- **Citation similarity**: >60% average

### Performance Targets
- **Response time**: <10 seconds per query
- **Citation count**: 3-10 citations per answer
- **Answer length**: 100-500 characters (depending on query type)

## Next Steps After Testing

1. **Analyze Results**: Review the generated JSON report
2. **Identify Best Config**: Select top-performing configuration
3. **Fix Issues**: Address any bugs or errors found
4. **Update Defaults**: Update system defaults with optimal parameters
5. **Document Findings**: Create recommendations document
6. **Re-test**: Validate fixes with targeted tests

## Notes

- Tests are run against the **production server** (http://44.221.84.58:8500)
- All documents are uploaded fresh for each test run
- Rate limiting is applied to avoid server overload
- Results are saved for later analysis
- Test can be interrupted and resumed (with some data loss)


