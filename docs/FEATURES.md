# ARIS RAG Features

## Source Referencing & Citations

ARIS RAG now includes comprehensive source referencing that shows exactly where information in answers comes from, whether it's text or images.

### How It Works

1. **Metadata Capture**: During parsing, the system captures:
   - Page numbers for each text block
   - Bounding box coordinates for text blocks (PyMuPDF)
   - Image references and positions
   - Section headers and document structure

2. **Metadata Preservation**: Throughout chunking and embedding:
   - Page numbers are preserved in each chunk
   - Character offsets track exact text positions
   - Source document information is maintained

3. **Citation Generation**: When answering questions:
   - Each retrieved chunk includes citation metadata
   - Page numbers are extracted and displayed
   - Text snippets show the exact source content

4. **UI Display**: In the Streamlit interface:
   - Answers show citation references like `[1]`, `[2]`, etc.
   - A "Sources & Citations" panel displays:
     - Source document name
     - Page number (if available)
     - Text snippet from the source
     - Full context chunk

### Citation Format

Citations are displayed in the following format:

```
[1] document.pdf - Page 5
[2] document.pdf - Page 12
```

Each citation includes:
- **ID**: Sequential citation number
- **Source**: Document filename
- **Page**: Page number where the information was found
- **Snippet**: Preview of the source text (first 200 characters)

### Supported Parsers

- **PyMuPDF**: Captures page numbers, text block bounding boxes, and image positions
- **Docling**: Captures page numbers and document structure
- **Textract**: (Metadata support coming soon)

### Example Usage

1. Upload a PDF document
2. Process it using any supported parser
3. Ask a question about the document
4. View the answer with citation markers
5. Expand "Sources & Citations" to see detailed source information

### Technical Details

- **Page Tracking**: Page numbers are extracted from parser metadata and preserved through chunking
- **Character Offsets**: Each chunk tracks its position in the original document (`start_char`, `end_char`)
- **Metadata Storage**: All citation metadata is stored in the vector store (FAISS or OpenSearch)
- **Retrieval**: Citations are automatically included when chunks are retrieved for answering questions

### Future Enhancements

- Inline citation markers within answer text (currently shown below answer)
- Image thumbnail previews for image-based citations
- Clickable citations that jump to source location
- Export citations in various formats (BibTeX, APA, etc.)

