"""
Binance exchange wrapper with paper trading support.
"""
import logging
import pandas as pd
from typing import Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import config

logger = logging.getLogger(__name__)


class PaperTrader:
    """Simulates order execution without real money."""
    def __init__(self):
        self.balance = {"USDT": config.MAX_POSITION_SIZE_USDT * config.MAX_OPEN_POSITIONS}
        self._order_id = 1000

    def get_balance(self, asset: str = "USDT") -> float:
        return self.balance.get(asset, 0.0)

    def place_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        base = symbol.replace("USDT", "")
        cost = quantity * price
        if side == "BUY":
            if self.balance.get("USDT", 0) < cost:
                raise Exception(f"Insufficient USDT balance: need {cost:.2f}, have {self.balance.get('USDT', 0):.2f}")
            self.balance["USDT"] = self.balance.get("USDT", 0) - cost
            self.balance[base] = self.balance.get(base, 0) + quantity
        else:
            if self.balance.get(base, 0) < quantity:
                raise Exception(f"Insufficient {base} balance")
            self.balance[base] = self.balance.get(base, 0) - quantity
            self.balance["USDT"] = self.balance.get("USDT", 0) + cost

        self._order_id += 1
        logger.info(f"[PAPER] {side} {quantity:.6f} {symbol} @ {price:.4f} | USDT balance: {self.balance.get('USDT', 0):.2f}")
        return {"orderId": str(self._order_id), "status": "FILLED", "price": price, "executedQty": quantity}


class BinanceExchange:
    def __init__(self):
        self.paper = PaperTrader()
        self.client: Optional[Client] = None
        if config.IS_LIVE and config.API_KEY and config.API_SECRET:
            try:
                self.client = Client(config.API_KEY, config.API_SECRET)
                self.client.ping()
                logger.info("Connected to Binance LIVE trading")
            except Exception as e:
                logger.error(f"Failed to connect to Binance: {e}")
                self.client = None
        else:
            logger.info("Running in PAPER trading mode")

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        interval_map = {
            "1m": Client.KLINE_INTERVAL_1MINUTE,
            "5m": Client.KLINE_INTERVAL_5MINUTE,
            "15m": Client.KLINE_INTERVAL_15MINUTE,
            "1h": Client.KLINE_INTERVAL_1HOUR,
            "4h": Client.KLINE_INTERVAL_4HOUR,
            "1d": Client.KLINE_INTERVAL_1DAY,
        }
        kline_interval = interval_map.get(interval, Client.KLINE_INTERVAL_15MINUTE)

        if self.client:
            klines = self.client.get_klines(symbol=symbol, interval=kline_interval, limit=limit)
        else:
            # Fallback: public API without auth
            import requests
            url = f"https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            klines = resp.json()

        df = pd.DataFrame(klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_vol", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        return df

    def get_price(self, symbol: str) -> float:
        if self.client:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        else:
            import requests
            url = f"https://api.binance.com/api/v3/ticker/price"
            resp = requests.get(url, params={"symbol": symbol}, timeout=5)
            resp.raise_for_status()
            return float(resp.json()["price"])

    def get_balance_usdt(self) -> float:
        if self.client and config.IS_LIVE:
            account = self.client.get_account()
            for asset in account["balances"]:
                if asset["asset"] == "USDT":
                    return float(asset["free"])
            return 0.0
        return self.paper.get_balance("USDT")

    def place_market_order(self, symbol: str, side: str, quantity: float, price: float) -> dict:
        if self.client and config.IS_LIVE:
            try:
                order = self.client.order_market(
                    symbol=symbol,
                    side=side,
                    quantity=round(quantity, 5),
                )
                return order
            except BinanceAPIException as e:
                logger.error(f"Binance order error: {e}")
                raise
        else:
            return self.paper.place_order(symbol, side, quantity, price)

    def get_symbol_info(self, symbol: str) -> dict:
        if self.client:
            return self.client.get_symbol_info(symbol)
        return {}
