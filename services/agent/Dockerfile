FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Generate self-signed TLS certs for local TLS usage (optional)
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /certs \
 && openssl req -x509 -newkey rsa:2048 -keyout /certs/server.key -out /certs/server.crt -days 3650 -nodes -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

COPY pyproject.toml /app/
COPY app /app/app
RUN pip install --upgrade pip && pip install -e .

EXPOSE 443
CMD ["aris-agent"]


