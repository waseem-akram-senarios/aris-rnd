# ARIS R&D - Architecture Diagrams

This folder contains Mermaid architecture diagrams for the ARIS R&D RAG System.

## Diagram Files

1. **01_high_level_architecture.mmd** - System architecture overview showing all layers and components
2. **02_document_processing_pipeline.mmd** - Complete document processing flow with token tracking
3. **03_query_processing_flow.mmd** - Query processing sequence diagram with token counting
4. **04_token_counting_architecture.mmd** - Token counting system architecture
5. **05_component_class_diagram.mmd** - UML class diagram showing component relationships
6. **06_data_flow_with_tokens.mmd** - Data flow diagram including token tracking
7. **07_parser_fallback_strategy.mmd** - Parser selection and fallback logic flow
8. **08_complete_system_flow.mmd** - End-to-end system flow from user actions to output

## How to View

### Option 1: Mermaid Live Editor (Recommended)
1. Go to https://mermaid.live/
2. Copy the content from any `.mmd` file
3. Paste into the editor
4. View and export as PNG/SVG

### Option 2: VS Code
1. Install the "Markdown Preview Mermaid Support" extension
2. Open any `.mmd` file
3. Use the preview feature

### Option 3: GitHub
- GitHub automatically renders `.mmd` files in repositories
- Just view the file on GitHub

### Option 4: Command Line (with Mermaid CLI)
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate PNG from diagram
mmdc -i diagrams/01_high_level_architecture.mmd -o diagrams/01_high_level_architecture.png
```

## Diagram Descriptions

### 1. High-Level Architecture
Shows the complete system architecture with:
- User Interface Layer (Streamlit)
- Application Layer (DocumentProcessor, RAGSystem)
- Parser Layer (ParserFactory, PyMuPDF, Textract)
- Processing Layer (Tokenizer, Embeddings, FAISS)
- LLM Layer (OpenAI, Cerebras)
- Analytics Layer (MetricsCollector)

### 2. Document Processing Pipeline
Step-by-step flow of document processing:
- File upload and validation
- Parser selection and fallback
- Token-aware chunking
- Embedding creation
- FAISS indexing
- Metrics tracking

### 3. Query Processing Flow
Sequence diagram showing:
- Query input
- Chunk retrieval from FAISS
- Context building
- Token counting
- LLM API calls
- Response generation
- Metrics recording

### 4. Token Counting Architecture
Shows token counting system:
- Input sources (documents, queries, responses)
- Token counter component (TokenTextSplitter, TikToken)
- Use cases (chunking, UI widget, query tracking)
- Storage and display

### 5. Component Class Diagram
UML class diagram showing:
- Class relationships
- Methods and attributes
- Dependencies between components

### 6. Data Flow with Tokens
Complete data flow including:
- Input processing
- Token counting at each stage
- Query processing
- Token tracking and analysis
- Output generation

### 7. Parser Fallback Strategy
Decision flow for parser selection:
- Auto mode logic
- PyMuPDF as primary parser
- Textract fallback for scanned PDFs
- Error handling and recovery

### 8. Complete System Flow
End-to-end flow showing:
- User actions
- Document processing
- Query processing
- Token management
- Metrics and display

## Notes

- All diagrams use valid Mermaid syntax
- Diagrams are color-coded for better visualization
- Each diagram focuses on a specific aspect of the system
- Diagrams can be combined or modified as needed





