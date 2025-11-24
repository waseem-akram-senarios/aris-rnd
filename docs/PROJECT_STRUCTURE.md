# Project Structure

This document describes the organization of the ARIS RAG system project.

## Directory Structure

```
aris/
├── app.py                    # Main Streamlit application
├── rag_system.py             # Core RAG system implementation
│
├── config/                   # Configuration files
│   └── requirements.txt      # Python dependencies
│
├── docs/                     # Documentation
│   ├── README.md            # Main project README
│   ├── SETUP.md             # Setup instructions
│   ├── SECURITY.md          # Security guidelines
│   ├── METRICS_GUIDE.md     # Metrics documentation
│   └── ...                  # Other documentation files
│
├── tests/                    # Test files
│   ├── test_*.py            # Unit and integration tests
│   ├── check_*.py           # Verification scripts
│   └── ...                  # Other test utilities
│
├── scripts/                  # Utility scripts
│   ├── *.sh                 # Shell scripts
│   └── ...                  # Other utility scripts
│
├── samples/                  # Sample files
│   ├── *.pdf                # Sample PDF documents
│   └── *.txt                # Sample text files
│
├── emails/                   # Email templates
│   └── EMAIL_*.txt          # Email templates for permissions, etc.
│
├── ingestion/                # Document ingestion module
│   └── document_processor.py
│
├── parsers/                  # Document parsers
│   ├── parser_factory.py
│   ├── pymupdf_parser.py
│   ├── docling_parser.py
│   └── textract_parser.py
│
├── utils/                    # Utility modules
│   ├── tokenizer.py
│   └── chunking_strategies.py
│
├── metrics/                  # Metrics collection
│   └── metrics_collector.py
│
├── vectorstores/             # Vector store implementations
│   ├── vector_store_factory.py
│   └── opensearch_store.py
│
└── diagrams/                 # Architecture diagrams
    └── *.mmd                # Mermaid diagram files
```

## Key Files

### Core Application
- `app.py` - Streamlit web UI
- `rag_system.py` - Main RAG system class

### Configuration
- `config/requirements.txt` - Python package dependencies

### Documentation
- `docs/README.md` - Project overview
- `docs/SETUP.md` - Installation and setup guide
- `docs/SECURITY.md` - Security best practices

### Tests
- `tests/test_*.py` - All test files
- `tests/check_*.py` - Verification scripts

## File Organization Principles

1. **Core code** stays in root (app.py, rag_system.py)
2. **Tests** go in `tests/` directory
3. **Documentation** goes in `docs/` directory
4. **Scripts** go in `scripts/` directory
5. **Samples** go in `samples/` directory
6. **Email templates** go in `emails/` directory
7. **Config files** go in `config/` directory

## Module Structure

- `ingestion/` - Document processing pipeline
- `parsers/` - Document parsing implementations
- `utils/` - Utility functions and helpers
- `metrics/` - Metrics collection and analytics
- `vectorstores/` - Vector store abstractions
- `diagrams/` - Architecture diagrams

