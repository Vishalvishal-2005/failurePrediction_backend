import joblib
import pandas as pd
from pathlib import Path
from utils import normalize_text, suggest_alternatives
from config import MODEL_PATH, ALT_INDEX_PATH

def _class_to_label(c: int) -> str:
    return ["Low Risk", "Medium Risk", "High Risk"][int(c)]

def _probas_to_percent_and_label(probas):
    best_idx = int(probas.argmax())
    risk_percent = float(probas[best_idx] * 100.0)
    label = _class_to_label(best_idx)
    return risk_percent, label

def main():
    # Load artifacts
    if not Path(MODEL_PATH).exists():
        print("❌ No trained model found. Run `python train.py` first.")
        return
    
    model = joblib.load(MODEL_PATH)
    alt_index = None
    if Path(ALT_INDEX_PATH).exists():
        alt_index = pd.read_parquet(ALT_INDEX_PATH)

    # Get user input
    device = input("Enter device name: ").strip()
    manuf = input("Enter manufacturer name: ").strip()

    row = {
        "manufacturer_name": normalize_text(manuf),
        "device_name": normalize_text(device),
    }
    X = pd.DataFrame([row])

    # Predict
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(X)[0]
    else:
        pred = int(model.predict(X)[0])
        probs = [0.2, 0.3, 0.5] if pred == 2 else [0.3, 0.5, 0.2] if pred == 1 else [0.7, 0.2, 0.1]

    risk_percent, risk_class = _probas_to_percent_and_label(pd.Series(probs).values)

    # Print results
    print("\n=== Risk Assessment ===")
    print(f"Device: {device}")
    print(f"Manufacturer: {manuf}")
    print(f"Risk Class: {risk_class}")
    print(f"Risk Percent: {risk_percent:.2f}%")

    if risk_class == "High Risk":
        print("⚠️  WARNING: Avoid purchase of this device.")

    # Alternatives
    if alt_index is not None:
        alts = suggest_alternatives(alt_index, manuf, device, top_k=5)
        if alts:
            print("\n✅ Suggested Alternatives:")
            for alt in alts:
                print(f" - {alt['manufacturer_name']} | {alt['device_name']} (Expected: {alt['expected_risk']})")

if __name__ == "__main__":
    main()
