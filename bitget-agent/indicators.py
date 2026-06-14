"""
المؤشرات الفنية — حسابات بدون مكتبات خارجية
"""


def ema(prices: list, period: int) -> list:
    if len(prices) < period:
        return []
    k = 2 / (period + 1)
    result = [sum(prices[:period]) / period]
    for p in prices[period:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def bollinger_bands(prices: list, period: int = 20, std_dev: float = 2.0) -> tuple:
    if len(prices) < period:
        return None, None, None
    window = prices[-period:]
    middle = sum(window) / period
    variance = sum((p - middle) ** 2 for p in window) / period
    std = variance ** 0.5
    return middle + std_dev * std, middle, middle - std_dev * std


def macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    if not ema_fast or not ema_slow:
        return None, None, None
    min_len = min(len(ema_fast), len(ema_slow))
    macd_line = [ema_fast[-(min_len - i)] - ema_slow[-(min_len - i)]
                 for i in range(min_len)]
    signal_line = ema(macd_line, signal)
    if not signal_line:
        return macd_line[-1], None, None
    hist = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], hist


def volume_spike(volumes: list, period: int = 20, multiplier: float = 2.0) -> bool:
    if len(volumes) < period + 1:
        return False
    avg_vol = sum(volumes[-period - 1:-1]) / period
    return volumes[-1] > avg_vol * multiplier


def analyze(candles: list, cfg: dict) -> dict:
    """
    تحليل الشموع وإرجاع إشارات التداول

    candles: قائمة من Bitget API
    كل شمعة: [timestamp, open, high, low, close, volume, ...]
    """
    if len(candles) < 30:
        return {"signal": "neutral", "reason": "بيانات غير كافية"}

    closes  = [float(c[4]) for c in candles]
    volumes = [float(c[5]) for c in candles]
    current = closes[-1]

    rsi_val   = rsi(closes, cfg["rsi_period"])
    bb_upper, bb_mid, bb_lower = bollinger_bands(closes, cfg["bb_period"], cfg["bb_std_dev"])
    macd_val, macd_sig, macd_hist = macd(closes, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"])
    ema_fast_val = ema(closes, cfg["ema_fast"])
    ema_slow_val = ema(closes, cfg["ema_slow"])
    ema_trend_val = ema(closes, cfg["ema_trend"])
    vol_spike = volume_spike(volumes, cfg["volume_ma_period"], cfg["volume_spike_mult"])

    signals = []

    # RSI
    if rsi_val < cfg["rsi_oversold"]:
        signals.append(("buy", f"RSI={rsi_val:.1f} (تشبع بيع)"))
    elif rsi_val > cfg["rsi_overbought"]:
        signals.append(("sell", f"RSI={rsi_val:.1f} (تشبع شراء)"))

    # بولينجر باند
    if bb_lower and current <= bb_lower:
        signals.append(("buy", "السعر عند الحد الأدنى BB"))
    elif bb_upper and current >= bb_upper:
        signals.append(("sell", "السعر عند الحد الأعلى BB"))

    # MACD
    if macd_hist and macd_hist > 0 and macd_val > macd_sig:
        signals.append(("buy", "MACD تقاطع صعودي"))
    elif macd_hist and macd_hist < 0 and macd_val < macd_sig:
        signals.append(("sell", "MACD تقاطع هبوطي"))

    # EMA
    if ema_fast_val and ema_slow_val:
        if ema_fast_val[-1] > ema_slow_val[-1]:
            signals.append(("buy", f"EMA{cfg['ema_fast']} فوق EMA{cfg['ema_slow']}"))
        else:
            signals.append(("sell", f"EMA{cfg['ema_fast']} تحت EMA{cfg['ema_slow']}"))

    # اتجاه السوق العام
    trend = "bull"
    if ema_trend_val and current < ema_trend_val[-1]:
        trend = "bear"

    buy_count  = sum(1 for s, _ in signals if s == "buy")
    sell_count = sum(1 for s, _ in signals if s == "sell")

    if buy_count >= 3 and trend == "bull":
        final = "buy"
    elif sell_count >= 3:
        final = "sell"
    else:
        final = "neutral"

    return {
        "signal":      final,
        "rsi":         round(rsi_val, 2),
        "bb_upper":    round(bb_upper, 6) if bb_upper else None,
        "bb_lower":    round(bb_lower, 6) if bb_lower else None,
        "macd_hist":   round(macd_hist, 6) if macd_hist else None,
        "trend":       trend,
        "vol_spike":   vol_spike,
        "buy_signals": buy_count,
        "sell_signals": sell_count,
        "reasons":     [r for _, r in signals],
    }
