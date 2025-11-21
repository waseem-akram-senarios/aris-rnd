# ARIS R&D - Enhanced RAG Document Q&A System

A production-grade Retrieval-Augmented Generation (RAG) system with advanced parsers, token-aware processing, and real-time ingestion.

## Features

- 📄 **Advanced Document Parsing**: Multiple parsers (PyMuPDF, Docling, Textract) with automatic fallback
- 🎯 **Token-Aware Processing**: Accurate token counting with TikToken for cost optimization
- ⚡ **Real-time Ingestion**: Process documents incrementally with progress tracking
- 🔍 **Semantic Search**: Find relevant context from your documents using FAISS vector store
- 💬 **Interactive Chat**: Ask questions and get answers based on your documents
- 🔄 **Multiple APIs**: Choose between OpenAI and Cerebras for answer generation
- 📎 **Source Attribution**: See which documents and chunks were used
- 💰 **Cost Tracking**: Monitor token usage and embedding costs
- 🏗️ **Extensible Architecture**: Easy to add new file types and parsers

## Installation

See `SETUP.md` for detailed setup instructions.

**Quick Start:**
```bash
# 1. Create and activate virtual environment
./setup_env.sh

# 2. Configure API keys in .env file
# Edit .env with your keys

# 3. Run the application
./run_rag.sh
```

**Requirements:**
- Python 3.10+
- Virtual environment (created automatically by setup script)
- API keys: OpenAI and/or Cerebras

## Usage

1. **Start the Streamlit app:**
   ```bash
   streamlit run app.py
   ```

2. **In the browser:**
   - Select your preferred API (OpenAI or Cerebras) in the sidebar
   - Upload your documents (PDF, TXT, or DOCX)
   - Click "Process Documents"
   - Start asking questions!

## How It Works

1. **Document Processing:**
   - **Parsing**: Documents are parsed using the selected parser (PyMuPDF, Docling, or Textract)
   - **Type Detection**: PDFs are analyzed to determine if they're text-based or image-heavy
   - **Chunking**: Text is split into chunks using token-aware splitting (512 tokens per chunk, 50 token overlap)
   - **Embedding**: Each chunk is converted to embeddings using OpenAI's `text-embedding-3-small` model
   - **Storage**: Embeddings are stored in a FAISS vector database for fast retrieval

2. **Parser Selection (Auto Mode):**
   - Try PyMuPDF first (fastest, free, good for text PDFs)
   - If extraction < 50% or images detected: Try Docling
   - If still poor results and AWS available: Try Textract
   - Return best result with confidence score

3. **Querying:**
   - Your question is converted to an embedding
   - Similar document chunks are retrieved (top K=4)
   - Context is sent to the LLM (OpenAI or Cerebras) along with your question
   - The LLM generates an answer based on the retrieved context
   - Sources are attributed to show which documents were used

## Supported File Formats

- **PDF** (.pdf) - Multiple parsers available:
  - **PyMuPDF**: Fast parser for text-based PDFs
  - **Docling**: Better for structured content, tables, complex layouts
  - **Textract**: AWS OCR for scanned/image-heavy PDFs (requires AWS credentials)
- **TXT** (.txt) - Plain text files
- **DOCX** (.docx, .doc) - Microsoft Word documents

## Parser Options

### Auto (Recommended)
Automatically selects the best parser based on PDF characteristics:
- Fast text PDFs → PyMuPDF
- Complex layouts → Docling
- Scanned PDFs → Textract (if AWS available)

### Manual Selection
Choose a specific parser:
- **PyMuPDF**: Fastest, free, best for text PDFs
- **Docling**: Better for tables and structured content
- **Textract**: AWS OCR, costs money but best for scanned PDFs

## API Options

### OpenAI
- Uses GPT-3.5-turbo for answer generation
- Uses text-embedding-3-small for embeddings (cost-optimized)
- Fast and reliable
- Requires OpenAI API key

### Cerebras
- Uses Cerebras models (llama3.1-8b, llama-3.3-70b, qwen-3-32b)
- Alternative to OpenAI
- Requires Cerebras API key

## Token-Aware Processing

The system uses TikToken for accurate token counting:
- **Chunk Size**: 512 tokens (optimal for small embeddings)
- **Overlap**: 50 tokens between chunks
- **Cost Tracking**: Monitor token usage and embedding costs
- **Embedding Model**: text-embedding-3-small (10x cheaper than ada-002)

## Troubleshooting

- **"No documents processed"**: Make sure to upload files and click "Process Documents"
- **API errors**: Check that your API keys are correct in the `.env` file
- **Parser errors**: Try a different parser or use "Auto" mode
- **Empty responses**: Ensure your documents contain readable text
- **Memory issues**: For large documents, consider splitting them into smaller files
- **Slow processing**: First run with Docling downloads OCR models (one-time)
- **Import errors**: Make sure virtual environment is activated: `source venv/bin/activate`

## Project Structure

```
aris/
├── parsers/                    # Parser modules
│   ├── base_parser.py         # Base parser interface
│   ├── pymupdf_parser.py      # PyMuPDF implementation
│   ├── docling_parser.py      # Docling implementation
│   ├── textract_parser.py     # AWS Textract implementation
│   ├── parser_factory.py      # Parser selection logic
│   └── pdf_type_detector.py   # PDF type detection
├── ingestion/                  # Document processing
│   └── document_processor.py  # Real-time processing pipeline
├── utils/                      # Utilities
│   └── tokenizer.py           # Token-aware text splitter
├── app.py                      # Streamlit UI
├── rag_system.py              # Core RAG system
├── requirements.txt           # Python dependencies
├── setup_env.sh              # Virtual environment setup
├── run_rag.sh                # Application launcher
├── .env                      # API keys (not in git)
├── README_RAG.md             # This file
└── SETUP.md                  # Detailed setup guide
```

## Notes

- The vector store is stored in memory (resets when app restarts)
- Use `save_vectorstore()` and `load_vectorstore()` methods for persistence
- Large documents may take time to process (especially with Docling on first run)
- The system works best with well-structured documents
- Token counting is accurate and matches OpenAI's tokenizer
- Real-time processing allows querying as soon as first document completes

## Architecture

- **Modular Design**: Easy to extend with new parsers and file types
- **Factory Pattern**: Parser selection handled automatically
- **Incremental Updates**: Documents added to vector store without full rebuild
- **Error Handling**: Continues processing other documents if one fails
- **Progress Tracking**: Real-time feedback during document processing


