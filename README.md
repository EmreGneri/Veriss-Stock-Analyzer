# Veriss Stock Analyzer

Stock analysis tool with a trained ML model behind it. Started as a GPT4All prompt
experiment, rewrote it with a proper pipeline: technical indicator features, model
training with chronological splits, backtesting with transaction costs, and both a
desktop (Tkinter) and web (FastAPI) interface on top of the same code.

## Features

- BUY / HOLD / SELL signal from a model trained on 5 years of daily data per symbol,
  with a written explanation of why the signal was produced
- Live price data with automatic failover: Yahoo Finance -> Twelve Data
- Company fundamentals (sector, market cap, P/E) with Yahoo -> Finnhub failover
- Famous investor portfolios scraped from Dataroma (Warren Buffett, Michael Burry...)
- Price charts, interactive on the web version (5D/1M/3M/6M/1Y)
- Optional local LLM commentary (GPT4All) if a .gguf model is present

## ML pipeline (`ml/`)

- `data.py` - price fetching with provider failover + daily disk cache
- `features.py` - 14 indicators (momentum, RSI, MACD, Bollinger z-score, volume ratios...).
  All ratio-based, no raw price levels, so the model can't memorize price regimes.
- `labels.py` - target: will close rise >=1% within 5 trading days
- `train.py` - RandomForest vs HistGradientBoosting, winner picked on a chronological
  validation slice (never on the test set). Train/test split is chronological too.
- `backtest.py` - strategy vs buy & hold with 0.1% transaction cost per trade,
  Sharpe ratio and max drawdown included
- `predict.py` - live signal. Thresholds are relative to the model's own recent
  probability median, because raw RF probabilities are uncalibrated and a fixed
  0.5-style cutoff produced SELL almost every day.

Honest results (AAPL test year): the strategy returned +8% vs +35% for buy & hold in
a strong bull year, but with a smaller max drawdown (-9% vs -14%) while being in the
market only ~20% of days. Daily-bar technical models don't beat buy & hold and this
project doesn't pretend otherwise - the point is the pipeline being leak-free and
honestly measured.

## Setup

```
git clone https://github.com/EmreGneri/Veriss-Stock-Analyzer.git
cd Veriss-Stock-Analyzer
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

API keys (both free, both optional but recommended):

- Twelve Data (price fallback): https://twelvedata.com -> paste key into `twelvedata_key.txt`
- Finnhub (fundamentals fallback): https://finnhub.io -> paste key into `finnhub_key.txt`

## Run

```
python ml/backtest.py AAPL         # train + backtest, saves chart to reports/
python stockanalyzer.py            # desktop app
run_web.bat                        # web app -> http://127.0.0.1:8000
```

First analysis of a new symbol trains a model, takes about a minute.

For LLM commentary: `pip install gpt4all` and drop a .gguf file into `models/`.

## Disclaimer

Educational project, not financial advice.

## License

MIT
