"""
Binance trading client — executes orders via REST API with HMAC-SHA256 signing.
Supports spot and USD-M futures, market and limit orders.
"""
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

logger = logging.getLogger(__name__)

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"
TESTNET_SPOT = "https://testnet.binance.vision"
TESTNET_FUTURES = "https://testnet.binancefuture.com"


class BinanceTrader:
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        self.testnet = os.getenv("BINANCE_TESTNET", "false").lower() == "true"
        self.default_market = os.getenv("BINANCE_MARKET", "spot")  # spot | futures

        if not self.api_key or not self.api_secret:
            raise ValueError("BINANCE_API_KEY و BINANCE_API_SECRET مطلوبان في .env")

    def _base_url(self, market: str) -> str:
        if market == "futures":
            return TESTNET_FUTURES if self.testnet else FUTURES_BASE
        return TESTNET_SPOT if self.testnet else SPOT_BASE

    def _sign(self, query: str) -> str:
        return hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()

    def _request(self, method: str, path: str, params: dict, market: str) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query = urllib.parse.urlencode(params)
        query += f"&signature={self._sign(query)}"

        base = self._base_url(market)
        url = f"{base}{path}"

        data = query.encode() if method == "POST" else None
        if method == "GET":
            url += f"?{query}"

        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("X-MBX-APIKEY", self.api_key)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            logger.error("Binance API error %s: %s", e.code, body)
            return {"error": body, "code": e.code}

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_balance(self, asset: str, market: str = "spot") -> float:
        """Return free balance for the given asset."""
        if market == "futures":
            data = self._request("GET", "/fapi/v2/account", {}, "futures")
            if "error" in data:
                return 0.0
            for item in data.get("assets", []):
                if item["asset"] == asset:
                    return float(item["availableBalance"])
        else:
            data = self._request("GET", "/api/v3/account", {}, "spot")
            if "error" in data:
                return 0.0
            for b in data.get("balances", []):
                if b["asset"] == asset:
                    return float(b["free"])
        return 0.0

    def place_order(
        self,
        symbol: str,
        side: str,          # BUY | SELL
        order_type: str,    # MARKET | LIMIT
        quantity: float,
        price: float | None = None,
        market: str | None = None,
    ) -> dict:
        market = market or self.default_market
        side = side.upper()
        order_type = order_type.upper()

        params: dict = {
            "symbol": symbol.upper(),
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type == "LIMIT":
            if price is None:
                raise ValueError("سعر LIMIT مطلوب")
            params["price"] = price
            params["timeInForce"] = "GTC"

        if market == "futures":
            path = "/fapi/v1/order"
        else:
            path = "/api/v3/order"

        env_label = "TESTNET" if self.testnet else "MAINNET"
        logger.info(
            "[%s/%s] %s %s %s qty=%s price=%s",
            env_label, market.upper(), order_type, side, symbol, quantity, price or "MARKET",
        )

        result = self._request("POST", path, params, market)
        self._log_trade(symbol, side, order_type, quantity, price, result)
        return result

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def buy_market(self, symbol: str, quantity: float, market: str | None = None) -> dict:
        return self.place_order(symbol, "BUY", "MARKET", quantity, market=market)

    def sell_market(self, symbol: str, quantity: float, market: str | None = None) -> dict:
        return self.place_order(symbol, "SELL", "MARKET", quantity, market=market)

    def buy_limit(self, symbol: str, quantity: float, price: float, market: str | None = None) -> dict:
        return self.place_order(symbol, "BUY", "LIMIT", quantity, price=price, market=market)

    def sell_limit(self, symbol: str, quantity: float, price: float, market: str | None = None) -> dict:
        return self.place_order(symbol, "SELL", "LIMIT", quantity, price=price, market=market)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _log_trade(self, symbol, side, order_type, qty, price, result):
        log_dir = os.getenv("LOG_DIR", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "trades.log")
        entry = {
            "time": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": qty,
            "price": price,
            "result": result,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
