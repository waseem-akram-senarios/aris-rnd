#!/bin/bash

# Benchmark Test with FL10.11 SPECIFIC8 (1).pdf
# Comprehensive end-to-end test using the benchmark document

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

SERVER_IP="${SERVER_IP:-35.175.133.235}"
SERVER_USER="${SERVER_USER:-ec2-user}"
SERVER_DIR="${SERVER_DIR:-/opt/aris-rag}"
PEM_FILE="$PROJECT_ROOT/scripts/ec2_wah_pk.pem"
BENCHMARK_FILE="FL10.11 SPECIFIC8 (1).pdf"

echo "╔════════════════════════════════════════════════════════╗"
echo "║  Benchmark Test: FL10.11 SPECIFIC8 (1).pdf            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check PEM file
if [ ! -f "$PEM_FILE" ]; then
    echo "❌ PEM file not found: $PEM_FILE"
    exit 1
fi

echo "📄 Benchmark Document: $BENCHMARK_FILE"
echo "🌐 Server: $SERVER_IP"
echo ""

# Run benchmark tests on server
ssh -i "$PEM_FILE" -o StrictHostKeyChecking=no "$SERVER_USER@$SERVER_IP" <<EOF
cd $SERVER_DIR

echo "╔════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK TEST: Document Processing                   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# Check if benchmark file exists
BENCHMARK_FILE="samples/$BENCHMARK_FILE"
if [ ! -f "\$BENCHMARK_FILE" ]; then
    echo "❌ Benchmark file not found: \$BENCHMARK_FILE"
    echo "Available files in samples/:"
    ls -lh samples/*.pdf 2>/dev/null | head -5
    exit 1
fi

FILE_SIZE=\$(du -h "\$BENCHMARK_FILE" | cut -f1)
echo "📄 File: \$BENCHMARK_FILE"
echo "📊 Size: \$FILE_SIZE"
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST 1: PyMuPDF Parser                               ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

sudo docker exec aris-rag-app python -c "
import sys
import time
sys.path.insert(0, '/app')
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector

try:
    # Initialize RAG system
    metrics = MetricsCollector()
    rag = RAGSystem(
        use_cerebras=False,
        metrics_collector=metrics,
        embedding_model='text-embedding-3-small',
        openai_model='gpt-3.5-turbo',
        vector_store_type='faiss',
        chunk_size=384,
        chunk_overlap=75
    )
    
    # Process benchmark document
    test_file = '/app/samples/$BENCHMARK_FILE'
    processor = DocumentProcessor(rag)
    
    with open(test_file, 'rb') as f:
        file_content = f.read()
    
    print('   Processing with PyMuPDF parser...')
    start = time.time()
    result = processor.process_document(
        file_path=test_file,
        file_content=file_content,
        file_name='$BENCHMARK_FILE',
        parser_preference='pymupdf'
    )
    process_time = time.time() - start
    
    if result and result.status == 'success':
        print(f'   ✅ Processing successful: {process_time:.2f}s')
        print(f'   ✅ Parser: {result.parser_used}')
        print(f'   ✅ Chunks created: {result.chunks_created}')
        print(f'   ✅ Extraction: {result.extraction_percentage:.1f}%')
        print(f'   ✅ Tokens extracted: {result.tokens_extracted:,}')
        
        # Test vector store
        if rag.vectorstore:
            chunks = rag.vectorstore.similarity_search('test', k=1000)
            print(f'   ✅ Vector store: {len(chunks)} chunks stored')
            
            # Test queries
            queries = [
                'What is this document about?',
                'What are the specifications?',
                'What are the key features?'
            ]
            
            print('')
            print('   Testing queries...')
            for query in queries:
                query_result = rag.query_with_rag(query, k=3)
                if query_result and query_result.get('answer'):
                    answer_len = len(query_result.get('answer', ''))
                    sources = len(query_result.get('sources', []))
                    print(f'   ✅ Query: \"{query[:40]}...\" - Answer: {answer_len} chars, {sources} sources')
                else:
                    print(f'   ⚠️  Query: \"{query[:40]}...\" - No answer')
        else:
            print('   ❌ Vector store not initialized')
    else:
        print(f'   ❌ Processing failed: {result.error if result else \"Unknown error\"}')
except Exception as e:
    print(f'   ❌ Test failed: {str(e)[:200]}')
" 2>/dev/null
echo ""

echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST 2: Different Chunking Strategies                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

for strategy in "precise" "balanced" "comprehensive"; do
    echo "Testing $strategy strategy..."
    sudo docker exec aris-rag-app python -c "
import sys
import time
sys.path.insert(0, '/app')
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector
from utils.chunking_strategies import get_chunking_params

try:
    chunk_size, chunk_overlap = get_chunking_params('$strategy')
    
    metrics = MetricsCollector()
    rag = RAGSystem(
        use_cerebras=False,
        metrics_collector=metrics,
        embedding_model='text-embedding-3-small',
        openai_model='gpt-3.5-turbo',
        vector_store_type='faiss',
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    test_file = '/app/samples/$BENCHMARK_FILE'
    processor = DocumentProcessor(rag)
    
    with open(test_file, 'rb') as f:
        file_content = f.read()
    
    start = time.time()
    result = processor.process_document(
        file_path=test_file,
        file_content=file_content,
        file_name='$BENCHMARK_FILE',
        parser_preference='pymupdf'
    )
    process_time = time.time() - start
    
    if result and result.status == 'success':
        print(f'   ✅ $strategy: {result.chunks_created} chunks in {process_time:.2f}s')
    else:
        print(f'   ❌ $strategy: Failed')
except Exception as e:
    print(f'   ❌ $strategy: {str(e)[:50]}')
" 2>/dev/null
    echo ""
done

echo "╔════════════════════════════════════════════════════════╗"
echo "║  TEST 3: Different Embedding Models                   ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

for embedding in "text-embedding-3-small" "text-embedding-3-large"; do
    echo "Testing $embedding..."
    sudo docker exec aris-rag-app python -c "
import sys
import time
sys.path.insert(0, '/app')
from rag_system import RAGSystem
from ingestion.document_processor import DocumentProcessor
from metrics.metrics_collector import MetricsCollector

try:
    metrics = MetricsCollector()
    rag = RAGSystem(
        use_cerebras=False,
        metrics_collector=metrics,
        embedding_model='$embedding',
        openai_model='gpt-3.5-turbo',
        vector_store_type='faiss',
        chunk_size=384,
        chunk_overlap=75
    )
    
    test_file = '/app/samples/$BENCHMARK_FILE'
    processor = DocumentProcessor(rag)
    
    with open(test_file, 'rb') as f:
        file_content = f.read()
    
    start = time.time()
    result = processor.process_document(
        file_path=test_file,
        file_content=file_content,
        file_name='$BENCHMARK_FILE',
        parser_preference='pymupdf'
    )
    process_time = time.time() - start
    
    if result and result.status == 'success':
        print(f'   ✅ $embedding: {result.chunks_created} chunks in {process_time:.2f}s')
    else:
        print(f'   ❌ $embedding: Failed')
except Exception as e:
    print(f'   ❌ $embedding: {str(e)[:50]}')
" 2>/dev/null
    echo ""
done

echo "╔════════════════════════════════════════════════════════╗"
echo "║  BENCHMARK TEST SUMMARY                                ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""
echo "✅ Benchmark document: $BENCHMARK_FILE"
echo "✅ All tests completed"
echo ""
echo "🌐 Test on web interface: http://\$(curl -s ifconfig.me)/"
echo ""

EOF

echo ""
echo "📊 Benchmark Test Summary:"
echo "   ✅ Document: $BENCHMARK_FILE"
echo "   ✅ Tests executed on server"
echo ""
echo "🌐 Application: http://$SERVER_IP/"
echo ""






