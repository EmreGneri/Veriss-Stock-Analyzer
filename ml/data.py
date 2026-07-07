import os
import time
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")

# API anahtarlari .env dosyasindan da okunabilsin (txt dosyalari yedek olarak kalir)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
except ImportError:
    pass

YAHOO_COOLDOWN = 600  # saniye; ilk hatadan sonra Yahoo bu süre atlanır
_yahoo_down_until = 0.0

PERIOD_DAYS = {
    "5d": 7, "1mo": 31, "3mo": 92, "6mo": 183,
    "1y": 366, "2y": 731, "5y": 1827, "10y": 3653, "max": None,
}


_probe_done = False


def yahoo_available() -> bool:
    """Yahoo kullanılabilir mi? Süreçteki ilk çağrıda 4 sn'lik hızlı bir sağlık
    yoklaması yapılır; Yahoo bloklu ise (429 vb.) 30-90 sn'lik yfinance zaman
    aşımlarını hiç yaşamadan doğrudan cooldown'a geçilir."""
    global _probe_done
    if time.time() < _yahoo_down_until:
        return False
    if not _probe_done:
        _probe_done = True
        try:
            r = requests.get(
                "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=1d&interval=1d",
                timeout=4,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code != 200:
                _mark_yahoo_down()
                return False
        except Exception:
            _mark_yahoo_down()
            return False
    return True


def _mark_yahoo_down():
    global _yahoo_down_until
    _yahoo_down_until = time.time() + YAHOO_COOLDOWN
    print(f"[WARN] Yahoo erisilemiyor; {YAHOO_COOLDOWN // 60} dk boyunca atlanacak.")


def _cache_path(symbol: str, period: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol.upper()}_{period}_{interval}_{date.today()}.csv")


def _slice_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    days = PERIOD_DAYS.get(period)
    if days is None:
        return df
    cutoff = pd.Timestamp(date.today() - timedelta(days=days))
    if df.index.tz is not None:
        cutoff = cutoff.tz_localize(df.index.tz)
    return df[df.index >= cutoff]


def _fetch_yahoo(symbol: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"Yahoo returned no data for '{symbol}'")
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index.name = "date"
    return df


def _twelvedata_key():
    key = os.environ.get("TWELVEDATA_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(ROOT_DIR, "twelvedata_key.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    return None


def _fetch_twelvedata(symbol: str, period: str, interval: str) -> pd.DataFrame:
    if interval != "1d":
        raise ValueError("Twelve Data fallback yalnizca gunluk (1d) veri destekler")
    key = _twelvedata_key()
    if not key:
        raise RuntimeError(
            "Twelve Data anahtari yok. https://twelvedata.com adresinden ucretsiz anahtar alip "
            "proje kokundeki twelvedata_key.txt dosyasina yapistirin."
        )

    days = PERIOD_DAYS.get(period)
    outputsize = 5000 if days is None else min(max(days, 30), 5000)
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": symbol, "interval": "1day",
                "outputsize": outputsize, "apikey": key},
        timeout=25,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "ok" or "values" not in data:
        raise ValueError(f"Twelve Data error: {data.get('message', data)}")

    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.set_index("datetime").sort_index()
    df.index.name = "date"
    df = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                            "close": "Close", "volume": "Volume"})
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Volume"] = df["Volume"].fillna(0)
    return _slice_period(df[["Open", "High", "Low", "Close", "Volume"]], period)


def fetch_history(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    path = _cache_path(symbol, period, interval)
    if os.path.exists(path):
        return pd.read_csv(path, index_col="date", parse_dates=["date"])

    errors = []
    df = None

    if yahoo_available():
        try:
            df = _fetch_yahoo(symbol, period, interval)
        except ValueError as e:
            # Yahoo cevap verdi ama sembol icin veri yok - kaynak saglikli.
            errors.append(str(e))
        except Exception as e:
            errors.append(f"Yahoo: {e}")
            _mark_yahoo_down()
    else:
        errors.append("Yahoo: cooldown (recent failure)")

    if df is None:
        try:
            df = _fetch_twelvedata(symbol, period, interval)
            print(f"[INFO] {symbol}: Twelve Data kullanildi (Yahoo devre disi).")
        except Exception as e:
            errors.append(f"TwelveData: {e}")

    if df is None or df.empty:
        raise ConnectionError(f"'{symbol}' icin veri alinamadi: " + " | ".join(errors))

    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(path)
    return df


def get_quote(symbol: str) -> dict:
    """Son iki günlük mumdan basit kotasyon üretir (kaynak zinciri + önbellek dahil)."""
    df = fetch_history(symbol, period="5d", interval="1d")
    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    return {
        "price": round(float(last["Close"]), 2),
        "previous_close": round(float(prev["Close"]), 2),
        "high": round(float(last["High"]), 2),
        "low": round(float(last["Low"]), 2),
        "volume": int(last["Volume"]),
    }


if __name__ == "__main__":
    data = fetch_history("AAPL")
    print(data.shape)
    print(data.tail())
    print(get_quote("AAPL"))
