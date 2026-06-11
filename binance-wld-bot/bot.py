"""
Binance WLD/USDT Automated Trading Bot
Strategy: RSI + EMA Crossover with risk management
"""

import os
import time
import logging
import hmac
import hashlib
import requests
from decimal import Decimal
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

SYMBOL          = "WLDUSDT"
BASE_URL        = "https://api.binance.com"
API_KEY         = os.environ["BINANCE_API_KEY"]
API_SECRET      = os.environ["BINANCE_API_SECRET"]

# Risk settings
TRADE_USDT      = float(os.environ.get("TRADE_USDT", "20"))      # $ per trade
STOP_LOSS_PCT   = float(os.environ.get("STOP_LOSS_PCT", "2.0"))   # %
TAKE_PROFIT_PCT = float(os.environ.get("TAKE_PROFIT_PCT", "4.0")) # %
MAX_OPEN_TRADES = int(os.environ.get("MAX_OPEN_TRADES", "1"))

# Strategy params
RSI_PERIOD      = 14
EMA_FAST        = 9
EMA_SLOW        = 21
CANDLE_INTERVAL = "15m"
CANDLE_LIMIT    = 100

POLL_SECONDS    = 60   # check every 60 s


# ── Binance REST helpers ────────────────────────────────────────────────────────

def _sign(params: dict) -> dict:
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params


def _headers() -> dict:
    return {"X-MBX-APIKEY": API_KEY}


def get_klines(symbol: str, interval: str, limit: int) -> list:
    r = requests.get(
        f"{BASE_URL}/api/v3/klines",
        params={"symbol": symbol, "interval": interval, "limit": limit},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def get_ticker(symbol: str) -> float:
    r = requests.get(
        f"{BASE_URL}/api/v3/ticker/price",
        params={"symbol": symbol},
        timeout=10,
    )
    r.raise_for_status()
    return float(r.json()["price"])


def get_account_balance(asset: str) -> float:
    params = _sign({"timestamp": int(time.time() * 1000)})
    r = requests.get(
        f"{BASE_URL}/api/v3/account",
        params=params,
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    for b in r.json()["balances"]:
        if b["asset"] == asset:
            return float(b["free"])
    return 0.0


def get_step_size(symbol: str) -> Decimal:
    r = requests.get(f"{BASE_URL}/api/v3/exchangeInfo", params={"symbol": symbol}, timeout=10)
    r.raise_for_status()
    for f in r.json()["symbols"][0]["filters"]:
        if f["filterType"] == "LOT_SIZE":
            return Decimal(f["stepSize"])
    return Decimal("0.01")


def place_order(symbol: str, side: str, quantity: float) -> dict:
    step = get_step_size(symbol)
    qty = float((Decimal(str(quantity)) // step) * step)
    params = _sign({
        "symbol":    symbol,
        "side":      side,
        "type":      "MARKET",
        "quantity":  qty,
        "timestamp": int(time.time() * 1000),
    })
    r = requests.post(
        f"{BASE_URL}/api/v3/order",
        params=params,
        headers=_headers(),
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


# ── Indicators ─────────────────────────────────────────────────────────────────

def closes(klines: list) -> list[float]:
    return [float(k[4]) for k in klines]


def ema(data: list[float], period: int) -> list[float]:
    k = 2 / (period + 1)
    result = [data[0]]
    for price in data[1:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def rsi(data: list[float], period: int = 14) -> float:
    deltas = [data[i] - data[i - 1] for i in range(1, len(data))]
    gains  = [max(d, 0) for d in deltas]
    losses = [abs(min(d, 0)) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# ── State ──────────────────────────────────────────────────────────────────────

class Position:
    def __init__(self, entry_price: float, quantity: float):
        self.entry_price   = entry_price
        self.quantity      = quantity
        self.stop_loss     = entry_price * (1 - STOP_LOSS_PCT / 100)
        self.take_profit   = entry_price * (1 + TAKE_PROFIT_PCT / 100)
        self.opened_at     = datetime.utcnow()

    def should_close(self, price: float) -> str | None:
        if price <= self.stop_loss:
            return "STOP_LOSS"
        if price >= self.take_profit:
            return "TAKE_PROFIT"
        return None

    def __str__(self):
        return (
            f"qty={self.quantity:.4f} entry={self.entry_price:.4f} "
            f"SL={self.stop_loss:.4f} TP={self.take_profit:.4f}"
        )


open_position: Position | None = None


# ── Signal logic ───────────────────────────────────────────────────────────────

def should_buy(prices: list[float]) -> bool:
    """BUY when fast EMA crosses above slow EMA AND RSI < 65."""
    fast = ema(prices, EMA_FAST)
    slow = ema(prices, EMA_SLOW)
    rsi_val = rsi(prices, RSI_PERIOD)

    cross_now  = fast[-1] > slow[-1]
    cross_prev = fast[-2] <= slow[-2]
    log.info("RSI=%.2f  EMA_fast=%.4f  EMA_slow=%.4f  cross=%s", rsi_val, fast[-1], slow[-1], cross_now and not cross_prev)
    return cross_now and not cross_prev and rsi_val < 65


def should_sell(prices: list[float]) -> bool:
    """SELL when fast EMA crosses below slow EMA OR RSI > 70."""
    fast = ema(prices, EMA_FAST)
    slow = ema(prices, EMA_SLOW)
    rsi_val = rsi(prices, RSI_PERIOD)

    cross_down = fast[-1] < slow[-1] and fast[-2] >= slow[-2]
    return cross_down or rsi_val > 70


# ── Main loop ──────────────────────────────────────────────────────────────────

def run():
    global open_position

    log.info("=== Binance WLD/USDT Bot started ===")
    log.info("Trade size: $%.2f | SL: %.1f%% | TP: %.1f%%", TRADE_USDT, STOP_LOSS_PCT, TAKE_PROFIT_PCT)

    while True:
        try:
            klines = get_klines(SYMBOL, CANDLE_INTERVAL, CANDLE_LIMIT)
            prices = closes(klines)
            price  = get_ticker(SYMBOL)
            log.info("Price: %.4f USDT", price)

            # ── Manage open position ─────────────────────────────────────
            if open_position:
                reason = open_position.should_close(price)

                if reason is None and should_sell(prices):
                    reason = "EMA_SIGNAL"

                if reason:
                    log.info("Closing position: %s  reason=%s", open_position, reason)
                    order = place_order(SYMBOL, "SELL", open_position.quantity)
                    pnl = (price - open_position.entry_price) * open_position.quantity
                    log.info("SELL executed | orderId=%s | PnL≈$%.4f", order.get("orderId"), pnl)
                    open_position = None

            # ── Look for new entry ───────────────────────────────────────
            if not open_position and should_buy(prices):
                usdt_balance = get_account_balance("USDT")
                trade_size   = min(TRADE_USDT, usdt_balance * 0.95)

                if trade_size < 1:
                    log.warning("Insufficient USDT balance (%.4f)", usdt_balance)
                else:
                    quantity = trade_size / price
                    log.info("Opening BUY | qty=%.4f @ %.4f", quantity, price)
                    order = place_order(SYMBOL, "BUY", quantity)
                    filled_price = float(order.get("fills", [{}])[0].get("price", price))
                    open_position = Position(filled_price or price, quantity)
                    log.info("BUY executed | orderId=%s | %s", order.get("orderId"), open_position)

        except requests.HTTPError as e:
            log.error("HTTP error: %s – %s", e.response.status_code, e.response.text)
        except Exception as e:
            log.exception("Unexpected error: %s", e)

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run()
