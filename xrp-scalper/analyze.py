#!/usr/bin/env python3
"""
تحليل XRP/USDT - السعر الحالي + المؤشرات الفنية + التوصية
"""

import os
import numpy as np
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv
from colorama import Fore, Style, init
from datetime import datetime

init(autoreset=True)
load_dotenv()

SYMBOL = "XRPUSDT"


def fetch_data(client: Client, interval: str, limit: int = 100) -> pd.DataFrame:
    raw = client.get_klines(symbol=SYMBOL, interval=interval, limit=limit)
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
    high = df["high"]
    low = df["low"]

    # EMAs
    for span in [9, 21, 50, 200]:
        df[f"ema{span}"] = close.ewm(span=span, adjust=False).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    df["bb_mid"] = close.rolling(20).mean()
    std = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * std
    df["bb_lower"] = df["bb_mid"] - 2 * std
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # Stochastic
    low14 = low.rolling(14).min()
    high14 = high.rolling(14).max()
    df["stoch_k"] = 100 * (close - low14) / (high14 - low14)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # ATR (تقلب السوق)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    # Volume ratio
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    return df


def rsi_label(rsi: float) -> str:
    if rsi >= 80:
        return f"{Fore.RED}تشبع شراء قوي ({rsi:.1f})"
    elif rsi >= 70:
        return f"{Fore.YELLOW}تشبع شراء ({rsi:.1f})"
    elif rsi <= 20:
        return f"{Fore.GREEN}تشبع بيع قوي ({rsi:.1f})"
    elif rsi <= 30:
        return f"{Fore.CYAN}تشبع بيع ({rsi:.1f})"
    else:
        return f"{Fore.WHITE}محايد ({rsi:.1f})"


def score_signal(last, prev) -> tuple[int, list[str]]:
    """يُعيد نقاط من -10 إلى +10 والأسباب"""
    score = 0
    reasons = []

    # EMA trend
    if last["ema9"] > last["ema21"] > last["ema50"]:
        score += 3
        reasons.append(f"{Fore.GREEN}✅ EMA9 > EMA21 > EMA50 (اتجاه صاعد قوي)")
    elif last["ema9"] < last["ema21"] < last["ema50"]:
        score -= 3
        reasons.append(f"{Fore.RED}❌ EMA9 < EMA21 < EMA50 (اتجاه هابط قوي)")

    # EMA cross
    if prev["ema9"] < prev["ema21"] and last["ema9"] > last["ema21"]:
        score += 2
        reasons.append(f"{Fore.GREEN}✅ تقاطع EMA صاعد (إشارة شراء)")
    elif prev["ema9"] > prev["ema21"] and last["ema9"] < last["ema21"]:
        score -= 2
        reasons.append(f"{Fore.RED}❌ تقاطع EMA هابط (إشارة بيع)")

    # RSI
    if 40 < last["rsi"] < 60:
        score += 1
        reasons.append(f"{Fore.WHITE}🔵 RSI محايد - مجال للحركة")
    elif last["rsi"] < 30:
        score += 2
        reasons.append(f"{Fore.GREEN}✅ RSI منخفض - فرصة شراء محتملة")
    elif last["rsi"] > 70:
        score -= 2
        reasons.append(f"{Fore.RED}❌ RSI مرتفع - تحذير من انعكاس")

    # MACD
    if last["macd"] > last["macd_signal"] and last["macd_hist"] > 0:
        score += 2
        reasons.append(f"{Fore.GREEN}✅ MACD إيجابي ومتصاعد")
    elif last["macd"] < last["macd_signal"] and last["macd_hist"] < 0:
        score -= 2
        reasons.append(f"{Fore.RED}❌ MACD سلبي ومتراجع")

    # Bollinger
    if last["bb_pct"] < 0.2:
        score += 1
        reasons.append(f"{Fore.GREEN}✅ السعر قرب الحد السفلي لـ Bollinger")
    elif last["bb_pct"] > 0.8:
        score -= 1
        reasons.append(f"{Fore.YELLOW}⚠️  السعر قرب الحد العلوي لـ Bollinger")

    # Volume
    if last["vol_ratio"] > 1.5:
        reasons.append(f"{Fore.YELLOW}📊 حجم تداول مرتفع (x{last['vol_ratio']:.1f} المتوسط)")

    return score, reasons


def print_analysis(df1m: pd.DataFrame, df5m: pd.DataFrame, df1h: pd.DataFrame):
    last1m = df1m.iloc[-1]
    last5m = df5m.iloc[-1]
    last1h = df1h.iloc[-1]
    prev1m = df1m.iloc[-2]

    price = last1m["close"]
    change_1h = ((price - df1h.iloc[-2]["close"]) / df1h.iloc[-2]["close"]) * 100
    atr_pct = (last1m["atr"] / price) * 100

    score, reasons = score_signal(last1m, prev1m)

    if score >= 4:
        recommendation = f"{Fore.GREEN}🟢 إشارة شراء قوية"
    elif score >= 2:
        recommendation = f"{Fore.GREEN}🟡 ميل للشراء"
    elif score <= -4:
        recommendation = f"{Fore.RED}🔴 إشارة بيع قوية"
    elif score <= -2:
        recommendation = f"{Fore.RED}🟡 ميل للبيع"
    else:
        recommendation = f"{Fore.WHITE}⚪ محايد - انتظر إشارة أوضح"

    print(f"\n{Fore.CYAN}{'═'*60}")
    print(f"{Fore.YELLOW}       📊 تحليل XRP/USDT  — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{Fore.CYAN}{'═'*60}")

    print(f"\n{Fore.WHITE}💰 السعر الحالي : {Fore.YELLOW}{price:.4f} USDT  {Fore.GREEN if change_1h>=0 else Fore.RED}({change_1h:+.2f}% آخر ساعة)")
    print(f"{Fore.WHITE}📉 ATR (تقلب)   : {atr_pct:.3f}% — {'تقلب مرتفع' if atr_pct > 0.3 else 'تقلب معتدل'}")

    print(f"\n{Fore.CYAN}─── المؤشرات الفنية (1m) ───────────────────────────")
    print(f"  EMA 9/21/50  : {last1m['ema9']:.4f} / {last1m['ema21']:.4f} / {last1m['ema50']:.4f}")
    print(f"  RSI (14)     : {rsi_label(last1m['rsi'])}")
    print(f"  MACD / Signal: {last1m['macd']:+.5f} / {last1m['macd_signal']:+.5f}")
    print(f"  Bollinger %B : {last1m['bb_pct']*100:.1f}%  (L:{last1m['bb_lower']:.4f}  H:{last1m['bb_upper']:.4f})")
    print(f"  Stoch K/D    : {last1m['stoch_k']:.1f} / {last1m['stoch_d']:.1f}")
    print(f"  حجم التداول  : x{last1m['vol_ratio']:.2f} المتوسط")

    print(f"\n{Fore.CYAN}─── الإطارات الزمنية الأعلى ────────────────────────")
    for label, last in [("5 دقائق", last5m), ("1 ساعة", last1h)]:
        trend = "📈 صاعد" if last["ema9"] > last["ema21"] else "📉 هابط"
        print(f"  {label}: RSI={last['rsi']:.1f} | {trend} | MACD_hist={last['macd_hist']:+.5f}")

    print(f"\n{Fore.CYAN}─── أسباب التوصية ──────────────────────────────────")
    for r in reasons:
        print(f"  {r}")

    print(f"\n{Fore.CYAN}─── التوصية ─────────────────────────────────────────")
    print(f"  النقاط: {score:+d}/10  →  {recommendation}")

    if score >= 2:
        entry = price
        sl = entry * 0.995
        tp = entry * 1.010
        print(f"\n  {Fore.GREEN}نقطة دخول مقترحة : {entry:.4f}")
        print(f"  {Fore.RED}وقف الخسارة (SL)  : {sl:.4f}  (-0.5%)")
        print(f"  {Fore.GREEN}هدف الربح (TP)    : {tp:.4f}  (+1.0%)")
    elif score <= -2:
        entry = price
        sl = entry * 1.005
        tp = entry * 0.990
        print(f"\n  {Fore.RED}فرصة بيع مقترحة  : {entry:.4f}")
        print(f"  {Fore.RED}وقف الخسارة (SL)  : {sl:.4f}  (+0.5%)")
        print(f"  {Fore.GREEN}هدف الربح (TP)    : {tp:.4f}  (-1.0%)")

    print(f"\n{Fore.CYAN}{'═'*60}")
    print(f"{Fore.RED}⚠️  تحذير: التحليل للأغراض التعليمية فقط. التداول ينطوي على مخاطر.{Style.RESET_ALL}\n")


if __name__ == "__main__":
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    client = Client(api_key or "", api_secret or "")

    print(f"{Fore.CYAN}⏳ جارٍ جلب البيانات وتحليل XRP/USDT...")

    df1m = add_indicators(fetch_data(client, Client.KLINE_INTERVAL_1MINUTE, 200))
    df5m = add_indicators(fetch_data(client, Client.KLINE_INTERVAL_5MINUTE, 100))
    df1h = add_indicators(fetch_data(client, Client.KLINE_INTERVAL_1HOUR, 100))

    print_analysis(df1m, df5m, df1h)
