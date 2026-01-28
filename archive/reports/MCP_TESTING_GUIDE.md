# 🧪 MCP Server Testing Guide

## ✅ Git Status: CODE COMMITTED BUT NOT PUSHED

Your latest code is **committed locally** but couldn't be pushed due to authentication issues. The commit contains all accuracy improvements.

### To Push to Git (when ready):
```bash
# Check if you need to set up authentication
git remote -v  # Check remote URL
git push origin main
```

## 🧪 Testing Your Accuracy-Optimized MCP Server

### 1. **Basic Connectivity Test**
```bash
# Test if server is running
curl -s 'http://44.221.84.58:8503/sse' -H 'Accept: text/event-stream' --max-time 2
# Should return: event: endpoint\ndata: /messages/?session_id=...
```

### 2. **Local Import Test**
```bash
cd /home/senarios/Desktop/aris
python3 -c "from mcp_server import mcp; print('✅ Imported:', mcp.name); print('Tools:', list(mcp._tool_manager._tools.keys()))"
```

### 3. **Integration Test - Add a Document**
```bash
# Test rag_ingest with sample text
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server import rag_ingest

result = rag_ingest(
    content='This is a test document about machine maintenance procedures. Regular maintenance includes checking oil levels, cleaning filters, and inspecting belts.',
    metadata={'domain': 'maintenance', 'language': 'en', 'source': 'test_manual'}
)
print('✅ Ingest Result:', result['success'])
print('Document ID:', result.get('document_id'))
print('Chunks created:', result.get('chunks_created'))
"
```

### 4. **Integration Test - Search Documents**
```bash
# Test rag_search with different accuracy features
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server import rag_search

# Test 1: Simple search
print('=== TEST 1: Simple Search ===')
result = rag_search('machine maintenance', k=3)
print('✅ Found', result['total_results'], 'results')

# Test 2: Complex question with Agentic RAG
print('\n=== TEST 2: Complex Question (Agentic RAG) ===')
result = rag_search(
    'What are the steps for machine maintenance?',
    k=5,
    use_agentic_rag=True,
    include_answer=True
)
print('✅ Answer generated:', len(result.get('answer', '')) > 0)
print('Accuracy info:', result.get('accuracy_info', {}).get('agentic_rag_enabled'))

# Test 3: Filtered search
print('\n=== TEST 3: Filtered Search ===')
result = rag_search(
    'maintenance',
    filters={'domain': 'maintenance'},
    k=2
)
print('✅ Filtered results:', result['total_results'])
"
```

### 5. **Accuracy Benchmark Test**
```bash
# Test with known content to verify accuracy
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server import rag_ingest, rag_search

# First, ingest test content
print('📝 Ingesting test document...')
ingest_result = rag_ingest(
    content='The ERROR-4042 indicates a hydraulic pressure failure. To fix: 1) Check pressure sensor, 2) Replace faulty valve, 3) Reset system.',
    metadata={'domain': 'troubleshooting', 'source': 'error_codes.pdf', 'language': 'en'}
)

if ingest_result['success']:
    print('✅ Document ingested successfully')
    doc_id = ingest_result['document_id']
    
    # Now search for specific error
    print('\n🔍 Searching for ERROR-4042...')
    search_result = rag_search('ERROR-4042', k=3, search_mode='keyword')
    
    if search_result['total_results'] > 0:
        top_result = search_result['results'][0]
        confidence = top_result.get('confidence', 0)
        print(f'✅ Found result with {confidence}% confidence')
        print(f'Content preview: {top_result[\"snippet\"][:100]}...')
        
        # Check if answer generation works
        search_with_answer = rag_search('How do I fix ERROR-4042?', k=3, include_answer=True)
        if search_with_answer.get('answer'):
            print('✅ Answer generation working')
            print(f'Answer: {search_with_answer[\"answer\"][:150]}...')
        else:
            print('⚠️  Answer generation may need tuning')
    else:
        print('❌ No results found - check ingestion')
else:
    print('❌ Ingestion failed:', ingest_result.get('message'))
"
```

### 6. **Cross-Language Test**
```bash
# Test multilingual capabilities
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server import rag_ingest, rag_search

# Ingest Spanish content
print('🌍 Testing multilingual support...')
ingest_result = rag_ingest(
    content='El mantenimiento preventivo incluye: inspección visual, limpieza de filtros, y verificación de niveles de aceite.',
    metadata={'language': 'es', 'domain': 'maintenance'}
)

if ingest_result['success']:
    # Search in Spanish
    result = rag_search('mantenimiento preventivo', k=3)
    print('✅ Found', result['total_results'], 'Spanish results')
    
    # Search in English (should auto-translate)
    result_en = rag_search('preventive maintenance', k=3)
    print('✅ Found', result_en['total_results'], 'English search results')
else:
    print('❌ Multilingual test failed')
"
```

### 7. **Performance Test**
```bash
# Test response times
python3 -c "
import time
import sys
sys.path.insert(0, '.')
from mcp_server import rag_search

queries = [
    'maintenance procedures',
    'What are the safety requirements?',
    'How do I troubleshoot ERROR-4042?',
    'Compare different machine models'
]

print('⏱️  Performance Test Results:')
for query in queries:
    start_time = time.time()
    try:
        result = rag_search(query, k=5)
        elapsed = time.time() - start_time
        print(f'✅ \"{query[:30]}...\": {elapsed:.2f}s ({result[\"total_results\"]} results)')
    except Exception as e:
        elapsed = time.time() - start_time
        print(f'❌ \"{query[:30]}...\": {elapsed:.2f}s (ERROR: {str(e)[:50]})')
"
```

### 8. **Load Test**
```bash
# Test multiple concurrent requests
python3 -c "
import concurrent.futures
import sys
sys.path.insert(0, '.')
from mcp_server import rag_search

def test_query(query):
    try:
        result = rag_search(query, k=3)
        return f'✅ {query}: {result[\"total_results\"]} results'
    except Exception as e:
        return f'❌ {query}: {str(e)[:50]}'

queries = [
    'maintenance',
    'safety procedures',
    'error codes',
    'troubleshooting guide',
    'machine specifications'
]

print('🔄 Load Test (5 concurrent queries):')
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(test_query, queries))

for result in results:
    print(result)
"
```

## 📊 Accuracy Metrics to Monitor

After running tests, check these metrics:

1. **Retrieval Quality**
   - Confidence scores should be > 70% for good matches
   - Top result should be relevant to query

2. **Answer Quality**
   - Answers should include citations [Source 1], [Source 2]
   - Complex questions should use Agentic RAG (check `sub_queries_generated`)

3. **Performance**
   - Simple queries: < 2 seconds
   - Complex queries with Agentic RAG: < 5 seconds
   - Concurrent requests: All should succeed

## 🚨 Troubleshooting

### If tests fail:

1. **"Cannot connect to remote MCP server"**
   ```bash
   # Check if container is running
   ssh ec2-user@44.221.84.58 'docker ps | grep mcp'
   
   # Check logs
   ssh ec2-user@44.221.84.58 'docker logs aris-mcp'
   ```

2. **"Import error"**
   ```bash
   # Check if all dependencies are installed
   pip list | grep fastmcp
   ```

3. **"No results found"**
   ```bash
   # Check if documents are indexed
   curl 'http://44.221.84.58:8501/health'
   ```

4. **"Low confidence scores"**
   - Check if reranking is enabled in settings
   - Verify OpenSearch is accessible
   - Check if documents were properly chunked

## 🎯 Next Steps

1. Run the basic connectivity test
2. Run the integration test with sample data
3. Test accuracy with known content
4. Monitor performance metrics
5. Push code to git when authentication is resolved

Your MCP server is now **accuracy-optimized** with:
- ✅ Agentic RAG for complex questions
- ✅ Confidence scoring
- ✅ Auto-translation
- ✅ Hybrid search with reranking
- ✅ Comprehensive error handling
