#!/usr/bin/env python3
"""
اختبار استراتيجية XRP Scalper على بيانات تاريخية
"""

import os
import pandas as pd
import numpy as np
from binance.client import Client
from dotenv import load_dotenv
from colorama import Fore, init

init(autoreset=True)
load_dotenv()

SYMBOL = "XRPUSDT"
EMA_FAST, EMA_SLOW = 9, 21
RSI_PERIOD = 14
RSI_OVERSOLD, RSI_OVERBOUGHT = 35, 65
BB_PERIOD, BB_STD = 20, 2.0
SL_PCT = 0.005
TP_PCT = 0.010
TRADE_USDT = 10.0


def get_historical(client: Client, days: int = 7) -> pd.DataFrame:
    print(f"📥 جارٍ جلب بيانات {days} أيام...")
    raw = client.get_historical_klines(
        SYMBOL, Client.KLINE_INTERVAL_1MINUTE,
        f"{days} day ago UTC"
    )
    df = pd.DataFrame(raw, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_vol","trades","tbbase","tbquote","ignore"
    ])
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    df["ema_fast"] = close.ewm(span=EMA_FAST, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=EMA_SLOW, adjust=False).mean()
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    df["bb_mid"] = close.rolling(BB_PERIOD).mean()
    std = close.rolling(BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + BB_STD * std
    df["bb_lower"] = df["bb_mid"] - BB_STD * std
    df["vol_ma"] = df["volume"].rolling(20).mean()
    return df.dropna().reset_index(drop=True)


def backtest(df: pd.DataFrame):
    trades = []
    position = None

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        price = row["close"]

        # إدارة الصفقة المفتوحة
        if position:
            if position["side"] == "BUY":
                if price <= position["sl"]:
                    pnl = (price - position["entry"]) * position["qty"]
                    trades.append({**position, "exit": price, "pnl": pnl, "result": "SL"})
                    position = None
                    continue
                elif price >= position["tp"]:
                    pnl = (price - position["entry"]) * position["qty"]
                    trades.append({**position, "exit": price, "pnl": pnl, "result": "TP"})
                    position = None
                    continue
            else:
                if price >= position["sl"]:
                    pnl = (position["entry"] - price) * position["qty"]
                    trades.append({**position, "exit": price, "pnl": pnl, "result": "SL"})
                    position = None
                    continue
                elif price <= position["tp"]:
                    pnl = (position["entry"] - price) * position["qty"]
                    trades.append({**position, "exit": price, "pnl": pnl, "result": "TP"})
                    position = None
                    continue

        if position:
            continue  # لا تفتح صفقة جديدة إذا هناك مفتوحة

        # إشارات
        ema_up = prev["ema_fast"] < prev["ema_slow"] and row["ema_fast"] > row["ema_slow"]
        ema_dn = prev["ema_fast"] > prev["ema_slow"] and row["ema_fast"] < row["ema_slow"]
        rsi_mid = RSI_OVERSOLD < row["rsi"] < RSI_OVERBOUGHT
        vol_ok = row["volume"] > row["vol_ma"] * 0.8

        if ema_up and rsi_mid and row["close"] < row["bb_mid"] and vol_ok:
            qty = TRADE_USDT / price
            position = {
                "side": "BUY", "entry": price, "qty": qty,
                "sl": price * (1 - SL_PCT), "tp": price * (1 + TP_PCT),
                "time": row["open_time"],
            }
        elif ema_dn and rsi_mid and row["close"] > row["bb_mid"] and vol_ok:
            qty = TRADE_USDT / price
            position = {
                "side": "SELL", "entry": price, "qty": qty,
                "sl": price * (1 + SL_PCT), "tp": price * (1 - TP_PCT),
                "time": row["open_time"],
            }

    return trades


def print_report(trades: list, df: pd.DataFrame):
    if not trades:
        print("❌ لا توجد صفقات في فترة الاختبار")
        return

    t = pd.DataFrame(trades)
    total = len(t)
    wins = (t["pnl"] > 0).sum()
    losses = (t["pnl"] <= 0).sum()
    total_pnl = t["pnl"].sum()
    avg_win = t[t["pnl"] > 0]["pnl"].mean() if wins else 0
    avg_loss = t[t["pnl"] <= 0]["pnl"].mean() if losses else 0
    win_rate = wins / total * 100

    print(f"\n{Fore.CYAN}{'='*55}")
    print(f"{Fore.YELLOW}         📊 نتائج الاختبار الخلفي - XRP Scalper")
    print(f"{Fore.CYAN}{'='*55}")
    print(f"الفترة: {df['open_time'].iloc[0].date()} → {df['open_time'].iloc[-1].date()}")
    print(f"إجمالي الصفقات : {Fore.WHITE}{total}")
    print(f"الصفقات الرابحة: {Fore.GREEN}{wins} ({win_rate:.1f}%)")
    print(f"الصفقات الخاسرة: {Fore.RED}{losses} ({100-win_rate:.1f}%)")
    print(f"متوسط الربح    : {Fore.GREEN}{avg_win:+.4f}$")
    print(f"متوسط الخسارة  : {Fore.RED}{avg_loss:+.4f}$")
    print(f"إجمالي PnL     : {Fore.GREEN if total_pnl >= 0 else Fore.RED}{total_pnl:+.4f}$")
    profit_factor = abs(t[t["pnl"]>0]["pnl"].sum() / t[t["pnl"]<=0]["pnl"].sum()) if losses else float("inf")
    print(f"Profit Factor  : {Fore.YELLOW}{profit_factor:.2f}")
    print(f"{Fore.CYAN}{'='*55}\n")

    # آخر 10 صفقات
    print(f"{Fore.WHITE}آخر 10 صفقات:")
    for _, row in t.tail(10).iterrows():
        color = Fore.GREEN if row["pnl"] > 0 else Fore.RED
        print(f"  {color}{row['side']:4s} | دخول: {row['entry']:.4f} | خروج: {row['exit']:.4f} | PnL: {row['pnl']:+.4f}$ [{row['result']}]")


if __name__ == "__main__":
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")

    # يمكن استخدام مفاتيح فارغة لجلب البيانات العامة فقط
    client = Client(api_key or "", api_secret or "")

    df = get_historical(client, days=7)
    df = add_indicators(df)
    trades = backtest(df)
    print_report(trades, df)
