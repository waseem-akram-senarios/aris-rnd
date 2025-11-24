# Setup Guide for Enhanced RAG System

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Git (optional, for cloning)

## Step-by-Step Setup

### 1. Check Python Version

```bash
python3 --version
```

Should show Python 3.10.x or higher.

### 2. Create Virtual Environment

**Option A: Using the setup script (Recommended)**
```bash
chmod +x setup_env.sh
./setup_env.sh
```

**Option B: Manual setup**
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate     # Windows

# Verify activation
which python  # Should point to venv/bin/python
```

### 3. Install Dependencies

```bash
# Make sure venv is activated
pip install --upgrade pip
pip install -r requirements.txt
```

This will install:
- Streamlit (web UI)
- OpenAI SDK
- LangChain and related packages
- FAISS (local vector database)
- OpenSearch (cloud vector database, optional)
- PyMuPDF (PDF parser)
- Docling (advanced PDF parser)
- TikToken (tokenization)
- And other dependencies

### 4. Configure API Keys

Create a `.env` file in the project root:

```bash
cp .env.example .env  # If .env.example exists
# OR create .env manually
```

Edit `.env` and add your API keys:

```env
OPENAI_API_KEY=your_openai_key_here
CEREBRAS_API_KEY=your_cerebras_key_here

# Optional: For AWS Textract parser
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1

# Optional: For OpenSearch vector store (if using OpenSearch instead of FAISS)
AWS_OPENSEARCH_ACCESS_KEY_ID=your_opensearch_access_key
AWS_OPENSEARCH_SECRET_ACCESS_KEY=your_opensearch_secret_key
AWS_OPENSEARCH_REGION=us-east-2
```

### 5. Verify Installation

```bash
# Test imports
python3 -c "from rag_system import RAGSystem; print('✅ RAG System OK')"
python3 -c "from parsers.parser_factory import ParserFactory; print('✅ Parsers OK')"
```

### 6. Configure Vector Store (Optional)

The system supports two vector store options:

**FAISS (Default - Local Storage)**
- No additional configuration needed
- Data stored locally in `vectorstore/` directory
- Fast and suitable for most use cases
- No cloud dependencies

**OpenSearch (Cloud Storage)**
- Requires AWS OpenSearch domain
- Add credentials to `.env`:
  ```env
  AWS_OPENSEARCH_ACCESS_KEY_ID=your_key
  AWS_OPENSEARCH_SECRET_ACCESS_KEY=your_secret
  AWS_OPENSEARCH_REGION=us-east-2
  ```
- Select OpenSearch domain in UI
- Scalable for large datasets
- Data stored in AWS cloud

You can select the vector store in the Streamlit UI sidebar.

### 7. Run the Application

**Option A: Using the run script**
```bash
./run_rag.sh
```

**Option B: Manual run**
```bash
source venv/bin/activate
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## Troubleshooting

### Virtual Environment Issues

**Problem:** `python3 -m venv venv` fails
- **Solution:** Install python3-venv: `sudo apt-get install python3-venv` (Linux)

**Problem:** Can't activate venv
- **Solution:** Check you're in the project directory and venv exists

### Dependency Installation Issues

**Problem:** `pip install` fails for specific packages
- **Solution:** Try installing individually: `pip install package_name`
- For PyMuPDF: `pip install pymupdf`
- For Docling: `pip install docling`

**Problem:** Import errors after installation
- **Solution:** Make sure venv is activated: `source venv/bin/activate`

### API Key Issues

**Problem:** "API key not found" error
- **Solution:** Check `.env` file exists and contains valid keys
- Verify file is in project root directory
- Check for typos in variable names (OPENAI_API_KEY, not OPENAI_KEY)

### Parser Issues

**Problem:** PyMuPDF parser fails
- **Solution:** Reinstall: `pip install --upgrade pymupdf`

**Problem:** Docling parser is slow
- **Solution:** This is normal for first run (downloads OCR models). Subsequent runs are faster.

**Problem:** Textract parser not available
- **Solution:** This is optional. Install boto3 and configure AWS credentials if needed.

### Vector Store Issues

**Problem:** OpenSearch connection fails
- **Solution:** Check your OpenSearch credentials in `.env` file
- Verify the domain name is correct
- Ensure your AWS credentials have OpenSearch permissions
- Try using FAISS instead for local storage

**Problem:** Switching vector stores loses data
- **Solution:** This is expected behavior. Each vector store maintains separate data. Reprocess documents when switching stores.

## Development Workflow

1. **Always activate venv before working:**
   ```bash
   source venv/bin/activate
   ```

2. **Install new dependencies:**
   ```bash
   pip install new_package
   pip freeze > requirements.txt  # Update requirements
   ```

3. **Run tests:**
   ```bash
   python3 test_openai.py
   python3 test_cerebras.py
   ```

## File Structure

```
aris/
├── venv/                    # Virtual environment (don't edit)
├── parsers/                 # Parser modules
│   ├── base_parser.py
│   ├── pymupdf_parser.py
│   ├── docling_parser.py
│   ├── textract_parser.py
│   ├── parser_factory.py
│   └── pdf_type_detector.py
├── ingestion/               # Document processing
│   └── document_processor.py
├── utils/                   # Utilities
│   └── tokenizer.py
├── app.py                   # Streamlit UI
├── rag_system.py           # Core RAG system
├── requirements.txt         # Dependencies
├── setup_env.sh            # Setup script
├── run_rag.sh              # Run script
└── .env                    # API keys (not in git)
```

## Next Steps

After setup:
1. Upload a test PDF document
2. Select a parser (Auto recommended)
3. Process the document
4. Ask questions about the document

For more information, see `README_RAG.md`


