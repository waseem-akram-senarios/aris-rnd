#!/usr/bin/env python3
"""
End-to-end automated testing for FAISS and OpenSearch vector store integration.
Tests document processing, querying, and both vector store backends.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Test results tracking
test_results = {
    'passed': [],
    'failed': [],
    'skipped': []
}

def log_test(test_name, passed=True, message=""):
    """Log test result."""
    if passed:
        test_results['passed'].append(test_name)
        print(f"✅ PASS: {test_name}")
        if message:
            print(f"   {message}")
    else:
        test_results['failed'].append(test_name)
        print(f"❌ FAIL: {test_name}")
        if message:
            print(f"   {message}")

def log_skip(test_name, reason):
    """Log skipped test."""
    test_results['skipped'].append((test_name, reason))
    print(f"⏭️  SKIP: {test_name} - {reason}")

print("=" * 70)
print("End-to-End Testing: FAISS and OpenSearch Vector Store Integration")
print("=" * 70)
print()

# Test 1: Import checks
print("📦 Test 1: Import Checks")
print("-" * 70)
try:
    from vectorstores.vector_store_factory import VectorStoreFactory
    from vectorstores.opensearch_store import OpenSearchVectorStore
    from rag_system import RAGSystem
    from langchain_openai import OpenAIEmbeddings
    log_test("Import vector store factory", True)
except Exception as e:
    log_test("Import vector store factory", False, str(e))
    sys.exit(1)

try:
    from langchain_community.vectorstores import FAISS
    log_test("Import FAISS", True)
except Exception as e:
    log_test("Import FAISS", False, str(e))

try:
    from langchain_community.vectorstores import OpenSearchVectorSearch
    log_test("Import OpenSearchVectorSearch", True)
except Exception as e:
    log_test("Import OpenSearchVectorSearch", False, str(e))
    log_skip("OpenSearch tests", "OpenSearchVectorSearch not available")

print()

# Test 2: FAISS Vector Store Factory
print("💾 Test 2: FAISS Vector Store Factory")
print("-" * 70)
try:
    embeddings = OpenAIEmbeddings(
        openai_api_key=os.getenv('OPENAI_API_KEY'),
        model="text-embedding-3-small"
    )
    
    faiss_store = VectorStoreFactory.create_vector_store(
        store_type="faiss",
        embeddings=embeddings
    )
    log_test("Create FAISS store via factory", True)
except Exception as e:
    log_test("Create FAISS store via factory", False, str(e))

print()

# Test 3: RAGSystem with FAISS
print("🤖 Test 3: RAGSystem with FAISS")
print("-" * 70)
try:
    rag_faiss = RAGSystem(
        vector_store_type="faiss",
        embedding_model="text-embedding-3-small"
    )
    log_test("Initialize RAGSystem with FAISS", True)
    
    # Check attributes
    if hasattr(rag_faiss, 'vector_store_type') and rag_faiss.vector_store_type == "faiss":
        log_test("RAGSystem vector_store_type attribute", True)
    else:
        log_test("RAGSystem vector_store_type attribute", False, "Attribute not set correctly")
except Exception as e:
    log_test("Initialize RAGSystem with FAISS", False, str(e))
    import traceback
    traceback.print_exc()

print()

# Test 4: FAISS Document Processing
print("📄 Test 4: FAISS Document Processing")
print("-" * 70)
try:
    test_texts = [
        "This is a test document about artificial intelligence. AI is transforming many industries.",
        "Machine learning is a subset of AI that focuses on algorithms and statistical models.",
        "Natural language processing enables computers to understand and generate human language."
    ]
    test_metadatas = [
        {"source": "test_doc_1.txt", "page": 1},
        {"source": "test_doc_2.txt", "page": 1},
        {"source": "test_doc_3.txt", "page": 1}
    ]
    
    chunks_created = rag_faiss.process_documents(test_texts, test_metadatas)
    if chunks_created > 0:
        log_test("FAISS: Process documents", True, f"Created {chunks_created} chunks")
    else:
        log_test("FAISS: Process documents", False, "No chunks created")
    
    if rag_faiss.vectorstore is not None:
        log_test("FAISS: Vector store created", True)
    else:
        log_test("FAISS: Vector store created", False, "Vector store is None")
        
except Exception as e:
    log_test("FAISS: Process documents", False, str(e))
    import traceback
    traceback.print_exc()

print()

# Test 5: FAISS Querying
print("🔍 Test 5: FAISS Querying")
print("-" * 70)
try:
    if rag_faiss.vectorstore is not None:
        result = rag_faiss.query_with_rag("What is artificial intelligence?", k=3, use_mmr=False)
        
        if result and "answer" in result:
            if "No documents" not in result["answer"]:
                log_test("FAISS: Query with RAG", True, f"Answer length: {len(result['answer'])} chars")
            else:
                log_test("FAISS: Query with RAG", False, "No documents message returned")
        else:
            log_test("FAISS: Query with RAG", False, "Invalid result structure")
            
        if "sources" in result:
            log_test("FAISS: Query returns sources", True, f"Found {len(result['sources'])} sources")
    else:
        log_test("FAISS: Query with RAG", False, "Vector store not initialized")
except Exception as e:
    log_test("FAISS: Query with RAG", False, str(e))
    import traceback
    traceback.print_exc()

print()

# Test 6: OpenSearch Configuration Check
print("☁️  Test 6: OpenSearch Configuration")
print("-" * 70)
opensearch_available = False
opensearch_access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
opensearch_secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
opensearch_region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')

if opensearch_access_key and opensearch_secret_key:
    log_test("OpenSearch credentials found", True)
    opensearch_available = True
else:
    log_skip("OpenSearch tests", "OpenSearch credentials not found in .env")

print()

# Test 7: OpenSearch Connection (if available)
if opensearch_available:
    print("🔌 Test 7: OpenSearch Connection")
    print("-" * 70)
    try:
        import boto3
        opensearch_client = boto3.client(
            'opensearch',
            aws_access_key_id=opensearch_access_key,
            aws_secret_access_key=opensearch_secret_key,
            region_name=opensearch_region
        )
        
        # Try to list domains
        domains = opensearch_client.list_domain_names()
        if domains.get('DomainNames'):
            log_test("OpenSearch: Connect to AWS", True, f"Found {len(domains['DomainNames'])} domain(s)")
        else:
            log_test("OpenSearch: Connect to AWS", False, "No domains found")
    except Exception as e:
        log_test("OpenSearch: Connect to AWS", False, str(e))
        opensearch_available = False
    
    print()

# Test 8: OpenSearch Vector Store Factory (if available)
if opensearch_available:
    print("💾 Test 8: OpenSearch Vector Store Factory")
    print("-" * 70)
    try:
        opensearch_store = VectorStoreFactory.create_vector_store(
            store_type="opensearch",
            embeddings=embeddings,
            opensearch_domain="intelycx-os-dev",
            opensearch_index="aris-rag-test-index"
        )
        log_test("Create OpenSearch store via factory", True)
    except Exception as e:
        log_test("Create OpenSearch store via factory", False, str(e))
        opensearch_available = False
        log_skip("OpenSearch document processing", "Failed to create OpenSearch store")
    
    print()

# Test 9: RAGSystem with OpenSearch (if available)
if opensearch_available:
    print("🤖 Test 9: RAGSystem with OpenSearch")
    print("-" * 70)
    try:
        rag_opensearch = RAGSystem(
            vector_store_type="opensearch",
            embedding_model="text-embedding-3-small",
            opensearch_domain="intelycx-os-dev",
            opensearch_index="aris-rag-test-index"
        )
        log_test("Initialize RAGSystem with OpenSearch", True)
        
        if hasattr(rag_opensearch, 'vector_store_type') and rag_opensearch.vector_store_type == "opensearch":
            log_test("RAGSystem OpenSearch vector_store_type attribute", True)
        else:
            log_test("RAGSystem OpenSearch vector_store_type attribute", False, "Attribute not set correctly")
    except Exception as e:
        log_test("Initialize RAGSystem with OpenSearch", False, str(e))
        opensearch_available = False
        log_skip("OpenSearch document processing", "Failed to initialize RAGSystem with OpenSearch")
        import traceback
        traceback.print_exc()
    
    print()

# Test 10: OpenSearch Document Processing (if available)
if opensearch_available:
    print("📄 Test 10: OpenSearch Document Processing")
    print("-" * 70)
    try:
        test_texts_opensearch = [
            "OpenSearch is a distributed search and analytics engine built on Apache Lucene.",
            "It provides real-time search, analytics, and visualization capabilities.",
            "OpenSearch supports vector search for semantic similarity and machine learning use cases."
        ]
        test_metadatas_opensearch = [
            {"source": "opensearch_doc_1.txt", "page": 1},
            {"source": "opensearch_doc_2.txt", "page": 1},
            {"source": "opensearch_doc_3.txt", "page": 1}
        ]
        
        chunks_created = rag_opensearch.process_documents(test_texts_opensearch, test_metadatas_opensearch)
        if chunks_created > 0:
            log_test("OpenSearch: Process documents", True, f"Created {chunks_created} chunks")
        else:
            log_test("OpenSearch: Process documents", False, "No chunks created")
        
        if rag_opensearch.vectorstore is not None:
            log_test("OpenSearch: Vector store created", True)
        else:
            log_test("OpenSearch: Vector store created", False, "Vector store is None")
            
    except Exception as e:
        log_test("OpenSearch: Process documents", False, str(e))
        import traceback
        traceback.print_exc()
    
    print()

# Test 11: OpenSearch Querying (if available)
if opensearch_available:
    print("🔍 Test 11: OpenSearch Querying")
    print("-" * 70)
    try:
        if rag_opensearch.vectorstore is not None:
            result = rag_opensearch.query_with_rag("What is OpenSearch?", k=3, use_mmr=False)
            
            if result and "answer" in result:
                if "No documents" not in result["answer"]:
                    log_test("OpenSearch: Query with RAG", True, f"Answer length: {len(result['answer'])} chars")
                else:
                    log_test("OpenSearch: Query with RAG", False, "No documents message returned")
            else:
                log_test("OpenSearch: Query with RAG", False, "Invalid result structure")
                
            if "sources" in result:
                log_test("OpenSearch: Query returns sources", True, f"Found {len(result['sources'])} sources")
        else:
            log_test("OpenSearch: Query with RAG", False, "Vector store not initialized")
    except Exception as e:
        log_test("OpenSearch: Query with RAG", False, str(e))
        import traceback
        traceback.print_exc()
    
    print()

# Test 12: Vector Store Switching
print("🔄 Test 12: Vector Store Switching")
print("-" * 70)
try:
    # Create new RAGSystem instances with different stores
    rag_faiss_2 = RAGSystem(vector_store_type="faiss", embedding_model="text-embedding-3-small")
    if rag_faiss_2.vector_store_type == "faiss":
        log_test("Switch to FAISS", True)
    
    if opensearch_available:
        rag_opensearch_2 = RAGSystem(
            vector_store_type="opensearch",
            embedding_model="text-embedding-3-small",
            opensearch_domain="intelycx-os-dev",
            opensearch_index="aris-rag-test-index-2"
        )
        if rag_opensearch_2.vector_store_type == "opensearch":
            log_test("Switch to OpenSearch", True)
except Exception as e:
    log_test("Vector store switching", False, str(e))

print()

# Test 13: Incremental Document Addition
print("➕ Test 13: Incremental Document Addition")
print("-" * 70)
try:
    if rag_faiss.vectorstore is not None:
        # Add more documents incrementally
        additional_texts = ["This is an additional document added incrementally."]
        additional_metadatas = [{"source": "additional_doc.txt", "page": 1}]
        
        stats = rag_faiss.add_documents_incremental(additional_texts, additional_metadatas)
        if stats.get('chunks_created', 0) > 0:
            log_test("FAISS: Incremental document addition", True, f"Added {stats['chunks_created']} chunks")
        else:
            log_test("FAISS: Incremental document addition", False, "No chunks added")
    else:
        log_test("FAISS: Incremental document addition", False, "Vector store not initialized")
except Exception as e:
    log_test("FAISS: Incremental document addition", False, str(e))

print()

# Test 14: Statistics and Metrics
print("📊 Test 14: Statistics and Metrics")
print("-" * 70)
try:
    if rag_faiss.vectorstore is not None:
        stats = rag_faiss.get_stats()
        if stats and 'total_documents' in stats:
            log_test("FAISS: Get statistics", True, 
                    f"Documents: {stats['total_documents']}, Chunks: {stats['total_chunks']}")
        else:
            log_test("FAISS: Get statistics", False, "Invalid stats structure")
            
        chunk_stats = rag_faiss.get_chunk_token_stats()
        if chunk_stats and 'total_chunks' in chunk_stats:
            log_test("FAISS: Get chunk token stats", True, 
                    f"Total chunks: {chunk_stats['total_chunks']}")
        else:
            log_test("FAISS: Get chunk token stats", False, "Invalid chunk stats structure")
    else:
        log_test("FAISS: Get statistics", False, "Vector store not initialized")
except Exception as e:
    log_test("FAISS: Get statistics", False, str(e))

print()

# Summary
print("=" * 70)
print("Test Summary")
print("=" * 70)
print(f"✅ Passed: {len(test_results['passed'])}")
print(f"❌ Failed: {len(test_results['failed'])}")
print(f"⏭️  Skipped: {len(test_results['skipped'])}")
print()

if test_results['failed']:
    print("Failed Tests:")
    for test in test_results['failed']:
        print(f"  - {test}")
    print()

if test_results['skipped']:
    print("Skipped Tests:")
    for test, reason in test_results['skipped']:
        print(f"  - {test}: {reason}")
    print()

# Final result
if len(test_results['failed']) == 0:
    print("🎉 All tests passed!")
    sys.exit(0)
else:
    print("⚠️  Some tests failed. Please review the errors above.")
    sys.exit(1)

