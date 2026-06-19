"""
WLD/USDT Scalping Bot — Bybit Spot
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
from collections import deque

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

BASE_URL = "https://api-testnet.bybit.com" if C.TESTNET else "https://api.bybit.com"

# ── HTTP ──────────────────────────────────────────────────────────────────────

def _sign(params: str) -> str:
    ts = str(int(time.time() * 1000))
    recv = "5000"
    raw = ts + C.API_KEY + recv + params
    sig = hmac.new(C.API_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return ts, recv, sig


def get(path: str, params: dict = None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    url = f"{BASE_URL}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(url, headers={"User-Agent": "wld-bot/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def post(path: str, body: dict) -> dict:
    payload = json.dumps(body)
    ts, recv, sig = _sign(payload)
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=payload.encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": C.API_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def get_auth(path: str, params: dict = None) -> dict:
    qs = urllib.parse.urlencode(params or {})
    ts, recv, sig = _sign(qs)
    url = f"{BASE_URL}{path}" + (f"?{qs}" if qs else "")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "wld-bot/1.0",
            "X-BAPI-API-KEY": C.API_KEY,
            "X-BAPI-TIMESTAMP": ts,
            "X-BAPI-RECV-WINDOW": recv,
            "X-BAPI-SIGN": sig,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


# ── Indicators ────────────────────────────────────────────────────────────────

def ema(values: list[float], period: int) -> float:
    if len(values) < period:
        return sum(values) / len(values)
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e


def rsi(closes: list[float], period: int) -> float:
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
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def avg_volume(volumes: list[float], period: int = 20) -> float:
    recent = volumes[-period:] if len(volumes) >= period else volumes
    return sum(recent) / len(recent) if recent else 0


# ── Market Data ───────────────────────────────────────────────────────────────

def fetch_candles(limit: int = 60) -> tuple[list, list, list]:
    """Returns (closes, highs, lows, volumes) as lists newest-last."""
    data = get("/v5/market/kline", {
        "category": "spot",
        "symbol": C.SYMBOL,
        "interval": C.CANDLE_INTERVAL.replace("m", "").replace("h", "60"),
        "limit": limit,
    })
    rows = data["result"]["list"]  # newest first
    rows.reverse()
    closes  = [float(r[4]) for r in rows]
    highs   = [float(r[2]) for r in rows]
    lows    = [float(r[3]) for r in rows]
    volumes = [float(r[5]) for r in rows]
    return closes, highs, lows, volumes


def current_price() -> float:
    data = get("/v5/market/tickers", {"category": "spot", "symbol": C.SYMBOL})
    return float(data["result"]["list"][0]["lastPrice"])


def usdt_balance() -> float:
    data = get_auth("/v5/account/wallet-balance", {"accountType": "UNIFIED"})
    for coin in data["result"]["list"][0]["coin"]:
        if coin["coin"] == "USDT":
            return float(coin["availableToWithdraw"])
    return 0.0


# ── Orders ────────────────────────────────────────────────────────────────────

def place_order(side: str, qty: float, price: float) -> dict:
    body = {
        "category": "spot",
        "symbol": C.SYMBOL,
        "side": side,          # "Buy" | "Sell"
        "orderType": "Limit",
        "qty": str(round(qty, 2)),
        "price": str(round(price, 4)),
        "timeInForce": "GTC",
    }
    resp = post("/v5/order/create", body)
    if resp["retCode"] != 0:
        log.error(f"فشل الأمر {side}: {resp['retMsg']}")
        return {}
    oid = resp["result"]["orderId"]
    log.info(f"أمر {side} @ {price:.4f}  qty={qty:.2f}  id={oid}")
    return resp["result"]


def cancel_order(order_id: str):
    resp = post("/v5/order/cancel", {"category": "spot", "symbol": C.SYMBOL, "orderId": order_id})
    if resp["retCode"] == 0:
        log.info(f"إلغاء الأمر {order_id}")
    else:
        log.warning(f"فشل الإلغاء: {resp['retMsg']}")


def open_orders() -> list:
    data = get_auth("/v5/order/realtime", {"category": "spot", "symbol": C.SYMBOL})
    return data["result"]["list"]


# ── Grid ──────────────────────────────────────────────────────────────────────

def build_grid() -> list[float]:
    step = (C.GRID_UPPER_PRICE - C.GRID_LOWER_PRICE) / (C.GRID_LEVELS - 1)
    return [round(C.GRID_LOWER_PRICE + i * step, 4) for i in range(C.GRID_LEVELS)]


def nearest_grid(price: float, grid: list[float]) -> float:
    return min(grid, key=lambda g: abs(g - price))


# ── Trade Log ─────────────────────────────────────────────────────────────────

def log_trade(side: str, price: float, qty: float, reason: str):
    row = {
        "time": datetime.now().isoformat(),
        "side": side,
        "price": price,
        "qty": qty,
        "usdt": price * qty,
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
    url = f"https://api.telegram.org/bot{C.TELEGRAM_TOKEN}/sendMessage"
    body = json.dumps({"chat_id": C.TELEGRAM_CHAT_ID, "text": msg}).encode()
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}),
            timeout=5,
        )
    except Exception as e:
        log.warning(f"Telegram error: {e}")


# ── Main Loop ─────────────────────────────────────────────────────────────────

class Bot:
    def __init__(self):
        self.grid = build_grid()
        self.open_positions: dict[str, dict] = {}  # order_id → {side, price, qty, ts}
        self.daily_trades = 0
        self.day = datetime.now().date()

    def reset_daily(self):
        today = datetime.now().date()
        if today != self.day:
            self.daily_trades = 0
            self.day = today

    def signal(self, closes, volumes) -> str:
        """Returns 'BUY', 'SELL', or 'HOLD'"""
        r = rsi(closes, C.RSI_PERIOD)
        fast = ema(closes, C.EMA_FAST)
        slow = ema(closes, C.EMA_SLOW)

        if C.VOLUME_FILTER:
            avg_vol = avg_volume(volumes)
            if volumes[-1] < avg_vol * C.VOLUME_MULTIPLIER:
                return "HOLD"

        if r < C.RSI_OVERSOLD and fast > slow:
            return "BUY"
        if r > C.RSI_OVERBOUGHT and fast < slow:
            return "SELL"
        return "HOLD"

    def check_exits(self, price: float):
        for oid, pos in list(self.open_positions.items()):
            entry = pos["price"]
            side  = pos["side"]
            qty   = pos["qty"]
            age   = (time.time() - pos["ts"]) / 60

            if side == "Buy":
                tp = entry * (1 + C.TAKE_PROFIT_PCT)
                sl = entry * (1 - C.STOP_LOSS_PCT)
                trail = entry * (1 - C.TRAILING_STOP_PCT)
                if price >= tp:
                    place_order("Sell", qty, round(price, 4))
                    log_trade("Sell", price, qty, "take_profit")
                    tg(f"✅ TP WLD Sell @ {price:.4f}  +{C.TAKE_PROFIT_PCT*100:.1f}%")
                    del self.open_positions[oid]
                    self.daily_trades += 1
                elif price <= sl:
                    place_order("Sell", qty, round(price, 4))
                    log_trade("Sell", price, qty, "stop_loss")
                    tg(f"🛑 SL WLD Sell @ {price:.4f}  -{C.STOP_LOSS_PCT*100:.1f}%")
                    del self.open_positions[oid]
                    self.daily_trades += 1
                elif price <= trail:
                    place_order("Sell", qty, round(price, 4))
                    log_trade("Sell", price, qty, "trailing_stop")
                    del self.open_positions[oid]
                    self.daily_trades += 1

            # إلغاء الأوامر المعلقة التي تجاوزت المهلة
            if age > C.ORDER_TIMEOUT_MIN:
                cancel_order(oid)
                del self.open_positions[oid]
                log.info(f"تجاوز المهلة — إلغاء {oid}")

    def run(self):
        log.info(f"▶  بوت WLD يعمل | نطاق الشبكة: {C.GRID_LOWER_PRICE} – {C.GRID_UPPER_PRICE}")
        tg(f"▶ WLD Bot started | Grid: {C.GRID_LOWER_PRICE}–{C.GRID_UPPER_PRICE}")

        while True:
            try:
                self.reset_daily()

                closes, highs, lows, volumes = fetch_candles(60)
                price = closes[-1]
                sig   = self.signal(closes, volumes)

                r    = rsi(closes, C.RSI_PERIOD)
                fast = ema(closes, C.EMA_FAST)
                slow = ema(closes, C.EMA_SLOW)

                log.info(
                    f"Price={price:.4f}  RSI={r:.1f}  EMA{C.EMA_FAST}={fast:.4f}  "
                    f"EMA{C.EMA_SLOW}={slow:.4f}  Signal={sig}  "
                    f"Trades={self.daily_trades}/{C.MAX_DAILY_TRADES}"
                )

                # ── فحص الخروج ───────────────────────────────────────────
                self.check_exits(price)

                # ── شروط الدخول ──────────────────────────────────────────
                in_range = C.GRID_LOWER_PRICE <= price <= C.GRID_UPPER_PRICE
                can_trade = (
                    sig == "BUY"
                    and in_range
                    and len(self.open_positions) < C.MAX_OPEN_ORDERS
                    and self.daily_trades < C.MAX_DAILY_TRADES
                )

                if can_trade:
                    grid_price = nearest_grid(price, self.grid)
                    qty = round(C.PER_GRID_USDT / grid_price, 2)
                    result = place_order("Buy", qty, grid_price)
                    if result:
                        self.open_positions[result["orderId"]] = {
                            "side": "Buy",
                            "price": grid_price,
                            "qty": qty,
                            "ts": time.time(),
                        }
                        log_trade("Buy", grid_price, qty, f"grid+rsi={r:.1f}")
                        tg(f"📈 WLD Buy @ {grid_price:.4f}  qty={qty}")

                # ── خارج النطاق ──────────────────────────────────────────
                if not in_range:
                    log.warning(f"السعر {price:.4f} خارج نطاق الشبكة!")

            except KeyboardInterrupt:
                log.info("إيقاف البوت.")
                tg("⏹ WLD Bot stopped.")
                break
            except Exception as e:
                log.error(f"خطأ: {e}", exc_info=True)

            time.sleep(C.LOOP_SLEEP_SEC)


if __name__ == "__main__":
    Bot().run()
