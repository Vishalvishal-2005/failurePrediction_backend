# Use a supported Python base image
#FROM python:3.9-slim-bullseye
FROM python:3.10-slim-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python application files
COPY *.py ./

# Create artifacts folder and copy pre-trained model files
RUN mkdir -p artifacts
COPY artifacts/risk_model.joblib artifacts/
COPY artifacts/alternatives.parquet artifacts/

# Expose the port your app runs on
EXPOSE 8000

# Healthcheck to monitor container status
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
