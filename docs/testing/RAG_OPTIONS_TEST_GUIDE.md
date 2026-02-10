# RAG System - Complete Options Testing Guide

## Overview

This guide helps you test all available options in the RAG system deployed on the server.

**Application URL**: http://35.175.133.235/

---

## Available Options

### 1. API & Model Selection

#### OpenAI API
- **gpt-3.5-turbo** (Default) - Fast, cost-effective
- **gpt-4** - Higher quality, more expensive
- **gpt-4-turbo-preview** - Latest GPT-4 with improvements

#### Cerebras API (Optional)
- **llama3.1-8b** - Fast inference
- **llama3.1-70b** - Higher quality

**Test**: Switch between APIs and models, process same document, compare answers.

---

### 2. Embedding Models

- **text-embedding-3-small** (Default) - 1536 dimensions, cost-effective
- **text-embedding-3-large** - 3072 dimensions, better accuracy
- **text-embedding-ada-002** - Legacy model, 1536 dimensions

**Test**: Use different embedding models, process document, compare retrieval quality.

---

### 3. Parsers

#### Auto (Recommended)
- Automatically tries: PyMuPDF → Docling → Textract
- Best for: Unknown PDF types

#### PyMuPDF
- **Speed**: Fast (~seconds)
- **Best for**: Text-based PDFs
- **Limitations**: May miss complex layouts

#### Docling
- **Speed**: Slow (5-20 minutes for scanned PDFs)
- **Best for**: Scanned PDFs, complex layouts, all pages
- **Features**: OCR processing, processes all pages

#### Textract
- **Speed**: Medium (~minutes)
- **Best for**: Scanned PDFs with AWS
- **Requirements**: AWS credentials

**Test**: 
1. Upload same PDF with each parser
2. Compare extraction quality
3. Check processing time
4. Verify Docling processes all pages

---

### 4. Chunking Strategies

#### Precise
- **Chunk Size**: 256 tokens
- **Overlap**: 50 tokens
- **Best for**: Exact matches, specific information
- **Use case**: Technical specifications, precise data

#### Balanced (Recommended)
- **Chunk Size**: 384 tokens
- **Overlap**: 75 tokens
- **Best for**: General Q&A
- **Use case**: Most documents

#### Comprehensive
- **Chunk Size**: 512 tokens
- **Overlap**: 100 tokens
- **Best for**: Context-rich answers
- **Use case**: Complex documents, need more context

#### Custom
- Set your own chunk size and overlap
- **Range**: 128-1024 tokens
- **Best for**: Specific requirements

**Test**:
1. Process same document with each strategy
2. Ask same questions
3. Compare answer quality and context
4. Check number of chunks created

---

### 5. Vector Stores

#### FAISS (Default)
- **Storage**: Local (`vectorstore/` directory)
- **Speed**: Very fast
- **Scalability**: Limited by disk space
- **Best for**: Single server, fast queries

#### OpenSearch
- **Storage**: Cloud (AWS OpenSearch)
- **Speed**: Fast (network dependent)
- **Scalability**: Highly scalable
- **Best for**: Multi-server, large datasets
- **Requirements**: AWS OpenSearch domain

**Test**:
1. Process document with FAISS
2. Switch to OpenSearch (if available)
3. Process same document
4. Compare query performance
5. Verify data persistence

---

## Complete Test Matrix

### Test Scenario 1: Fast Processing
- **API**: OpenAI
- **Model**: gpt-3.5-turbo
- **Embedding**: text-embedding-3-small
- **Parser**: PyMuPDF
- **Chunking**: Balanced
- **Vector Store**: FAISS
- **Expected**: Fast processing, good results

### Test Scenario 2: Best Quality
- **API**: OpenAI
- **Model**: gpt-4
- **Embedding**: text-embedding-3-large
- **Parser**: Docling
- **Chunking**: Comprehensive
- **Vector Store**: FAISS
- **Expected**: Highest quality, slower processing

### Test Scenario 3: Scanned PDF
- **API**: OpenAI
- **Model**: gpt-3.5-turbo
- **Embedding**: text-embedding-3-small
- **Parser**: Docling (or Textract if AWS available)
- **Chunking**: Balanced
- **Vector Store**: FAISS
- **Expected**: OCR processing, all pages extracted

### Test Scenario 4: Custom Chunking
- **API**: OpenAI
- **Model**: gpt-3.5-turbo
- **Embedding**: text-embedding-3-small
- **Parser**: Auto
- **Chunking**: Custom (e.g., 600 tokens, 120 overlap)
- **Vector Store**: FAISS
- **Expected**: Custom chunk sizes applied

### Test Scenario 5: OpenSearch (if available)
- **API**: OpenAI
- **Model**: gpt-3.5-turbo
- **Embedding**: text-embedding-3-small
- **Parser**: PyMuPDF
- **Chunking**: Balanced
- **Vector Store**: OpenSearch
- **Expected**: Data stored in cloud, scalable

---

## Step-by-Step Testing

### 1. Access Application
```
http://35.175.133.235/
```

### 2. Configure Options (Sidebar)

**API Selection:**
- Choose OpenAI or Cerebras

**Model Selection:**
- Select model based on API choice

**Embedding Model:**
- Choose embedding model

**Parser:**
- Select parser (Auto recommended)

**Chunking Strategy:**
- Choose strategy or Custom

**Vector Store:**
- Select FAISS or OpenSearch

### 3. Upload Document
- Click "Upload Documents"
- Select a PDF file
- Wait for processing

### 4. Monitor Processing
- Watch progress bar
- Check parser used
- Verify chunking
- Confirm embeddings created

### 5. Test Queries
- Ask questions about the document
- Verify answers are accurate
- Check source attribution
- Test different question types

### 6. Test Different Combinations
- Change options
- Reprocess document
- Compare results
- Note performance differences

---

## What to Verify

### Parser Testing
- ✅ PyMuPDF: Fast extraction for text PDFs
- ✅ Docling: Processes all pages, handles scanned PDFs
- ✅ Auto: Selects best parser automatically
- ✅ Parser used matches selection (no fallback when specific parser selected)

### Chunking Testing
- ✅ Precise: Creates more, smaller chunks
- ✅ Balanced: Medium-sized chunks
- ✅ Comprehensive: Fewer, larger chunks
- ✅ Custom: Uses specified parameters

### Vector Store Testing
- ✅ FAISS: Fast local queries
- ✅ OpenSearch: Cloud storage (if configured)
- ✅ Data persists across sessions
- ✅ Switching stores works correctly

### Query Testing
- ✅ Simple questions return answers
- ✅ Complex questions use context
- ✅ Source documents are cited
- ✅ Answers are relevant and accurate

---

## Expected Results

### Processing Times
- **PyMuPDF**: 5-30 seconds
- **Docling**: 5-20 minutes (for scanned PDFs)
- **Textract**: 2-5 minutes
- **Chunking**: 10-60 seconds
- **Embedding**: 30 seconds - 5 minutes

### Quality Indicators
- **Extraction Rate**: > 50% for text PDFs
- **Chunk Count**: Varies by strategy and document size
- **Query Accuracy**: Answers should be relevant
- **Source Attribution**: Should cite correct documents

---

## Troubleshooting

### Parser Issues
- **Docling timeout**: Normal for large scanned PDFs (up to 20 min)
- **Textract error**: Check AWS credentials
- **PyMuPDF empty**: Document may be image-based, try Docling

### Chunking Issues
- **Too many chunks**: Use Comprehensive strategy
- **Too few chunks**: Use Precise strategy
- **Custom not working**: Check token limits (128-1024)

### Vector Store Issues
- **FAISS error**: Check disk space
- **OpenSearch error**: Verify AWS credentials and domain

### Query Issues
- **No answers**: Process documents first
- **Poor answers**: Try different chunking strategy
- **Wrong sources**: Check document processing results

---

## Test Report Template

After testing, document:

1. **Options Tested**: List all combinations tested
2. **Results**: What worked, what didn't
3. **Performance**: Processing times, query speeds
4. **Quality**: Answer accuracy, extraction rates
5. **Issues**: Any problems encountered
6. **Recommendations**: Best configurations for your use case

---

## Quick Test Commands

### Test on Server (via SSH)
```bash
ssh -i scripts/ec2_wah_pk.pem ec2-user@35.175.133.235
cd /opt/aris-rag
# Check container logs
sudo docker logs aris-rag-app --tail 50
```

### Test Locally (if needed)
```bash
# Run automated test
python3 tests/test_rag_all_options.py

# Or use test guide
./tests/test_rag_on_server.sh
```

---

**Last Updated**: November 28, 2025  
**Application**: http://35.175.133.235/

