"""
تغليف Bitget REST API v2
HMAC-SHA256 للمصادقة
"""

import hmac, hashlib, base64, json, time, urllib.request, urllib.parse, urllib.error
from config import API_KEY, API_SECRET, API_PASSPHRASE, BASE_URL


def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    msg = timestamp + method.upper() + path + body
    return base64.b64encode(
        hmac.new(API_SECRET.encode(), msg.encode(), hashlib.sha256).digest()
    ).decode()


def _request(method: str, path: str, params: dict = None, body: dict = None) -> dict:
    timestamp = str(int(time.time() * 1000))
    query = ""
    if params:
        query = "?" + urllib.parse.urlencode(params)
    body_str = json.dumps(body) if body else ""
    sig = _sign(timestamp, method, path + query, body_str)

    url = BASE_URL + path + query
    req = urllib.request.Request(url, method=method.upper())
    req.add_header("ACCESS-KEY",        API_KEY)
    req.add_header("ACCESS-SIGN",       sig)
    req.add_header("ACCESS-TIMESTAMP",  timestamp)
    req.add_header("ACCESS-PASSPHRASE", API_PASSPHRASE)
    req.add_header("Content-Type",      "application/json")
    req.add_header("locale",            "en-US")

    if body_str:
        req.data = body_str.encode()

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"code": str(e.code), "msg": e.read().decode()}


# ── بيانات السوق ─────────────────────────────────────────────

def get_tickers(symbols: list = None) -> list:
    """جلب أسعار جميع الأزواج أو أزواج محددة"""
    data = _request("GET", "/api/v2/spot/market/tickers")
    tickers = data.get("data", [])
    if symbols:
        tickers = [t for t in tickers if t["symbol"] in symbols]
    return tickers


def get_ticker(symbol: str) -> dict:
    data = _request("GET", "/api/v2/spot/market/tickers", {"symbol": symbol})
    items = data.get("data", [])
    return items[0] if items else {}


def get_candles(symbol: str, granularity: str = "15min", limit: int = 150) -> list:
    """
    granularity: 1min 5min 15min 30min 1h 4h 12h 1day 1week
    """
    data = _request("GET", "/api/v2/spot/market/candles", {
        "symbol":      symbol,
        "granularity": granularity,
        "limit":       limit,
    })
    return data.get("data", [])


def get_orderbook(symbol: str, limit: int = 20) -> dict:
    return _request("GET", "/api/v2/spot/market/orderbook", {
        "symbol": symbol,
        "limit":  limit,
    })


# ── بيانات الحساب ─────────────────────────────────────────────

def get_spot_assets() -> list:
    """عرض رصيد المحفظة الفورية"""
    data = _request("GET", "/api/v2/spot/account/assets")
    assets = data.get("data", [])
    return [a for a in assets if float(a.get("available", 0)) > 0]


def get_usdt_balance() -> float:
    for a in get_spot_assets():
        if a["coin"] == "USDT":
            return float(a["available"])
    return 0.0


# ── إدارة الأوامر ─────────────────────────────────────────────

def place_order(symbol: str, side: str, size: str,
                price: str = None, order_type: str = "limit") -> dict:
    """
    side: buy | sell
    order_type: limit | market
    """
    body = {
        "symbol":    symbol,
        "side":      side,
        "orderType": order_type,
        "size":      size,
        "force":     "GTC",
    }
    if order_type == "limit" and price:
        body["price"] = price
    return _request("POST", "/api/v2/spot/trade/place-order", body=body)


def cancel_order(symbol: str, order_id: str) -> dict:
    return _request("POST", "/api/v2/spot/trade/cancel-order", body={
        "symbol":  symbol,
        "orderId": order_id,
    })


def get_open_orders(symbol: str = None) -> list:
    params = {}
    if symbol:
        params["symbol"] = symbol
    data = _request("GET", "/api/v2/spot/trade/unfilled-orders", params)
    return data.get("data", [])


def get_order_history(symbol: str, limit: int = 50) -> list:
    data = _request("GET", "/api/v2/spot/trade/history-orders", {
        "symbol": symbol,
        "limit":  limit,
    })
    return data.get("data", [])
