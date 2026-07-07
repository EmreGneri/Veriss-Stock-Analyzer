"""Veriss web arayüzü - FastAPI backend.

Masaüstü uygulamasıyla aynı ml/ paketini kullanır. Çalıştırma (proje kökünden):

    venv\\Scripts\\python.exe -m uvicorn web.main:app --port 8000

Sonra tarayıcıda: http://127.0.0.1:8000
"""

import glob
import logging
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))

import yfinance as yf
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from investors import resolve_investor, get_dataroma_portfolio
from data import fetch_history, get_quote, yahoo_available
from fundamentals import get_company_info

try:
    from predict import get_ml_signal
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logging.warning(f"ML module unavailable: {e}")

try:
    from gpt4all import GPT4All
    GPT4ALL_AVAILABLE = True
except ImportError:
    GPT4ALL_AVAILABLE = False

app = FastAPI(title="Veriss Stock Analyzer API")

_llm = None
_llm_lock = threading.Lock()


def _find_llm_model_path():
    candidates = sorted(glob.glob(os.path.join(ROOT, "models", "*.gguf")))
    return candidates[0] if candidates else None


def _get_llm():
    """LLM'i ilk istekte bir kez yükler; eşzamanlı istekleri kilitle sıralar."""
    global _llm
    with _llm_lock:
        if _llm is None:
            path = _find_llm_model_path()
            if not path:
                raise RuntimeError("No .gguf model found in models/")
            try:
                _llm = GPT4All(path, allow_download=False, device="gpu")
            except Exception:
                _llm = GPT4All(path, allow_download=False, device="cpu")
        return _llm


def _quote(symbol: str) -> dict:
    """Kotasyon: ml/data.py'daki çok kaynaklı zincir (Yahoo -> Twelve Data) + önbellek."""
    try:
        return get_quote(symbol)
    except Exception as e:
        logging.error(f"quote fetch failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Data unavailable for {symbol}: {e}")


@app.get("/api/health")
def health():
    return {
        "ml_available": ML_AVAILABLE,
        "llm_model_present": GPT4ALL_AVAILABLE and _find_llm_model_path() is not None,
    }


@app.get("/api/analyze/{query}")
def analyze(query: str, llm: bool = False):
    investor_code = resolve_investor(query)
    if investor_code:
        return _portfolio_response(query, investor_code)

    symbol = query.strip().upper()
    quote = _quote(symbol)

    # Şirket profili: Yahoo müsaitse Yahoo, değilse Finnhub (fundamentals.py zinciri)
    company = get_company_info(symbol)

    change = quote["price"] - quote["previous_close"]
    change_pct = (change / quote["previous_close"]) * 100 if quote["previous_close"] else 0.0

    result = {
        "type": "stock",
        "symbol": symbol,
        "company": {
            "name": company["name"] or symbol,
            "sector": company["sector"],
            "industry": company["industry"],
            "country": company["country"],
            "market_cap": company["market_cap"],
        },
        "price": {**quote, "change": round(change, 2), "change_pct": round(change_pct, 2)},
        "ml_signal": None,
        "commentary": None,
    }

    if ML_AVAILABLE:
        try:
            result["ml_signal"] = get_ml_signal(symbol)
        except Exception as e:
            logging.error(f"ML signal failed for {symbol}: {e}")
            result["ml_signal"] = {"error": str(e)}

    if llm and GPT4ALL_AVAILABLE and _find_llm_model_path():
        try:
            prompt = (
                "You are a financial analyst. Write a short, plain-language analysis "
                "of this stock. Be concise, avoid jargon.\n\n"
                f"Stock: {symbol}\n"
                f"Price: ${quote['price']:.2f}\n"
                f"Change: {change_pct:+.1f}%\n"
                f"High: ${quote['high']:.2f}\nLow: ${quote['low']:.2f}\n\n"
                "Short analysis and a one-word stance (BUY/HOLD/SELL):"
            )
            model = _get_llm()
            with _llm_lock:
                text = model.generate(prompt, max_tokens=200, temp=0.1,
                                      top_p=0.8, repeat_penalty=1.05).strip()
            result["commentary"] = text if len(text) >= 10 else None
        except Exception as e:
            logging.error(f"LLM commentary failed: {e}")

    return result


def _portfolio_response(name: str, investor_code: str):
    tickers = get_dataroma_portfolio(investor_code)
    if not tickers:
        raise HTTPException(status_code=404, detail=f"Portfolio not found for {name}")

    holdings = []
    for ticker in tickers[:10]:
        try:
            q = _quote(ticker)
            change_pct = ((q["price"] - q["previous_close"]) / q["previous_close"]) * 100
            holdings.append({"symbol": ticker, "price": q["price"],
                             "change_pct": round(change_pct, 2)})
        except Exception:
            holdings.append({"symbol": ticker, "price": None, "change_pct": None})

    return {"type": "portfolio", "investor": name.title(), "holdings": holdings}


@app.get("/api/history/{symbol}")
def history(symbol: str, period: str = "1mo"):
    if period not in {"5d", "1mo", "3mo", "6mo", "1y"}:
        raise HTTPException(status_code=400, detail="period must be one of 5d,1mo,3mo,6mo,1y")
    try:
        hist = fetch_history(symbol.upper(), period=period)
    except Exception as e:
        logging.error(f"history fetch failed for {symbol}: {e}")
        raise HTTPException(status_code=502, detail=f"Data unavailable for {symbol}: {e}")
    return {
        "symbol": symbol.upper(),
        "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
        "close": [round(float(v), 2) for v in hist["Close"]],
        "volume": [int(v) for v in hist["Volume"]],
    }


@app.get("/api/sample-portfolio")
def sample_portfolio():
    tickers = get_dataroma_portfolio("BRK") or [
        "AAPL", "AXP", "BAC", "KO", "CVX", "OXY", "MCO", "KHC", "CB", "DVA", "V", "AMZN"
    ]
    rows = []
    # 8 hisse: Twelve Data ücretsiz planının dakikalık limiti (8 istek/dk) ile uyumlu.
    for ticker in tickers[:8]:
        # Fiyat: çok kaynaklı zincir (Yahoo yoksa Twelve Data). P/E ve piyasa
        # değeri yalnızca Yahoo'dan gelir; Yahoo kapalıyken N/A kalır.
        price = None
        try:
            price = get_quote(ticker)["price"]
        except Exception as e:
            logging.warning(f"sample portfolio quote failed for {ticker}: {e}")

        fund = get_company_info(ticker)
        cap = fund["market_cap"]

        rows.append({
            "symbol": ticker,
            "name": (fund["name"] or ticker)[:24],
            "price": price,
            "pe": fund["pe"],
            "market_cap_b": round(cap / 1e9, 2) if cap and cap >= 1e9 else None,
        })
    return {"holdings": rows}


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"),
                           html=True), name="static")
