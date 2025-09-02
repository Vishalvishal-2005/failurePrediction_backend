
# Hospital Device Risk - Quickstart

1) Put/verify your dataset at: hospital-device-risk/realistic_risk_data.csv
2) Train:
   python train.py
3) Run API locally:
   uvicorn service:app --reload
4) Docker:
   docker build -t device-risk .
   docker run -p 8000:8000 device-risk

Endpoints:
- POST /predict
  {"device_name":"emerald cleanser","manufacturer_name":"dyn"}

Artifacts saved under artifacts/
