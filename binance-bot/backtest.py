"""
Simple backtester to evaluate strategy performance on historical data.
Usage: python backtest.py --symbol BTCUSDT --interval 15m --days 30
"""
import argparse
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategy import analyze, calculate_indicators, Signal
from config import config


def fetch_historical(symbol: str, interval: str, days: int) -> pd.DataFrame:
    limit = min(1000, days * 24 * (60 // int(interval.replace("m","").replace("h","60"))))
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    klines = resp.json()
    df = pd.DataFrame(klines, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_vol","trades","taker_buy_base","taker_buy_quote","ignore"
    ])
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def run_backtest(symbol: str, interval: str, days: int):
    print(f"\nBacktesting {symbol} on {interval} | {days} days of data")
    df = fetch_historical(symbol, interval, days)
    df = calculate_indicators(df)
    print(f"Total candles: {len(df)}")

    capital = 1000.0
    initial = capital
    position = None
    trades = []

    for i in range(50, len(df)):
        window = df.iloc[:i+1]
        result = analyze(window, symbol)
        price = result.price

        if position is None and result.signal == Signal.BUY:
            sl = price * (1 - config.STOP_LOSS_PERCENT / 100)
            tp = price * (1 + config.TAKE_PROFIT_PERCENT / 100)
            qty = (capital * config.RISK_PER_TRADE_PERCENT / 100) / abs(price - sl)
            qty = min(qty, (capital * 0.95) / price)
            position = {"entry": price, "qty": qty, "sl": sl, "tp": tp, "bar": i}

        elif position:
            should_exit = False
            exit_reason = ""
            if price <= position["sl"]:
                should_exit, exit_reason = True, "STOP_LOSS"
            elif price >= position["tp"]:
                should_exit, exit_reason = True, "TAKE_PROFIT"
            elif result.signal == Signal.SELL:
                should_exit, exit_reason = True, "SELL_SIGNAL"

            if should_exit:
                pnl = (price - position["entry"]) * position["qty"]
                capital += pnl
                pnl_pct = (price - position["entry"]) / position["entry"] * 100
                trades.append({"entry": position["entry"], "exit": price, "pnl_pct": pnl_pct, "reason": exit_reason})
                position = None

    # Results
    if not trades:
        print("No trades generated.")
        return

    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]

    print(f"\n{'='*50}")
    print(f"Total Trades   : {len(trades)}")
    print(f"Win Rate       : {len(wins)/len(trades)*100:.1f}%")
    print(f"Total Return   : {(capital-initial)/initial*100:+.2f}%")
    print(f"Avg PnL/Trade  : {np.mean(pnls):+.2f}%")
    print(f"Best Trade     : {max(pnls):+.2f}%")
    print(f"Worst Trade    : {min(pnls):+.2f}%")
    print(f"Final Capital  : ${capital:.2f} (started ${initial:.2f})")
    print(f"{'='*50}\n")

    print("Last 10 trades:")
    for t in trades[-10:]:
        icon = "✓" if t["pnl_pct"] > 0 else "✗"
        print(f"  {icon} Entry={t['entry']:.2f} Exit={t['exit']:.2f} PnL={t['pnl_pct']:+.2f}% [{t['reason']}]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()
    run_backtest(args.symbol, args.interval, args.days)
