
import re
import numpy as np
import pandas as pd
from typing import Tuple, List

DEVICE_SPLIT_RE = re.compile(r"[\-_/|>]+")

def normalize_text(s: str) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = str(s).lower().strip()
    s = re.sub(r"[^a-z0-9\s\-_/|>]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def split_device_slug(slug: str) -> Tuple[str, str, str]:
    slug = normalize_text(slug)
    parts = [p for p in DEVICE_SPLIT_RE.split(slug) if p]
    country, manufacturer, device = "", "", ""
    if len(parts) >= 1: country = parts[0]
    if len(parts) >= 2: manufacturer = parts[1]
    if len(parts) >= 3: device = " ".join(parts[2:])
    return country, manufacturer, device

def ensure_device_manufacturer_cols(df: pd.DataFrame) -> pd.DataFrame:
    if "device_name" not in df.columns or "manufacturer_name" not in df.columns:
        device = df.get("Device", "")
        derived = [split_device_slug(x) for x in device.fillna("").astype(str)]
        ctry, manuf, dev = zip(*derived) if len(derived) else ([], [], [])
        if "Country" not in df.columns:
            df["Country"] = list(ctry)
        df["manufacturer_name"] = manuf
        df["device_name"] = dev
    for col in ["Country", "manufacturer_name", "device_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).map(normalize_text)
    return df

def action_to_risk_class(action_level: str) -> int:
    mapping = {
        "public recall": 2, "hospital/pharmacy/laboratory": 2, "healthcare professional": 2,
        "class i": 2, "class iii": 2, "mandatory": 2,
        "class ii": 1, "sponsor control": 1,
        "retail": 0, "wholesale": 0, "voluntary": 0, "unknown": 0
    }
    if action_level is None or (isinstance(action_level, float) and pd.isna(action_level)):
        return 1
    key = normalize_text(action_level)
    return mapping.get(key, 1)

def build_alternatives_index(df: pd.DataFrame, preds: np.ndarray) -> pd.DataFrame:
    out = df[["manufacturer_name", "device_name"]].copy()
    out["pred_risk_class"] = preds
    group = out.groupby(["manufacturer_name", "device_name"])["pred_risk_class"].mean().reset_index()
    group["avg_class"] = group["pred_risk_class"]
    group.drop(columns=["pred_risk_class"], inplace=True)
    return group

def suggest_alternatives(index_df: pd.DataFrame, manufacturer: str, device: str, top_k: int = 5) -> List[dict]:
    manufacturer = normalize_text(manufacturer)
    device = normalize_text(device)
    same_m = index_df[index_df["manufacturer_name"] == manufacturer]
    pool = same_m if len(same_m) >= 3 else index_df
    pool = pool.sort_values(["avg_class", "device_name"]).head(50)
    alts = []
    for _, row in pool.iterrows():
        if row["device_name"] != device:
            label = "Low Risk" if row["avg_class"] < 0.5 else "Medium Risk" if row["avg_class"] < 1.5 else "High Risk"
            alts.append({
                "manufacturer_name": row["manufacturer_name"],
                "device_name": row["device_name"],
                "expected_risk": label
            })
        if len(alts) >= top_k:
            break
    return alts
