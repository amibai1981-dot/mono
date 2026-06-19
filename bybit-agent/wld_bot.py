"""
WLD/USDT Scalping Bot — Binance Spot
استراتيجية: Grid + RSI + EMA على شموع 1m
"""

import time
import hmac
import hashlib
import json
import urllib.request
import urllib.parse
import os
import csv
import logging
from datetime import datetime

import config as C

# ── Logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, C.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(C.LOG_FILE),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("wld_bot")

BASE_URL = "https://testnet.binance.vision" if C.TESTNET else "https://api.binance.com"


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return str(int(time.time() * 1000))


def _sign(params: str) -> str:
    return hmac.new(C.API_SECRET.encode(), params.encode(), hashlib.sha256).hexdigest()


def get(path: str, params: dict = None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, headers={"User-Agent": "wld-bot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get_signed(path: str, params: dict = None) -> dict:
    p = params or {}
    p["timestamp"] = _ts()
    qs = urllib.parse.urlencode(p)
    qs += "&signature=" + _sign(qs)
    url = f"{BASE_URL}{path}?{qs}"
    req = urllib.request.Request(
        url,
        headers={"X-MBX-APIKEY": C.API_KEY, "User-Agent": "wld-bot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def post_signed(path: str, params: dict) -> dict:
    params["timestamp"] = _ts()
    qs = urllib.parse.urlencode(params)
    qs += "&signature=" + _sign(qs)
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=qs.encode(),
        method="POST",
        headers={"X-MBX-APIKEY": C.API_KEY, "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def delete_signed(path: str, params: dict) -> dict:
    params["timestamp"] = _ts()
    qs = urllib.parse.urlencode(params)
    qs += "&signature=" + _sign(qs)
    req = urllib.request.Request(
        f"{BASE_URL}{path}?{qs}",
        method="DELETE",
        headers={"X-MBX-APIKEY": C.API_KEY},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ── Indicators ────────────────────────────────────────────────────────────────

def ema(values: list, period: int) -> float:
    if len(values) < period:
        return sum(values) / len(values)
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes: list, period: int) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[-period:]) / period
    avg_l = sum(losses[-period:]) / period
    if avg_l == 0:
        return 100.0
    return 100 - (100 / (1 + avg_g / avg_l))


def avg_volume(volumes: list, period: int = 20) -> float:
    recent = volumes[-period:] if len(volumes) >= period else volumes
    return sum(recent) / len(recent) if recent else 0


# ── Market Data ───────────────────────────────────────────────────────────────

def fetch_candles(limit: int = 60):
    """Returns closes, volumes (oldest → newest)"""
    rows = get("/api/v3/klines", {
        "symbol": C.SYMBOL,
        "interval": C.CANDLE_INTERVAL,
        "limit": limit,
    })
    closes  = [float(r[4]) for r in rows]
    volumes = [float(r[5]) for r in rows]
    return closes, volumes


def current_price() -> float:
    data = get("/api/v3/ticker/price", {"symbol": C.SYMBOL})
    return float(data["price"])


def usdt_balance() -> float:
    data = get_signed("/api/v3/account")
    for b in data["balances"]:
        if b["asset"] == "USDT":
            return float(b["free"])
    return 0.0


def symbol_info() -> dict:
    data = get("/api/v3/exchangeInfo", {"symbol": C.SYMBOL})
    return data["symbols"][0]


def round_qty(qty: float, step: float) -> float:
    precision = len(str(step).rstrip("0").split(".")[-1]) if "." in str(step) else 0
    return round(round(qty / step) * step, precision)


def round_price(price: float, tick: float) -> float:
    precision = len(str(tick).rstrip("0").split(".")[-1]) if "." in str(tick) else 0
    return round(round(price / tick) * tick, precision)


# ── Orders ────────────────────────────────────────────────────────────────────

def place_order(side: str, qty: float, price: float) -> dict:
    params = {
        "symbol": C.SYMBOL,
        "side": side,           # BUY | SELL
        "type": "LIMIT",
        "timeInForce": "GTC",
        "quantity": qty,
        "price": price,
    }
    try:
        resp = post_signed("/api/v3/order", params)
        oid = resp.get("orderId", "")
        log.info(f"أمر {side} @ {price}  qty={qty}  id={oid}")
        return resp
    except Exception as e:
        log.error(f"فشل الأمر {side}: {e}")
        return {}


def cancel_order(order_id: int):
    try:
        delete_signed("/api/v3/order", {"symbol": C.SYMBOL, "orderId": order_id})
        log.info(f"إلغاء الأمر {order_id}")
    except Exception as e:
        log.warning(f"فشل الإلغاء: {e}")


def open_orders() -> list:
    return get_signed("/api/v3/openOrders", {"symbol": C.SYMBOL})


# ── Grid ──────────────────────────────────────────────────────────────────────

def build_grid(tick: float) -> list:
    step = (C.GRID_UPPER_PRICE - C.GRID_LOWER_PRICE) / (C.GRID_LEVELS - 1)
    return [round_price(C.GRID_LOWER_PRICE + i * step, tick) for i in range(C.GRID_LEVELS)]


def nearest_grid(price: float, grid: list) -> float:
    return min(grid, key=lambda g: abs(g - price))


# ── Trade Log ─────────────────────────────────────────────────────────────────

def log_trade(side: str, price: float, qty: float, reason: str):
    row = {
        "time": datetime.now().isoformat(),
        "side": side,
        "price": price,
        "qty": qty,
        "usdt": round(price * qty, 4),
        "reason": reason,
    }
    exists = os.path.isfile(C.TRADE_LOG_FILE)
    with open(C.TRADE_LOG_FILE, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            w.writeheader()
        w.writerow(row)


# ── Telegram ──────────────────────────────────────────────────────────────────

def tg(msg: str):
    if not C.TELEGRAM_ENABLED:
        return
    try:
        url = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage"
        body = json.dumps({"chat_id": C.TELEGRAM_CHAT_ID, "text": msg}).encode()
        urllib.request.urlopen(
            urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}),
            timeout=5,
        )
    except Exception as e:
        log.warning(f"Telegram: {e}")


# ── Bot ───────────────────────────────────────────────────────────────────────

class Bot:
    def __init__(self):
        info = symbol_info()
        filters = {f["filterType"]: f for f in info["filters"]}
        self.tick_size = float(filters["PRICE_FILTER"]["tickSize"])
        self.step_size = float(filters["LOT_SIZE"]["stepSize"])
        self.min_notional = float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 5.0))

        self.grid = build_grid(self.tick_size)
        self.positions: dict = {}   # order_id → {price, qty, ts}
        self.daily_trades = 0
        self.day = datetime.now().date()

        log.info(f"tick={self.tick_size}  step={self.step_size}  minNotional={self.min_notional}")
        log.info(f"Grid: {self.grid}")

    def reset_daily(self):
        today = datetime.now().date()
        if today != self.day:
            self.daily_trades = 0
            self.day = today

    def signal(self, closes: list, volumes: list) -> str:
        r    = rsi(closes, C.RSI_PERIOD)
        fast = ema(closes, C.EMA_FAST)
        slow = ema(closes, C.EMA_SLOW)

        if C.VOLUME_FILTER:
            if volumes[-1] < avg_volume(volumes) * C.VOLUME_MULTIPLIER:
                return "HOLD"

        if r < C.RSI_OVERSOLD and fast > slow:
            return "BUY"
        if r > C.RSI_OVERBOUGHT and fast < slow:
            return "SELL"
        return "HOLD"

    def check_exits(self, price: float):
        for oid, pos in list(self.positions.items()):
            entry = pos["price"]
            qty   = pos["qty"]
            age   = (time.time() - pos["ts"]) / 60

            tp     = round_price(entry * (1 + C.TAKE_PROFIT_PCT), self.tick_size)
            sl     = round_price(entry * (1 - C.STOP_LOSS_PCT),   self.tick_size)
            trail  = round_price(entry * (1 - C.TRAILING_STOP_PCT), self.tick_size)
            sell_p = round_price(price, self.tick_size)

            if price >= tp:
                r = place_order("SELL", qty, sell_p)
                if r:
                    log_trade("SELL", sell_p, qty, "take_profit")
                    tg(f"✅ TP WLD SELL @ {sell_p}  +{C.TAKE_PROFIT_PCT*100:.1f}%")
                    self.daily_trades += 1
                del self.positions[oid]

            elif price <= sl:
                r = place_order("SELL", qty, sell_p)
                if r:
                    log_trade("SELL", sell_p, qty, "stop_loss")
                    tg(f"🛑 SL WLD SELL @ {sell_p}  -{C.STOP_LOSS_PCT*100:.1f}%")
                    self.daily_trades += 1
                del self.positions[oid]

            elif price <= trail:
                r = place_order("SELL", qty, sell_p)
                if r:
                    log_trade("SELL", sell_p, qty, "trailing_stop")
                    self.daily_trades += 1
                del self.positions[oid]

            elif age > C.ORDER_TIMEOUT_MIN:
                cancel_order(oid)
                if oid in self.positions:
                    del self.positions[oid]

    def run(self):
        log.info(f"▶  بوت WLD/USDT يعمل على Binance")
        log.info(f"   نطاق الشبكة: {C.GRID_LOWER_PRICE} – {C.GRID_UPPER_PRICE}  |  رأس المال: {C.TOTAL_CAPITAL_USDT} USDT")
        tg(f"▶ WLD Bot started\nGrid: {C.GRID_LOWER_PRICE}–{C.GRID_UPPER_PRICE}\nCapital: {C.TOTAL_CAPITAL_USDT} USDT")

        while True:
            try:
                self.reset_daily()

                closes, volumes = fetch_candles(60)
                price = closes[-1]
                sig   = self.signal(closes, volumes)

                r    = rsi(closes, C.RSI_PERIOD)
                fast = ema(closes, C.EMA_FAST)
                slow = ema(closes, C.EMA_SLOW)

                log.info(
                    f"Price={price:.4f}  RSI={r:.1f}  "
                    f"EMA{C.EMA_FAST}={fast:.4f}  EMA{C.EMA_SLOW}={slow:.4f}  "
                    f"Signal={sig}  Pos={len(self.positions)}/{C.MAX_OPEN_ORDERS}  "
                    f"Trades={self.daily_trades}/{C.MAX_DAILY_TRADES}"
                )

                # فحص الخروج من المراكز المفتوحة
                self.check_exits(price)

                # شروط الدخول
                in_range = C.GRID_LOWER_PRICE <= price <= C.GRID_UPPER_PRICE

                if not in_range:
                    log.warning(f"⚠️  السعر {price:.4f} خارج نطاق الشبكة [{C.GRID_LOWER_PRICE}–{C.GRID_UPPER_PRICE}]")

                if (
                    sig == "BUY"
                    and in_range
                    and len(self.positions) < C.MAX_OPEN_ORDERS
                    and self.daily_trades < C.MAX_DAILY_TRADES
                ):
                    grid_p = nearest_grid(price, self.grid)
                    qty    = round_qty(C.PER_GRID_USDT / grid_p, self.step_size)

                    if qty * grid_p < self.min_notional:
                        log.warning(f"الكمية أقل من الحد الأدنى ({self.min_notional} USDT)")
                    else:
                        result = place_order("BUY", qty, grid_p)
                        if result.get("orderId"):
                            self.positions[result["orderId"]] = {
                                "price": grid_p,
                                "qty": qty,
                                "ts": time.time(),
                            }
                            log_trade("BUY", grid_p, qty, f"grid+rsi={r:.1f}")
                            tg(f"📈 WLD BUY @ {grid_p}  qty={qty}  RSI={r:.1f}")

            except KeyboardInterrupt:
                log.info("⏹  إيقاف البوت.")
                tg("⏹ WLD Bot stopped.")
                break
            except Exception as e:
                log.error(f"خطأ: {e}", exc_info=True)
                time.sleep(5)

            time.sleep(C.LOOP_SLEEP_SEC)


if __name__ == "__main__":
    Bot().run()
