"""
Binance Exchange Wrapper
Handles REST calls with retry logic, rate limiting, and testnet support.
"""
import logging
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceOrderException

logger = logging.getLogger("exchange")

MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _retry(fn, *args, **kwargs):
    for attempt in range(MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except BinanceAPIException as e:
            if e.code in (-1003, -1015):       # rate limit
                wait = RETRY_DELAY * (2 ** attempt)
                logger.warning("Rate limit hit, retrying in %.1fs", wait)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {MAX_RETRIES} retries")


class BinanceClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.client = Client(api_key, api_secret, testnet=testnet)
        if testnet:
            self.client.API_URL = "https://testnet.binance.vision/api"
        logger.info("Binance client initialized (testnet=%s)", testnet)

    # ─── Market Data ─────────────────────────────────────────────────────────

    def get_price(self, symbol: str) -> float:
        t = _retry(self.client.get_symbol_ticker, symbol=symbol)
        return float(t["price"])

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[dict]:
        raw = _retry(self.client.get_klines, symbol=symbol, interval=interval, limit=limit)
        return [{
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        } for k in raw]

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        return _retry(self.client.get_order_book, symbol=symbol, limit=limit)

    # ─── Account ─────────────────────────────────────────────────────────────

    def get_balance(self, asset: str) -> float:
        info = _retry(self.client.get_asset_balance, asset=asset)
        return float(info["free"]) if info else 0.0

    def get_open_orders(self, symbol: str) -> list:
        return _retry(self.client.get_open_orders, symbol=symbol)

    # ─── Orders ──────────────────────────────────────────────────────────────

    def place_limit_buy(self, symbol: str, qty: float, price: float) -> dict:
        try:
            order = _retry(self.client.order_limit_buy,
                           symbol=symbol,
                           quantity=f"{qty:.4f}",
                           price=f"{price:.4f}")
            logger.info("LIMIT BUY placed: id=%s price=%.4f qty=%.4f",
                        order["orderId"], price, qty)
            return order
        except BinanceOrderException as e:
            logger.error("BUY order failed: %s", e)
            raise

    def place_limit_sell(self, symbol: str, qty: float, price: float) -> dict:
        try:
            order = _retry(self.client.order_limit_sell,
                           symbol=symbol,
                           quantity=f"{qty:.4f}",
                           price=f"{price:.4f}")
            logger.info("LIMIT SELL placed: id=%s price=%.4f qty=%.4f",
                        order["orderId"], price, qty)
            return order
        except BinanceOrderException as e:
            logger.error("SELL order failed: %s", e)
            raise

    def place_market_sell(self, symbol: str, qty: float) -> dict:
        order = _retry(self.client.order_market_sell,
                       symbol=symbol,
                       quantity=f"{qty:.4f}")
        logger.warning("MARKET SELL executed: qty=%.4f", qty)
        return order

    def cancel_order(self, symbol: str, order_id: int) -> bool:
        try:
            _retry(self.client.cancel_order, symbol=symbol, orderId=order_id)
            logger.info("Order %d cancelled", order_id)
            return True
        except BinanceAPIException as e:
            logger.warning("Cancel failed (may already be filled): %s", e)
            return False

    def get_order_status(self, symbol: str, order_id: int) -> dict:
        return _retry(self.client.get_order, symbol=symbol, orderId=order_id)
