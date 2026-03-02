"""
Multimodal (vision) PDF parsing + page-grounded RAG.

Design:
- Parse PDFs per page using PyMuPDF rendering -> vision model extracts text.
- Store per-page text with metadata {source_pdf, page}.
- Build a FAISS index (local) for retrieval.
- Answer with citations that include page numbers deterministically.
"""