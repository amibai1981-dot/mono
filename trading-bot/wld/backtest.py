"""
Simple Grid + RSI Backtester on historical OHLCV data (CSV or list).
Usage:
    python backtest.py --symbol WLDUSDT --days 60
"""
import argparse
import csv
import logging
from binance.client import Client

import config
from grid_manager import GridManager
from indicators import rsi, ema

logging.basicConfig(level=logging.WARNING)


def fetch_klines(symbol: str, days: int) -> list[dict]:
    client = Client("", "")
    limit  = min(days * 96, 1000)   # 96 candles/day on 15m
    raw    = client.get_historical_klines(symbol, "15m", f"{days} day ago UTC", limit=limit)
    return [{
        "ts":    int(k[0]),
        "open":  float(k[1]),
        "high":  float(k[2]),
        "low":   float(k[3]),
        "close": float(k[4]),
        "vol":   float(k[5]),
    } for k in raw]


def run_backtest(klines: list[dict]) -> dict:
    grid     = GridManager(config.GRID_LOWER_PRICE, config.GRID_UPPER_PRICE,
                           config.GRID_LEVELS, config.PER_GRID_USDT, config.GRID_PROFIT_PCT)
    closes   = [k["close"] for k in klines]
    trades   = []
    capital  = config.TOTAL_CAPITAL_USDT

    for i in range(30, len(klines)):
        window = closes[:i]
        price  = window[-1]
        r      = rsi(window, config.RSI_PERIOD)
        ef     = ema(window, 9)
        es     = ema(window, 21)

        # Check RSI-filtered buy
        if r < config.RSI_OVERSOLD and ef >= es and capital >= config.PER_GRID_USDT:
            levels = grid.get_active_buy_levels(price)
            for level in levels:
                if capital < level.usdt_size:
                    continue
                capital -= level.usdt_size
                grid.mark_buy_filled(level.level_id, price, level.qty)

        # Simulate sells at target price
        for level in grid.grid:
            if level.filled_buy and not level.filled_sell:
                hi = klines[i]["high"]
                if hi >= level.sell_price or r > config.RSI_OVERBOUGHT:
                    exit_price = level.sell_price
                    pnl = (exit_price - level.buy_price) * level.qty
                    capital += level.usdt_size + pnl
                    grid.mark_sell_filled(level.level_id, exit_price)
                    trades.append(pnl)
                # Stop loss
                lo = klines[i]["low"]
                sl = level.buy_price * (1 - config.STOP_LOSS_PCT)
                if lo <= sl:
                    pnl = (sl - level.buy_price) * level.qty
                    capital += level.usdt_size + pnl
                    grid.mark_sell_filled(level.level_id, sl)
                    trades.append(pnl)

    total_pnl  = sum(trades)
    win_trades = [t for t in trades if t > 0]
    win_rate   = len(win_trades) / len(trades) * 100 if trades else 0

    return {
        "trades":       len(trades),
        "win_rate_pct": round(win_rate, 2),
        "total_pnl":    round(total_pnl, 4),
        "final_capital": round(capital, 4),
        "roi_pct":      round(total_pnl / config.TOTAL_CAPITAL_USDT * 100, 2),
        "avg_pnl":      round(total_pnl / len(trades), 4) if trades else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="WLDUSDT")
    parser.add_argument("--days",   default=60, type=int)
    args = parser.parse_args()

    print(f"\n📊 Backtesting {args.symbol} — last {args.days} days\n")
    klines = fetch_klines(args.symbol, args.days)
    print(f"Loaded {len(klines)} candles (15m)\n")

    result = run_backtest(klines)
    print("=" * 40)
    print(f"Total trades  : {result['trades']}")
    print(f"Win rate      : {result['win_rate_pct']}%")
    print(f"Total PnL     : {result['total_pnl']} USDT")
    print(f"ROI           : {result['roi_pct']}%")
    print(f"Avg PnL/trade : {result['avg_pnl']} USDT")
    print(f"Final capital : {result['final_capital']} USDT")
    print("=" * 40)


if __name__ == "__main__":
    main()
