"""
بوت تداول Binance — يدعم استراتيجيتي RSI و EMA Crossover
الاستخدام:
    python3 bot.py monitor    # مراقبة السوق
    python3 bot.py balance    # عرض الرصيد
    python3 bot.py orders     # الصفقات المفتوحة
    python3 bot.py rsi        # تشغيل استراتيجية RSI
    python3 bot.py ema        # تشغيل استراتيجية EMA
"""

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

# تحميل متغيرات البيئة من ملف .env
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    value = value.split("#")[0].strip()
                    os.environ.setdefault(key.strip(), value)

load_env()

API_KEY    = os.getenv("BINANCE_API_KEY", "")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
ENV        = os.getenv("BINANCE_ENV", "testnet")
SYMBOL     = os.getenv("SYMBOL", "BTCUSDT")
TRADE_AMT  = float(os.getenv("TRADE_AMOUNT", "10"))
RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
RSI_OB     = float(os.getenv("RSI_OVERBOUGHT", "70"))
RSI_OS     = float(os.getenv("RSI_OVERSOLD", "30"))
EMA_FAST   = int(os.getenv("EMA_FAST", "9"))
EMA_SLOW   = int(os.getenv("EMA_SLOW", "21"))
REFRESH    = int(os.getenv("REFRESH_SECONDS", "60"))

BASE_URL = (
    "https://testnet.binance.vision"
    if ENV == "testnet"
    else "https://api.binance.com"
)

# ─── توقيع الطلبات ──────────────────────────────────────────────────────────

def sign(params: dict) -> str:
    query = urllib.parse.urlencode(params)
    return hmac.new(
        SECRET_KEY.encode(), query.encode(), hashlib.sha256
    ).hexdigest()

# ─── طلبات HTTP ──────────────────────────────────────────────────────────────

def _request(method: str, path: str, params: dict = None, auth: bool = False) -> dict:
    params = params or {}
    if auth:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = 5000
        params["signature"] = sign(params)

    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}"
    if method == "GET" and query:
        url += f"?{query}"

    data = query.encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-MBX-APIKEY", API_KEY)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "binance-bot/1.0")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"خطأ HTTP {e.code}: {body}")
        return {}

def get(path, params=None, auth=False):
    return _request("GET", path, params, auth)

def post(path, params=None):
    return _request("POST", path, params, auth=True)

# ─── بيانات السوق ─────────────────────────────────────────────────────────────

def get_price(symbol: str) -> float:
    data = get("/api/v3/ticker/price", {"symbol": symbol})
    return float(data.get("price", 0))

def get_klines(symbol: str, interval: str = "1h", limit: int = 100) -> list[list]:
    """جلب الشموع اليابانية OHLCV"""
    return get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})

def get_ticker_24h(symbol: str) -> dict:
    return get("/api/v3/ticker/24hr", {"symbol": symbol})

def get_orderbook(symbol: str, depth: int = 5) -> dict:
    return get("/api/v3/depth", {"symbol": symbol, "limit": depth})

# ─── الحساب والأوامر ─────────────────────────────────────────────────────────

def get_balance(asset: str = None) -> list | float:
    data = get("/api/v3/account", auth=True)
    balances = data.get("balances", [])
    if asset:
        for b in balances:
            if b["asset"] == asset:
                return float(b["free"])
        return 0.0
    return [b for b in balances if float(b["free"]) > 0 or float(b["locked"]) > 0]

def get_open_orders(symbol: str = None) -> list:
    params = {}
    if symbol:
        params["symbol"] = symbol
    return get("/api/v3/openOrders", params, auth=True) or []

def place_order(symbol: str, side: str, quantity: float) -> dict:
    """side: BUY أو SELL"""
    return post("/api/v3/order", {
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "quantity":  f"{quantity:.6f}",
    })

def cancel_order(symbol: str, order_id: int) -> dict:
    params = {"symbol": symbol, "orderId": order_id,
              "timestamp": int(time.time() * 1000), "recvWindow": 5000}
    params["signature"] = sign(params)
    return _request("DELETE", "/api/v3/order", params)

# ─── المؤشرات الفنية ──────────────────────────────────────────────────────────

def calc_rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains  = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_ema(closes: list[float], period: int) -> list[float]:
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(closes[:period]) / period]
    for price in closes[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

# ─── عرض البيانات ─────────────────────────────────────────────────────────────

def show_balance():
    balances = get_balance()
    non_zero = [b for b in balances if float(b["free"]) > 0.0001]
    print(f"\n{'العملة':<10} {'متاح':>15} {'محجوز':>15}")
    print("-" * 44)
    for b in non_zero:
        print(f"{b['asset']:<10} {float(b['free']):>15.6f} {float(b['locked']):>15.6f}")

def show_market(symbol: str):
    price   = get_price(symbol)
    t24     = get_ticker_24h(symbol)
    change  = float(t24.get("priceChangePercent", 0))
    high    = float(t24.get("highPrice", 0))
    low     = float(t24.get("lowPrice", 0))
    volume  = float(t24.get("quoteVolume", 0))
    arrow   = "▲" if change >= 0 else "▼"
    color   = "\033[92m" if change >= 0 else "\033[91m"
    reset   = "\033[0m"
    ts      = datetime.now().strftime("%H:%M:%S")

    klines  = get_klines(symbol, "1h", RSI_PERIOD + 5)
    closes  = [float(k[4]) for k in klines]
    rsi     = calc_rsi(closes, RSI_PERIOD)

    print(f"\n[ {symbol} — {ts} ]")
    print(f"  السعر:   {price:>12.4f} USDT  {color}{arrow} {abs(change):.2f}%{reset}")
    print(f"  أعلى:    {high:>12.4f}    أدنى: {low:.4f}")
    print(f"  حجم 24h: {volume:>12,.0f} USDT")
    print(f"  RSI({RSI_PERIOD}):  {rsi:>12.2f}  {'↑ تشبع شراء' if rsi > RSI_OB else '↓ تشبع بيع' if rsi < RSI_OS else 'محايد'}")

def show_open_orders(symbol: str):
    orders = get_open_orders(symbol)
    if not orders:
        print("لا توجد أوامر مفتوحة.")
        return
    print(f"\n{'#':<6} {'النوع':<8} {'الجانب':<6} {'الكمية':>12} {'السعر':>12} {'الحالة':<12}")
    print("-" * 60)
    for o in orders:
        print(f"{o['orderId']:<6} {o['type']:<8} {o['side']:<6} "
              f"{float(o['origQty']):>12.6f} {float(o['price']):>12.4f} {o['status']:<12}")

# ─── الاستراتيجيات ────────────────────────────────────────────────────────────

class RSIStrategy:
    """شراء عند RSI < 30، بيع عند RSI > 70"""

    def __init__(self):
        self.in_position = False
        self.buy_price   = 0.0

    def run_once(self):
        klines = get_klines(SYMBOL, "1h", RSI_PERIOD + 10)
        closes = [float(k[4]) for k in klines]
        price  = closes[-1]
        rsi    = calc_rsi(closes, RSI_PERIOD)
        ts     = datetime.now().strftime("%H:%M:%S")

        print(f"[{ts}] {SYMBOL} | السعر: {price:.4f} | RSI: {rsi:.2f}", end="")

        if not self.in_position and rsi < RSI_OS:
            qty = round(TRADE_AMT / price, 6)
            result = place_order(SYMBOL, "BUY", qty)
            if result:
                self.in_position = True
                self.buy_price   = price
                print(f" → ✅ شراء {qty} @ {price:.4f}")
            else:
                print(" → ❌ فشل الشراء")

        elif self.in_position and rsi > RSI_OB:
            qty = round(TRADE_AMT / self.buy_price, 6)
            result = place_order(SYMBOL, "SELL", qty)
            if result:
                profit = (price - self.buy_price) / self.buy_price * 100
                print(f" → ✅ بيع {qty} @ {price:.4f} | ربح: {profit:+.2f}%")
                self.in_position = False
                self.buy_price   = 0.0
            else:
                print(" → ❌ فشل البيع")
        else:
            status = "في صفقة" if self.in_position else "انتظار"
            print(f" | {status}")

    def run(self):
        print(f"استراتيجية RSI — {SYMBOL} | شراء < {RSI_OS} | بيع > {RSI_OB}")
        print("اضغط Ctrl+C للإيقاف\n")
        while True:
            try:
                self.run_once()
                time.sleep(REFRESH)
            except KeyboardInterrupt:
                print("\nتم الإيقاف.")
                break
            except Exception as e:
                print(f"\nخطأ: {e}")
                time.sleep(10)


class EMAStrategy:
    """شراء عند تقاطع EMA سريع فوق بطيء، بيع عند التقاطع العكسي"""

    def __init__(self):
        self.in_position  = False
        self.buy_price    = 0.0
        self.prev_signal  = None  # "above" | "below"

    def run_once(self):
        needed  = EMA_SLOW + 30
        klines  = get_klines(SYMBOL, "1h", needed)
        closes  = [float(k[4]) for k in klines]
        price   = closes[-1]

        ema_f   = calc_ema(closes, EMA_FAST)
        ema_s   = calc_ema(closes, EMA_SLOW)

        if not ema_f or not ema_s:
            print("بيانات غير كافية لحساب EMA")
            return

        # محاذاة الطولين
        min_len  = min(len(ema_f), len(ema_s))
        fast_now = ema_f[-1]
        slow_now = ema_s[-1]
        signal   = "above" if fast_now > slow_now else "below"

        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {SYMBOL} | السعر: {price:.4f} | EMA{EMA_FAST}: {fast_now:.4f} | EMA{EMA_SLOW}: {slow_now:.4f}", end="")

        if self.prev_signal is not None:
            # تقاطع صاعد
            if self.prev_signal == "below" and signal == "above" and not self.in_position:
                qty = round(TRADE_AMT / price, 6)
                result = place_order(SYMBOL, "BUY", qty)
                if result:
                    self.in_position = True
                    self.buy_price   = price
                    print(f" → ✅ تقاطع صاعد — شراء {qty} @ {price:.4f}")
                else:
                    print(" → ❌ فشل الشراء")

            # تقاطع هابط
            elif self.prev_signal == "above" and signal == "below" and self.in_position:
                qty = round(TRADE_AMT / self.buy_price, 6)
                result = place_order(SYMBOL, "SELL", qty)
                if result:
                    profit = (price - self.buy_price) / self.buy_price * 100
                    print(f" → ✅ تقاطع هابط — بيع {qty} @ {price:.4f} | ربح: {profit:+.2f}%")
                    self.in_position = False
                    self.buy_price   = 0.0
                else:
                    print(" → ❌ فشل البيع")
            else:
                status = "في صفقة" if self.in_position else "انتظار"
                print(f" | {status}")
        else:
            print(" | تهيئة...")

        self.prev_signal = signal

    def run(self):
        print(f"استراتيجية EMA Crossover — {SYMBOL} | EMA{EMA_FAST} / EMA{EMA_SLOW}")
        print("اضغط Ctrl+C للإيقاف\n")
        while True:
            try:
                self.run_once()
                time.sleep(REFRESH)
            except KeyboardInterrupt:
                print("\nتم الإيقاف.")
                break
            except Exception as e:
                print(f"\nخطأ: {e}")
                time.sleep(10)

# ─── نقطة الدخول ──────────────────────────────────────────────────────────────

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "monitor"

    if not API_KEY or "ضع" in API_KEY:
        print("⚠ لم يتم إعداد مفاتيح API. عدّل ملف .env أولاً.")
        if mode not in ("monitor",):
            sys.exit(1)

    if mode == "balance":
        show_balance()

    elif mode == "orders":
        show_open_orders(SYMBOL)

    elif mode == "monitor":
        print(f"مراقبة {SYMBOL} — اضغط Ctrl+C للإيقاف\n")
        while True:
            try:
                show_market(SYMBOL)
                time.sleep(REFRESH)
            except KeyboardInterrupt:
                print("\nتم الإيقاف.")
                break

    elif mode == "rsi":
        RSIStrategy().run()

    elif mode == "ema":
        EMAStrategy().run()

    else:
        print(f"وضع غير معروف: {mode}")
        print("الأوضاع المتاحة: monitor | balance | orders | rsi | ema")

if __name__ == "__main__":
    main()
