FROM python:3.9-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py . 
COPY config.py .
COPY models.py .
COPY chroma_utils.py .
COPY auth.py .
COPY utils.py .

RUN mkdir -p artifacts
COPY artifacts/risk_model.joblib artifacts/
COPY artifacts/alternatives.parquet artifacts/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
