# ARIS R&D - RAG Document Q&A System

## Overview
ARIS R&D is a comprehensive RAG (Retrieval-Augmented Generation) system for document processing and question-answering. It supports multiple parsers (PyMuPDF, Docling, AWS Textract), token tracking, and advanced metrics collection.

## Features
- **Multiple Document Parsers**: PyMuPDF, Docling, AWS Textract with intelligent fallback
- **Dual Vector Stores**: Choose between FAISS (local) or OpenSearch (cloud) for storing embeddings
- **Token Tracking**: Real-time token counting and cost estimation
- **Progress Feedback**: Enhanced progress tracking for chunking and embedding operations
- **Metrics Dashboard**: Comprehensive R&D analytics and performance metrics
- **Streamlit UI**: User-friendly web interface

## Quick Start

See `QUICK_START.md` for detailed setup instructions.

## Documentation

- `SETUP.md` - Installation and configuration
- `QUICK_START.md` - Getting started guide
- `METRICS_GUIDE.md` - Metrics and analytics
- `HOW_TO_USE_DOCLING.md` - Docling parser usage
- `diagrams/` - Architecture diagrams
