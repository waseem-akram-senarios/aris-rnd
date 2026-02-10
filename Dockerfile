# Multi-stage Dockerfile for ARIS Microservices
# Stage 1: Builder - Install dependencies
FROM python:3.10-slim AS builder

# Set working directory
WORKDIR /build

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file from the new shared location
COPY shared/config/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime - Containerized microservices
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install runtime system dependencies for PDF/OCR
# Install Tesseract with multilingual language packs for OCR support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgthread-2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    tesseract-ocr-por \
    tesseract-ocr-rus \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    tesseract-ocr-chi-sim \
    tesseract-ocr-ara \
    ghostscript \
    qpdf \
    unpaper \
    pngquant \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Environment variables
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Copy application structure
COPY services/ ./services/
COPY shared/ ./shared/
COPY storage/ ./storage/
COPY scripts/ ./scripts/
COPY metrics/ ./metrics/
COPY vectorstores/ ./vectorstores/
COPY api/ ./api/
COPY pages/ ./pages/
COPY .streamlit/ ./.streamlit/
COPY app.py .
COPY mcp_server.py .

# Copy and set entrypoint
COPY scripts/docker_entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create persistent directories
RUN mkdir -p /app/vectorstore /app/data /app/logs

# Default ports (can be overridden)
EXPOSE 8500 8501 8502 8503

# The entrypoint script uses the SERVICE_TYPE env var to start the correct service
ENTRYPOINT ["/app/entrypoint.sh"]
