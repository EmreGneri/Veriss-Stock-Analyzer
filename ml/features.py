import numpy as np
import pandas as pd

# hepsi orana/yüzdeye dayalı, ham fiyat seviyesi yok
FEATURE_COLUMNS = [
    "daily_return", "momentum_5", "momentum_10", "momentum_20",
    "sma_ratio", "dist_high_60", "rsi_14",
    "macd", "macd_hist", "bb_z",
    "volatility_10", "vol_ratio_10_30",
    "volume_change", "volume_ratio",
]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"]

    df["daily_return"] = close.pct_change()
    df["momentum_5"] = close.pct_change(5)
    df["momentum_10"] = close.pct_change(10)
    df["momentum_20"] = close.pct_change(20)

    # sma_5/sma_20 arayüzde gösteriliyor, feature olarak sadece oran giriyor
    df["sma_5"] = close.rolling(window=5).mean()
    df["sma_20"] = close.rolling(window=20).mean()
    df["sma_ratio"] = df["sma_5"] / df["sma_20"]

    df["dist_high_60"] = close / close.rolling(60).max() - 1

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df["rsi_14"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_raw = (ema12 - ema26) / close
    df["macd"] = macd_raw
    df["macd_hist"] = macd_raw - macd_raw.ewm(span=9, adjust=False).mean()

    std20 = close.rolling(20).std()
    df["bb_z"] = (close - df["sma_20"]) / std20

    df["volatility_10"] = df["daily_return"].rolling(window=10).std()
    df["vol_ratio_10_30"] = (
        df["daily_return"].rolling(10).std() / df["daily_return"].rolling(30).std()
    )

    df["volume_change"] = df["Volume"].pct_change()
    df["volume_ratio"] = df["Volume"] / df["Volume"].rolling(20).mean()

    # 0'a bölmelerden gelen inf'leri NaN yap, dropna toplasın
    df = df.replace([np.inf, -np.inf], np.nan)
    return df


if __name__ == "__main__":
    from data import fetch_history

    raw = fetch_history("AAPL")
    features = compute_features(raw)

    missing = [c for c in FEATURE_COLUMNS if c not in features.columns]
    if missing:
        print(f"[HATA] Eksik sutunlar: {missing}")
    else:
        print("[OK] Tum oznitelik sutunlari mevcut")
        print(features[FEATURE_COLUMNS].tail(5).T)
