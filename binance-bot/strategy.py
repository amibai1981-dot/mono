"""
Multi-indicator strategy: RSI + MACD + Bollinger Bands + EMA Trend + Volume filter
Signal is generated only when multiple indicators agree (confluence).
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from config import config


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    signal: Signal
    strength: int          # 0-5 (number of confluent indicators)
    price: float
    rsi: float
    macd: float
    macd_signal: float
    bb_upper: float
    bb_lower: float
    bb_mid: float
    ema_fast: float
    ema_slow: float
    ema_trend: float
    volume_ratio: float
    reason: str


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=config.RSI_PERIOD - 1, min_periods=config.RSI_PERIOD).mean()
    avg_loss = loss.ewm(com=config.RSI_PERIOD - 1, min_periods=config.RSI_PERIOD).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema_fast = close.ewm(span=config.MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=config.MACD_SLOW, adjust=False).mean()
    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=config.MACD_SIGNAL, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    df["bb_mid"] = close.rolling(config.BB_PERIOD).mean()
    bb_std = close.rolling(config.BB_PERIOD).std()
    df["bb_upper"] = df["bb_mid"] + config.BB_STD * bb_std
    df["bb_lower"] = df["bb_mid"] - config.BB_STD * bb_std
    df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]

    # EMAs
    df["ema_fast"] = close.ewm(span=config.EMA_FAST, adjust=False).mean()
    df["ema_slow"] = close.ewm(span=config.EMA_SLOW, adjust=False).mean()
    df["ema_trend"] = close.ewm(span=config.EMA_TREND, adjust=False).mean()

    # Volume MA
    df["vol_ma"] = volume.rolling(config.VOLUME_MA_PERIOD).mean()
    df["vol_ratio"] = volume / df["vol_ma"]

    return df


def analyze(df: pd.DataFrame, symbol: str) -> StrategyResult:
    df = calculate_indicators(df.copy())
    row = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(row["close"])
    rsi = float(row["rsi"])
    macd = float(row["macd"])
    macd_sig = float(row["macd_signal"])
    macd_hist = float(row["macd_hist"])
    prev_macd_hist = float(prev["macd_hist"])
    bb_upper = float(row["bb_upper"])
    bb_lower = float(row["bb_lower"])
    bb_mid = float(row["bb_mid"])
    ema_fast = float(row["ema_fast"])
    ema_slow = float(row["ema_slow"])
    ema_trend = float(row["ema_trend"])
    vol_ratio = float(row["vol_ratio"])

    # --- BUY conditions ---
    buy_signals = []

    # 1. RSI oversold
    if rsi < config.RSI_OVERSOLD:
        buy_signals.append(f"RSI={rsi:.1f} oversold")

    # 2. MACD bullish crossover (histogram turned positive)
    if macd_hist > 0 and prev_macd_hist <= 0:
        buy_signals.append("MACD bullish crossover")

    # 3. Price near/below lower Bollinger Band
    if price <= bb_lower * 1.005:
        buy_signals.append("Price at BB lower")

    # 4. EMA fast above slow (short-term bullish)
    if ema_fast > ema_slow:
        buy_signals.append("EMA bullish alignment")

    # 5. Price above trend EMA (uptrend)
    if price > ema_trend:
        buy_signals.append("Price above EMA50 trend")

    # 6. Volume confirmation
    if vol_ratio >= config.VOLUME_MULTIPLIER:
        buy_signals.append(f"Volume surge x{vol_ratio:.1f}")

    # --- SELL conditions ---
    sell_signals = []

    if rsi > config.RSI_OVERBOUGHT:
        sell_signals.append(f"RSI={rsi:.1f} overbought")

    if macd_hist < 0 and prev_macd_hist >= 0:
        sell_signals.append("MACD bearish crossover")

    if price >= bb_upper * 0.995:
        sell_signals.append("Price at BB upper")

    if ema_fast < ema_slow:
        sell_signals.append("EMA bearish alignment")

    if price < ema_trend:
        sell_signals.append("Price below EMA50 trend")

    if vol_ratio >= config.VOLUME_MULTIPLIER:
        sell_signals.append(f"Volume surge x{vol_ratio:.1f}")

    # Require at least 3 confluent signals
    if len(buy_signals) >= 3:
        return StrategyResult(
            signal=Signal.BUY,
            strength=len(buy_signals),
            price=price, rsi=rsi, macd=macd, macd_signal=macd_sig,
            bb_upper=bb_upper, bb_lower=bb_lower, bb_mid=bb_mid,
            ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend,
            volume_ratio=vol_ratio,
            reason=" | ".join(buy_signals),
        )

    if len(sell_signals) >= 3:
        return StrategyResult(
            signal=Signal.SELL,
            strength=len(sell_signals),
            price=price, rsi=rsi, macd=macd, macd_signal=macd_sig,
            bb_upper=bb_upper, bb_lower=bb_lower, bb_mid=bb_mid,
            ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend,
            volume_ratio=vol_ratio,
            reason=" | ".join(sell_signals),
        )

    return StrategyResult(
        signal=Signal.HOLD,
        strength=0,
        price=price, rsi=rsi, macd=macd, macd_signal=macd_sig,
        bb_upper=bb_upper, bb_lower=bb_lower, bb_mid=bb_mid,
        ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend,
        volume_ratio=vol_ratio,
        reason="Insufficient confluence",
    )
