
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, accuracy_score, f1_score
from sklearn.ensemble import GradientBoostingClassifier
import joblib

from config import DATASET_PATH, MODEL_PATH, ALT_INDEX_PATH, TEST_SIZE, RANDOM_STATE, CV_FOLDS
from utils import ensure_device_manufacturer_cols, action_to_risk_class, build_alternatives_index

def load_data():
    df = pd.read_csv(DATASET_PATH)
    df = ensure_device_manufacturer_cols(df)
    if "Action_Level" in df.columns:
        y = df["Action_Level"].map(action_to_risk_class).astype(int)
    elif "risk_class" in df.columns:
        y = df["risk_class"].astype(int)
    else:
        raise ValueError("Dataset must have 'Action_Level' or 'risk_class'.")
    X = df[["manufacturer_name", "device_name"]].copy()
    if "Country" in df.columns:
        X["Country"] = df["Country"]
    return X, y, df

def build_pipeline():
    text_union = ColumnTransformer([
        ("manuf", TfidfVectorizer(ngram_range=(3,5), analyzer="char_wb", min_df=2), "manufacturer_name"),
        ("device", TfidfVectorizer(ngram_range=(3,5), analyzer="char_wb", min_df=2), "device_name"),
    ], remainder="drop", verbose_feature_names_out=False)
    clf = GradientBoostingClassifier(random_state=RANDOM_STATE)
    model = Pipeline([
        ("features", text_union),
        ("clf", clf),
    ])
    return model

def main():
    X, y, raw = load_data()
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    model = build_pipeline()
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    cv_scores = cross_val_score(model, X_train, y_train, scoring="accuracy", cv=skf)
    print(f"CV accuracy: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    print("Test accuracy:", accuracy_score(y_test, y_pred))
    print("Weighted F1:", f1_score(y_test, y_pred, average="weighted"))
    print(classification_report(y_test, y_pred, target_names=["Low Risk","Medium Risk","High Risk"]))
    joblib.dump(model, MODEL_PATH)
    full_pred = model.predict(raw[["manufacturer_name","device_name"]])
    alt_index = build_alternatives_index(raw, full_pred)
    alt_index.to_parquet(ALT_INDEX_PATH, index=False)
    print(f"Saved model to {MODEL_PATH} and alternatives to {ALT_INDEX_PATH}")

if __name__ == "__main__":
    main()
