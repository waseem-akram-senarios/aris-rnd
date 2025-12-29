# 🔄 OCRmyPDF Workflow Examples

**Real-world workflows for OCR integration with ARIS RAG System**

---

## Workflow 1: Basic Scanned PDF Processing

**Scenario:** Process a scanned invoice for RAG queries

### Step 1: Upload with OCRmyPDF Parser

```bash
curl -X POST "http://44.221.84.58:8500/documents" \
  -F "file=@scanned_invoice.pdf" \
  -F "parser_preference=ocrmypdf"
```

### Step 2: Query the Document

```bash
curl -X POST "http://44.221.84.58:8500/query?type=text" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the invoice total?", "k": 5}'
```

---

## Workflow 2: Multi-Language Document

**Scenario:** Process a bilingual contract (English + Spanish)

### Step 1: Install Spanish Language Pack

```bash
sudo apt-get install tesseract-ocr-spa -y
```

### Step 2: Preprocess with Multi-Language OCR

```bash
curl -X POST "http://44.221.84.58:8500/documents/ocr-preprocess" \
  -F "file=@bilingual_contract.pdf" \
  -F "languages=eng+spa" \
  --output ocr_contract.pdf
```

---

## Workflow 3: Hybrid OCR + Fast Parsing

**Scenario:** OCR accuracy + PyMuPDF speed

```bash
curl -X POST "http://44.221.84.58:8500/documents" \
  -F "file=@mixed_document.pdf" \
  -F "parser_preference=pymupdf" \
  -F "use_ocr_preprocessing=true"
```

---

## Workflow 4: RAG Pipeline with OCR

Complete pipeline from scanned PDF to RAG queries:

```
[Scanned PDF] → [OCRmyPDF] → [Text Extraction] → [Chunking] → [Embeddings] → [Vector DB] → [RAG Queries]
```

---

**See OCR_INTEGRATION_GUIDE.md for complete documentation**
