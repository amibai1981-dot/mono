"""
Webhook server — receives TradingView alerts and executes orders on Binance.

Run:
    pip install flask python-dotenv
    python server.py

TradingView webhook URL:
    http://<your-server-ip>:8080/webhook

TradingView alert message (JSON):
    {
      "secret": "YOUR_WEBHOOK_SECRET",
      "action": "buy",
      "symbol": "BTCUSDT",
      "type": "market",
      "quantity": "0.001",
      "price": "{{close}}",
      "market": "spot"
    }
"""
import hashlib
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------
log_dir = os.getenv("LOG_DIR", "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "server.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

if not WEBHOOK_SECRET:
    logger.warning("⚠️  WEBHOOK_SECRET غير مضبوط — أي طلب سيُنفَّذ!")

# ------------------------------------------------------------------
# Trader (lazy-init so startup fails fast on missing env vars)
# ------------------------------------------------------------------
_trader = None


def get_trader():
    global _trader
    if _trader is None:
        from trader import BinanceTrader
        _trader = BinanceTrader()
    return _trader


# ------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------
app = Flask(__name__)


def _verify_secret(payload: dict) -> bool:
    if not WEBHOOK_SECRET:
        return True
    incoming = payload.get("secret", "")
    # constant-time comparison
    expected = WEBHOOK_SECRET.encode()
    actual = incoming.encode() if isinstance(incoming, str) else incoming
    return len(expected) == len(actual) and hashlib.compare_digest(expected, actual)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@app.route("/webhook", methods=["POST"])
def webhook():
    raw = request.get_data(as_text=True)
    logger.info("Webhook received: %s", raw[:500])

    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        return jsonify({"error": "JSON غير صالح"}), 400

    # --- Auth ---
    if not _verify_secret(payload):
        logger.warning("Webhook rejected: secret خاطئ")
        return jsonify({"error": "Unauthorized"}), 401

    # --- Parse ---
    action = str(payload.get("action", "")).lower()       # buy | sell | close
    symbol = str(payload.get("symbol", "")).upper()
    order_type = str(payload.get("type", "market")).upper()  # MARKET | LIMIT
    market = str(payload.get("market", "")).lower() or None  # spot | futures
    close_action = str(payload.get("close_action", "sell")).upper()  # عند close

    try:
        quantity = float(payload.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "quantity غير صالح"}), 400

    try:
        price = float(payload["price"]) if "price" in payload and order_type == "LIMIT" else None
    except (TypeError, ValueError):
        return jsonify({"error": "price غير صالح"}), 400

    if not symbol:
        return jsonify({"error": "symbol مطلوب"}), 400
    if quantity <= 0:
        return jsonify({"error": "quantity يجب أن يكون أكبر من صفر"}), 400
    if action not in ("buy", "sell", "close"):
        return jsonify({"error": f"action غير معروف: {action}"}), 400

    # --- Execute ---
    trader = get_trader()
    try:
        if action == "buy":
            if order_type == "LIMIT":
                result = trader.buy_limit(symbol, quantity, price, market=market)
            else:
                result = trader.buy_market(symbol, quantity, market=market)

        elif action in ("sell", "close"):
            side = close_action if action == "close" else "SELL"
            if order_type == "LIMIT":
                result = trader.sell_limit(symbol, quantity, price, market=market)
            else:
                result = trader.sell_market(symbol, quantity, market=market)

    except Exception as exc:
        logger.exception("خطأ أثناء التنفيذ")
        return jsonify({"error": str(exc)}), 500

    if "error" in result:
        logger.error("Binance رفض الأمر: %s", result)
        return jsonify({"status": "error", "detail": result}), 502

    logger.info("✅ أمر مُنفَّذ: %s", result)
    return jsonify({"status": "ok", "order": result})


@app.route("/balance", methods=["GET"])
def balance():
    """عرض الرصيد — للاختبار المحلي فقط، لا تكشفه للعموم."""
    asset = request.args.get("asset", "USDT")
    mkt = request.args.get("market", "spot")
    trader = get_trader()
    bal = trader.get_balance(asset, mkt)
    return jsonify({"asset": asset, "market": mkt, "free": bal})


if __name__ == "__main__":
    env_label = "TESTNET" if os.getenv("BINANCE_TESTNET", "").lower() == "true" else "MAINNET"
    logger.info("🚀 Binance-TradingView Bot يعمل على %s:%s [%s]", HOST, PORT, env_label)
    app.run(host=HOST, port=PORT, debug=False)
