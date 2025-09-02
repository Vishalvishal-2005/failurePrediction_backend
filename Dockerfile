# Use Python slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Copy application code
COPY --chown=appuser:appuser *.py ./
COPY --chown=appuser:appuser config.py ./
COPY --chown=appuser:appuser models.py ./
COPY --chown=appuser:appuser utils.py ./
COPY --chown=appuser:appuser chroma_utils.py ./
COPY --chown=appuser:appuser auth.py ./

# Copy pre-trained model artifacts
RUN mkdir -p artifacts && chown appuser:appuser artifacts
COPY --chown=appuser:appuser artifacts/risk_model.joblib artifacts/
COPY --chown=appuser:appuser artifacts/alternatives.parquet artifacts/

# Switch to non-root user
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Healthcheck for Render
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run FastAPI
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
