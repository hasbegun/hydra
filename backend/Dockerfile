# Hydra Backend API - Lightweight FastAPI service
# Garak now runs in its own container (see Dockerfile.garak)

FROM python:3.11-slim

WORKDIR /app

# Minimal system dependencies (no Rust, no git - garak is in its own container)
# libpq5 is the PostgreSQL client lib needed by psycopg2-binary at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install backend dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Reports directory (shared volume mount point, read-only)
RUN mkdir -p /data/garak_reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HOST=0.0.0.0
ENV PORT=8888
ENV LOG_LEVEL=INFO
ENV GARAK_REPORTS_DIR=/data/garak_reports
ENV GARAK_SERVICE_URL=http://garak:9090

# Expose port
EXPOSE 8888

# Health check (faster start since no garak to initialize)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/health')" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888"]
