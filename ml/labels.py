import pandas as pd

HORIZON = 5        # işlem günü
THRESHOLD = 0.01   # %1 artış


def add_labels(df: pd.DataFrame, horizon: int = HORIZON, threshold: float = THRESHOLD) -> pd.DataFrame:
    df = df.copy()
    future_close = df["Close"].shift(-horizon)
    future_return = (future_close - df["Close"]) / df["Close"]
    df["future_return"] = future_return
    df["target"] = (future_return > threshold).astype("float")
    df.loc[future_close.isna(), "target"] = pd.NA
    return df


if __name__ == "__main__":
    from data import fetch_history
    from features import compute_features

    df = add_labels(compute_features(fetch_history("AAPL")))
    labeled = df["target"].dropna()
    print(f"Etiketli satır sayısı: {len(labeled)}")
    print(f"Pozitif oran (fiyat %1+ arttı): {labeled.mean():.2%}")
    print(df[["Close", "future_return", "target"]].tail(10))
