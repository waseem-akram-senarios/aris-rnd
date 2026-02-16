FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies for ReportLab and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml /app/
COPY app /app/app

# Install dependencies
RUN pip install --upgrade pip && pip install -e .

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser

# Expose port
EXPOSE 8080

# Health check moved to docker-compose.yml

# Run the server
CMD ["intelycx-file-generator-mcp-server"]
