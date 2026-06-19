"""
TradingView Webhook → Bybit Order Executor

TradingView alert message format (JSON):
{
  "secret": "YOUR_WEBHOOK_SECRET",
  "symbol": "BTCUSDT",
  "side": "Buy" | "Sell",
  "qty": "0.01",
  "order_type": "Market" | "Limit",
  "price": "50000"       // only for Limit orders
}
"""

import time, base64, json, urllib.request, urllib.parse, subprocess, os, sys, hmac, hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler

API_KEY = os.getenv("BYBIT_API_KEY", "")
PRIVATE_KEY_PATH = os.getenv("BYBIT_API_PRIVATE_KEY_PATH", "./private.pem")
ENV = os.getenv("BYBIT_ENV", "mainnet")
BASE_URL = "https://api-testnet.bybit.com" if ENV == "testnet" else "https://api.bybit.com"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_me_in_env")
PORT = int(os.getenv("WEBHOOK_PORT", "8080"))


def sign_request(payload: str) -> str:
    result = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", PRIVATE_KEY_PATH],
        input=payload.encode(), capture_output=True
    )
    return base64.b64encode(result.stdout).decode()


def post(path: str, body: dict) -> dict:
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    body_str = json.dumps(body)
    signature = sign_request(timestamp + API_KEY + recv_window + body_str)

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body_str.encode(),
        method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "bybit-agent/1.0")
    req.add_header("X-BAPI-API-KEY", API_KEY)
    req.add_header("X-BAPI-TIMESTAMP", timestamp)
    req.add_header("X-BAPI-RECV-WINDOW", recv_window)
    req.add_header("X-BAPI-SIGN", signature)

    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def place_order(symbol: str, side: str, qty: str, order_type: str = "Market", price: str = None) -> dict:
    body = {
        "category": "spot",
        "symbol": symbol,
        "side": side,
        "orderType": order_type,
        "qty": qty,
    }
    if order_type == "Limit" and price:
        body["price"] = price
        body["timeInForce"] = "GTC"

    return post("/v5/order/create", body)


class WebhookHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{time.strftime('%H:%M:%S')}] {format % args}")

    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)

        try:
            alert = json.loads(raw.decode())
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid JSON"})
            return

        # التحقق من السر
        if alert.get("secret") != WEBHOOK_SECRET:
            print(f"[!] محاولة وصول بسر خاطئ")
            self._reply(403, {"error": "forbidden"})
            return

        symbol = alert.get("symbol", "")
        side = alert.get("side", "")
        qty = alert.get("qty", "")
        order_type = alert.get("order_type", "Market")
        price = alert.get("price")

        if not all([symbol, side, qty]):
            self._reply(400, {"error": "missing fields: symbol, side, qty"})
            return

        if side not in ("Buy", "Sell"):
            self._reply(400, {"error": "side must be Buy or Sell"})
            return

        print(f"[→] أمر {side} {qty} {symbol} ({order_type})")

        try:
            result = place_order(symbol, side, qty, order_type, price)
        except Exception as e:
            print(f"[✗] فشل: {e}")
            self._reply(500, {"error": str(e)})
            return

        if result.get("retCode") == 0:
            order_id = result["result"].get("orderId", "?")
            print(f"[✓] تم الأمر — orderId: {order_id}")
            self._reply(200, {"status": "ok", "orderId": order_id})
        else:
            msg = result.get("retMsg", "unknown error")
            print(f"[✗] رفض Bybit: {msg}")
            self._reply(400, {"error": msg, "retCode": result.get("retCode")})

    def _reply(self, code: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


def main():
    if not API_KEY:
        print("خطأ: BYBIT_API_KEY غير محدد في البيئة")
        sys.exit(1)
    if WEBHOOK_SECRET == "change_me_in_env":
        print("تحذير: WEBHOOK_SECRET لم يتغير — غيّره في .env قبل الاستخدام الفعلي")

    print(f"=== TradingView Webhook Server ===")
    print(f"البيئة  : {ENV}")
    print(f"المنفذ  : {PORT}")
    print(f"المسار  : POST /webhook")
    print(f"الخادم  : {BASE_URL}")
    print()

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"يستمع على المنفذ {PORT} — اضغط Ctrl+C للإيقاف\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nتم الإيقاف.")


if __name__ == "__main__":
    main()
