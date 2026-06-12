"""Bybit trading client with RSA key signing."""
import asyncio
import base64
import hashlib
import hmac
import json
import logging
import subprocess
import time
from typing import Any

import httpx

import config

logger = logging.getLogger(__name__)


def _sign_rsa(payload: str) -> str:
    """Sign payload with RSA private key using openssl subprocess (same pattern as monitor.py)."""
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", config.BYBIT_PRIVATE_KEY_PATH],
        input=payload.encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"RSA signing failed: {result.stderr.decode()}")
    return base64.b64encode(result.stdout).decode()


def _build_auth_headers(params_str: str = "") -> dict[str, str]:
    """Build Bybit authentication headers."""
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    sign_payload = timestamp + config.BYBIT_API_KEY + recv_window + params_str
    signature = _sign_rsa(sign_payload)
    return {
        "X-BAPI-API-KEY": config.BYBIT_API_KEY,
        "X-BAPI-TIMESTAMP": timestamp,
        "X-BAPI-RECV-WINDOW": recv_window,
        "X-BAPI-SIGN": signature,
        "Content-Type": "application/json",
    }


class BybitClient:
    """Async Bybit V5 API client."""

    def __init__(self) -> None:
        self.base_url = config.BYBIT_BASE_URL
        self._http: httpx.AsyncClient | None = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"User-Agent": "tradingview-bot/1.0"},
                timeout=10.0,
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None, auth: bool = False) -> dict:
        client = await self._client()
        params = params or {}
        params_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        headers = _build_auth_headers(params_str) if auth else {}
        url = f"{path}?{params_str}" if params_str else path
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode", 0) != 0:
            raise RuntimeError(f"Bybit GET error {data['retCode']}: {data.get('retMsg')}")
        return data

    async def _post(self, path: str, body: dict[str, Any]) -> dict:
        client = await self._client()
        body_str = json.dumps(body)
        headers = _build_auth_headers(body_str)
        resp = await client.post(path, content=body_str, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get("retCode", 0) != 0:
            raise RuntimeError(f"Bybit POST error {data['retCode']}: {data.get('retMsg')}")
        return data

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_balance(self, coin: str = "USDT") -> float:
        """Return available wallet balance for the given coin."""
        data = await self._get(
            "/v5/account/wallet-balance",
            params={"accountType": "UNIFIED"},
            auth=True,
        )
        coins = data["result"]["list"][0]["coin"]
        for c in coins:
            if c["coin"] == coin:
                return float(c.get("availableToWithdraw") or c.get("walletBalance") or 0)
        return 0.0

    async def get_position(self, symbol: str, category: str = "linear") -> dict | None:
        """Return the open position for symbol, or None."""
        data = await self._get(
            "/v5/position/list",
            params={"category": category, "symbol": symbol},
            auth=True,
        )
        positions = data["result"]["list"]
        for p in positions:
            if float(p.get("size", 0)) != 0:
                return p
        return None

    async def get_ticker(self, symbol: str, category: str = "spot") -> dict:
        """Return ticker data for symbol."""
        data = await self._get(
            "/v5/market/tickers",
            params={"category": category, "symbol": symbol},
        )
        tickers = data["result"]["list"]
        if not tickers:
            raise ValueError(f"No ticker found for {symbol}")
        return tickers[0]

    async def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: str,
        category: str = "spot",
    ) -> dict:
        """Place a market order. side: 'Buy' or 'Sell'."""
        body = {
            "category": category,
            "symbol": symbol,
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": qty,
            "timeInForce": "IOC",
        }
        logger.info("Placing %s market order: %s %s @ market", side, qty, symbol)
        data = await self._post("/v5/order/create", body)
        logger.info("Order placed: %s", data["result"])
        return data["result"]

    async def cancel_all_orders(self, symbol: str, category: str = "spot") -> dict:
        """Cancel all open orders for symbol."""
        body = {"category": category, "symbol": symbol}
        data = await self._post("/v5/order/cancel-all", body)
        logger.info("Cancelled all orders for %s: %s", symbol, data["result"])
        return data["result"]

    async def cancel_order(self, symbol: str, order_id: str, category: str = "spot") -> dict:
        """Cancel a specific order by orderId."""
        body = {"category": category, "symbol": symbol, "orderId": order_id}
        data = await self._post("/v5/order/cancel", body)
        logger.info("Cancelled order %s for %s", order_id, symbol)
        return data["result"]
