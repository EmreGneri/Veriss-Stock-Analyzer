import logging
import time

import requests
from bs4 import BeautifulSoup

INVESTOR_CODES = {
    "warren buffett": "BRK",
    "bill gates": "GFT",
    "bill ackman": "psc",
    "charlie munger": "DJCO",
    "michael burry": "SAM",
    "ray dalio": "BRIDGE",
    "joel greenblatt": "GOTHAM",
    "tiger global": "TGM",
    "jeff bezos": "AMZN",
    "david einhorn": "GLRE",
    "seth klarman": "BAUPOST",
    "leon cooperman": "oa",
    "carl icahn": "ic",
    "david tepper": "AM",
    "bill miller": "LMM",
    "chuck akre": "AC",
    "mohnish pabrai": "PI",
    "guy spier": "aq",
    "li lu": "HC",
    "prem watsa": "FFH",
    "francis chou": "ca",
    "thomas russo": "GR",
    "mason hawkins": "LLPFX",
    "chase coleman": "TGM",
    "lee ainslie": "mc",
    "daniel loeb": "tp",
    "david abrams": "abc",
    "bruce berkowitz": "fairx",
    "glenn greenberg": "CCM",
    "pat dorsey": "DA",
    "christopher davis": "DAV",
    "john rogers": "CAAPX",
    "bill nygren": "oaklx",
    "dodge cox": "DODGX",
    "third avenue": "TA",
    "first eagle": "FE",
}


def resolve_investor(name: str):
    return INVESTOR_CODES.get(name.strip().lower())


def get_dataroma_portfolio(investor_code: str):
    if not investor_code:
        return []

    url = f"https://www.dataroma.com/m/holdings.php?m={investor_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

    try:
        time.sleep(2)
        session = requests.Session()
        session.headers.update(headers)
        response = session.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        stock_links = soup.find_all("a", href=lambda x: x and "/m/stock.php?sym=" in str(x))
        tickers = []
        for link in stock_links:
            href = link.get("href", "")
            if "sym=" in href:
                ticker = href.split("sym=")[1].split("&")[0].strip().upper()
                if ticker and len(ticker) <= 6 and ticker not in tickers:
                    tickers.append(ticker)
        return tickers[:15]

    except Exception as e:
        logging.error(f"Error scraping Dataroma: {e}")
        return []
