# ARIS R&D - Metrics & Analytics Guide

## Overview

The ARIS R&D RAG system includes a comprehensive metrics and analytics system designed for research and development purposes. This system tracks all aspects of document processing, querying, costs, and performance.

## Metrics Collected

### 1. Document Processing Metrics

**Per-Document Tracking:**
- File name, size, and type
- Parser used (PyMuPDF, Docling, Textract)
- Number of pages processed
- Chunks created
- Tokens extracted
- Extraction percentage (text extraction quality)
- Confidence score
- Processing time breakdown (parsing, chunking, embedding)
- Success/failure status
- Image detection flag

**Aggregated Statistics:**
- Total documents processed
- Success rate
- Average processing time
- Average tokens per document
- Average chunks per document
- Average extraction percentage
- Average confidence

### 2. Query Performance Metrics

**Per-Query Tracking:**
- Question text
- Answer length
- Response time
- Number of chunks used
- Number of sources referenced
- API used (OpenAI or Cerebras)
- Success/failure status
- Timestamp

**Aggregated Statistics:**
- Total queries
- Query success rate
- Average response time
- Average answer length
- Average chunks per query
- API usage distribution

### 3. Cost Analytics

**Cost Breakdown:**
- Embedding costs (based on tokens processed)
- Query costs (estimated based on API usage)
- Total cost
- Cost per document
- Cost per query

**Cost Calculation:**
- Embedding: `text-embedding-3-small` at $0.02 per 1M tokens
- Query: GPT-3.5-turbo estimated at ~$0.0015 per 1K tokens

### 4. Parser Performance Comparison

**Parser Statistics:**
- Usage count per parser
- Success rate per parser
- Average processing time per parser
- Average tokens per document per parser
- Average chunks per document per parser
- Average confidence per parser
- Average extraction percentage per parser

### 5. File Type Statistics

**Per File Type:**
- Count of files processed
- Total file size
- Total processing time
- Total tokens extracted

### 6. Quality Metrics

**Extraction Quality:**
- Average extraction percentage across all documents
- Average confidence score
- Average chunks per document
- Average tokens per document

### 7. System Health

**Error Tracking:**
- Total errors
- Processing errors
- Query errors
- Error details with timestamps

## Using the Metrics Dashboard

### Accessing Metrics

1. **In Streamlit UI:**
   - Metrics are displayed in the sidebar under "📊 R&D Metrics & Analytics"
   - Metrics update in real-time as documents are processed and queries are made

2. **Sections:**
   - **Overview**: Basic counts (documents, chunks, tokens, queries)
   - **Performance**: Processing and response times, success rates
   - **Cost Analysis**: Cost breakdown and per-document costs
   - **Parser Performance**: Comparison table of all parsers
   - **Quality Metrics**: Extraction quality and confidence scores
   - **Query Analytics**: Query performance and API usage
   - **File Type Statistics**: Statistics grouped by file type
   - **Error Summary**: Error counts and types

### Exporting Metrics

1. **JSON Export:**
   - Click "Download Metrics (JSON)" button in the metrics dashboard
   - Exports all metrics in JSON format for analysis
   - Includes:
     - All processing metrics (per document)
     - All query metrics (per query)
     - Aggregated summary statistics

2. **Data Format:**
   ```json
   {
     "processing_metrics": [...],
     "query_metrics": [...],
     "summary": {
       "processing": {...},
       "queries": {...},
       "costs": {...},
       "parser_comparison": {...},
       "performance_trends": {...},
       "error_summary": {...}
     }
   }
   ```

## Programmatic Access

### Using MetricsCollector

```python
from metrics.metrics_collector import MetricsCollector

# Initialize collector
collector = MetricsCollector()

# Record processing
collector.record_processing(
    document_name="document.pdf",
    file_size=1024000,
    file_type="pdf",
    parser_used="pymupdf",
    pages=10,
    chunks_created=25,
    tokens_extracted=5000,
    extraction_percentage=95.5,
    confidence=0.98,
    processing_time=2.5,
    success=True
)

# Record query
collector.record_query(
    question="What is the main topic?",
    answer_length=500,
    response_time=1.2,
    chunks_used=6,
    sources_count=2,
    api_used="openai",
    success=True
)

# Get all metrics
all_metrics = collector.get_all_metrics()

# Get specific statistics
processing_stats = collector.get_processing_stats()
query_stats = collector.get_query_stats()
cost_analysis = collector.get_cost_analysis()
parser_comparison = collector.get_parser_comparison()
```

## Integration with RAG System

The metrics collector is automatically integrated into the RAG system:

1. **Initialization:**
   ```python
   from metrics.metrics_collector import MetricsCollector
   from rag_system import RAGSystem
   
   collector = MetricsCollector()
   rag = RAGSystem(use_cerebras=False, metrics_collector=collector)
   ```

2. **Automatic Tracking:**
   - Document processing is automatically tracked when using `DocumentProcessor`
   - Queries are automatically tracked when using `query_with_rag()`

3. **Session Persistence:**
   - Metrics persist across API switches (OpenAI ↔ Cerebras)
   - Metrics are cleared when "Clear All" is clicked

## Metrics Use Cases

### 1. Parser Selection Optimization
- Compare parser performance to choose the best parser for specific document types
- Identify which parsers work best for different file types

### 2. Cost Optimization
- Track embedding and query costs
- Identify cost-efficient document processing strategies
- Monitor cost per document and per query

### 3. Performance Tuning
- Identify bottlenecks in processing pipeline
- Compare processing times across parsers
- Optimize chunking and embedding strategies

### 4. Quality Assurance
- Monitor extraction quality and confidence scores
- Identify documents with low extraction rates
- Track success rates and error patterns

### 5. Research & Development
- Analyze query patterns and answer quality
- Compare API performance (OpenAI vs Cerebras)
- Track system improvements over time

## Best Practices

1. **Regular Export:**
   - Export metrics periodically for analysis
   - Keep historical metrics for trend analysis

2. **Monitor Key Metrics:**
   - Success rates (should be >95%)
   - Average processing time (should be reasonable)
   - Cost per document (should be minimal)
   - Extraction percentage (should be >80% for text PDFs)

3. **Parser Selection:**
   - Use parser comparison metrics to choose optimal parsers
   - Monitor parser-specific success rates

4. **Error Analysis:**
   - Review error summaries regularly
   - Investigate failed document processing
   - Track query errors and API issues

## Technical Details

### Metrics Storage
- Metrics are stored in memory (session state)
- Metrics persist during the Streamlit session
- Metrics are cleared when "Clear All" is clicked

### Performance Impact
- Minimal overhead (<1ms per metric recording)
- Metrics collection is non-blocking
- No impact on document processing or query performance

### Data Structure
- Metrics use dataclasses for type safety
- Aggregated statistics calculated on-demand
- JSON export for external analysis

## Future Enhancements

Potential future additions:
- Persistent metrics storage (database/file)
- Time-series analysis and trends
- Visualization charts and graphs
- Alert system for anomalies
- Metrics comparison across sessions
- Advanced cost prediction models


