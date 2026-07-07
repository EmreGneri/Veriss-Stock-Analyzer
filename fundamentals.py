import logging
import os
import sys
from datetime import date

import requests
import yfinance as yf

ROOT = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.join(ROOT, "ml")
if ML_DIR not in sys.path:
    sys.path.insert(0, ML_DIR)

from data import yahoo_available

_cache = {}

DEFAULTS = {"name": None, "sector": "Unknown", "industry": "Unknown",
            "country": "Unknown", "market_cap": None, "pe": None}


def _finnhub_key():
    key = os.environ.get("FINNHUB_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(ROOT, "finnhub_key.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    return None


def _from_yahoo(symbol):
    info = yf.Ticker(symbol).info or {}
    if not info.get("shortName") and not info.get("longName") and not info.get("marketCap"):
        raise ValueError("Yahoo returned empty info")
    pe = info.get("trailingPE", info.get("forwardPE"))
    return {
        "name": info.get("shortName") or info.get("longName") or symbol,
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "country": info.get("country", "Unknown"),
        "market_cap": info.get("marketCap"),
        "pe": round(pe, 2) if pe and pe > 0 else None,
    }


def _from_finnhub(symbol):
    key = _finnhub_key()
    if not key:
        raise RuntimeError(
            "Finnhub anahtari yok. https://finnhub.io adresinden ucretsiz anahtar alip "
            "proje kokundeki finnhub_key.txt dosyasina yapistirin."
        )
    base = "https://finnhub.io/api/v1"

    prof = requests.get(f"{base}/stock/profile2",
                        params={"symbol": symbol, "token": key}, timeout=15).json()
    if not prof or not prof.get("name"):
        raise ValueError(f"Finnhub profile empty for {symbol}")

    pe = None
    try:
        met = requests.get(f"{base}/stock/metric",
                           params={"symbol": symbol, "metric": "all", "token": key},
                           timeout=15).json()
        pe = (met.get("metric") or {}).get("peTTM")
    except Exception:
        pass  # F/K opsiyonel; profil geldiyse devam

    cap = prof.get("marketCapitalization")  # Finnhub milyon USD cinsinden döner
    return {
        "name": prof.get("name") or symbol,
        "sector": prof.get("finnhubIndustry") or "Unknown",
        "industry": prof.get("finnhubIndustry") or "Unknown",
        "country": prof.get("country") or "Unknown",
        "market_cap": int(cap * 1e6) if cap else None,
        "pe": round(pe, 2) if pe and pe > 0 else None,
    }


def get_company_info(symbol: str) -> dict:
    symbol = symbol.upper()
    cache_key = (symbol, date.today())
    if cache_key in _cache:
        return _cache[cache_key]

    result = None
    if yahoo_available():
        try:
            result = _from_yahoo(symbol)
        except Exception as e:
            logging.warning(f"Yahoo info failed for {symbol}: {e}")

    if result is None:
        try:
            result = _from_finnhub(symbol)
        except Exception as e:
            logging.warning(f"Finnhub info failed for {symbol}: {e}")

    if result is None:
        result = dict(DEFAULTS, name=symbol)

    _cache[cache_key] = result
    return result


if __name__ == "__main__":
    import json
    sym = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(json.dumps(get_company_info(sym), indent=2))
