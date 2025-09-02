FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY config.py ./
COPY models.py ./
COPY chroma_utils.py ./
COPY auth.py ./
COPY utils.py ./

# Create artifacts directory and copy pre-trained model
RUN mkdir -p artifacts
COPY artifacts/risk_model.joblib artifacts/
COPY artifacts/alternatives.parquet artifacts/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
