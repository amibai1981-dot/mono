"""
Simple backtester for the WLD bot strategy using historical Binance klines.
Run: python backtest.py
"""

import requests
from bot import closes, ema, rsi, EMA_FAST, EMA_SLOW, RSI_PERIOD, STOP_LOSS_PCT, TAKE_PROFIT_PCT

SYMBOL   = "WLDUSDT"
INTERVAL = "15m"
LIMIT    = 500   # last 500 candles ≈ 5 days of 15-min data


def fetch_klines():
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": SYMBOL, "interval": INTERVAL, "limit": LIMIT},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def backtest():
    klines  = fetch_klines()
    prices  = closes(klines)
    timestamps = [k[0] for k in klines]

    trades  = []
    position = None
    win_count = loss_count = 0
    total_pnl = 0.0

    WINDOW = max(EMA_SLOW, RSI_PERIOD) + 2

    for i in range(WINDOW, len(prices)):
        window = prices[:i]
        price  = prices[i]

        fast = ema(window, EMA_FAST)
        slow = ema(window, EMA_SLOW)
        rsi_val = rsi(window, RSI_PERIOD)

        buy_signal  = fast[-1] > slow[-1] and fast[-2] <= slow[-2] and rsi_val < 65
        sell_signal = (fast[-1] < slow[-1] and fast[-2] >= slow[-2]) or rsi_val > 70

        if position is None and buy_signal:
            position = {
                "entry": price,
                "sl":    price * (1 - STOP_LOSS_PCT / 100),
                "tp":    price * (1 + TAKE_PROFIT_PCT / 100),
                "idx":   i,
            }

        elif position:
            reason = None
            if price <= position["sl"]:
                reason = "SL"
            elif price >= position["tp"]:
                reason = "TP"
            elif sell_signal:
                reason = "SIGNAL"

            if reason:
                pnl = price - position["entry"]
                total_pnl += pnl
                if pnl > 0:
                    win_count += 1
                else:
                    loss_count += 1
                trades.append({"entry": position["entry"], "exit": price, "pnl": pnl, "reason": reason})
                position = None

    total = win_count + loss_count
    wr = win_count / total * 100 if total else 0

    print(f"\n{'='*50}")
    print(f"  Backtest: {SYMBOL} {INTERVAL}  (last {LIMIT} candles)")
    print(f"{'='*50}")
    print(f"  Total trades : {total}")
    print(f"  Wins         : {win_count}  ({wr:.1f}%)")
    print(f"  Losses       : {loss_count}")
    print(f"  Total PnL    : {total_pnl:.4f} USDT (per unit)")
    print(f"{'='*50}\n")

    for i, t in enumerate(trades, 1):
        marker = "✓" if t["pnl"] > 0 else "✗"
        print(f"  {marker} #{i:02d}  entry={t['entry']:.4f}  exit={t['exit']:.4f}  "
              f"pnl={t['pnl']:+.4f}  [{t['reason']}]")
    print()


if __name__ == "__main__":
    backtest()
