
import argparse
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)

from data import fetch_history
from features import FEATURE_COLUMNS, compute_features
from labels import add_labels

MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")

SIGNAL_DELTA = 0.05


def build_dataset(symbol: str, period: str = "5y") -> pd.DataFrame:
    df = fetch_history(symbol, period=period)
    df = compute_features(df)
    df = add_labels(df)
    df = df.dropna(subset=FEATURE_COLUMNS + ["target"])
    return df


def chronological_split(df: pd.DataFrame, train_ratio: float = 0.8):
    split_idx = int(len(df) * train_ratio)
    return df.iloc[:split_idx], df.iloc[split_idx:]


def _make_candidates():
    return {
        "RandomForest": RandomForestClassifier(
            n_estimators=400,
            max_depth=6,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
        "HistGradientBoosting": HistGradientBoostingClassifier(
            max_depth=3,
            learning_rate=0.05,
            max_iter=300,
            l2_regularization=1.0,
            early_stopping=False,
            class_weight="balanced",
            random_state=42,
        ),
    }


def train_model(symbol: str, period: str = "5y", save: bool = True):
    df = build_dataset(symbol, period)
    train_df, test_df = chronological_split(df)

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df["target"].astype(int)
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df["target"].astype(int)

    fit_idx = int(len(train_df) * 0.85)
    fit_df, val_df = train_df.iloc[:fit_idx], train_df.iloc[fit_idx:]

    print(f"\n--- {symbol}: model seçimi (doğrulama: son {len(val_df)} eğitim günü) ---")
    best_name, best_score = None, -1.0
    candidates = _make_candidates()
    for name, candidate in candidates.items():
        candidate.fit(fit_df[FEATURE_COLUMNS], fit_df["target"].astype(int))
        val_preds = candidate.predict(val_df[FEATURE_COLUMNS])
        score = balanced_accuracy_score(val_df["target"].astype(int), val_preds)
        print(f"  {name}: dogrulama balanced accuracy = {score:.3f}")
        if score > best_score:
            best_name, best_score = name, score

    print(f"  Secilen model: {best_name}")
    model = _make_candidates()[best_name]
    model.fit(X_train, y_train)

   
    train_probas = model.predict_proba(X_train)[:, 1]
    proba_center = float(np.median(train_probas))

    preds = model.predict(X_test)
    metrics = {
        "symbol": symbol,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "accuracy": accuracy_score(y_test, preds),
        "precision": precision_score(y_test, preds, zero_division=0),
        "recall": recall_score(y_test, preds, zero_division=0),
        "f1": f1_score(y_test, preds, zero_division=0),
        "baseline_positive_rate": y_test.mean(),
        "proba_center": proba_center,
        "model_name": best_name,
    }

    print(f"\n=== {symbol} | eğitim {len(X_train)} gün, test {len(X_test)} gün ===")
    print(classification_report(y_test, preds, zero_division=0))
    print(f"Test setinde pozitif sınıf oranı (naif baseline): {y_test.mean():.2%}")
    print(f"Model olasılık merkezi (train medyanı, bilgi amaçlı): {proba_center:.3f}")

    if hasattr(model, "feature_importances_"):
        importances = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS)
        print("\nÖznitelik önemleri:")
        print(importances.sort_values(ascending=False).to_string())

    if save:
        os.makedirs(MODELS_DIR, exist_ok=True)
        path = os.path.join(MODELS_DIR, f"{symbol.upper()}_rf.joblib")
        joblib.dump({"model": model, "features": FEATURE_COLUMNS, "metrics": metrics}, path)
        print(f"\nModel kaydedildi: {path}")

    return model, metrics, test_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hisse yönü tahmini için RandomForest eğit")
    parser.add_argument("symbol", nargs="?", default="AAPL")
    parser.add_argument("--period", default="5y")
    args = parser.parse_args()
    train_model(args.symbol, args.period)
