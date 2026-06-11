"""
Technical indicators: RSI, EMA, Bollinger Bands, ATR
"""
import numpy as np


def rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = np.diff(closes[-(period + 1):])
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains.mean()
    avg_loss = losses.mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def ema(closes: list[float], period: int) -> float:
    if len(closes) < period:
        return closes[-1]
    k = 2 / (period + 1)
    result = closes[-period]
    for price in closes[-period + 1:]:
        result = price * k + result * (1 - k)
    return round(result, 6)


def bollinger_bands(closes: list[float], period: int = 20, std_dev: float = 2.0):
    if len(closes) < period:
        mid = closes[-1]
        return mid, mid, mid
    window = closes[-period:]
    mid    = np.mean(window)
    std    = np.std(window)
    upper  = mid + std_dev * std
    lower  = mid - std_dev * std
    return round(upper, 6), round(mid, 6), round(lower, 6)


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, period + 1):
        h, l, pc = highs[-i], lows[-i], closes[-(i + 1)]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(np.mean(trs), 6)


def volume_sma(volumes: list[float], period: int = 20) -> float:
    if len(volumes) < period:
        return volumes[-1]
    return round(np.mean(volumes[-period:]), 2)
