import os

import joblib
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(__file__), "saved_models")


def _model_path(symbol: str) -> str:
    return os.path.join(MODELS_DIR, f"{symbol.upper()}_rf.joblib")


def get_ml_signal(symbol: str, period: str = "5y") -> dict:
    from data import fetch_history
    from features import FEATURE_COLUMNS, compute_features
    from train import train_model

    path = _model_path(symbol)
    if os.path.exists(path):
        bundle = joblib.load(path)
    else:
        train_model(symbol, period, save=True)
        bundle = joblib.load(path)

    model = bundle["model"]
    metrics = bundle["metrics"]

    df = compute_features(fetch_history(symbol, period="6mo"))
    features_window = df[FEATURE_COLUMNS].dropna()
    latest = features_window.iloc[[-1]]

    proba_up = float(model.predict_proba(latest)[0][1])

    window_probas = model.predict_proba(features_window)[:, 1]
    center = float(np.median(window_probas[:-1])) if len(window_probas) > 1 else float(window_probas[0])

    from train import SIGNAL_DELTA
    if proba_up >= center + SIGNAL_DELTA:
        signal = "BUY"
    elif proba_up <= center - SIGNAL_DELTA:
        signal = "SELL"
    else:
        signal = "HOLD"

    rsi = float(latest["rsi_14"].iloc[0])
    sma_ratio = float(latest["sma_ratio"].iloc[0])
    volatility = float(latest["volatility_10"].iloc[0])

    return {
        "symbol": symbol.upper(),
        "signal": signal,
        "probability_up": proba_up,
        "proba_baseline": center,
        "model_name": metrics.get("model_name", "RandomForest"),
        "as_of": str(latest.index[-1].date()),
        "rsi_14": rsi,
        "sma_ratio": sma_ratio,
        "model_test_accuracy": metrics["accuracy"],
        "model_test_f1": metrics["f1"],
        "explanation": _build_explanation(signal, proba_up, center, rsi, sma_ratio,
                                          volatility, metrics["accuracy"]),
    }


def _build_explanation(signal, proba_up, center, rsi, sma_ratio, volatility, accuracy):
    """Sinyalin gerekçesini gösterge değerlerinden kısa düzyazıya çevirir."""
    pct = proba_up * 100
    base = center * 100
    diff = pct - base
    parts = []

    if signal == "BUY":
        parts.append(
            f"The model estimates a {pct:.0f}% probability that the price rises at least 1% "
            f"within the next 5 trading days. That is {diff:.0f} points above this model's own "
            f"typical estimate of {base:.0f}%, which is what triggers the BUY signal."
        )
    elif signal == "SELL":
        parts.append(
            f"The model estimates a {pct:.0f}% probability that the price rises at least 1% "
            f"within the next 5 trading days. That is {abs(diff):.0f} points below this model's "
            f"own typical estimate of {base:.0f}%, which is what triggers the SELL signal."
        )
    else:
        parts.append(
            f"The model estimates a {pct:.0f}% probability of a 1%+ rise within the next 5 trading "
            f"days, close to this model's own typical estimate of {base:.0f}% - no clear edge "
            f"either way, hence HOLD."
        )

    diff = (sma_ratio - 1) * 100
    if sma_ratio >= 1.01:
        parts.append(
            f"Short-term momentum is positive: the 5-day average trades "
            f"{diff:.1f}% above the 20-day average."
        )
    elif sma_ratio <= 0.99:
        parts.append(
            f"Short-term momentum is weak: the 5-day average sits "
            f"{abs(diff):.1f}% below the 20-day average."
        )
    else:
        parts.append(
            "The 5-day and 20-day averages are nearly equal, showing no clear "
            "momentum in either direction."
        )

    if rsi >= 70:
        parts.append(
            f"RSI(14) at {rsi:.0f} indicates overbought conditions, which typically "
            f"raises the risk of a pullback."
        )
    elif rsi <= 30:
        parts.append(
            f"RSI(14) at {rsi:.0f} indicates oversold conditions, which often "
            f"precedes a rebound."
        )
    else:
        parts.append(f"RSI(14) at {rsi:.0f} is in neutral territory, neither overbought nor oversold.")

    vol_pct = volatility * 100
    if vol_pct >= 2.5:
        parts.append(f"Recent daily volatility is elevated at about {vol_pct:.1f}%, so moves in either direction can be sharp.")
    elif vol_pct >= 1.2:
        parts.append(f"Recent daily volatility is moderate at about {vol_pct:.1f}%.")
    else:
        parts.append(f"Recent daily volatility is low at about {vol_pct:.1f}%, suggesting relatively calm trading.")

    parts.append(
        f"Keep in mind the model's test accuracy is {accuracy * 100:.0f}%, so treat this as one "
        f"weak statistical input rather than trading advice."
    )
    return " ".join(parts)


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    result = get_ml_signal(symbol)
    print(f"\n=== ML SİNYALİ: {result['symbol']} (veri tarihi: {result['as_of']}) ===")
    print(f"Sinyal            : {result['signal']}")
    print(f"Yükseliş olasılığı: {result['probability_up']:.1%}")
    print(f"RSI(14)           : {result['rsi_14']:.1f}")
    print(f"SMA5/SMA20        : {result['sma_ratio']:.3f}")
    print(f"Model test doğruluğu: {result['model_test_accuracy']:.2%} | F1: {result['model_test_f1']:.2f}")
