"""Dataroma yatırımcı portföyü çekme. Yatırımcı kodları investors.json'da tutulur."""

import json
import logging
import os

import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.abspath(__file__))
_CODES_FILE = os.path.join(ROOT, "investors.json")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def _load_codes() -> dict:
    try:
        with open(_CODES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data:
            raise ValueError("bos ya da beklenmeyen format")
        return {str(k).lower(): str(v) for k, v in data.items()}
    except Exception as e:
        logging.error(f"investors.json okunamadi ({e}); yatirimci aramasi devre disi kalacak")
        return {}


INVESTOR_CODES = _load_codes()


def resolve_investor(name: str):
    return INVESTOR_CODES.get(name.strip().lower())


def get_dataroma_portfolio(investor_code: str):
    if not investor_code:
        return []

    url = f"https://www.dataroma.com/m/holdings.php?m={investor_code}"
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        response = session.get(url, timeout=15)
        response.raise_for_status()
        if not response.content:
            raise ValueError("bos yanit")

        soup = BeautifulSoup(response.content, "html.parser")
        stock_links = soup.find_all("a", href=lambda x: x and "/m/stock.php?sym=" in str(x))

        tickers = []
        for link in stock_links:
            try:
                ticker = link.get("href", "").split("sym=")[1].split("&")[0].strip().upper()
            except IndexError:
                continue  # beklenmeyen link formati; siteyi degistirmis olabilirler
            if ticker and len(ticker) <= 6 and ticker not in tickers:
                tickers.append(ticker)

        if not tickers:
            logging.warning(f"Dataroma sayfasi geldi ama hic sembol bulunamadi: {url} "
                            f"(site yapisi degismis olabilir)")
        return tickers[:15]

    except Exception as e:
        logging.error(f"Dataroma scrape hatasi ({url}): {e}")
        return []
