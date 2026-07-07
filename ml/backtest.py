import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TRANSACTION_COST = 0.001  

from features import FEATURE_COLUMNS
from train import train_model, SIGNAL_DELTA

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


def run_backtest(symbol: str, period: str = "5y", save_plot: bool = True):
    model, metrics, test_df = train_model(symbol, period, save=True)

    test_df = test_df.copy()

    probas = pd.Series(model.predict_proba(test_df[FEATURE_COLUMNS])[:, 1],
                       index=test_df.index)
    center_series = probas.rolling(90, min_periods=30).median().shift(1)
    test_df["signal"] = (probas >= center_series + SIGNAL_DELTA).astype(int)

    test_df["next_day_return"] = test_df["Close"].pct_change().shift(-1)
    test_df = test_df.dropna(subset=["next_day_return"])

    position_change = test_df["signal"].diff().abs()
    position_change.iloc[0] = test_df["signal"].iloc[0]
    test_df["strategy_return"] = (
        test_df["signal"] * test_df["next_day_return"] - TRANSACTION_COST * position_change
    )
    test_df["strategy_equity"] = (1 + test_df["strategy_return"]).cumprod()
    test_df["buyhold_equity"] = (1 + test_df["next_day_return"]).cumprod()

    strat_total = test_df["strategy_equity"].iloc[-1] - 1
    bh_total = test_df["buyhold_equity"].iloc[-1] - 1
    days_in_market = int(test_df["signal"].sum())
    n_trades = int(position_change.sum())

    def annualized_sharpe(returns):
        return float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0.0

    strat_sharpe = annualized_sharpe(test_df["strategy_return"])
    bh_sharpe = annualized_sharpe(test_df["next_day_return"])
    equity = test_df["strategy_equity"]
    max_drawdown = float((equity / equity.cummax() - 1).min())
    bh_equity = test_df["buyhold_equity"]
    bh_drawdown = float((bh_equity / bh_equity.cummax() - 1).min())

    print(f"\n=== BACKTEST: {symbol} (test dönemi: {test_df.index[0].date()} → {test_df.index[-1].date()}) ===")
    print(f"                          Strateji      Buy & Hold")
    print(f"Toplam getiri           : {strat_total:+9.2%}    {bh_total:+9.2%}")
    print(f"Sharpe (yıllık)         : {strat_sharpe:9.2f}    {bh_sharpe:9.2f}")
    print(f"Maksimum düşüş          : {max_drawdown:9.2%}    {bh_drawdown:9.2%}")
    print(f"Piyasada kalınan gün    : {days_in_market}/{len(test_df)}  |  işlem sayısı: {n_trades}  |  maliyet: %{TRANSACTION_COST*100:.1f}/işlem")

    if save_plot:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(test_df.index, test_df["strategy_equity"], label="Model stratejisi", linewidth=2)
        ax.plot(test_df.index, test_df["buyhold_equity"], label="Buy & Hold", linewidth=2, alpha=0.8)
        ax.set_title(f"{symbol} — Model sinyali vs Buy & Hold (test dönemi)")
        ax.set_ylabel("Kümülatif getiri (1 = başlangıç)")
        ax.legend()
        ax.grid(alpha=0.3)
        fig.tight_layout()
        out_path = os.path.join(REPORTS_DIR, f"{symbol.upper()}_backtest.png")
        fig.savefig(out_path, dpi=120)
        print(f" Grafik kaydedildi: {out_path}")

    return {
        "strategy_return": strat_total,
        "buyhold_return": bh_total,
        "days_in_market": days_in_market,
        "test_days": len(test_df),
        **metrics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Model sinyalini buy & hold ile karşılaştır")
    parser.add_argument("symbol", nargs="?", default="AAPL")
    parser.add_argument("--period", default="5y")
    args = parser.parse_args()
    run_backtest(args.symbol, args.period)
